"""
A/B Testing Framework for Dynamic Configuration
Supports experimentation and testing different configurations.
"""

from typing import Dict, Any, List, Optional
from enum import Enum
import hashlib
import json
import time


class ExperimentStatus(Enum):
    """Status of an A/B test experiment."""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class ABTestingFramework:
    """
    A/B Testing framework for testing different chatbot configurations.
    Supports user segmentation, variant allocation, and metrics tracking.
    """
    
    def __init__(self, experiments: Optional[List[Dict[str, Any]]] = None):
        """
        Initialize A/B testing framework.
        
        Args:
            experiments: List of experiment configurations
        """
        self.experiments: Dict[str, Dict[str, Any]] = {}
        if experiments:
            for exp in experiments:
                self.add_experiment(exp)
    
    def add_experiment(self, experiment: Dict[str, Any]):
        """Add or update an experiment."""
        exp_id = experiment.get("experiment_id")
        if not exp_id:
            raise ValueError("Experiment must have 'experiment_id'")
        
        # Validate experiment structure
        required_fields = ["name", "variants", "allocation"]
        for field in required_fields:
            if field not in experiment:
                raise ValueError(f"Experiment must have '{field}' field")
        
        # Set default values
        experiment.setdefault("status", ExperimentStatus.DRAFT.value)
        experiment.setdefault("start_date", None)
        experiment.setdefault("end_date", None)
        experiment.setdefault("metrics", {})
        
        self.experiments[exp_id] = experiment
    
    def get_variant_for_user(
        self,
        experiment_id: str,
        user_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Get the variant assignment for a user in an experiment.
        Uses consistent hashing to ensure same user gets same variant.
        
        Args:
            experiment_id: ID of the experiment
            user_id: Unique user identifier
            context: Additional context for segmentation
        
        Returns:
            Variant name or None if user not in experiment
        """
        if experiment_id not in self.experiments:
            return None
        
        experiment = self.experiments[experiment_id]
        
        # Check if experiment is active
        if experiment.get("status") != ExperimentStatus.ACTIVE.value:
            return None
        
        # Check date range
        start_date = experiment.get("start_date")
        end_date = experiment.get("end_date")
        current_time = time.time()
        
        if start_date and current_time < start_date:
            return None
        if end_date and current_time > end_date:
            return None
        
        # Check user segmentation
        if not self._user_matches_segments(user_id, experiment.get("segments", []), context):
            return None
        
        # Consistent variant assignment using hash
        variant = self._assign_variant(experiment_id, user_id, experiment.get("variants", []))
        
        return variant
    
    def _assign_variant(
        self,
        experiment_id: str,
        user_id: str,
        variants: List[Dict[str, Any]]
    ) -> str:
        """
        Assign a variant to a user using consistent hashing.
        Ensures same user always gets same variant.
        """
        if not variants:
            return "control"
        
        # Create hash from experiment_id + user_id
        hash_input = f"{experiment_id}:{user_id}"
        hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
        
        # Calculate cumulative weights
        total_weight = sum(v.get("weight", 1) for v in variants)
        random_value = hash_value % total_weight
        
        # Assign based on weights
        cumulative = 0
        for variant in variants:
            cumulative += variant.get("weight", 1)
            if random_value < cumulative:
                return variant.get("name", "control")
        
        # Fallback to first variant
        return variants[0].get("name", "control")
    
    def _user_matches_segments(
        self,
        user_id: str,
        segments: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]]
    ) -> bool:
        """
        Check if user matches experiment segments.
        
        Segment format:
        {
            "type": "user_property",
            "field": "session.first_name",
            "operator": "exists"
        }
        """
        if not segments:
            return True  # No segments = all users
        
        context = context or {}
        
        for segment in segments:
            segment_type = segment.get("type", "")
            field = segment.get("field", "")
            operator = segment.get("operator", "exists")
            value = segment.get("value")
            
            if segment_type == "user_property":
                field_value = self._get_nested_value(context, field)
                if not self._evaluate_segment_condition(field_value, operator, value):
                    return False
            
            elif segment_type == "random":
                # Random segmentation (e.g., 50% of users)
                percentage = segment.get("percentage", 50)
                hash_value = int(hashlib.md5(f"{user_id}:{segment.get('seed', '')}".encode()).hexdigest(), 16)
                if (hash_value % 100) >= percentage:
                    return False
        
        return True
    
    def _evaluate_segment_condition(self, field_value: Any, operator: str, expected_value: Any) -> bool:
        """Evaluate a segment condition."""
        if operator == "exists":
            return field_value is not None
        elif operator == "not_exists":
            return field_value is None
        elif operator == "equals":
            return field_value == expected_value
        elif operator == "contains":
            if isinstance(field_value, str) and isinstance(expected_value, str):
                return expected_value.lower() in field_value.lower()
            return False
        
        return True
    
    def get_experiment_config(
        self,
        experiment_id: str,
        variant: str
    ) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific experiment variant."""
        if experiment_id not in self.experiments:
            return None
        
        experiment = self.experiments[experiment_id]
        variants = experiment.get("variants", [])
        
        for v in variants:
            if v.get("name") == variant:
                return v.get("config", {})
        
        return None
    
    def track_event(
        self,
        experiment_id: str,
        variant: str,
        event_name: str,
        event_data: Optional[Dict[str, Any]] = None
    ):
        """Track an event for A/B testing metrics."""
        if experiment_id not in self.experiments:
            return
        
        if "metrics" not in self.experiments[experiment_id]:
            self.experiments[experiment_id]["metrics"] = {}
        
        if variant not in self.experiments[experiment_id]["metrics"]:
            self.experiments[experiment_id]["metrics"][variant] = {}
        
        if event_name not in self.experiments[experiment_id]["metrics"][variant]:
            self.experiments[experiment_id]["metrics"][variant][event_name] = {
                "count": 0,
                "events": []
            }
        
        metrics = self.experiments[experiment_id]["metrics"][variant][event_name]
        metrics["count"] += 1
        metrics["events"].append({
            "timestamp": time.time(),
            "data": event_data or {}
        })
    
    def get_experiment_results(self, experiment_id: str) -> Optional[Dict[str, Any]]:
        """Get results/metrics for an experiment."""
        if experiment_id not in self.experiments:
            return None
        
        experiment = self.experiments[experiment_id]
        return {
            "experiment_id": experiment_id,
            "name": experiment.get("name"),
            "status": experiment.get("status"),
            "metrics": experiment.get("metrics", {}),
            "variants": experiment.get("variants", [])
        }
    
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


# Global instance
_ab_testing_instance = None


def get_ab_testing_framework() -> ABTestingFramework:
    """Get global A/B testing framework instance."""
    global _ab_testing_instance
    if _ab_testing_instance is None:
        _ab_testing_instance = ABTestingFramework()
    return _ab_testing_instance
