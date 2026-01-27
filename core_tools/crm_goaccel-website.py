"""
Example: Business-Specific CRM Functions for GoAccel Website
This file demonstrates how to create tenant-specific CRM implementations.

To use:
1. Create a file named crm_{business_id}.py in core_tools/
2. Define a CRMTools class with your CRM functions
3. The CRM manager will automatically load it when that business_id is used
"""

from core_tools.crm_functions import CRMTools as BaseCRMTools


class CRMTools(BaseCRMTools):
    """
    GoAccel Website-specific CRM implementation.
    Extends base CRM tools with custom logic for this tenant.
    """
    
    def search_contact(self, email: str = None, phone_number: str = None) -> dict:
        """
        Custom search logic for GoAccel Website.
        You can override the base implementation here.
        """
        # Example: Add custom logging or API calls
        print(f"[GoAccel CRM] Searching contact: email={email}, phone={phone_number}")
        
        # Call base implementation or implement custom logic
        result = super().search_contact(email=email, phone_number=phone_number)
        
        # Add custom processing if needed
        # result["custom_field"] = "custom_value"
        
        return result
    
    def create_new_contact(self, first_name: str, email: str, phone_number: str = None) -> dict:
        """
        Custom contact creation for GoAccel Website.
        """
        print(f"[GoAccel CRM] Creating contact: {first_name}, {email}, {phone_number}")
        
        # Example: Custom validation or API integration
        # In production, this would call GoAccel's specific CRM API
        
        result = super().create_new_contact(
            first_name=first_name,
            email=email,
            phone_number=phone_number
        )
        
        return result
    
    def create_deal(self, title: str, contact_id: str, description: str = None) -> dict:
        """
        Custom deal creation for GoAccel Website.
        """
        print(f"[GoAccel CRM] Creating deal: {title} for contact {contact_id}")
        
        result = super().create_deal(
            title=title,
            contact_id=contact_id,
            description=description
        )
        
        return result
    
    # You can add additional CRM functions specific to this tenant:
    # def custom_function(self, param1: str, param2: int) -> dict:
    #     """Custom CRM function only available for this tenant."""
    #     return {"status": "success", "data": "..."}
