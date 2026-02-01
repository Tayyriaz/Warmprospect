"""
CRM: only available if a business has businesses/<business_id>/crm.py.

No defaults. If a business has no crm.py, CRM functions are not available.
"""

import importlib.util
import sys
from typing import Dict, Any, Optional
from pathlib import Path


def _load_business_crm(project_root: Path, business_id: str):
    """Load CRMTools from businesses/<business_id>/crm.py if it exists."""
    path = project_root / "businesses" / business_id / "crm.py"
    if not path.exists():
        return None
    name = f"crm_{business_id}".replace("-", "_")
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        if not spec or not spec.loader:
            return None
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
        cls = getattr(mod, "CRMTools", None)
        return cls(business_id=business_id) if cls else None
    except Exception as e:
        print(f"[CRM] Failed to load businesses/{business_id}/crm.py: {e}")
        return None


class CRMManager:
    """Resolves CRM for a business: businesses/<id>/crm.py if present, else None (no CRM)."""

    def __init__(self):
        self._cache: Dict[str, Optional[Any]] = {}

    def get_crm_tools(self, business_id: Optional[str]):
        """Get CRM for this business, or None if no businesses/<id>/crm.py exists."""
        if not business_id:
            return None
        if business_id in self._cache:
            return self._cache[business_id]
        root = Path(__file__).resolve().parent.parent.parent
        instance = _load_business_crm(root, business_id)
        self._cache[business_id] = instance
        return instance

    def execute_crm_function(
        self, business_id: Optional[str], function_name: str, **kwargs
    ) -> Dict[str, Any]:
        """Run a CRM function. Returns error if business has no CRM or function doesn't exist."""
        tools = self.get_crm_tools(business_id)
        if tools is None:
            return {"error": f"CRM not available for business '{business_id}'", "status": "CRM not configured"}
        if not hasattr(tools, function_name):
            return {"error": f"CRM function '{function_name}' not found", "status": "Function not available"}
        try:
            return getattr(tools, function_name)(**kwargs)
        except Exception as e:
            print(f"[CRM] {function_name} failed: {e}")
            return {"error": str(e), "status": "Error executing CRM function"}


crm_manager = CRMManager()
