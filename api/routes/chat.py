"""
Chat API routes for handling conversations.
"""

import os
from fastapi import APIRouter, Request, HTTPException
from slowapi import Limiter
from slowapi.util import get_remote_address
from typing import Dict, Any, Optional, List
from google.genai import types
from core.rag.retriever import format_context
from core.session import get_session, save_session, get_or_create_chat_session, save_chat_history_to_session, analytics
from core.guards import check_hard_guards
from core.cta import get_entry_point_ctas, should_attach_ctas, detect_intent_from_message
from core.prompts import build_system_instruction
from core.config.business_config import config_manager
from core.rag import get_retriever_for_business
from core.features import sentiment_analyzer
from core.integrations.crm import crm_manager

router = APIRouter()

# Limiter - will use app.state.limiter from main.py via request object
# The @limiter.limit decorator accesses app.state.limiter automatically
limiter = Limiter(key_func=get_remote_address)


# Base guardrails that apply to every business
BASE_SYSTEM_INSTRUCTION = """
You are an AI concierge for this specific business. You act as an always-on front desk to capture leads and share information from the business's own Knowledge Base or provided context.
Tone: warm, upbeat, human, joyful; use contractions and light positivity. Ask one question per turn and end with a friendly CTA.
Do not use bullets in replies.

Allowed HTML: <b> <i> <u> <br> <code> <a> only. Knowledge first—never guess.
Collect/share minimum PII; verify and E.164-format phone before creating a deal or booking any appointment.
Never reveal tool/API/action names or internal strings. Do not offer services that don't exist in tools or provided business context.
Use memory; NEVER repeat a question the user already answered.

RAG CONTEXT RULES (STRICT):
- If a 'Context:' block is provided, answer ONLY with that information. Do not cite sources or URLs.
- If the context does not contain the answer, say you don't have that info. Do not guess.
- Keep answers concise and stay within the paragraph + CTA format.

PARAGRAPH + CTA FORMAT (STRICT):
For every normal reply: write one paragraph (less than 35 words), then insert exactly <br><br> and ask one CTA question (less than 12 words).
Do not put <br> at the start/end or inside <a>/<b>.

INLINE BOLD ECHO:
When repeating user values, embed them inline with <b>...</b>; never start a message with bold.

FIELD LOCK (MEMORY RULE - CRITICAL):
- Once a required field (first name, email, phone) is captured and validated in this conversation, NEVER ask for it again unless the user explicitly corrects it.
- Before asking ANY field, ALWAYS check the conversation history first. If the user has already provided that information, acknowledge it and move forward.
- Examples:
  * If user said "My name is John" → NEVER ask "What's your first name?" again
  * If user provided email "john@example.com" → NEVER ask "What's your email?" again
  * If user gave phone "123-456-7890" → NEVER ask "What's your phone number?" again
- If you see the information in conversation history, use it directly without asking.
- This is CRITICAL: Repeating questions frustrates users and breaks trust.
"""


# These will be set by main.py
_client = None
_model_name = None
_max_history_turns = None


def init_chat_router(client, model_name: str, max_history_turns: int):
    """Initialize chat router with dependencies."""
    global _client, _model_name, _max_history_turns
    _client = client
    _model_name = model_name
    _max_history_turns = max_history_turns


@router.post("/chat")
async def chat_endpoint(request: Request):
    """
    Main API endpoint to handle incoming chat messages, manages state,
    calls Gemini with tools, and handles the function response loop.
    """
    try:
        return await _handle_chat_request(request)
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_msg = str(e)
        full_traceback = traceback.format_exc()
        print(f"[CRITICAL ERROR] Unhandled exception in chat endpoint: {error_msg}")
        print(f"[CRITICAL ERROR] Full traceback:\n{full_traceback}")
        # Return error details for debugging (remove in production)
        return {
            "error": error_msg,
            "traceback": full_traceback.split('\n')[-10:] if len(full_traceback) > 500 else full_traceback.split('\n')
        }


