"""
Public API routes (no authentication required).
"""

import os
from fastapi import APIRouter
from fastapi.responses import FileResponse
from rag.retriever import format_context
from core.rag_manager import get_default_retriever, get_retriever_for_business
from core.utils.logger import get_logger, IS_PRODUCTION
from core.session_store import REDIS_AVAILABLE

router = APIRouter()
logger = get_logger("public")


@router.get("/")
async def root():
    """Serve the landing/marketing page."""
    return FileResponse("static/landing.html")


@router.get("/bot")
async def bot():
    """Serve the chatbot interface. Requires business_id query parameter."""
    return FileResponse("static/bot.html")


@router.get("/health")
async def health():
    """Detailed health endpoint to verify the system status."""
    retriever = get_default_retriever()
    
    # Check database connection
    db_status = "healthy"
    try:
        from core.database import engine
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        db_status = "unhealthy"
        logger.error(f"Database health check failed: {e}")
    
    health_status = {
        "status": "ok" if db_status == "healthy" else "degraded",
        "message": "WarmProspect Chatbot Platform is running",
        "components": {
            "api": "healthy",
            "database": db_status,
            "redis": "available" if REDIS_AVAILABLE else "unavailable",
            "rag": "loaded" if retriever is not None else "not_loaded",
            "gemini_api": "configured"
        }
    }
    return health_status


@router.get("/rag/status")
async def rag_status():
    """Returns whether the RAG index is loaded."""
    retriever = get_default_retriever()
    return {
        "rag_loaded": retriever is not None,
        "index_path": "data/index.faiss",
        "meta_path": "data/meta.jsonl",
    }


@router.get("/rag/test/{business_id}")
async def test_rag_for_business(business_id: str):
    """Test RAG retrieval for a specific business."""
    test_query = "What is GoAccel?"
    
    try:
        biz_retriever = get_retriever_for_business(business_id)
        if not biz_retriever:
            return {
                "success": False,
                "error": f"No RAG retriever found for business_id={business_id}",
                "index_exists": os.path.exists(os.path.join("data", business_id, "index.faiss")),
                "meta_exists": os.path.exists(os.path.join("data", business_id, "meta.jsonl")),
            }
        
        hits = biz_retriever.search(test_query)
        ctx = format_context(hits)
        
        return {
            "success": True,
            "business_id": business_id,
            "query": test_query,
            "hits_found": len(hits),
            "context_generated": ctx is not None,
            "context_length": len(ctx) if ctx else 0,
            "sample_hits": [
                {
                    "url": h.get("url", "")[:60],
                    "score": round(h.get("score", 0), 4),
                    "text_preview": h.get("text", "")[:100]
                }
                for h in hits[:3]
            ],
            "context_preview": ctx[:300] if ctx else None,
        }
    except Exception as e:
        logger.error(f"RAG test failed for business_id={business_id}: {e}")
        response = {
            "success": False,
            "error": str(e),
        }
        if not IS_PRODUCTION:
            import traceback
            response["traceback"] = traceback.format_exc().split('\n')
        return response