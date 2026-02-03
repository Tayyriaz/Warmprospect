"""
CRM Tools Package
Per-tenant CRM management. Each business defines CRMTools in businesses/<id>/crm.py.
"""

from .crm_manager import crm_manager, CRMManager

__all__ = [
    "crm_manager",
    "CRMManager",
]
