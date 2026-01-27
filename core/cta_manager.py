"""
Dynamic CTA (Call-to-Action) Management System
Supports tree-based CTAs with context-aware selection.
Uses only cta_tree structure - no primary/secondary/nested CTAs.
"""

from typing import Dict, Any, List, Optional
from enum import Enum
from core.rules_engine import BusinessRulesEngine, RuleType
from core.cta_tree import get_cta_children, get_entry_point_cta


class CTAAction(Enum):
    """Types of CTA actions."""
    SEND = "send"  # Send a message
    SHOW_CHILDREN = "show_children"  # Show next level CTAs
    LINK = "link"  # Redirect to URL


class DynamicCTAManager:
    """
    Manages dynamic CTA system using only cta_tree structure.
    """
    
    def __init__(self, rules_engine: Optional[BusinessRulesEngine] = None):
        self.rules_engine = rules_engine
    
    def get_ctas_for_context(
        self,
        context: Dict[str, Any],
        business_config: Dict[str, Any],
        conversation_history: List[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get CTAs based on current context and conversation state.
        Returns only CTAs from cta_tree structure.
        
        Args:
            context: Current conversation context
            business_config: Business configuration containing cta_tree
            conversation_history: List of conversation messages
        
        Returns:
            List of CTA objects from cta_tree
        """
        conversation_history = conversation_history or []
        
        # Get cta_tree from business config
        cta_tree = business_config.get("cta_tree", {})
        if not cta_tree or not isinstance(cta_tree, dict):
            return []
        
        # Build full context for rule evaluation
        full_context = {
            "session": context.get("session", {}),
            "conversation": {
                "history_length": len(conversation_history),
                "last_message": conversation_history[-1] if conversation_history else None,
                "topic": self._detect_topic(conversation_history),
                "intent": self._detect_intent(conversation_history, context)
            },
            "user": {
                "first_name": context.get("session", {}).get("first_name"),
                "email": context.get("session", {}).get("email"),
                "phone": context.get("session", {}).get("phone_number"),
                "contact_id": context.get("session", {}).get("contact_id"),
                "deal_id": context.get("session", {}).get("deal_id")
            },
            "business": {
                "business_id": business_config.get("business_id"),
                "primary_goal": business_config.get("primary_goal")
            }
        }
        
        # Evaluate CTA visibility rules if rules engine is available
        if self.rules_engine:
            _, full_context = self.rules_engine.evaluate_rules(
                RuleType.CTA_VISIBILITY,
                full_context
            )
        
        # Get entry point CTA based on user message/intent
        last_user_message = ""
        if conversation_history:
            for msg in reversed(conversation_history):
                if isinstance(msg, dict) and msg.get("role") == "user":
                    parts = msg.get("parts", [])
                    if parts and isinstance(parts[0], dict):
                        last_user_message = parts[0].get("text", "")
                        break
        
        # Get entry point CTA from tree
        entry_cta = get_entry_point_cta(cta_tree, last_user_message, None, conversation_history)
        
        if entry_cta:
            # Return entry point CTA
            return [entry_cta]
        
        # If no entry point found, return empty list
        return []
    
    def get_cta_children(
        self,
        cta_tree: Dict[str, Any],
        cta_id: str,
        context: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Get children CTAs for a given CTA ID from cta_tree.
        
        Args:
            cta_tree: Complete CTA tree dictionary
            cta_id: ID of the CTA to get children for
            context: Optional context for filtering
        
        Returns:
            List of child CTA objects
        """
        if not cta_tree or not isinstance(cta_tree, dict):
            return []
        
        # Get children from tree
        children = get_cta_children(cta_tree, cta_id)
        
        # Filter by visibility rules if context provided
        if context and self.rules_engine:
            filtered_children = []
            for cta in children:
                if self._should_show_cta(cta, context):
                    filtered_children.append(cta)
            return filtered_children
        
        return children
    
    def _should_show_cta(self, cta: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """Check if a CTA should be shown based on its conditions."""
        conditions = cta.get("conditions", [])
        
        if not conditions:
            return True  # No conditions = always show
        
        # Check visibility conditions
        for condition in conditions:
            field = condition.get("field", "")
            operator = condition.get("operator", "equals")
            value = condition.get("value")
            
            context_value = self._get_context_value(context, field)
            
            if not self._evaluate_condition(context_value, operator, value):
                if condition.get("required", True):
                    return False
        
        return True
    
    def _detect_topic(self, conversation_history) -> Optional[str]:
        """Detect conversation topic from history."""
        if not conversation_history:
            return None
        
        # Handle both SDK objects and dictionaries
        recent_messages_list = []
        for msg in conversation_history[-5:]:
            # Check if it's an SDK object (has attributes) or dict (has get method)
            if hasattr(msg, 'role'):
                # SDK object
                if msg.role == "user" and hasattr(msg, 'parts') and msg.parts:
                    first_part = msg.parts[0]
                    if hasattr(first_part, 'text') and first_part.text:
                        recent_messages_list.append(first_part.text)
            elif isinstance(msg, dict):
                # Dictionary
                if msg.get("role") == "user":
                    parts = msg.get("parts", [])
                    if parts and isinstance(parts[0], dict):
                        recent_messages_list.append(parts[0].get("text", ""))
        
        recent_messages = " ".join(recent_messages_list).lower()
        
        topic_keywords = {
            "pricing": ["price", "cost", "pricing", "how much", "fee"],
            "services": ["service", "what do you", "offer", "provide"],
            "booking": ["book", "appointment", "schedule", "availability"],
            "support": ["help", "support", "problem", "issue", "fix"]
        }
        
        for topic, keywords in topic_keywords.items():
            if any(keyword in recent_messages for keyword in keywords):
                return topic
        
        return None
    
    def _detect_intent(
        self,
        conversation_history,
        context: Dict[str, Any]
    ) -> Optional[str]:
        """Detect user intent from conversation and context."""
        if not conversation_history:
            return "greeting"
        
        last_user_message = ""
        for msg in reversed(conversation_history):
            # Handle both SDK objects and dictionaries
            msg_role = None
            msg_text = ""
            
            if hasattr(msg, 'role'):
                # SDK object
                msg_role = msg.role
                if msg.role == "user" and hasattr(msg, 'parts') and msg.parts:
                    first_part = msg.parts[0]
                    if hasattr(first_part, 'text') and first_part.text:
                        msg_text = first_part.text
            elif isinstance(msg, dict):
                # Dictionary
                msg_role = msg.get("role")
                if msg_role == "user":
                    parts = msg.get("parts", [])
                    if parts:
                        if isinstance(parts[0], dict):
                            msg_text = parts[0].get("text", "")
                        elif hasattr(parts[0], 'text'):
                            msg_text = parts[0].text
            
            if msg_role == "user" and msg_text:
                last_user_message = msg_text.lower()
                break
        
        intent_patterns = {
            "pricing_inquiry": ["price", "cost", "how much", "pricing", "fee"],
            "service_inquiry": ["what do you", "services", "offer", "provide", "can you"],
            "booking_inquiry": ["book", "appointment", "schedule", "available", "when"],
            "complaint": ["problem", "issue", "wrong", "bad", "disappointed"],
            "compliment": ["great", "excellent", "love", "amazing", "thank you"],
            "greeting": ["hi", "hello", "hey", "good morning", "good afternoon"]
        }
        
        for intent, patterns in intent_patterns.items():
            if any(pattern in last_user_message for pattern in patterns):
                return intent
        
        return None
    
    def _evaluate_condition(self, context_value: Any, operator: str, expected_value: Any) -> bool:
        """Evaluate a condition."""
        if operator == "equals":
            return context_value == expected_value
        elif operator == "not_equals":
            return context_value != expected_value
        elif operator == "contains":
            if isinstance(context_value, str) and isinstance(expected_value, str):
                return expected_value.lower() in context_value.lower()
            return False
        elif operator == "exists":
            return context_value is not None
        elif operator == "not_exists":
            return context_value is None
        elif operator == "greater_than":
            try:
                return float(context_value) > float(expected_value)
            except (ValueError, TypeError):
                return False
        
        return False
    
    def _get_context_value(self, context: Dict[str, Any], path: str) -> Any:
        """Get value from context using dot notation."""
        keys = path.split(".")
        current = context
        
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
            else:
                return None
            
            if current is None:
                return None
        
        return current
