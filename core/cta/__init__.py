"""
CTA (Call-to-Action) Management Module
Handles CTA trees, handlers, and dynamic CTA management.
"""

from .cta_manager import DynamicCTAManager, CTAAction
from .cta_handlers import get_entry_point_ctas, should_attach_ctas
from .cta_tree import detect_intent_from_message

__all__ = [
    "DynamicCTAManager",
    "CTAAction",
    "get_entry_point_ctas",
    "should_attach_ctas",
    "detect_intent_from_message",
]
