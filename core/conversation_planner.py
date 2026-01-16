"""
Multi-turn Conversation Planning
Better handling of complex, multi-step conversations.
"""

from typing import Dict, Any, List, Optional, Tuple, Callable
from enum import Enum


class ConversationGoal(Enum):
    """Types of conversation goals."""
    INFORMATION_GATHERING = "information_gathering"
    LEAD_QUALIFICATION = "lead_qualification"
    APPOINTMENT_BOOKING = "appointment_booking"
    PRODUCT_DEMONSTRATION = "product_demonstration"
    CUSTOMER_SUPPORT = "customer_support"
    SALES_CLOSING = "sales_closing"


class ConversationStep:
    """Represents a step in a multi-turn conversation."""
    
    def __init__(
        self,
        step_id: str,
        goal: str,
        question: str,
        expected_response_type: str = "text",
        required: bool = False,
        validation: Optional[Callable[[Any], bool]] = None
    ):
        self.step_id = step_id
        self.goal = goal
        self.question = question
        self.expected_response_type = expected_response_type
        self.required = required
        self.validation = validation
        self.completed = False
        self.response = None
    
    def complete(self, response: Any) -> bool:
        """
        Mark step as completed with response.
        
        Args:
            response: User's response
        
        Returns:
            True if response is valid
        """
        if self.validation and not self.validation(response):
            return False
        
        self.response = response
        self.completed = True
        return True


class ConversationPlanner:
    """Plans and manages multi-turn conversations."""
    
    def __init__(self):
        self.active_plans: Dict[str, List[ConversationStep]] = {}
    
    def create_plan(
        self,
        session: Dict[str, Any],
        goal: str,
        steps: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Create a conversation plan for a session.
        
        Args:
            session: Session dictionary
            goal: Conversation goal
            steps: List of step definitions
        
        Returns:
            Updated session dictionary
        """
        session_key = session.get("session_key", "default")
        
        conversation_steps = []
        for step_def in steps:
            step = ConversationStep(
                step_id=step_def.get("step_id", f"step_{len(conversation_steps)}"),
                goal=goal,
                question=step_def.get("question", ""),
                expected_response_type=step_def.get("expected_response_type", "text"),
                required=step_def.get("required", False),
                validation=step_def.get("validation")
            )
            conversation_steps.append(step)
        
        self.active_plans[session_key] = conversation_steps
        
        if "conversation_plan" not in session:
            session["conversation_plan"] = {}
        
        session["conversation_plan"] = {
            "goal": goal,
            "steps": [
                {
                    "step_id": step.step_id,
                    "question": step.question,
                    "completed": step.completed,
                    "required": step.required
                }
                for step in conversation_steps
            ],
            "current_step_index": 0,
            "completed": False
        }
        
        return session
    
    def get_current_step(self, session: Dict[str, Any]) -> Optional[ConversationStep]:
        """
        Get the current step in the conversation plan.
        
        Args:
            session: Session dictionary
        
        Returns:
            Current ConversationStep or None
        """
        session_key = session.get("session_key", "default")
        plan = self.active_plans.get(session_key)
        
        if not plan:
            return None
        
        plan_info = session.get("conversation_plan", {})
        current_index = plan_info.get("current_step_index", 0)
        
        if 0 <= current_index < len(plan):
            return plan[current_index]
        
        return None
    
    def advance_step(self, session: Dict[str, Any], response: Any) -> Tuple[Dict[str, Any], Optional[str]]:
        """
        Advance to next step in conversation plan.
        
        Args:
            session: Session dictionary
            response: User's response to current step
        
        Returns:
            Tuple of (updated session, next question or None if plan complete)
        """
        session_key = session.get("session_key", "default")
        plan = self.active_plans.get(session_key)
        
        if not plan:
            return session, None
        
        plan_info = session.get("conversation_plan", {})
        current_index = plan_info.get("current_step_index", 0)
        
        if 0 <= current_index < len(plan):
            current_step = plan[current_index]
            
            # Complete current step
            if current_step.complete(response):
                plan_info["current_step_index"] = current_index + 1
                
                # Check if plan is complete
                if current_index + 1 >= len(plan):
                    plan_info["completed"] = True
                    session["conversation_plan"] = plan_info
                    return session, None
                
                # Get next step
                next_step = plan[current_index + 1]
                session["conversation_plan"] = plan_info
                return session, next_step.question
        
        return session, None
    
    def get_plan_progress(self, session: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get progress of current conversation plan.
        
        Args:
            session: Session dictionary
        
        Returns:
            Dictionary with plan progress information
        """
        plan_info = session.get("conversation_plan", {})
        session_key = session.get("session_key", "default")
        plan = self.active_plans.get(session_key, [])
        
        if not plan_info or not plan:
            return {
                "has_plan": False,
                "progress": 0.0
            }
        
        current_index = plan_info.get("current_step_index", 0)
        total_steps = len(plan)
        progress = (current_index / total_steps) * 100 if total_steps > 0 else 0.0
        
        return {
            "has_plan": True,
            "goal": plan_info.get("goal"),
            "current_step": current_index + 1,
            "total_steps": total_steps,
            "progress": progress,
            "completed": plan_info.get("completed", False)
        }
    
    def create_lead_qualification_plan(self, session: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a standard lead qualification conversation plan.
        
        Args:
            session: Session dictionary
        
        Returns:
            Updated session dictionary
        """
        steps = [
            {
                "step_id": "company_name",
                "question": "What's the name of your company?",
                "required": True
            },
            {
                "step_id": "industry",
                "question": "What industry are you in?",
                "required": True
            },
            {
                "step_id": "company_size",
                "question": "How many employees does your company have?",
                "required": False
            },
            {
                "step_id": "pain_points",
                "question": "What challenges are you currently facing?",
                "required": False
            },
            {
                "step_id": "budget",
                "question": "What's your approximate budget range?",
                "required": False
            }
        ]
        
        return self.create_plan(
            session,
            ConversationGoal.LEAD_QUALIFICATION.value,
            steps
        )
    
    def create_appointment_booking_plan(self, session: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a standard appointment booking conversation plan.
        
        Args:
            session: Session dictionary
        
        Returns:
            Updated session dictionary
        """
        steps = [
            {
                "step_id": "preferred_date",
                "question": "What date works best for you?",
                "required": True
            },
            {
                "step_id": "preferred_time",
                "question": "What time of day do you prefer?",
                "required": True
            },
            {
                "step_id": "contact_method",
                "question": "How would you like us to contact you? (Phone, Email, or Video Call)",
                "required": True
            },
            {
                "step_id": "confirm_details",
                "question": "Please confirm your contact information.",
                "required": True
            }
        ]
        
        return self.create_plan(
            session,
            ConversationGoal.APPOINTMENT_BOOKING.value,
            steps
        )


# Global instance
conversation_planner = ConversationPlanner()
