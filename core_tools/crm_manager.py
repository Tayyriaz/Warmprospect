"""
CRM Manager - Per-Tenant CRM Function Handler
Supports different CRM implementations per business/tenant.
CRM functions are called from CTAs with action="crm_function".
"""

import os
import importlib
import importlib.util
import sys
from typing import Dict, Any, Optional, List, Callable
from pathlib import Path


class CRMManager:
    """
    Manages per-tenant CRM function implementations.
    
    Architecture:
    - Each tenant can have their own CRM function file: core_tools/crm_{business_id}.py
    - CRM functions are called from CTAs with action="crm_function" and function_name specified
    - Default CRM functions are in core_tools/crm_functions.py (fallback)
    """
    
    def __init__(self):
        self._crm_cache: Dict[str, Any] = {}  # Cache loaded CRM modules per business_id
    
    def get_crm_tools(self, business_id: Optional[str]) -> Any:
        """
        Get CRM tools instance for a specific business.
        
        Args:
            business_id: Business identifier (e.g., "goaccel-website")
        
        Returns:
            CRM tools instance (class with CRM methods)
        """
        if not business_id:
            # Return default CRM tools
            from core_tools.crm_functions import CRMTools
            return CRMTools()
        
        # Check cache first
        if business_id in self._crm_cache:
            return self._crm_cache[business_id]
        
        # Try to load business-specific CRM module
        crm_module_name = f"crm_{business_id}"
        crm_file_path = Path(__file__).parent / f"crm_{business_id}.py"
        
        if crm_file_path.exists():
            try:
                # Import business-specific CRM module
                spec = importlib.util.spec_from_file_location(crm_module_name, crm_file_path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[crm_module_name] = module
                    spec.loader.exec_module(module)
                    
                    # Get CRM class from module (defaults to CRMTools if not specified)
                    crm_class = getattr(module, "CRMTools", None)
                    if crm_class:
                        crm_instance = crm_class()
                        self._crm_cache[business_id] = crm_instance
                        print(f"[CRM] Loaded business-specific CRM for {business_id}")
                        return crm_instance
            except Exception as e:
                print(f"[WARNING] Failed to load CRM module for {business_id}: {e}")
                import traceback
                traceback.print_exc()
        
        # Fallback to default CRM tools
        from core_tools.crm_functions import CRMTools
        default_tools = CRMTools()
        self._crm_cache[business_id] = default_tools
        return default_tools
    
    def execute_crm_function(
        self,
        business_id: Optional[str],
        function_name: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute a CRM function for a specific business.
        
        Args:
            business_id: Business identifier
            function_name: Name of CRM function to call (e.g., "search_contact", "create_new_contact")
            **kwargs: Arguments to pass to the CRM function
        
        Returns:
            Result dictionary from CRM function
        """
        crm_tools = self.get_crm_tools(business_id)
        
        if not hasattr(crm_tools, function_name):
            return {
                "error": f"CRM function '{function_name}' not found for business '{business_id}'",
                "status": "Function not available"
            }
        
        try:
            func = getattr(crm_tools, function_name)
            result = func(**kwargs)
            return result
        except Exception as e:
            print(f"[ERROR] CRM function '{function_name}' failed for {business_id}: {e}")
            import traceback
            traceback.print_exc()
            return {
                "error": str(e),
                "status": "Error executing CRM function"
            }


# Global instance
crm_manager = CRMManager()
