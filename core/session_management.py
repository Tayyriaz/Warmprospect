"""
Session management functions for chat sessions and state.
"""

from typing import Dict, Any, List, Optional
from core.session_state_machine import ConversationState
from core.session_store import load_session, save_session

# In-memory cache for chat sessions (fallback when Redis fails)
# Key: user_id, Value: chat session object
_chat_sessions_cache: Dict[str, Any] = {}


def initialize_session_state() -> Dict[str, Any]:
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
        
        # Session & Conversation Enhancements
        "conversation_state": ConversationState.INITIAL.value,  # State machine
        "state_history": [],  # State transition history
        "metadata": {},  # Custom metadata storage
        "analytics": {},  # Analytics tracking
        "conversation_plan": None,  # Multi-turn conversation plan
        "detected_intent": None,  # Latest detected intent
        "sentiment": None,  # Latest sentiment analysis
    }


def get_session(user_id: str) -> Dict[str, Any]:
    """
    Get or create a session for the given user_id.
    Uses Redis if available, falls back to in-memory cache.
    """
    def create_default_session():
        """Factory function to create a new session."""
        session = initialize_session_state()
        session["user_id"] = user_id
        return session
    
    session = load_session(user_id, create_default_session)
    if not session:
        session = initialize_session_state()
        session["user_id"] = user_id
        save_session(user_id, session)
    return session


def clear_chat_session_cache(session_key: str):
    """Clear a chat session from the in-memory cache."""
    if session_key in _chat_sessions_cache:
        del _chat_sessions_cache[session_key]
        print(f"[DEBUG] Cleared chat session cache for session_key: {session_key}")


def get_chat_sessions_cache() -> Dict[str, Any]:
    """Get the chat sessions cache."""
    return _chat_sessions_cache
