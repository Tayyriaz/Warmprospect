# main.py

import os
import json
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types
from typing import Dict, Any, List, Optional
from rag.retriever import WarmProspectRetriever, format_context
from session_store import load_session, save_session

# Custom CRM Tools import
from core_tools.crm_functions import CRMTools

# Business Configuration Manager
from business_config import config_manager

# Database initialization (optional - will use file storage if database not available)
try:
    from database import init_db
    # Initialize database tables on startup
    try:
        init_db()
        print("✅ Database initialized successfully!")
    except Exception as e:
        print(f"[WARNING] Database initialization failed: {e}")
        print("[INFO] Using file-based storage as fallback.")
except ImportError:
    print("[INFO] Database module not available. Using file-based storage.")

# --- 0. SETUP AND CONFIGURATION ---

# Load environment variables (API Key)
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in .env file.")

client = genai.Client(api_key=GEMINI_API_KEY)
# Using GEMINI_MODEL from .env or defaulting to gemini-2.5-flash
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Port configuration (for deployment platforms like Readect)
PORT = int(os.getenv("PORT", "8000")) 

# Clamp how many history turns we send to Gemini to control token use
MAX_HISTORY_TURNS = int(os.getenv("MAX_HISTORY_TURNS", "20"))

# Initialize FastAPI App
app = FastAPI(title="WarmProspect Concierge Bot")

# Add CORS middleware to allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize CRM Tool Handler
crm_tools = CRMTools()

# Optional RAG retriever(s)
# NOTE: In multi-tenant mode, each business should have its own index under:
#   data/{business_id}/index.faiss and data/{business_id}/meta.jsonl
# The legacy default index (data/index.faiss) is only used when business_id is not provided.
retriever: Optional[WarmProspectRetriever] = None
_retriever_cache: Dict[str, WarmProspectRetriever] = {}

try:
    retriever = WarmProspectRetriever(
        api_key=os.getenv("GEMINI_API_KEY", ""),
        index_path="data/index.faiss",
        meta_path="data/meta.jsonl",
        model="text-embedding-004",
        top_k=5,
    )
    print("Default RAG retriever loaded (data/index.faiss).")
except Exception as e:
    print(f"Default RAG retriever not loaded: {e}")


def get_retriever_for_business(business_id: Optional[str]) -> Optional[WarmProspectRetriever]:
    """
    Returns a retriever for the given business_id if a business-specific index exists.
    - If business_id is None -> returns the default retriever (if loaded)
    - If business_id is set -> returns a cached business retriever only if its index exists
    """
    if not business_id:
        return retriever

    if business_id in _retriever_cache:
        return _retriever_cache[business_id]

    index_path = os.path.join("data", business_id, "index.faiss")
    meta_path = os.path.join("data", business_id, "meta.jsonl")
    if not (os.path.exists(index_path) and os.path.exists(meta_path)):
        # No business KB yet -> disable RAG for this business to avoid cross-tenant contamination
        return None

    try:
        biz_ret = WarmProspectRetriever(
            api_key=os.getenv("GEMINI_API_KEY", ""),
            index_path=index_path,
            meta_path=meta_path,
            model="text-embedding-004",
            top_k=5,
        )
        _retriever_cache[business_id] = biz_ret
        print(f"Business RAG retriever loaded for business_id={business_id}.")
        return biz_ret
    except Exception as e:
        print(f"[WARNING] Could not load business RAG for {business_id}: {e}")
        return None

# Serve static frontend
app.mount("/static", StaticFiles(directory="static"), name="static")


# --- 1. GLOBAL STATE MANAGEMENT / MULTI-BUSINESS SUPPORT ---

# In-memory cache for chat sessions (fallback when Redis fails)
# Key: user_id, Value: chat session object
_chat_sessions_cache: Dict[str, Any] = {}

def initialize_session_state():
    """Defines the initial structure for a new user session.

    This is deliberately generic so the same backend can serve many businesses.
    Per-business configuration (name, system prompt, appointment link, etc.)
    can be attached at runtime and stored on this session object.
    """
    return {
        # Business / tenant-level config (optional, per user or per channel)
        "business_id": None,
        "system_instruction": None,  # full effective system prompt for this session
        "appointment_link": None,    # override default appointment link if provided

        # PII and IDs (Memory/Field Lock)
        "first_name": None,
        "email": None,
        "phone_number": None,
        "contact_id": None,
        "deal_id": None,
        
        # Conversation History (Gemini needs this to remember context)
        # Stored as list of dicts with "role" and "parts" keys
        "history": [],
        
        # Flow/Route Tracking
        "current_route": "intro",
        "awaiting_field": None,
    }

