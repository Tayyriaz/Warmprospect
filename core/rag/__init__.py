"""
RAG (Retrieval Augmented Generation) module.
"""

from .retriever import ChatbotRetriever, format_context
from .manager import (
    initialize_default_retriever,
    get_retriever_for_business,
    clear_retriever_cache,
    get_default_retriever,
)
from .builder import build_kb_for_business

__all__ = [
    "ChatbotRetriever",
    "format_context",
    "initialize_default_retriever",
    "get_retriever_for_business",
    "clear_retriever_cache",
    "get_default_retriever",
    "build_kb_for_business",
]
