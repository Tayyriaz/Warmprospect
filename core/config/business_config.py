"""
Business Configuration Storage
Stores and manages business-specific chatbot configurations.
Uses PostgreSQL database only.
"""

from typing import Dict, Any, Optional, List

# Import database manager
from core.database import db_manager

# Removed DEFAULT_PRIMARY_CTAS and DEFAULT_SECONDARY_CTAS
# Now using only cta_tree for dynamic CTA management


class BusinessConfigManager:
    """Manages business configurations for multi-tenant chatbot system."""
    
    def __init__(self):
        pass
    
    def create_or_update_business(
        self,
        business_id: str,
        business_name: str,
        system_prompt: str,
        greeting_message: str = None,
        # appointment_link removed - use CTA tree with redirect action instead
        primary_goal: str = None,
        personality: str = None,
        privacy_statement: str = None,
        theme_color: str = "#2563eb",
        widget_position: str = "center",
        website_url: str = None,
        contact_email: str = None,
        contact_phone: str = None,
        cta_tree: Dict[str, Any] = None,
        rules: List[Dict[str, Any]] = None,
        custom_routes: Dict[str, Any] = None,
        available_services: List[Dict[str, Any]] = None,
        topic_ctas: Dict[str, List[Dict[str, Any]]] = None,
        experiments: List[Dict[str, Any]] = None,
        voice_enabled: bool = False,
        chatbot_button_text: str = None,
        business_logo: str = None,
        enabled_categories: List[str] = None,
    ) -> Dict[str, Any]:
        """
        Create or update a business configuration.
        
        Args:
            business_id: Unique identifier for the business
            business_name: Display name of the business
            system_prompt: Custom system prompt/instructions for the chatbot
            greeting_message: Initial greeting message
            appointment_link: Booking/appointment URL
            primary_goal: Business primary goal (e.g., "Generate more leads")
            personality: Assistant personality description
            privacy_statement: Privacy policy statement
            theme_color: Theme color for the widget
            widget_position: Widget position (center, bottom-right, bottom-left)
            website_url: Business website URL
            contact_email: Business contact email
            contact_phone: Business contact phone
        
        Returns:
            The created/updated configuration
        """
        return db_manager.create_or_update_business(
            business_id=business_id,
            business_name=business_name,
            system_prompt=system_prompt,
            greeting_message=greeting_message,
            # appointment_link removed - use CTA tree instead
            primary_goal=primary_goal,
            personality=personality,
            privacy_statement=privacy_statement,
            theme_color=theme_color,
            widget_position=widget_position,
            website_url=website_url,
            contact_email=contact_email,
            contact_phone=contact_phone,
            cta_tree=cta_tree,
            rules=rules,
            custom_routes=custom_routes,
            available_services=available_services,
            topic_ctas=topic_ctas,
            experiments=experiments,
            voice_enabled=voice_enabled,
            chatbot_button_text=chatbot_button_text,
            business_logo=business_logo,
            enabled_categories=enabled_categories,
        )
    
    def get_business(self, business_id: str) -> Optional[Dict[str, Any]]:
        """Get business configuration by ID."""
        return db_manager.get_business(business_id)
    
    def get_all_businesses(self) -> Dict[str, Dict[str, Any]]:
        """Get all business configurations."""
        return db_manager.get_all_businesses()
    
    def delete_business(self, business_id: str) -> bool:
        """Delete a business configuration."""
        return db_manager.delete_business(business_id)
    
    def build_system_prompt(self, business_id: str) -> str:
        """
        Builds the complete system prompt for a business by combining
        base instructions with business-specific customizations.
        """
        return db_manager.build_system_prompt(business_id)


# Global instance
config_manager = BusinessConfigManager()

