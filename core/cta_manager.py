"""
Dynamic CTA (Call-to-Action) Management System
Supports multi-level CTAs, context-aware selection, and dynamic generation.
"""

from typing import Dict, Any, List, Optional, Set
from enum import Enum
import json
from core.rules_engine import BusinessRulesEngine, RuleType


class CTALevel(Enum):
    """CTA hierarchy levels."""
    PRIMARY = "primary"
    SECONDARY = "secondary"
    TERTIARY = "tertiary"
    NESTED = "nested"


class CTAAction(Enum):
    """Types of CTA actions."""
    SEND = "send"  # Send a message
    SHOW_NEXT = "show_next"  # Show next level CTAs
    REDIRECT = "redirect"  # Redirect to URL
    FUNCTION = "function"  # Call a function
    CONDITIONAL = "conditional"  # Conditional action based on context


class DynamicCTAManager:
    """
    Manages dynamic, multi-level CTA system with context-aware selection.
    """
    
    def __init__(self, rules_engine: Optional[BusinessRulesEngine] = None):
        self.rules_engine = rules_engine
    
    def get_ctas_for_context(
        self,
        context: Dict[str, Any],
        business_config: Dict[str, Any],
        conversation_history: List[Dict[str, Any]] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get CTAs based on current context and conversation state.
        
        Returns:
            Dictionary with keys: "primary", "secondary", "tertiary", "nested"
            Each containing a list of CTA objects
        """
        conversation_history = conversation_history or []
        
        # Start with configured CTAs
        base_ctas = {
            "primary": business_config.get("primary_ctas", []),
            "secondary": business_config.get("secondary_ctas", []),
            "tertiary": business_config.get("tertiary_ctas", []),
            "nested": business_config.get("nested_ctas", {})
        }
        
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
        
        # Evaluate CTA visibility rules
        if self.rules_engine:
            _, full_context = self.rules_engine.evaluate_rules(
                RuleType.CTA_VISIBILITY,
                full_context
            )
        
        # Filter CTAs based on visibility rules
        filtered_ctas = self._filter_ctas_by_rules(base_ctas, full_context)
        
        # Generate dynamic CTAs if needed
        dynamic_ctas = self._generate_dynamic_ctas(full_context, business_config)
        
        # Merge base and dynamic CTAs
        merged_ctas = self._merge_ctas(filtered_ctas, dynamic_ctas)
        
        # Sort by priority
        for level in merged_ctas:
            merged_ctas[level] = sorted(
                merged_ctas[level],
                key=lambda cta: cta.get("priority", 0),
                reverse=True
            )
        
        return merged_ctas
    
    def _filter_ctas_by_rules(
        self,
        ctas: Dict[str, List[Dict[str, Any]]],
        context: Dict[str, Any]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Filter CTAs based on visibility conditions."""
        filtered = {
            "primary": [],
            "secondary": [],
            "tertiary": [],
            "nested": {}
        }
        
        for level, cta_list in ctas.items():
            if level == "nested":
                # Handle nested CTAs (dictionary structure)
                filtered["nested"] = {}
                for key, nested_ctas in cta_list.items():
                    visible = self._should_show_cta_group(nested_ctas, context)
                    if visible:
                        filtered["nested"][key] = nested_ctas
                continue
            
            for cta in cta_list:
                if self._should_show_cta(cta, context):
                    filtered[level].append(cta)
        
        return filtered
    
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
    
    def _should_show_cta_group(
        self,
        cta_group: List[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> bool:
        """Check if a group of CTAs should be shown."""
        # If any CTA in the group should be shown, show the group
        return any(self._should_show_cta(cta, context) for cta in cta_group)
    
    def _generate_dynamic_ctas(
        self,
        context: Dict[str, Any],
        business_config: Dict[str, Any]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Generate CTAs dynamically based on context.
        
        Examples:
        - Generate CTAs based on detected intent
        - Generate CTAs based on available services/products
        - Generate CTAs based on conversation topic
        """
        dynamic_ctas = {
            "primary": [],
            "secondary": [],
            "tertiary": [],
            "nested": {}
        }
        
        # Detect user intent and generate relevant CTAs
        intent = context.get("conversation", {}).get("intent")
        topic = context.get("conversation", {}).get("topic")
        
        # Generate based on intent
        if intent == "pricing_inquiry":
            dynamic_ctas["primary"].append({
                "label": "Get Pricing Information",
                "action": "send",
                "message": "I'd like to know more about pricing",
                "priority": 5
            })
        
        elif intent == "service_inquiry":
            # Generate CTAs for available services
            services = business_config.get("available_services", [])
            for service in services[:3]:  # Limit to 3
                dynamic_ctas["secondary"].append({
                    "label": f"Learn About {service.get('name', 'Service')}",
                    "action": "send",
                    "message": f"Tell me about {service.get('name', 'this service')}",
                    "priority": service.get("priority", 0)
                })
        
        elif intent == "booking_inquiry":
            dynamic_ctas["primary"].append({
                "label": "Book Now",
                "action": "send",
                "message": "I'd like to book an appointment",
                "priority": 10
            })
        
        # Generate based on conversation topic
        if topic:
            topic_ctas = business_config.get("topic_ctas", {}).get(topic, [])
            dynamic_ctas["secondary"].extend(topic_ctas)
        
        # Use rules engine to generate CTAs
        if self.rules_engine:
            actions, _ = self.rules_engine.evaluate_rules(
                RuleType.CTA_GENERATION,
                context
            )
            
            for action in actions:
                if action.get("type") == "add_cta":
                    level = action.get("level", "secondary")
                    cta = action.get("cta", {})
                    if level in dynamic_ctas:
                        dynamic_ctas[level].append(cta)
        
        return dynamic_ctas
    
    def _merge_ctas(
        self,
        base_ctas: Dict[str, List[Dict[str, Any]]],
        dynamic_ctas: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Merge base and dynamic CTAs, avoiding duplicates."""
        merged = {
            "primary": base_ctas["primary"].copy(),
            "secondary": base_ctas["secondary"].copy(),
            "tertiary": base_ctas["tertiary"].copy(),
            "nested": base_ctas["nested"].copy()
        }
        
        # Add dynamic CTAs that don't duplicate existing ones
        seen_labels = {cta.get("label") for level in merged.values() 
                      for cta in (level if isinstance(level, list) else [])}
        
        for level, ctas in dynamic_ctas.items():
            if level == "nested":
                merged["nested"].update(ctas)
            else:
                for cta in ctas:
                    if cta.get("label") not in seen_labels:
                        merged[level].append(cta)
                        seen_labels.add(cta.get("label"))
        
        return merged
    
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
