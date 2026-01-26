"""
RAG (Retrieval Augmented Generation) retriever management.
"""

import os
from typing import Dict, Any, Optional
from rag.retriever import GoAccelRetriever

# Optional RAG retriever(s)
# NOTE: In multi-tenant mode, each business should have its own index under:
#   data/{business_id}/index.faiss and data/{business_id}/meta.jsonl
# The legacy default index (data/index.faiss) is only used when business_id is not provided.
retriever: Optional[GoAccelRetriever] = None
_retriever_cache: Dict[str, GoAccelRetriever] = {}


def initialize_default_retriever() -> Optional[GoAccelRetriever]:
    """Initialize the default RAG retriever."""
    global retriever
    try:
        retriever = GoAccelRetriever(
            api_key=os.getenv("GEMINI_API_KEY", ""),
            index_path="data/index.faiss",
            meta_path="data/meta.jsonl",
            model="text-embedding-004",
            top_k=5,
        )
        print("Default RAG retriever loaded (data/index.faiss).")
        return retriever
    except Exception as e:
        print(f"Default RAG retriever not loaded: {e}")
        return None


def get_retriever_for_business(business_id: Optional[str]) -> Optional[GoAccelRetriever]:
    """
    Returns a retriever for the given business_id if a business-specific index exists.
    - If business_id is None -> returns the default retriever (if loaded)
    - If business_id is set -> returns a cached business retriever only if its index exists
    """
    global retriever, _retriever_cache
    
    if not business_id:
        return retriever

    if business_id in _retriever_cache:
        print(f"[RAG] Using cached retriever for business_id={business_id}")
        return _retriever_cache[business_id]

    index_path = os.path.join("data", business_id, "index.faiss")
    meta_path = os.path.join("data", business_id, "meta.jsonl")
    
    print(f"[RAG] Checking for business KB: business_id={business_id}")
    print(f"[RAG] Index path: {index_path} (exists: {os.path.exists(index_path)})")
    print(f"[RAG] Meta path: {meta_path} (exists: {os.path.exists(meta_path)})")
    
    if not (os.path.exists(index_path) and os.path.exists(meta_path)):
        # No business KB yet -> disable RAG for this business to avoid cross-tenant contamination
        print(f"[RAG] No KB found for business_id={business_id}, RAG disabled")
        return None

    try:
        print(f"[RAG] Loading retriever for business_id={business_id}...")
        biz_ret = GoAccelRetriever(
            api_key=os.getenv("GEMINI_API_KEY", ""),
            index_path=index_path,
            meta_path=meta_path,
            model="text-embedding-004",
            top_k=5,
        )
        _retriever_cache[business_id] = biz_ret
        print(f"✅ Business RAG retriever loaded for business_id={business_id}.")
        return biz_ret
    except Exception as e:
        print(f"[ERROR] Could not load business RAG for {business_id}: {e}")
        import traceback
        traceback.print_exc()
        return None


def get_default_retriever() -> Optional[GoAccelRetriever]:
    """Get the default retriever."""
    return retriever
