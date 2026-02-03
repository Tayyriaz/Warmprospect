"""
Chat session management with Gemini SDK.
"""

from typing import Dict, Any, List, Optional
from google.genai import types
from core.session.session_management import get_chat_sessions_cache
from core.integrations.crm import crm_manager


def get_or_create_chat_session(
    user_id: str,
    system_instruction: str,
    client,
    model_name: str,
    stored_history: Optional[List[Dict[str, Any]]] = None,
    business_id: Optional[str] = None
):
    """
    Get or create a chat session for a user, restoring history if available.
    Uses in-memory cache to avoid recreating sessions unnecessarily.
    """
    _chat_sessions_cache = get_chat_sessions_cache()
    
    # Check if we have a cached session with matching system instruction
    if user_id in _chat_sessions_cache:
        cached = _chat_sessions_cache[user_id]
        if cached.get("system_instruction") == system_instruction:
            print(f"[DEBUG] Reusing cached chat session for user: {user_id}")
            chat = cached["chat"]
            
            # Restore history if provided and chat is empty
            if stored_history and not list(chat.get_history()):
                restore_chat_history(chat, stored_history)
            
            return chat
        
        # System instruction changed -> recreate session to avoid old persona/history leakage
        print(f"[DEBUG] System instruction changed for user={user_id}; recreating chat session")
        try:
            del _chat_sessions_cache[user_id]
        except Exception:
            pass

    # Create new chat session for this user using the effective system instruction
    print(f"[DEBUG] Creating new chat session for user: {user_id}")
    chat = create_chat_session(system_instruction, client, model_name, business_id)
    _chat_sessions_cache[user_id] = {"chat": chat, "system_instruction": system_instruction}
    
    # Restore history if provided
    if stored_history:
        restore_chat_history(chat, stored_history)
    
    return chat


def create_chat_session(system_instruction: str, client, model_name: str, business_id: Optional[str] = None):
    """
    Creates a new Gemini chat session with system instruction and tools.
    The chat API automatically manages conversation history internally.
    """
    # Get CRM tools for this business (if available)
    crm_tools = crm_manager.get_crm_tools(business_id)
    tools_config = None
    if crm_tools is not None:
        tools_config = [crm_tools.search_contact, crm_tools.create_new_contact, crm_tools.create_deal]
    
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        tools=tools_config,
    )
    
    # Create chat session with config - SDK will manage history automatically
    chat = client.chats.create(
        model=model_name,
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


def save_chat_history_to_session(chat, session: Dict[str, Any], max_history_turns: int):
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
        if len(session['history']) > max_history_turns * 2:
            session['history'] = session['history'][-max_history_turns*2:]
            print(f"[DEBUG] Trimmed history to {len(session['history'])} messages")
            
        print(f"[DEBUG] Total saved: {len(session['history'])} messages in SDK format (role + parts)")
    except Exception as e:
        print(f"[ERROR] Failed to save chat history: {e}")
