"""
Session Analytics
Tracking and analytics for session data.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict


class SessionAnalytics:
    """Tracks analytics and metrics for sessions."""
    
    def __init__(self):
        self.metrics = defaultdict(lambda: defaultdict(int))
        self.session_events: List[Dict[str, Any]] = []
    
    def track_event(
        self,
        session: Dict[str, Any],
        event_type: str,
        event_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Track an event in the session.
        
        Args:
            session: Session dictionary
            event_type: Type of event (e.g., "message_sent", "cta_clicked", "state_changed")
            event_data: Additional event data
        
        Returns:
            Updated session dictionary
        """
        if "analytics" not in session:
            session["analytics"] = {
                "events": [],
                "metrics": {},
                "start_time": datetime.utcnow().isoformat()
            }
        
        event = {
            "type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": event_data or {}
        }
        
        session["analytics"]["events"].append(event)
        session["analytics"]["last_event_time"] = datetime.utcnow().isoformat()
        
        # Update metrics
        if "metrics" not in session["analytics"]:
            session["analytics"]["metrics"] = {}
        
        session["analytics"]["metrics"][f"{event_type}_count"] = \
            session["analytics"]["metrics"].get(f"{event_type}_count", 0) + 1
        
        # Store event globally for aggregation
        self.session_events.append({
            "session_key": session.get("session_key", "unknown"),
            "business_id": session.get("business_id"),
            **event
        })
        
        return session
    
    def track_message(self, session: Dict[str, Any], message_type: str = "user") -> Dict[str, Any]:
        """
        Track a message event.
        
        Args:
            session: Session dictionary
            message_type: Type of message ("user" or "assistant")
        
        Returns:
            Updated session dictionary
        """
        return self.track_event(
            session,
            f"{message_type}_message",
            {"message_type": message_type}
        )
    
    def track_cta_click(self, session: Dict[str, Any], cta_id: str, cta_label: str) -> Dict[str, Any]:
        """
        Track a CTA click event.
        
        Args:
            session: Session dictionary
            cta_id: ID of the clicked CTA
            cta_label: Label of the clicked CTA
        
        Returns:
            Updated session dictionary
        """
        return self.track_event(
            session,
            "cta_clicked",
            {"cta_id": cta_id, "cta_label": cta_label}
        )
    
    def track_state_change(self, session: Dict[str, Any], from_state: str, to_state: str) -> Dict[str, Any]:
        """
        Track a state change event.
        
        Args:
            session: Session dictionary
            from_state: Previous state
            to_state: New state
        
        Returns:
            Updated session dictionary
        """
        return self.track_event(
            session,
            "state_changed",
            {"from_state": from_state, "to_state": to_state}
        )
    
    def get_session_metrics(self, session: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get analytics metrics for a session.
        
        Args:
            session: Session dictionary
        
        Returns:
            Dictionary of metrics
        """
        analytics = session.get("analytics", {})
        metrics = analytics.get("metrics", {})
        
        # Calculate derived metrics
        events = analytics.get("events", [])
        user_messages = len([e for e in events if e.get("type") == "user_message"])
        assistant_messages = len([e for e in events if e.get("type") == "assistant_message"])
        cta_clicks = len([e for e in events if e.get("type") == "cta_clicked"])
        
        start_time = analytics.get("start_time")
        last_event_time = analytics.get("last_event_time")
        duration_seconds = 0
        if start_time and last_event_time:
            try:
                start = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                end = datetime.fromisoformat(last_event_time.replace("Z", "+00:00"))
                duration_seconds = int((end - start).total_seconds())
            except Exception:
                pass
        
        return {
            **metrics,
            "total_events": len(events),
            "user_messages": user_messages,
            "assistant_messages": assistant_messages,
            "cta_clicks": cta_clicks,
            "session_duration_seconds": duration_seconds,
            "start_time": start_time,
            "last_event_time": last_event_time
        }
    
    def get_events(self, session: Dict[str, Any], event_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get events from session, optionally filtered by type.
        
        Args:
            session: Session dictionary
            event_type: Optional event type filter
        
        Returns:
            List of events
        """
        events = session.get("analytics", {}).get("events", [])
        
        if event_type:
            return [e for e in events if e.get("type") == event_type]
        
        return events
    
    def get_aggregated_metrics(
        self,
        business_id: Optional[str] = None,
        time_range_hours: int = 24
    ) -> Dict[str, Any]:
        """
        Get aggregated metrics across all sessions.
        
        Args:
            business_id: Optional business ID to filter by
            time_range_hours: Time range in hours to include
        
        Returns:
            Dictionary of aggregated metrics
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=time_range_hours)
        
        filtered_events = []
        for event in self.session_events:
            try:
                event_time = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
                if event_time >= cutoff_time:
                    if not business_id or event.get("business_id") == business_id:
                        filtered_events.append(event)
            except Exception:
                continue
        
        # Aggregate metrics
        event_counts = defaultdict(int)
        cta_clicks = defaultdict(int)
        unique_sessions = set()
        
        for event in filtered_events:
            event_counts[event["type"]] += 1
            unique_sessions.add(event.get("session_key", "unknown"))
            
            if event["type"] == "cta_clicked":
                cta_id = event.get("data", {}).get("cta_id", "unknown")
                cta_clicks[cta_id] += 1
        
        return {
            "total_events": len(filtered_events),
            "unique_sessions": len(unique_sessions),
            "event_counts": dict(event_counts),
            "cta_clicks": dict(cta_clicks),
            "time_range_hours": time_range_hours
        }


# Global instance
analytics = SessionAnalytics()
