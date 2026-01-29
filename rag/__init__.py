"""
RAG (Retrieval-Augmented Generation) package.
"""

from .retriever import GoAccelRetriever, format_context

__all__ = [
    "GoAccelRetriever",
    "format_context",
]
