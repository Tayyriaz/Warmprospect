"""
Analytics API routes.
"""

from fastapi import APIRouter, Request, HTTPException
from slowapi import Limiter
from slowapi.util import get_remote_address
from core.session_management import get_session
from core.session_analytics import analytics
from core.conversation_planner import conversation_planner
from core.session_state_machine import state_machine

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


@router.get("/api/analytics/session/{session_id}")
@limiter.limit("30/minute")
async def get_session_analytics(request: Request, session_id: str):
    """
    Get analytics metrics for a specific session.
    """
    try:
        session = get_session(session_id)
        metrics = analytics.get_session_metrics(session)
        plan_progress = conversation_planner.get_plan_progress(session)
        
        return {
            "session_id": session_id,
            "metrics": metrics,
            "conversation_plan": plan_progress,
            "current_state": state_machine.get_current_state(session),
            "intent": session.get("detected_intent"),
            "sentiment": session.get("sentiment")
        }
    except Exception as e:
        import traceback
        print(f"!!! Analytics endpoint error: {str(e)}")
        print(f"!!! Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error getting analytics: {str(e)}")


@router.get("/api/analytics/business/{business_id}")
@limiter.limit("30/minute")
async def get_business_analytics(request: Request, business_id: str, hours: int = 24):
    """
    Get aggregated analytics for a business.
    """
    try:
        aggregated = analytics.get_aggregated_metrics(business_id=business_id, time_range_hours=hours)
        return {
            "business_id": business_id,
            "time_range_hours": hours,
            **aggregated
        }
    except Exception as e:
        import traceback
        print(f"!!! Business analytics endpoint error: {str(e)}")
        print(f"!!! Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error getting business analytics: {str(e)}")
