"""
RAG (Retrieval-Augmented Generation) Module
Handles knowledge base retrieval and vector search.
"""

from .retriever import GoAccelRetriever, format_context

__all__ = [
    "GoAccelRetriever",
    "format_context",
]
