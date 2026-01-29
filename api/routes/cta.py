"""
CTA (Call-to-Action) API routes.
"""

from fastapi import APIRouter, Request, HTTPException
from slowapi import Limiter
from slowapi.util import get_remote_address
from core.config.business_config import config_manager
from core.cta.cta_tree import get_cta_children, get_cta_by_id
from core.session import get_session, save_session, analytics
from core.integrations.crm import crm_manager

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
        
        # Get the clicked CTA
        cta_node = get_cta_by_id(cta_tree, cta_id)
        if not cta_node:
            raise HTTPException(status_code=404, detail="CTA not found")
        
        action = cta_node.get("action")
        
        # Handle CRM function action
        if action == "crm_function":
            function_name = cta_node.get("function_name")
            if not function_name:
                raise HTTPException(status_code=400, detail="CRM function name not specified in CTA")
            
            # Get function parameters from CTA or request
            function_params = cta_node.get("function_params", {})
            # Allow overriding params from request
            if "function_params" in data:
                function_params.update(data.get("function_params", {}))
            
            # Execute CRM function
            crm_result = crm_manager.execute_crm_function(
                business_id=business_id,
                function_name=function_name,
                **function_params
            )
            
            # Track CTA click
            if session_id:
                session = get_session(session_id)
                session = analytics.track_cta_click(
                    session,
                    cta_id,
                    cta_node.get("label", cta_id)
                )
                save_session(session_id, session)
            
            # Return CRM function result
            return {
                "response": crm_result.get("status", "CRM function executed"),
                "crm_result": crm_result  # Include full result for frontend
            }
        
        # Handle show_children action (default)
        children = get_cta_children(cta_tree, cta_id)
        
        # Track CTA click in analytics
        if session_id:
            session = get_session(session_id)
            session = analytics.track_cta_click(
                session,
                cta_id,
                cta_node.get("label", cta_id)
            )
            save_session(session_id, session)
        
        # Generate appropriate response message
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