async def _handle_chat_request(request: Request):
    """Internal handler for chat requests."""
    print(f"[DEBUG] ===== CHAT REQUEST RECEIVED =====")
    try:
        data = await request.json()
        print(f"[DEBUG] Request data received: {data}")
        user_input = data.get("message", "")
        user_id = data.get("user_id", "default_user")
        business_id = data.get("business_id")
        cta_id = data.get("cta_id")  # Optional: explicit CTA ID for API consumers
        # appointment_link removed - use CTA tree with redirect action instead

        print(f"[DEBUG] Processing: user_id={user_id}, business_id={business_id}, message='{user_input[:50]}...', cta_id={cta_id}")

    except Exception as e:
        print(f"[ERROR] Failed to parse request: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail="Invalid request format.")

    # Basic validation
    if not isinstance(user_input, str) or not user_input.strip():
        raise HTTPException(status_code=400, detail="Message is required.")

    # 1. Initialize/Retrieve Session State
    session_key = f"{business_id}:{user_id}" if business_id else user_id
    session = get_session(session_key)
    session["user_id"] = user_id
    session["session_key"] = session_key
    
    # 1.5. Session & Conversation Enhancements
    session = analytics.track_message(session, "user")
    
    # Detect intent from message
    chat_history = []
    if session.get("history"):
        chat_history = session["history"]
    
    intent_result = detect_intent_from_message(user_input, chat_history)
    session["detected_intent"] = intent_result.get("intent")
    
    # Detect sentiment
    sentiment_result = sentiment_analyzer.analyze(user_input)
    session["sentiment"] = sentiment_result.get("sentiment")
    
    # 2. Hard Guard Check (Priority 1)
    hard_guard_response = check_hard_guards(user_input, session, session_key, user_id, business_id)
    if hard_guard_response:
        # Use business greeting_message if available, otherwise let AI handle it naturally
        payload = {}
        if hard_guard_response.get("response"):
            payload["response"] = hard_guard_response["response"]
        # Use cta_tree entry points instead of legacy primary/secondary CTAs
        # CTAs are ALWAYS separate, never in response
        if business_id and hard_guard_response.get("cta_mode") == "primary":
            entry_ctas = get_entry_point_ctas(business_id, user_input)
            if entry_ctas:
                payload["cta"] = entry_ctas  # Separate CTA field
        # Only return if we have a response or CTAs to show
        if payload:
            return payload

    # 3. Build System Instruction
    business_config = config_manager.get_business(business_id) if business_id else None
    business_system_prompt = business_config.get("system_prompt") if business_config else None
    
    system_instruction = build_system_instruction(
        BASE_SYSTEM_INSTRUCTION,
        business_system_prompt
    )
    
    # Store effective system instruction in session
    session["system_instruction"] = system_instruction
    
    # 4. Get or Create Chat Session
    # Validate that client and model are initialized
    if _client is None or _model_name is None:
        error_msg = "Chat service not initialized. Please check server logs."
        print(f"[ERROR] {error_msg} - _client={_client is not None}, _model_name={_model_name}")
        raise HTTPException(status_code=500, detail=error_msg)
    
    stored_history = session.get("history", [])
    chat = get_or_create_chat_session(
        session_key,
        system_instruction,
        _client,
        _model_name,
        stored_history,
        business_id=business_id
    )
    
    # 5. RAG Context Retrieval
    context_text = None
    biz_retriever = get_retriever_for_business(business_id)
    if biz_retriever:
        try:
            hits = biz_retriever.search(user_input)
            if hits:
                context_text = format_context(hits)
                print(f"[RAG] Retrieved {len(hits)} relevant documents")
        except Exception as e:
            print(f"[WARNING] RAG retrieval failed: {e}")
    
    # 6. Main Conversation Loop using Chat API
    def run_conversation_with_chat(chat_session, message: str) -> str:
        """Uses chat API's send_message which automatically includes full history."""
        response = chat_session.send_message(message)
        
        # Check for Function Calls
        if response.function_calls:
            print(">>> Gemini requested a function call...")
            tool_responses = []

            for call in response.function_calls:
                function_name = call.name
                function_args = dict(call.args)
                
                try:
                    # Get CRM tools for this business (per-tenant)
                    crm_tools = crm_manager.get_crm_tools(business_id)
                    if crm_tools is None:
                        tool_responses.append(types.Part.from_function_response(
                            name=function_name,
                            response={"error": "CRM not available for this business", "status": "CRM not configured"}
                        ))
                        continue
                    func_to_call = getattr(crm_tools, function_name)
                    tool_output = func_to_call(**function_args)
                    
                    if 'contact_id' in tool_output:
                        session['contact_id'] = tool_output['contact_id']
                    if 'deal_id' in tool_output:
                        session['deal_id'] = tool_output['deal_id']
                    
                    tool_responses.append(types.Part.from_function_response(
                        name=function_name,
                        response=tool_output
                    ))
                    
                except Exception as e:
                    print(f"!!! Error executing tool {function_name}: {e}")
                    tool_responses.append(types.Part.from_function_response(
                        name=function_name,
                        response={"error": str(e), "status": "Error executing function."}
                    ))

            # For function responses, we need to use generate_content with chat's current history
            contents_with_tool_response = list(chat_session.get_history()) + tool_responses
            return run_conversation_with_chat_recursive(contents_with_tool_response, business_id)
        
        return response.text if response.text else ""
    
    def run_conversation_with_chat_recursive(current_contents: List[types.Content], business_id: Optional[str] = None) -> str:
        """Recursive function call handler."""
        if _client is None or _model_name is None:
            raise Exception("Chat client not initialized")
        
        # Get CRM tools for this business (per-tenant)
        crm_tools = crm_manager.get_crm_tools(business_id)
        
        # Only pass CRM tools to Gemini if this business has CRM configured
        tools_config = None
        if crm_tools is not None:
            tools_config = [crm_tools.search_contact, crm_tools.create_new_contact, crm_tools.create_deal]
        
        gemini_response = _client.models.generate_content(
            model=_model_name,
            contents=current_contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                tools=tools_config,
            )
        )
        
        if gemini_response.function_calls:
            tool_responses = []
            for call in gemini_response.function_calls:
                function_name = call.name
                function_args = dict(call.args)
                
                try:
                    func_to_call = getattr(crm_tools, function_name)
                    tool_output = func_to_call(**function_args)
                    tool_responses.append(types.Part.from_function_response(
                        name=function_name,
                        response=tool_output
                    ))
                except Exception as e:
                    tool_responses.append(types.Part.from_function_response(
                        name=function_name,
                        response={"error": str(e)}
                    ))
            
            contents_with_tool_response = current_contents + [
                types.Content(role="model", parts=gemini_response.candidates[0].content.parts),
                types.Content(role="user", parts=tool_responses)
            ]
            return run_conversation_with_chat_recursive(contents_with_tool_response, business_id)
        
        return gemini_response.text if gemini_response.text else ""
    
    # 7. Execute the conversation turn using Chat API
    try:
        user_message_with_context = user_input
        if context_text:
            user_message_with_context = f"Context:\n{context_text}\n\nUser Question: {user_input}"
        
        final_response_text = run_conversation_with_chat(chat, user_message_with_context)
        
        if not final_response_text:
            return {"response": "I apologize, but I couldn't generate a response. Please try again."}
        
    except Exception as e:
        error_text = str(e)
        print(f"!!! Error in chat endpoint: {error_text}")
        import traceback
        full_traceback = traceback.format_exc()
        print(f"!!! Full traceback:\n{full_traceback}")
        
        # Return error details for debugging
        if "quota" in error_text.lower() or "rate limit" in error_text.lower():
            user_friendly = "I'm experiencing high demand right now. Please try again in a moment."
            return {"response": user_friendly}
        
        # For debugging, return more details
        error_msg = f"Sorry, I encountered an error. Please try again. ({error_text[:100]})"
        print(f"[ERROR] Returning error message to user: {error_msg}")
        return {"response": error_msg}
    
    # 8. Track assistant message and update analytics
    session = analytics.track_message(session, "assistant")
    
    # 9. Save chat history to session
    save_chat_history_to_session(chat, session, _max_history_turns)
    
    print(f"[DEBUG] ===== SENDING RESPONSE: '{final_response_text[:100] if final_response_text else 'EMPTY'}...' =====")
    print(f"[ANALYTICS] Intent: {intent_result.get('intent', 'unknown')}, Sentiment: {sentiment_result.get('sentiment', 'unknown')}, State: {session.get('conversation_state', 'unknown')}")

    # Response payload - NEVER include CTAs in response
    response_payload = {"response": final_response_text}
    
    # Dynamic CTA approach: CTAs are ALWAYS separate, never in response
    # Get CTAs separately based on context and intent
    cta_payload = None
    if business_id:
        config = config_manager.get_business(business_id)
        if config and config.get("cta_tree"):
            cta_tree = config.get("cta_tree", {})
            from core.cta.cta_tree import get_cta_children
            
            # If explicit cta_id provided (for API-only consumers), return its children
            if cta_id:
                matched_cta = cta_tree.get(cta_id)
                if matched_cta and isinstance(matched_cta, dict) and matched_cta.get("action") == "show_children":
                    children_ctas = get_cta_children(cta_tree, cta_id)
                    if children_ctas:
                        cta_payload = {"cta": children_ctas}
            
            # If no explicit CTA or no children, return entry point CTAs only when response suggests options (not every message)
            if not cta_payload:
                entry_ctas = get_entry_point_ctas(business_id, user_input)
                if entry_ctas and should_attach_ctas(final_response_text):
                    cta_payload = {"cta": entry_ctas}
    
    # 10. Save session state (after updating CTA context)
    save_session(session_key, session)
    
    # Return response and CTA separately - CTAs are NEVER in the response object
    if cta_payload:
        return {
            "response": final_response_text,
            "cta": cta_payload["cta"]  # Separate CTA field, not in response
        }
    
    return response_payload
