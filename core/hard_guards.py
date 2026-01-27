"""
Hard guard logic for handling special user inputs before processing.
"""

import os
from typing import Dict, Any, Optional
from core.session_management import initialize_session_state, clear_chat_session_cache
from core.session_store import save_session

def check_hard_guards(
    user_input: str,
    session: Dict[str, Any],
    session_key: str,
    original_user_id: str,
    business_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Checks for strict hard guards (Intro Token) before calling Gemini.
    Note: Appointment booking is now handled via CTA tree (redirect action with URL).
    """
    
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
        
        # Use business greeting_message if available, otherwise return None to let AI handle it
        from core.config.business_config import config_manager
        greeting_message = None
        if business_id:
            config = config_manager.get_business(business_id)
            if config:
                greeting_message = config.get("greeting_message")
        
        # Return greeting message if available, otherwise return None to let AI generate natural response
        if greeting_message:
            return {
                "response": greeting_message,
                "cta_mode": "primary",
            }
        # Return None - session is reset, but let normal chat flow generate the greeting naturally
        # CTAs will be attached by the normal flow based on should_attach_ctas() logic
        return None
        
    # Note: Appointment booking is now handled via CTA tree
    # Users click CTAs with action="redirect" and url pointing to appointment links
    # This allows multiple appointment links per tenant (e.g., different departments)
        
    return None  # No hard guard triggered
