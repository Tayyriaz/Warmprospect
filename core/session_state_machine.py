"""
Session State Machine
Manages complex conversation flow with state transitions.
"""

from typing import Dict, Any, Optional, List, Callable
from enum import Enum
from datetime import datetime


class ConversationState(Enum):
    """Standard conversation states."""
    INITIAL = "initial"
    GREETING = "greeting"
    COLLECTING_INFO = "collecting_info"
    PROVIDING_INFO = "providing_info"
    QUALIFYING_LEAD = "qualifying_lead"
    BOOKING_APPOINTMENT = "booking_appointment"
    HANDLING_OBJECTION = "handling_objection"
    CLOSING = "closing"
    FOLLOW_UP = "follow_up"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class StateTransition:
    """Represents a state transition with conditions."""
    
    def __init__(
        self,
        from_state: str,
        to_state: str,
        condition: Optional[Callable[[Dict[str, Any]], bool]] = None,
        trigger_keywords: Optional[List[str]] = None
    ):
        self.from_state = from_state
        self.to_state = to_state
        self.condition = condition
        self.trigger_keywords = trigger_keywords or []
    
    def can_transition(self, session: Dict[str, Any], user_input: str = "") -> bool:
        """
        Check if transition can occur based on condition and keywords.
        
        Args:
            session: Current session state
            user_input: User's current message (optional)
        
        Returns:
            True if transition is allowed
        """
        # Check condition function if provided
        if self.condition and not self.condition(session):
            return False
        
        # Check trigger keywords if provided
        if self.trigger_keywords and user_input:
            user_input_lower = user_input.lower()
            if any(keyword.lower() in user_input_lower for keyword in self.trigger_keywords):
                return True
        
        # If no condition or keywords, allow transition
        if not self.condition and not self.trigger_keywords:
            return True
        
        return False


class SessionStateMachine:
    """Manages conversation state machine with transitions."""
    
    def __init__(self):
        self.transitions: List[StateTransition] = []
        self._initialize_default_transitions()
    
    def _initialize_default_transitions(self):
        """Initialize default state transitions."""
        # Initial -> Greeting
        self.add_transition(
            ConversationState.INITIAL.value,
            ConversationState.GREETING.value,
            trigger_keywords=["hi", "hello", "hey", "start"]
        )
        
        # Greeting -> Collecting Info
        self.add_transition(
            ConversationState.GREETING.value,
            ConversationState.COLLECTING_INFO.value,
            trigger_keywords=["tell me", "information", "help", "need"]
        )
        
        # Collecting Info -> Providing Info
        self.add_transition(
            ConversationState.COLLECTING_INFO.value,
            ConversationState.PROVIDING_INFO.value
        )
        
        # Providing Info -> Qualifying Lead
        self.add_transition(
            ConversationState.PROVIDING_INFO.value,
            ConversationState.QUALIFYING_LEAD.value,
            trigger_keywords=["interested", "yes", "sure", "okay"]
        )
        
        # Qualifying Lead -> Booking Appointment
        self.add_transition(
            ConversationState.QUALIFYING_LEAD.value,
            ConversationState.BOOKING_APPOINTMENT.value,
            trigger_keywords=["book", "schedule", "appointment", "call"]
        )
        
        # Any state -> Handling Objection
        self.add_transition(
            "*",
            ConversationState.HANDLING_OBJECTION.value,
            trigger_keywords=["no", "not interested", "too expensive", "maybe later"]
        )
        
        # Booking Appointment -> Closing
        self.add_transition(
            ConversationState.BOOKING_APPOINTMENT.value,
            ConversationState.CLOSING.value
        )
        
        # Closing -> Completed
        self.add_transition(
            ConversationState.CLOSING.value,
            ConversationState.COMPLETED.value
        )
    
    def add_transition(
        self,
        from_state: str,
        to_state: str,
        condition: Optional[Callable[[Dict[str, Any]], bool]] = None,
        trigger_keywords: Optional[List[str]] = None
    ):
        """
        Add a custom state transition.
        
        Args:
            from_state: Source state (use "*" for any state)
            to_state: Target state
            condition: Optional function to check if transition is allowed
            trigger_keywords: Optional list of keywords that trigger transition
        """
        transition = StateTransition(from_state, to_state, condition, trigger_keywords)
        self.transitions.append(transition)
    
    def get_current_state(self, session: Dict[str, Any]) -> str:
        """
        Get current conversation state from session.
        
        Args:
            session: Session dictionary
        
        Returns:
            Current state string
        """
        return session.get("conversation_state", ConversationState.INITIAL.value)
    
    def set_state(self, session: Dict[str, Any], state: str, reason: str = "") -> Dict[str, Any]:
        """
        Set conversation state in session.
        
        Args:
            session: Session dictionary
            state: New state
            reason: Reason for state change
        
        Returns:
            Updated session dictionary
        """
        previous_state = session.get("conversation_state", ConversationState.INITIAL.value)
        
        session["conversation_state"] = state
        session["state_history"] = session.get("state_history", [])
        session["state_history"].append({
            "from_state": previous_state,
            "to_state": state,
            "timestamp": datetime.utcnow().isoformat(),
            "reason": reason
        })
        
        return session
    
    def can_transition(self, session: Dict[str, Any], target_state: str, user_input: str = "") -> bool:
        """
        Check if transition to target state is allowed.
        
        Args:
            session: Current session
            target_state: Target state to transition to
            user_input: User's current message (optional)
        
        Returns:
            True if transition is allowed
        """
        current_state = self.get_current_state(session)
        
        # Check all transitions from current state
        for transition in self.transitions:
            if transition.from_state == current_state or transition.from_state == "*":
                if transition.to_state == target_state:
                    if transition.can_transition(session, user_input):
                        return True
        
        return False
    
    def transition(self, session: Dict[str, Any], target_state: str, user_input: str = "", reason: str = "") -> Dict[str, Any]:
        """
        Attempt to transition to target state.
        
        Args:
            session: Current session
            target_state: Target state to transition to
            user_input: User's current message (optional)
            reason: Reason for transition
        
        Returns:
            Updated session dictionary
        """
        if self.can_transition(session, target_state, user_input):
            return self.set_state(session, target_state, reason)
        else:
            # Log failed transition attempt
            current_state = self.get_current_state(session)
            print(f"[STATE_MACHINE] Cannot transition from {current_state} to {target_state}")
            return session
    
    def auto_transition(self, session: Dict[str, Any], user_input: str = "") -> Dict[str, Any]:
        """
        Automatically determine and apply state transition based on user input.
        
        Args:
            session: Current session
            user_input: User's current message
        
        Returns:
            Updated session dictionary
        """
        current_state = self.get_current_state(session)
        
        # Find matching transitions
        for transition in self.transitions:
            if transition.from_state == current_state or transition.from_state == "*":
                if transition.can_transition(session, user_input):
                    return self.set_state(
                        session,
                        transition.to_state,
                        f"Auto-transition triggered by user input"
                    )
        
        return session
    
    def get_state_history(self, session: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Get state transition history.
        
        Args:
            session: Session dictionary
        
        Returns:
            List of state transitions
        """
        return session.get("state_history", [])


# Global instance
state_machine = SessionStateMachine()
