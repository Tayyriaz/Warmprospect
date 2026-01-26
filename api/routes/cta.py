"""
CTA (Call-to-Action) API routes.
"""

from fastapi import APIRouter, Request, HTTPException
from slowapi import Limiter
from slowapi.util import get_remote_address
from core.config.business_config import config_manager
from core.cta_tree import get_cta_children
from core.session_management import get_session
from core.session_store import save_session
from core.session_analytics import analytics

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


@router.post("/api/chat/cta")
@limiter.limit("30/minute")
async def handle_cta_click(request: Request):
    """
    Handle CTA click - return children CTAs for the clicked CTA.
    Tree-based approach: Frontend sends CTA ID, backend returns children.
    """
    try:
        data = await request.json()
        cta_id = data.get("cta_id")
        business_id = data.get("business_id")
        session_id = data.get("session_id")
        
        if not cta_id:
            raise HTTPException(status_code=400, detail="cta_id is required")
        
        if not business_id:
            raise HTTPException(status_code=400, detail="business_id is required")
        
        # Get business config
        config = config_manager.get_business(business_id)
        if not config:
            raise HTTPException(status_code=404, detail="Business not found")
        
        # Get CTA tree
        cta_tree = config.get("cta_tree", {})
        if not cta_tree or not isinstance(cta_tree, dict):
            raise HTTPException(status_code=400, detail="CTA tree not configured for this business")
        
        # Get children CTAs
        children = get_cta_children(cta_tree, cta_id)
        
        # Track CTA click in analytics
        if session_id:
            session = get_session(session_id)
            cta_node = cta_tree.get(cta_id, {})
            session = analytics.track_cta_click(
                session,
                cta_id,
                cta_node.get("label", cta_id)
            )
            save_session(session_id, session)
        
        # Generate appropriate response message
        cta_node = cta_tree.get(cta_id)
        if cta_node:
            response_text = f"Here are your options for {cta_node.get('label', 'this category')}:"
        else:
            response_text = "Here are your options:"
        
        return {
            "response": response_text,
            "cta": children  # Always separate CTA field, never in response text
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"!!! CTA endpoint error: {str(e)}")
        print(f"!!! Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error handling CTA click: {str(e)}")
