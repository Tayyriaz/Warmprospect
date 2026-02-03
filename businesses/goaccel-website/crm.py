"""
GoAccel CRM: one example of wiring search_contact / create_new_contact / create_deal.

This business uses a REST API with Bearer token (env). Other businesses can do
OAuth, webhooks, SDKs, or no integration—each crm.py owns its own auth and wiring.
"""

import os
import requests

# This business: API base + key from env
API_BASE = os.getenv("GOACCEL_CRM_API_BASE", "https://api.example.com/crm").rstrip("/")
API_KEY = os.getenv("GOACCEL_CRM_API_KEY", "")


class CRMTools:
    """GoAccel: REST API with Bearer auth. Other businesses can use any auth/integration."""

    def __init__(self, business_id=None):
        self.business_id = business_id

    def _headers(self):
        return {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

    def search_contact(self, email=None, phone_number=None):
        if not email and not phone_number:
            return {"found": False, "status": "Email or phone required."}
        try:
            r = requests.post(
                f"{API_BASE}/contact/search",
                json={"email": email, "phone_number": phone_number},
                headers=self._headers(),
                timeout=10,
            )
            r.raise_for_status()
            data = r.json()
            return {
                "found": data.get("found", False),
                "contact_id": data.get("contact_id"),
                "status": data.get("status", "OK"),
            }
        except requests.RequestException as e:
            return {"found": False, "status": str(e)}

    def create_new_contact(self, first_name, email, phone_number=None):
        try:
            r = requests.post(
                f"{API_BASE}/contact/create",
                json={"first_name": first_name, "email": email, "phone_number": phone_number},
                headers=self._headers(),
                timeout=10,
            )
            r.raise_for_status()
            data = r.json()
            return {
                "created": True,
                "contact_id": data.get("contact_id"),
                "status": data.get("status", "Contact successfully created."),
            }
        except requests.RequestException as e:
            return {"created": False, "status": str(e)}

    def create_deal(self, title, contact_id, description=None):
        try:
            r = requests.post(
                f"{API_BASE}/deal/create",
                json={"title": title, "contact_id": contact_id, "description": description},
                headers=self._headers(),
                timeout=10,
            )
            r.raise_for_status()
            data = r.json()
            return {
                "created": True,
                "deal_id": data.get("deal_id"),
                "status": data.get("status", "Deal created successfully."),
            }
        except requests.RequestException as e:
            return {"created": False, "status": str(e)}