# In-memory session storage (for PII only - history handled by SDK)
_in_memory_sessions: Dict[str, Dict[str, Any]] = {}

def get_session(user_id: str) -> Dict[str, Any]:
    """
    Gets session state (for PII storage only - first_name, email, etc.).
    History is managed by SDK's chat session - no Redis needed!
    """
    # Use in-memory sessions only (Redis not needed - SDK handles history)
    if user_id not in _in_memory_sessions:
        _in_memory_sessions[user_id] = initialize_session_state()
    return _in_memory_sessions[user_id]

def get_or_create_chat_session(user_id: str, system_instruction: str):
    """
    Gets existing chat session from cache or creates a new one.
    This ensures SDK history is maintained even if Redis fails.
    """
    # Check if chat session exists in cache AND matches current system instruction
    if user_id in _chat_sessions_cache:
        cached = _chat_sessions_cache[user_id]
        cached_chat = cached.get("chat") if isinstance(cached, dict) else cached
        cached_instr = cached.get("system_instruction") if isinstance(cached, dict) else None

        if cached_instr == system_instruction and cached_chat is not None:
            print(f"[DEBUG] Using existing chat session from cache for user: {user_id}")
            return cached_chat

        # System instruction changed -> recreate session to avoid old persona/history leakage
        print(f"[DEBUG] System instruction changed for user={user_id}; recreating chat session")
        try:
            del _chat_sessions_cache[user_id]
        except Exception:
            pass

    # Create new chat session for this user using the effective system instruction
    print(f"[DEBUG] Creating new chat session for user: {user_id}")
    chat = create_chat_session(system_instruction)
    _chat_sessions_cache[user_id] = {"chat": chat, "system_instruction": system_instruction}
    return chat


def create_chat_session(system_instruction: str):
    """
    Creates a new Gemini chat session with system instruction and tools.
    The chat API automatically manages conversation history internally.
    """
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        tools=[crm_tools.search_contact, crm_tools.create_new_contact, crm_tools.create_deal],
    )
    
    # Create chat session with config - SDK will manage history automatically
    chat = client.chats.create(
        model=MODEL_NAME,
        config=config,
    )
    
    return chat


def restore_chat_history(chat, stored_history: List[Dict[str, Any]]):
    """
    Restores chat history by replaying messages to the chat session.
    This builds up the SDK's internal history state.
    Only replays user messages - model responses are generated automatically.
    """
    if not stored_history:
        return
    
    print(f"[DEBUG] Restoring {len(stored_history)} history messages to chat session")
    
    # Replay history: send each user message to build up chat's internal state
    # Skip model responses as they'll be regenerated
    i = 0
    while i < len(stored_history):
        msg = stored_history[i]
        if msg.get("role") == "user":
            parts = msg.get("parts", [])
            if parts and "text" in parts[0]:
                user_text = parts[0]["text"]
                try:
                    # Send user message - SDK automatically adds it to history
                    # Skip the response as we're just building history
                    chat.send_message(user_text)
                    print(f"[DEBUG] Replayed user message: {user_text[:50]}...")
                except Exception as e:
                    print(f"[WARNING] Could not replay history message: {e}")
                i += 1
            else:
                i += 1
        elif msg.get("role") == "model":
            # Skip model responses - they're part of history but we don't need to replay them
            i += 1
        else:
            i += 1


def save_chat_history_to_session(chat, session: Dict[str, Any]):
    """
    Saves chat history from the SDK's chat session to our Redis session storage.
    """
    try:
        chat_history = list(chat.get_history())
        
        print(f"[DEBUG] Saving chat history: {len(chat_history)} messages from SDK")
        
        # Convert chat history to our storage format (SDK format: Content[] with role + Part objects)
        session['history'] = []
        for msg in chat_history:
            parts_list = []
            for part in msg.parts:
                # Extract text from Part object
                if hasattr(part, 'text') and part.text:
                    parts_list.append({"text": part.text})
                # Extract function response from Part object
                elif hasattr(part, 'function_response'):
                    parts_list.append({
                        "function_response": part.function_response,
                        "name": getattr(part, 'name', '')
                    })
            
            # Save message with role (user/model/tool) and parts (SDK format)
            if parts_list:
                history_item = {
                    "role": msg.role,  # "user", "model", or "tool"
                    "parts": parts_list  # List of Part objects (text or function_response)
                }
                session['history'].append(history_item)
                print(f"[DEBUG] Saved message: role={msg.role}, parts={len(parts_list)}")
        
        # Trim history if it exceeds MAX_HISTORY_TURNS
        if len(session['history']) > MAX_HISTORY_TURNS * 2:
            session['history'] = session['history'][-MAX_HISTORY_TURNS*2:]
            print(f"[DEBUG] Trimmed history to {len(session['history'])} messages")
            
        print(f"[DEBUG] Total saved: {len(session['history'])} messages in SDK format (role + parts)")
    except Exception as e:
        print(f"[ERROR] Failed to save chat history: {e}")


