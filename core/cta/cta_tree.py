"""
CTA Tree Management
Handles tree-based CTA structure as per team lead's approach.

Key Concept:
- CTAs stored as tree structure in database/config
- Backend only decides entry point based on intent
- Frontend sends CTA ID to get children
- Each response contains only current level CTAs
"""

from typing import Dict, Any, List, Optional, Tuple


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


def detect_intent_from_message(
    message: str,
    conversation_history: Optional[List[Any]] = None
) -> Dict[str, Any]:
    """
    Enhanced intent detection from message and conversation history.
    Returns detailed intent classification with confidence.
    
    Args:
        message: User message text
        conversation_history: Optional conversation history for context
    
    Returns:
        Dictionary with intent type, confidence, and details
    """
    if not message:
        return {
            "intent": "general_inquiry",
            "confidence": 0.5,
            "category": "general"
        }
    
    message_lower = message.lower()
    
    # Intent categories with keywords and weights
    intent_patterns = {
        "service_inquiry": {
            "keywords": ["service", "offer", "provide", "what do you", "tell me about", "what can you", "features", "capabilities", "do you have"],
            "weight": 1.0
        },
        "appointment_inquiry": {
            "keywords": ["appointment", "schedule", "book", "call", "meeting", "calendar", "consultation", "available", "when can"],
            "weight": 1.2
        },
        "sales_inquiry": {
            "keywords": ["sales", "speak to", "talk to", "contact", "representative", "speak with", "salesperson", "sales rep"],
            "weight": 1.1
        },
        "pricing_inquiry": {
            "keywords": ["price", "cost", "pricing", "how much", "fee", "charge", "budget", "afford"],
            "weight": 1.0
        },
        "technical_support": {
            "keywords": ["help", "support", "issue", "problem", "error", "bug", "not working", "broken"],
            "weight": 1.0
        },
        "product_inquiry": {
            "keywords": ["product", "solution", "platform", "software", "tool", "system"],
            "weight": 0.9
        }
    }
    
    # Score each intent
    intent_scores = {}
    for intent, pattern in intent_patterns.items():
        score = 0.0
        for keyword in pattern["keywords"]:
            if keyword in message_lower:
                score += pattern["weight"]
        intent_scores[intent] = score
    
    # Get top intent
    if intent_scores:
        top_intent = max(intent_scores.items(), key=lambda x: x[1])
        if top_intent[1] > 0:
            # Normalize confidence (0.5 to 0.95 based on score)
            confidence = min(0.95, 0.5 + (top_intent[1] / 5.0))
            return {
                "intent": top_intent[0],
                "confidence": confidence,
                "category": top_intent[0].split("_")[0] if "_" in top_intent[0] else "general",
                "score": top_intent[1],
                "all_scores": intent_scores
            }
    
    # Consider conversation history for context
    if conversation_history:
        recent_intent = _detect_intent_from_history(conversation_history)
        if recent_intent and recent_intent.get("intent") != "general_inquiry":
            # Weight current message 60%, history 40%
            if recent_intent["intent"] in intent_scores:
                combined_confidence = (0.6 * intent_scores.get(recent_intent["intent"], 0) / 5.0) + \
                                     (0.4 * recent_intent.get("confidence", 0.5))
                return {
                    "intent": recent_intent["intent"],
                    "confidence": min(0.95, combined_confidence),
                    "category": recent_intent.get("category", "general"),
                    "context_enhanced": True
                }
    
    return {
        "intent": "general_inquiry",
        "confidence": 0.5,
        "category": "general"
    }


def _detect_intent_from_history(conversation_history: List[Any]) -> Optional[Dict[str, Any]]:
    """
    Detect intent from recent conversation history.
    
    Args:
        conversation_history: List of conversation messages
    
    Returns:
        Intent detection result or None
    """
    if not conversation_history:
        return None
    
    # Analyze last 3 user messages
    recent_messages = []
    for msg in reversed(conversation_history[-6:]):  # Last 6 messages
        text = ""
        if hasattr(msg, 'role') and hasattr(msg, 'parts'):
            # SDK object
            if msg.role == "user" and msg.parts:
                text = getattr(msg.parts[0], 'text', '')
        elif isinstance(msg, dict):
            # Dictionary format
            if msg.get("role") == "user":
                parts = msg.get("parts", [])
                if parts and isinstance(parts[0], dict):
                    text = parts[0].get("text", "")
        
        if text:
            recent_messages.append(text)
            if len(recent_messages) >= 3:
                break
    
    if not recent_messages:
        return None
    
    # Analyze combined recent messages
    combined_text = " ".join(recent_messages)
    return detect_intent_from_message(combined_text)


def get_entry_point_cta(
    cta_tree: Dict[str, Any], 
    message: str, 
    intent_result: Optional[Dict[str, Any]] = None,
    conversation_history: Optional[List[Any]] = None
) -> Optional[Dict[str, Any]]:
    """
    Get entry point CTA based on user message and intent.
    
    Args:
        cta_tree: Complete CTA tree dictionary
        message: User message
        intent_result: Optional pre-detected intent result (if None, will detect)
        conversation_history: Optional conversation history for context
    
    Returns:
        Entry point CTA object (without children field) or None
    """
    if not cta_tree or not isinstance(cta_tree, dict):
        return None
    
    # Detect intent if not provided
    if intent_result is None:
        intent_result = detect_intent_from_message(message, conversation_history)
    
    # Extract intent string from result (backward compatibility)
    intent = intent_result.get("intent", "general_inquiry") if isinstance(intent_result, dict) else intent_result
    
    # No hardcoded CTA IDs - use generic fallback to find first available entry point
    # Return first available CTA with show_children action (entry point)
    for cta_id, cta in cta_tree.items():
        if cta.get("action") == "show_children":
            return get_cta_by_id(cta_tree, cta_id)
    
    return None
