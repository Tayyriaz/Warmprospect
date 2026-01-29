"""
CRM Tools Package
Provides CRM function implementations and per-tenant CRM management.
"""

from .crm_functions import CRMTools
from .crm_manager import crm_manager, CRMManager

__all__ = [
    "CRMTools",
    "crm_manager",
    "CRMManager",
]
