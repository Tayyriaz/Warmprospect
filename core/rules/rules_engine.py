"""
Business Rules Engine for Dynamic Configuration
Supports conditional logic, context-aware routing, and dynamic CTA generation.
"""

from typing import Dict, Any, List, Optional, Callable
from enum import Enum
import json
import re


class RuleType(Enum):
    """Types of rules that can be defined."""
    CTA_VISIBILITY = "cta_visibility"
    CTA_GENERATION = "cta_generation"
    ROUTING = "routing"
    RESPONSE_MODIFICATION = "response_modification"
    FIELD_COLLECTION = "field_collection"


class ConditionOperator(Enum):
    """Operators for condition evaluation."""
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    IN = "in"
    NOT_IN = "not_in"
    MATCHES = "matches"  # regex
    EXISTS = "exists"
    NOT_EXISTS = "not_exists"


class BusinessRulesEngine:
    """
    Pluggable rule system for conditional logic in conversation flow.
    Supports multi-level rules, context-aware decisions, and dynamic CTA generation.
    """
    
    def __init__(self, rules: Optional[List[Dict[str, Any]]] = None):
        """
        Initialize the rules engine.
        
        Args:
            rules: List of rule dictionaries. Each rule should have:
                - type: RuleType value
                - name: Unique rule identifier
                - conditions: List of condition dictionaries
                - actions: List of action dictionaries
                - priority: Integer (higher = evaluated first, default: 0)
        """
        self.rules: List[Dict[str, Any]] = rules or []
        self._validate_rules()
    
    def _validate_rules(self):
        """Validate rule structure."""
        for rule in self.rules:
            if "type" not in rule or "name" not in rule:
                raise ValueError(f"Rule must have 'type' and 'name': {rule}")
            if "conditions" not in rule:
                rule["conditions"] = []
            if "actions" not in rule:
                rule["actions"] = []
            if "priority" not in rule:
                rule["priority"] = 0
    
    def add_rule(self, rule: Dict[str, Any]):
        """Add a new rule to the engine."""
        if "type" not in rule or "name" not in rule:
            raise ValueError("Rule must have 'type' and 'name'")
        if "conditions" not in rule:
            rule["conditions"] = []
        if "actions" not in rule:
            rule["actions"] = []
        if "priority" not in rule:
            rule["priority"] = 0
        
        self.rules.append(rule)
        self.rules.sort(key=lambda r: r.get("priority", 0), reverse=True)
    
    def evaluate_condition(self, condition: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """
        Evaluate a single condition against the context.
        
        Condition format:
        {
            "field": "session.current_route",  # Path to field in context
            "operator": "equals",
            "value": "appointments"
        }
        """
        field_path = condition.get("field", "")
        operator_str = condition.get("operator", "equals")
        expected_value = condition.get("value")
        
        # Get field value from context using dot notation
        field_value = self._get_nested_value(context, field_path)
        
        # Map string operator to enum
        try:
            operator = ConditionOperator(operator_str)
        except ValueError:
            operator = ConditionOperator.EQUALS
        
        # Evaluate based on operator
        if operator == ConditionOperator.EQUALS:
            return field_value == expected_value
        elif operator == ConditionOperator.NOT_EQUALS:
            return field_value != expected_value
        elif operator == ConditionOperator.CONTAINS:
            if isinstance(field_value, str) and isinstance(expected_value, str):
                return expected_value.lower() in field_value.lower()
            return False
        elif operator == ConditionOperator.NOT_CONTAINS:
            if isinstance(field_value, str) and isinstance(expected_value, str):
                return expected_value.lower() not in field_value.lower()
            return True
        elif operator == ConditionOperator.GREATER_THAN:
            try:
                return float(field_value) > float(expected_value)
            except (ValueError, TypeError):
                return False
        elif operator == ConditionOperator.LESS_THAN:
            try:
                return float(field_value) < float(expected_value)
            except (ValueError, TypeError):
                return False
        elif operator == ConditionOperator.IN:
            if isinstance(expected_value, list):
                return field_value in expected_value
            return False
        elif operator == ConditionOperator.NOT_IN:
            if isinstance(expected_value, list):
                return field_value not in expected_value
            return True
        elif operator == ConditionOperator.MATCHES:
            if isinstance(field_value, str) and isinstance(expected_value, str):
                try:
                    return bool(re.search(expected_value, field_value, re.IGNORECASE))
                except re.error:
                    return False
            return False
        elif operator == ConditionOperator.EXISTS:
            return field_value is not None
        elif operator == ConditionOperator.NOT_EXISTS:
            return field_value is None
        
        return False
    
    def evaluate_conditions(self, conditions: List[Dict[str, Any]], context: Dict[str, Any], 
                           logic: str = "AND") -> bool:
        """
        Evaluate multiple conditions with AND/OR logic.
        
        Args:
            conditions: List of condition dictionaries
            context: Current conversation context
            logic: "AND" or "OR" (default: "AND")
        """
        if not conditions:
            return True  # No conditions = always true
        
        results = [self.evaluate_condition(cond, context) for cond in conditions]
        
        if logic.upper() == "OR":
            return any(results)
        else:  # AND
            return all(results)
    
    def execute_actions(self, actions: List[Dict[str, Any]], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute actions and return modified context.
        
        Action format:
        {
            "type": "set_field",
            "field": "session.current_route",
            "value": "appointments"
        }
        """
        modified_context = context.copy()
        
        for action in actions:
            action_type = action.get("type", "")
            
            if action_type == "set_field":
                field_path = action.get("field", "")
                value = action.get("value")
                self._set_nested_value(modified_context, field_path, value)
            
            elif action_type == "append_to_field":
                field_path = action.get("field", "")
                value = action.get("value")
                current = self._get_nested_value(modified_context, field_path)
                if isinstance(current, list):
                    current.append(value)
                else:
                    self._set_nested_value(modified_context, field_path, [value])
            
            elif action_type == "increment_field":
                field_path = action.get("field", "")
                increment = action.get("value", 1)
                current = self._get_nested_value(modified_context, field_path, 0)
                self._set_nested_value(modified_context, field_path, current + increment)
            
            elif action_type == "log_event":
                # Log events for analytics
                event_name = action.get("event_name", "")
                event_data = action.get("data", {})
                if "events" not in modified_context:
                    modified_context["events"] = []
                modified_context["events"].append({
                    "name": event_name,
                    "data": event_data,
                    "timestamp": __import__("time").time()
                })
        
        return modified_context
    
    def evaluate_rules(self, rule_type: RuleType, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Evaluate all rules of a specific type and return matching actions.
        
        Returns:
            List of actions from rules that matched
        """
        matching_actions = []
        
        # Filter rules by type and evaluate
        for rule in self.rules:
            try:
                rule_type_enum = RuleType(rule["type"])
            except ValueError:
                continue
            
            if rule_type_enum != rule_type:
                continue
            
            # Evaluate conditions
            conditions = rule.get("conditions", [])
            logic = rule.get("logic", "AND")
            
            if self.evaluate_conditions(conditions, context, logic):
                # Execute actions and collect results
                actions = rule.get("actions", [])
                context = self.execute_actions(actions, context)
                matching_actions.extend(actions)
        
        return matching_actions, context
    
    def _get_nested_value(self, data: Dict[str, Any], path: str, default: Any = None) -> Any:
        """Get nested value from dictionary using dot notation."""
        keys = path.split(".")
        current = data
        
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
            else:
                return default
            
            if current is None:
                return default
        
        return current
    
    def _set_nested_value(self, data: Dict[str, Any], path: str, value: Any):
        """Set nested value in dictionary using dot notation."""
        keys = path.split(".")
        current = data
        
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        current[keys[-1]] = value


def load_rules_from_config(business_config: Dict[str, Any]) -> BusinessRulesEngine:
    """
    Load rules from business configuration.
    
    Expected format in business_config:
    {
        "rules": [
            {
                "type": "cta_visibility",
                "name": "show_appointment_cta",
                "priority": 10,
                "logic": "AND",
                "conditions": [
                    {
                        "field": "session.current_route",
                        "operator": "equals",
                        "value": "intro"
                    }
                ],
                "actions": [
                    {
                        "type": "set_field",
                        "field": "ctas.visible",
                        "value": ["appointment"]
                    }
                ]
            }
        ]
    }
    """
    rules_data = business_config.get("rules", [])
    return BusinessRulesEngine(rules=rules_data)
