"""
CRM tools package - provides CRM function implementations.
"""

from .crm_functions import CRMTools
from .crm_manager import crm_manager, CRMManager

__all__ = [
    "CRMTools",
    "crm_manager",
    "CRMManager",
]
