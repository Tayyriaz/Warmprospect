"""
Dynamic Routing System
Supports context-aware routing decisions based on business rules.
"""

from typing import Dict, Any, List, Optional
from enum import Enum
from core.rules_engine import BusinessRulesEngine, RuleType


class RouteType(Enum):
    """Types of routes in the conversation flow."""
    INTRO = "intro"
    APPOINTMENTS = "appointments"
    SALES = "sales"
    SUPPORT = "support"
    INFORMATION = "information"
    PRODUCT_INQUIRY = "product_inquiry"
    PRICING = "pricing"
    CUSTOM = "custom"


class DynamicRouter:
    """
    Handles dynamic routing decisions based on conversation context and business rules.
    """
    
    def __init__(self, rules_engine: Optional[BusinessRulesEngine] = None):
        self.rules_engine = rules_engine
    
    def determine_route(
        self,
        context: Dict[str, Any],
        user_input: str,
        conversation_history: List[Dict[str, Any]],
        business_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Determine the optimal route based on context, user input, and business rules.
        
        Returns:
            Dictionary with:
                - route: RouteType value
                - confidence: Float (0.0-1.0)
                - reasoning: String explanation
                - actions: List of actions to execute
        """
        # Build full context for routing
        full_context = {
            "session": context.get("session", {}),
            "user_input": user_input,
            "conversation": {
                "history_length": len(conversation_history),
                "last_message": conversation_history[-1] if conversation_history else None,
                "topic": self._detect_topic(conversation_history),
                "intent": self._detect_intent(user_input, conversation_history, context)
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
        
        # Get current route from session
        current_route = context.get("session", {}).get("current_route", "intro")
        
        # Evaluate routing rules
        if self.rules_engine:
            routing_actions, full_context = self.rules_engine.evaluate_rules(
                RuleType.ROUTING,
                full_context
            )
            
            # Check if rules explicitly set a route
            for action in routing_actions:
                if action.get("type") == "set_field" and action.get("field") == "session.current_route":
                    route_name = action.get("value")
                    return {
                        "route": route_name,
                        "confidence": 1.0,
                        "reasoning": "Business rule explicitly set route",
                        "actions": routing_actions,
                        "context": full_context
                    }
        
        # Rule-based routing using intent and context
        route_decision = self._intent_based_routing(full_context)
        
        # Override with custom routing logic if business has custom rules
        custom_routes = business_config.get("custom_routes", {})
        if custom_routes:
            custom_route = self._evaluate_custom_routes(custom_routes, full_context)
            if custom_route:
                route_decision = custom_route
        
        return {
            **route_decision,
            "context": full_context
        }
    
    def _intent_based_routing(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Route based on detected intent."""
        intent = context.get("conversation", {}).get("intent")
        user_input = context.get("user_input", "").lower()
        
        route_map = {
            "pricing_inquiry": {
                "route": RouteType.PRICING.value,
                "confidence": 0.9,
                "reasoning": "User is asking about pricing"
            },
            "booking_inquiry": {
                "route": RouteType.APPOINTMENTS.value,
                "confidence": 0.9,
                "reasoning": "User wants to book an appointment"
            },
            "service_inquiry": {
                "route": RouteType.PRODUCT_INQUIRY.value,
                "confidence": 0.8,
                "reasoning": "User is inquiring about services"
            },
            "complaint": {
                "route": RouteType.SUPPORT.value,
                "confidence": 0.9,
                "reasoning": "User has a complaint or issue"
            },
            "greeting": {
                "route": RouteType.INTRO.value,
                "confidence": 0.7,
                "reasoning": "User is greeting or starting conversation"
            }
        }
        
        if intent in route_map:
            return route_map[intent]
        
        # Fallback: keyword-based routing
        if any(word in user_input for word in ["price", "cost", "pricing", "how much"]):
            return {
                "route": RouteType.PRICING.value,
                "confidence": 0.7,
                "reasoning": "Keywords suggest pricing inquiry"
            }
        elif any(word in user_input for word in ["book", "appointment", "schedule", "available"]):
            return {
                "route": RouteType.APPOINTMENTS.value,
                "confidence": 0.8,
                "reasoning": "Keywords suggest booking inquiry"
            }
        elif any(word in user_input for word in ["service", "what do you", "offer", "provide"]):
            return {
                "route": RouteType.INFORMATION.value,
                "confidence": 0.7,
                "reasoning": "Keywords suggest information inquiry"
            }
        
        # Default route
        return {
            "route": RouteType.INTRO.value,
            "confidence": 0.5,
            "reasoning": "Default route - no specific intent detected"
        }
    
    def _evaluate_custom_routes(
        self,
        custom_routes: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Evaluate custom routing rules defined by business."""
        routes = custom_routes.get("routes", [])
        
        for route_rule in routes:
            conditions = route_rule.get("conditions", [])
            route_name = route_rule.get("route")
            priority = route_rule.get("priority", 0)
            
            # Evaluate conditions
            if self._evaluate_route_conditions(conditions, context):
                return {
                    "route": route_name,
                    "confidence": route_rule.get("confidence", 0.8),
                    "reasoning": route_rule.get("reasoning", "Custom route matched"),
                    "priority": priority
                }
        
        return None
    
    def _evaluate_route_conditions(
        self,
        conditions: List[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> bool:
        """Evaluate route conditions."""
        if not conditions:
            return True
        
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
        user_input: str,
        conversation_history: List[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> Optional[str]:
        """Detect user intent from input and context."""
        user_input_lower = user_input.lower()
        
        intent_patterns = {
            "pricing_inquiry": ["price", "cost", "how much", "pricing", "fee"],
            "service_inquiry": ["what do you", "services", "offer", "provide", "can you"],
            "booking_inquiry": ["book", "appointment", "schedule", "available", "when"],
            "complaint": ["problem", "issue", "wrong", "bad", "disappointed"],
            "compliment": ["great", "excellent", "love", "amazing", "thank you"],
            "greeting": ["hi", "hello", "hey", "good morning", "good afternoon"]
        }
        
        for intent, patterns in intent_patterns.items():
            if any(pattern in user_input_lower for pattern in patterns):
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


def apply_routing_to_session(
    route_decision: Dict[str, Any],
    session: Dict[str, Any]
) -> Dict[str, Any]:
    """Apply routing decision to session context."""
    session["current_route"] = route_decision.get("route", "intro")
    session["route_confidence"] = route_decision.get("confidence", 0.5)
    session["route_reasoning"] = route_decision.get("reasoning", "")
    
    # Apply any actions from routing
    actions = route_decision.get("actions", [])
    for action in actions:
        if action.get("type") == "set_field":
            field_path = action.get("field", "")
            value = action.get("value")
            keys = field_path.split(".")
            current = session
            for key in keys[:-1]:
                if key not in current:
                    current[key] = {}
                current = current[key]
            current[keys[-1]] = value
    
    return session
