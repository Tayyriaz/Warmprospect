"""
CTA (Call-to-Action) handling functions.
"""

from typing import Dict, Any, List, Optional
from core.config.business_config import config_manager
from core.cta_tree import get_entry_point_cta


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
    
    # Get entry point CTA based on intent
    entry_cta = get_entry_point_cta(cta_tree, user_message)
    if entry_cta:
        return [entry_cta]
    
    return []


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
