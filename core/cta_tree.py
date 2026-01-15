"""
CTA Tree Management
Handles tree-based CTA structure as per team lead's approach.

Key Concept:
- CTAs stored as tree structure in database/config
- Backend only decides entry point based on intent
- Frontend sends CTA ID to get children
- Each response contains only current level CTAs
"""

from typing import Dict, Any, List, Optional


def get_cta_children(cta_tree: Dict[str, Any], cta_id: str) -> List[Dict[str, Any]]:
    """
    Get children CTAs for a given CTA ID.
    Returns list of CTA objects (without nested children array).
    
    Args:
        cta_tree: Complete CTA tree dictionary
        cta_id: ID of the CTA to get children for
    
    Returns:
        List of CTA objects (without children field)
    """
    if not cta_tree or not isinstance(cta_tree, dict):
        return []
    
    cta = cta_tree.get(cta_id)
    if not cta:
        return []
    
    # Only return children if action is show_children
    if cta.get("action") != "show_children" or not cta.get("children"):
        return []
    
    # Return children as CTA objects (without their children array)
    children_ctas = []
    for child_id in cta["children"]:
        child_cta = cta_tree.get(child_id)
        if child_cta:
            # Return CTA without children array (frontend doesn't need it)
            cta_obj = {
                "id": child_cta["id"],
                "label": child_cta["label"],
                "action": child_cta["action"]
            }
            if child_cta.get("url"):
                cta_obj["url"] = child_cta["url"]
            if child_cta.get("message"):
                cta_obj["message"] = child_cta["message"]
            children_ctas.append(cta_obj)
    
    return children_ctas


def get_cta_by_id(cta_tree: Dict[str, Any], cta_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a single CTA by ID (without children array).
    
    Args:
        cta_tree: Complete CTA tree dictionary
        cta_id: ID of the CTA to get
    
    Returns:
        CTA object (without children field) or None
    """
    if not cta_tree or not isinstance(cta_tree, dict):
        return None
    
    cta = cta_tree.get(cta_id)
    if not cta:
        return None
    
    # Return CTA without children array
    cta_obj = {
        "id": cta["id"],
        "label": cta["label"],
        "action": cta["action"]
    }
    if cta.get("url"):
        cta_obj["url"] = cta["url"]
    if cta.get("message"):
        cta_obj["message"] = cta["message"]
    
    return cta_obj


def detect_intent_from_message(message: str) -> str:
    """
    Detect user intent from message.
    Returns intent type: 'service_inquiry', 'appointment_inquiry', 'sales_inquiry', or 'general_inquiry'
    
    Args:
        message: User message text
    
    Returns:
        Intent type string
    """
    if not message:
        return "general_inquiry"
    
    message_lower = message.lower()
    
    # Service inquiry keywords
    if any(word in message_lower for word in ["service", "offer", "provide", "what do you", "tell me about", "what can you"]):
        return "service_inquiry"
    
    # Appointment inquiry keywords
    if any(word in message_lower for word in ["appointment", "schedule", "book", "call", "meeting", "calendar", "consultation"]):
        return "appointment_inquiry"
    
    # Sales inquiry keywords
    if any(word in message_lower for word in ["sales", "speak to", "talk to", "contact", "representative", "speak with"]):
        return "sales_inquiry"
    
    return "general_inquiry"


def get_entry_point_cta(
    cta_tree: Dict[str, Any], 
    message: str, 
    intent: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Get entry point CTA based on user message and intent.
    
    Args:
        cta_tree: Complete CTA tree dictionary
        message: User message
        intent: Optional pre-detected intent (if None, will detect)
    
    Returns:
        Entry point CTA object (without children field) or None
    """
    if not cta_tree or not isinstance(cta_tree, dict):
        return None
    
    # Detect intent if not provided
    if intent is None:
        intent = detect_intent_from_message(message)
    
    message_lower = message.lower()
    
    # Map intent to entry point CTA IDs
    # Check for specific keywords first
    if "website" in message_lower or "design" in message_lower:
        entry_cta = get_cta_by_id(cta_tree, "website_design")
        if entry_cta:
            return entry_cta
    
    if "crm" in message_lower or "software" in message_lower:
        entry_cta = get_cta_by_id(cta_tree, "crm_platform")
        if entry_cta:
            return entry_cta
    
    if any(word in message_lower for word in ["growth", "scale", "expand", "grow"]):
        entry_cta = get_cta_by_id(cta_tree, "business_growth")
        if entry_cta:
            return entry_cta
    
    # Map intent to default entry points
    if intent == "service_inquiry":
        entry_cta = get_cta_by_id(cta_tree, "learn_services")
        if entry_cta:
            return entry_cta
    
    elif intent == "appointment_inquiry":
        entry_cta = get_cta_by_id(cta_tree, "book_appointment")
        if entry_cta:
            return entry_cta
    
    elif intent == "sales_inquiry":
        entry_cta = get_cta_by_id(cta_tree, "speak_sales")
        if entry_cta:
            return entry_cta
    
    # Default fallback
    entry_cta = get_cta_by_id(cta_tree, "learn_services")
    if entry_cta:
        return entry_cta
    
    # If no specific entry point found, return first available CTA with show_children
    for cta_id, cta in cta_tree.items():
        if cta.get("action") == "show_children":
            return get_cta_by_id(cta_tree, cta_id)
    
    return None
