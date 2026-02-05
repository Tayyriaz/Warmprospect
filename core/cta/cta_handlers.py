"""
CTA (Call-to-Action) handling functions.
"""

from typing import Dict, Any, List, Optional
from core.config.business_config import config_manager
from core.cta.cta_tree import get_entry_point_cta


def get_entry_point_ctas(
    business_id: Optional[str],
    user_message: str
) -> List[Dict[str, Any]]:
    """
    Get entry point CTAs based on user message and intent (Tree-based approach).
    
    Args:
        business_id: Business identifier
        user_message: User's message to detect intent from
    
    Returns:
        List of entry point CTA objects (single level, no nested children)
    """
    if not business_id:
        return []
    
    config = config_manager.get_business(business_id)
    if not config:
        return []
    
    # Get CTA tree from config
    cta_tree = config.get("cta_tree", {})
    if not cta_tree or not isinstance(cta_tree, dict):
        return []
    
    # Get entry point CTAs based on intent
    # Return ALL entry point CTAs (CTAs with action="show_children" at root level)
    # Skip "main_menu" as it's just a container - return its children instead
    entry_ctas = []
    main_menu_cta = None
    
    for cta_id, cta in cta_tree.items():
        # Skip if cta is not a dict (e.g. corrupted data, string, etc.)
        if not isinstance(cta, dict):
            print(f"[WARN] Skipping invalid CTA entry '{cta_id}': expected dict, got {type(cta).__name__}")
            continue
        
        # Special handling for main_menu - get its children instead
        if cta_id == "main_menu" and cta.get("action") == "show_children":
            main_menu_cta = cta
            continue
            
        if cta.get("action") == "show_children":
            cta_obj = {
                "id": cta.get("id", cta_id),
                "label": cta.get("label", cta_id),
                "action": cta.get("action", "show_children")
            }
            if cta.get("url"):
                cta_obj["url"] = cta["url"]
            if cta.get("message"):
                cta_obj["message"] = cta["message"]
            entry_ctas.append(cta_obj)
    
    # If main_menu exists, return its children as entry points instead
    if main_menu_cta and main_menu_cta.get("children"):
        from core.cta.cta_tree import get_cta_children
        children_ctas = get_cta_children(cta_tree, "main_menu")
        if children_ctas:
            return children_ctas
    
    # If no entry points found, try to get one using intent detection
    if not entry_ctas:
        entry_cta = get_entry_point_cta(cta_tree, user_message)
        if entry_cta:
            return [entry_cta]
    
    return entry_ctas


def should_attach_ctas(text: str) -> bool:
    """
    Determine if CTAs should be attached to the response.
    CTAs are shown when:
    1. Response contains "please choose one of the options below"
    2. Response asks a question or suggests an action
    3. Response is a greeting or initial message
    """
    if not text:
        return False
    normalized = text.lower()
    
    # Always show CTAs if response contains these phrases
    cta_indicators = [
        "please choose one of the options below",
        "how can i help",
        "what would you like",
        "would you like to",
        "can i help you",
        "let me know",
        "feel free to"
    ]
    
    # Check if any indicator is present
    for indicator in cta_indicators:
        if indicator in normalized:
            return True
    
    # Also show CTAs if response ends with a question mark
    if text.strip().endswith("?"):
        return True
    
    return False