# --- 2. SYSTEM INSTRUCTION (The Bot's Brain and Rules) ---

# Base guardrails that apply to every business. Individual businesses can add
# their own tone/branding/instructions on top of this at runtime.
BASE_SYSTEM_INSTRUCTION = """
You are an AI concierge for this specific business. You act as an always-on front desk to capture leads and share information from the business's own Knowledge Base or provided context.
Tone: warm, upbeat, human, joyful; use contractions and light positivity. Ask one question per turn and end with a friendly CTA.
Do not use bullets in replies.

Allowed HTML: <b> <i> <u> <br> <code> <a> only. Knowledge first—never guess.
Collect/share minimum PII; verify and E.164-format phone before creating a deal or booking any appointment.
Never reveal tool/API/action names or internal strings. Do not offer services that don’t exist in tools or provided business context.
Use memory; NEVER repeat a question the user already answered.

RAG CONTEXT RULES (STRICT):
- If a 'Context:' block is provided, answer ONLY with that information and cite the source URL inline (e.g., (source: https://...)).
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


def build_system_instruction(
    base_instruction: str,
    business_instruction: str | None = None,
) -> str:
    """
    Combines the global guardrails with any business- or tenant-specific
    instructions. This lets multiple businesses share the same backend while
    customizing tone, offerings, and domain knowledge.
    """
    parts: List[str] = [base_instruction.strip()]
    if business_instruction:
        parts.append(
            "BUSINESS / TENANT SPECIFIC INSTRUCTIONS:\n"
            + business_instruction.strip()
        )
    return "\n\n".join(parts)


# --- 3. HARD GUARD LOGIC ---

# Appointment Hard Guard defaults (can be overridden per session)
APPOINTMENT_LINK = '<a href="https://wp.wpgrowth.site/public/appointment/u/cQ4wCdoD2pBZmj8dFUXbzgRFZY1" target="_blank">Click Here</a>'
APPOINTMENT_RESPONSE_TEMPLATE = "You can check our availability and schedule directly through our calendar here: {link}."

def check_hard_guards(
    user_input: str,
    session: Dict[str, Any],
    session_key: str,
    original_user_id: str,
) -> str | None:
    """Checks for strict hard guards (Intro Token, Appointment) before calling Gemini."""
    
    clean_input = user_input.lower().strip()
    
    # Check for INTRO TOKEN (Resets the session if triggered)
    intro_triggers = ["hi", "hello", "hey", "start", "get started", "menu", "options", "help", "show choices", "what can you do", "reset", "restart"]
    if clean_input in intro_triggers or clean_input == 'action:click-intro':
        # Reset the session for a clean restart
        reset_session = initialize_session_state()
        reset_session['user_id'] = original_user_id
        reset_session['session_key'] = session_key
        # Update the session dict in place
        session.clear()
        session.update(reset_session)
        # Clear SDK chat session cache for this user (fresh start)
        if session_key in _chat_sessions_cache:
            del _chat_sessions_cache[session_key]
            print(f"[DEBUG] Cleared chat session cache for session_key: {session_key}")
        # Save to in-memory
        _in_memory_sessions[session_key] = session
        # Return a friendly prompt with primary options
        return (
            "Please choose one of the options below 👇<br><br>"
            "📅 Book an Appointment<br>"
            "💬 Speak to Sales<br>"
            "📦 Send More Information"
        )

    # Check for APPOINTMENT HARD GUARD
    appointment_triggers = [
        "booking",
        "book an appointment",
        "book appointment",
        "rescheduling",
        "canceling",
        "updating",
        "finding",
        "availability",
        "meeting",
        "call",
        "calendar",
    ]
    
    if any(trigger in clean_input for trigger in appointment_triggers):
        # Choose appointment link: per-session override first, then global default
        appointment_link = session.get("appointment_link") or APPOINTMENT_LINK
        response_text = APPOINTMENT_RESPONSE_TEMPLATE.format(link=appointment_link)
        # Update route and return the fixed response
        session["current_route"] = "appointments"
        # Save to in-memory (no Redis needed)
        _in_memory_sessions[session_key] = session
        return response_text
        
    return None # No hard guard triggered


# --- 4. CORE CONVERSATION ENDPOINT ---

@app.get("/")
async def root():
    """Serve the simple chat frontend."""
    return FileResponse("static/index.html")


@app.get("/health")
async def health():
    """Basic health endpoint to verify the server is running."""
    return {"status": "ok", "message": "WarmProspect Concierge Bot is running"}


@app.get("/rag/status")
async def rag_status():
    """Returns whether the RAG index is loaded."""
    return {
        "rag_loaded": retriever is not None,
        "index_path": "data/index.faiss",
        "meta_path": "data/meta.jsonl",
    }


# --- ADMIN API ENDPOINTS FOR BUSINESS CONFIGURATION ---

@app.post("/admin/business")
async def create_or_update_business(request: Request):
    """
    Create or update a business configuration.
    Clients can use this to configure their chatbot.
    """
    try:
        data = await request.json()
        
        business_id = data.get("business_id")
        if not business_id:
            raise HTTPException(status_code=400, detail="business_id is required")
        
        config = config_manager.create_or_update_business(
            business_id=business_id,
            business_name=data.get("business_name", business_id),
            system_prompt=data.get("system_prompt", ""),
            greeting_message=data.get("greeting_message"),
            appointment_link=data.get("appointment_link"),
            primary_goal=data.get("primary_goal"),
            personality=data.get("personality"),
            privacy_statement=data.get("privacy_statement"),
            theme_color=data.get("theme_color", "#2563eb"),
            widget_position=data.get("widget_position", "center"),
            website_url=data.get("website_url"),
            contact_email=data.get("contact_email"),
            contact_phone=data.get("contact_phone"),
        )
        
        return {"success": True, "config": config}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/admin/business/{business_id}")
async def get_business_config(business_id: str):
    """Get business configuration by ID."""
    config = config_manager.get_business(business_id)
    if not config:
        raise HTTPException(status_code=404, detail="Business not found")
    return {"success": True, "config": config}


@app.get("/admin/business")
async def list_all_businesses():
    """List all configured businesses."""
    businesses = config_manager.get_all_businesses()
    return {"success": True, "businesses": businesses}


@app.delete("/admin/business/{business_id}")
async def delete_business_config(business_id: str):
    """Delete a business configuration."""
    success = config_manager.delete_business(business_id)
    if not success:
        raise HTTPException(status_code=404, detail="Business not found")
    return {"success": True, "message": f"Business {business_id} deleted"}


@app.get("/admin")
async def admin_panel():
    """Serve the admin configuration panel."""
    return FileResponse("static/admin.html")


@app.get("/api/business/{business_id}/config")
async def get_business_config_for_widget(business_id: str):
    """
    Get business configuration for frontend widget.
    This endpoint is used by the chat widget to load business-specific settings.
    """
    config = config_manager.get_business(business_id)
    if not config:
        raise HTTPException(status_code=404, detail="Business not found")
    
    # Return only the fields needed for the frontend widget
    return {
        "businessId": config.get("business_id"),
        "businessName": config.get("business_name"),  # Added business name
        "businessPrimaryGoal": config.get("primary_goal"),
        "personalityPrompt": config.get("personality"),
        "greetingMessage": config.get("greeting_message"),
        "privacyStatement": config.get("privacy_statement"),
        "themeColor": config.get("theme_color", "#2563eb"),
        "widgetPosition": config.get("widget_position", "center"),
        "appointmentLink": config.get("appointment_link"),
    }

@app.post("/chat")
async def chat_endpoint(request: Request):
    """
    Main API endpoint to handle incoming chat messages, manages state,
    calls Gemini with tools, and handles the function response loop.
    """
    print(f"[DEBUG] ===== CHAT REQUEST RECEIVED =====")
    try:
        data = await request.json()
        print(f"[DEBUG] Request data received: {data}")
        user_input = data.get("message", "")
        user_id = data.get("user_id", "default_user")  # external user identifier
        # Optional multi-business / multi-tenant fields:
        business_id = data.get("business_id")
        # business-specific instructions (optional runtime override; DB config takes priority if present)
        business_system_prompt = data.get("system_prompt")
        appointment_link_override = data.get("appointment_link")
        use_request_prompt = bool(data.get("use_request_prompt", False))
        print(f"[DEBUG] Processing: user_id={user_id}, business_id={business_id}, message='{user_input[:50]}...'")

    except Exception as e:
        print(f"[ERROR] Failed to parse request: {e}")
        raise HTTPException(status_code=400, detail="Invalid request format.")

    # Basic validation
    if not isinstance(user_input, str) or not user_input.strip():
        raise HTTPException(status_code=400, detail="Message is required.")

    # 1. Initialize/Retrieve Session State
    # IMPORTANT: isolate sessions by (business_id, user_id) so history/prompt never leaks across tenants
    session_key = f"{business_id}:{user_id}" if business_id else user_id
    session = get_session(session_key)
    session["user_id"] = user_id
    session["session_key"] = session_key
    
    # Load business configuration if business_id is provided
    if business_id:
        session["business_id"] = business_id
        # Load stored business config if available
        stored_config = config_manager.get_business(business_id)
        if stored_config:
            # Prefer stored config (admin panel) over request-provided prompt unless explicitly overridden
            if not use_request_prompt:
                business_system_prompt = config_manager.build_system_prompt(business_id)
            if not appointment_link_override and stored_config.get("appointment_link"):
                appointment_link_override = stored_config.get("appointment_link")
            # Store other config values in session for frontend use
            session["business_name"] = stored_config.get("business_name")
            session["greeting_message"] = stored_config.get("greeting_message")
            session["theme_color"] = stored_config.get("theme_color")
            session["widget_position"] = stored_config.get("widget_position")
    
    # Apply runtime overrides
    if appointment_link_override:
        session["appointment_link"] = appointment_link_override
    
    # Keep session system instruction aligned with the business config.
    # If it changes, reset the cached chat session so old persona/history doesn't leak.
    if business_system_prompt and session.get("system_instruction") != business_system_prompt:
        session["system_instruction"] = business_system_prompt
        if session_key in _chat_sessions_cache:
            try:
                del _chat_sessions_cache[session_key]
                print(f"[DEBUG] Cleared chat session cache due to prompt change: {session_key}")
            except Exception:
                pass

    # 2. Hard Guard Check (Priority 1)
    hard_guard_response = check_hard_guards(user_input, session, session_key, user_id)
    if hard_guard_response:
        return {"response": hard_guard_response}

    # 3. Build effective system instruction (base guardrails + business-specific)
    effective_system_instruction = build_system_instruction(
        BASE_SYSTEM_INSTRUCTION,
        session.get("system_instruction"),
    )

    # 4. Get or create chat session using Gemini SDK Chat API
    # SDK automatically manages FULL conversation history - no Redis needed!
    print(f"[DEBUG] Session Key: {session_key} (user_id={user_id}, business_id={business_id})")
    
    # Get existing chat session from cache OR create new one.
    # SDK maintains history automatically in chat session object.
    chat = get_or_create_chat_session(session_key, effective_system_instruction)
    
    # Check SDK's internal history (automatically maintained!)
    current_sdk_history = list(chat.get_history())
    print(f"[DEBUG] SDK maintains {len(current_sdk_history)} messages in chat session")
    
    # Debug: Print recent history to verify memory
    if current_sdk_history:
        print(f"[DEBUG] Recent conversation history:")
        for i, msg in enumerate(current_sdk_history[-4:]):  # Last 4 messages
            role = msg.role
            text_preview = ""
            if msg.parts:
                first_part = msg.parts[0]
                if hasattr(first_part, 'text') and first_part.text:
                    text_preview = first_part.text[:60] + "..." if len(first_part.text) > 60 else first_part.text
            print(f"  [{i}] {role}: {text_preview}")
    
    # No need to restore history - SDK already has it if session exists!
    
    # 5. Prepare message with RAG context if available
    # IMPORTANT: Use business-specific retriever only (if its index exists).
    message_to_send = user_input
    biz_retriever = get_retriever_for_business(business_id)

    if biz_retriever:
        try:
            hits = biz_retriever.search(user_input)
            print(f"[RAG] hits={len(hits)}")
            for h in hits[:3]:
                print(f"[RAG] url={h.get('url')} score={h.get('score')}")
            
            ctx = format_context(hits)
            if ctx:
                # Prepend RAG context to the user message
                message_to_send = f"{ctx}\n\n{user_input}"
        except Exception as rag_err:
            print(f"RAG retrieval skipped: {rag_err}")
    
    # 6. Main Conversation Loop using Chat API (Handles Function Calling)
    # The chat.send_message() automatically includes FULL history - SDK manages it!
    def run_conversation_with_chat(chat_session, message: str) -> str:
        """
        Uses chat API's send_message which automatically includes full history.
        Handles function calling by using generate_content when needed.
        """
        # Send message - SDK automatically includes full history!
        response = chat_session.send_message(message)
        
        # Check for Function Calls
        if response.function_calls:
            print(">>> Gemini requested a function call...")
            tool_responses = []

            for call in response.function_calls:
                function_name = call.name
                function_args = dict(call.args)
                
                # Dynamic Tool Execution
                try:
                    func_to_call = getattr(crm_tools, function_name)
                    tool_output = func_to_call(**function_args)
                    
                    # Store results in session state
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
            # Get current chat history
            chat_history = list(chat_session.get_history())
            
            # Build contents with function response
            contents_with_tool_response = []
            for msg in chat_history:
                contents_with_tool_response.append(msg)
            
            # Add tool response
            contents_with_tool_response.append(types.Content(role="tool", parts=tool_responses))
            
            # Use generate_content to continue conversation with function response
            config = types.GenerateContentConfig(
                system_instruction=effective_system_instruction,
                tools=[crm_tools.search_contact, crm_tools.create_new_contact, crm_tools.create_deal]
            )
            
            gemini_response = client.models.generate_content(
                model=MODEL_NAME,
                contents=contents_with_tool_response,
                config=config,
            )
            
            # If there are more function calls, recurse
            if gemini_response.function_calls:
                # Add model response and recurse
                contents_with_tool_response.append(gemini_response.candidates[0].content)
                return run_conversation_with_chat_recursive(contents_with_tool_response)
            
            return gemini_response.text if gemini_response.text else ""
        
        # If no function call, return the text response
        return response.text
    
    def run_conversation_with_chat_recursive(current_contents: List[types.Content]) -> str:
        """
        Recursive helper for handling multiple rounds of function calling.
        """
        config = types.GenerateContentConfig(
            system_instruction=effective_system_instruction,
            tools=[crm_tools.search_contact, crm_tools.create_new_contact, crm_tools.create_deal],
        )
        
        gemini_response = client.models.generate_content(
            model=MODEL_NAME,
            contents=current_contents,
            config=config,
        )
        
        if gemini_response.function_calls:
            print(">>> Gemini requested another function call...")
            tool_responses = []
            
            for call in gemini_response.function_calls:
                function_name = call.name
                function_args = dict(call.args)
                
                try:
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
            
            current_contents.append(gemini_response.candidates[0].content)
            current_contents.append(types.Content(role="tool", parts=tool_responses))
            
            return run_conversation_with_chat_recursive(current_contents)
        
        return gemini_response.text if gemini_response.text else ""

    # 7. Execute the conversation turn using Chat API
    try:
        final_response_text = run_conversation_with_chat(chat, message_to_send)
    except Exception as exc:
        # Surface a JSON error instead of FastAPI HTML so the frontend can display it
        error_text = str(exc)
        import traceback
        print(f"!!! Chat endpoint error: {error_text}")
        print(f"!!! Traceback: {traceback.format_exc()}")
        
        if "RESOURCE_EXHAUSTED" in error_text or "quota" in error_text.lower():
            user_friendly = "We hit the model rate limit. Please wait ~30s and try again."
            print(f"!!! Quota hit: {error_text}")
            return {"response": user_friendly}
        
        # Return user-friendly error message
        error_msg = f"Sorry, I encountered an error. Please try again. ({error_text[:100]})"
        print(f"!!! {error_msg}")
        return {"response": error_msg}
    
    # 8. SDK automatically manages history - no need to save separately!
    # The chat session maintains full conversation history internally
    # We only update in-memory session for PII tracking (first_name, email, etc.)
    _in_memory_sessions[session_key] = session
    
    # SDK history is automatically maintained - check it
    current_sdk_history = list(chat.get_history())
    print(f"[DEBUG] SDK maintains {len(current_sdk_history)} messages in chat session (no Redis needed!)")
    print(f"[DEBUG] ===== SENDING RESPONSE: '{final_response_text[:100] if final_response_text else 'EMPTY'}...' =====")

    return {"response": final_response_text}


# --- 5. RUN SERVER INSTRUCTIONS (For local testing) ---
# To run this server:
# 1. Make sure you are in the warmprospect_poc directory.
# 2. Run the command: uvicorn main:app --reload