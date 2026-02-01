"""
Integrations Module
External service integrations (CRM, Voice, etc.)
"""

from .crm import crm_manager, CRMManager
from .voice import get_voice_service, get_voice_manager

__all__ = [
    "crm_manager",
    "CRMManager",
    "get_voice_service",
    "get_voice_manager",
]
