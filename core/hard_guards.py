"""
Hard guard logic for handling special user inputs before processing.
"""

import os
from typing import Dict, Any, Optional
from core.session_management import initialize_session_state, clear_chat_session_cache
from core.session_store import save_session

# Appointment Hard Guard defaults (can be overridden per session)
APPOINTMENT_LINK = os.getenv("DEFAULT_APPOINTMENT_LINK", "") 
APPOINTMENT_RESPONSE_TEMPLATE = "You can check our availability and schedule directly through our calendar here: {link}."


def check_hard_guards(
    user_input: str,
    session: Dict[str, Any],
    session_key: str,
    original_user_id: str,
) -> Optional[Dict[str, Any]]:
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
        clear_chat_session_cache(session_key)
        # Save to Redis immediately
        save_session(session_key, session)
        # Return a friendly prompt - CTAs will be provided dynamically from cta_tree
        return {
            "response": "Please choose one of the options below.",
            "cta_mode": "primary",
        }

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
        # Save to Redis immediately
        save_session(session_key, session)
        return {"response": response_text}
        
    return None  # No hard guard triggered
