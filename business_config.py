"""
Business Configuration Storage
Stores and manages business-specific chatbot configurations.
Uses PostgreSQL database (with file fallback for development).
"""

import json
import os
from typing import Dict, Any, Optional, List
from datetime import datetime

# Try to import database manager
try:
    from database import db_manager
    USE_DATABASE = True
except ImportError:
    USE_DATABASE = False
    print("[WARNING] Database module not found. Using file-based storage.")

# File-based storage fallback
CONFIG_FILE = "business_configs.json"

# Removed DEFAULT_PRIMARY_CTAS and DEFAULT_SECONDARY_CTAS
# Now using only cta_tree for dynamic CTA management


class BusinessConfigManager:
    """Manages business configurations for multi-tenant chatbot system."""
    
    def __init__(self, config_file: str = CONFIG_FILE):
        self.config_file = config_file
        self._configs: Dict[str, Dict[str, Any]] = {}
        self.use_database = USE_DATABASE
        if not self.use_database:
            self._load_configs()
    
    def _load_configs(self):
        """Load configurations from file."""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self._configs = json.load(f)
            except Exception as e:
                print(f"[WARNING] Failed to load business configs: {e}")
                self._configs = {}
        else:
            self._configs = {}
    
    def _save_configs(self):
        """Save configurations to file."""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self._configs, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[ERROR] Failed to save business configs: {e}")
    
    def create_or_update_business(
        self,
        business_id: str,
        business_name: str,
        system_prompt: str,
        greeting_message: str = None,
        appointment_link: str = None,
        primary_goal: str = None,
        personality: str = None,
        privacy_statement: str = None,
        theme_color: str = "#2563eb",
        widget_position: str = "center",
        website_url: str = None,
        contact_email: str = None,
        contact_phone: str = None,
        cta_tree: Dict[str, Any] = None,
        tertiary_ctas: List[Dict[str, Any]] = None,
        nested_ctas: Dict[str, List[Dict[str, Any]]] = None,
        rules: List[Dict[str, Any]] = None,
        custom_routes: Dict[str, Any] = None,
        available_services: List[Dict[str, Any]] = None,
        topic_ctas: Dict[str, List[Dict[str, Any]]] = None,
        experiments: List[Dict[str, Any]] = None,
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
        if self.use_database:
            try:
                return db_manager.create_or_update_business(
                    business_id=business_id,
                    business_name=business_name,
                    system_prompt=system_prompt,
                    greeting_message=greeting_message,
                    appointment_link=appointment_link,
                    primary_goal=primary_goal,
                    personality=personality,
                    privacy_statement=privacy_statement,
                    theme_color=theme_color,
                    widget_position=widget_position,
                    website_url=website_url,
            contact_email=contact_email,
            contact_phone=contact_phone,
            cta_tree=cta_tree,
            tertiary_ctas=tertiary_ctas,
            nested_ctas=nested_ctas,
            rules=rules,
            custom_routes=custom_routes,
            available_services=available_services,
            topic_ctas=topic_ctas,
            experiments=experiments,
                )
            except Exception as e:
                print(f"[ERROR] Database operation failed, falling back to file storage: {e}")
                self.use_database = False
                # Ensure file configs are loaded for fallback mode
                self._load_configs()
        
        # File-based fallback
        config = {
            "business_id": business_id,
            "business_name": business_name,
            "system_prompt": system_prompt,
            "greeting_message": greeting_message or f"Hi! How can {business_name} help you today?",
            "appointment_link": appointment_link,
            "primary_goal": primary_goal,
            "personality": personality,
            "privacy_statement": privacy_statement,
            "theme_color": theme_color,
            "widget_position": widget_position,
            "website_url": website_url,
            "contact_email": contact_email,
            "contact_phone": contact_phone,
            "cta_tree": cta_tree or {},
            "created_at": self._configs.get(business_id, {}).get("created_at", datetime.now().isoformat()),
            "updated_at": datetime.now().isoformat(),
        }
        
        self._configs[business_id] = config
        self._save_configs()
        
        return config
    
    def get_business(self, business_id: str) -> Optional[Dict[str, Any]]:
        """Get business configuration by ID."""
        if self.use_database:
            try:
                return db_manager.get_business(business_id)
            except Exception as e:
                print(f"[ERROR] Database operation failed, falling back to file storage: {e}")
                self.use_database = False
                self._load_configs()
        
        return self._configs.get(business_id)
    
    def get_all_businesses(self) -> Dict[str, Dict[str, Any]]:
        """Get all business configurations."""
        if self.use_database:
            try:
                return db_manager.get_all_businesses()
            except Exception as e:
                print(f"[ERROR] Database operation failed, falling back to file storage: {e}")
                self.use_database = False
                self._load_configs()
        
        return self._configs.copy()
    
    def delete_business(self, business_id: str) -> bool:
        """Delete a business configuration."""
        if self.use_database:
            try:
                return db_manager.delete_business(business_id)
            except Exception as e:
                print(f"[ERROR] Database operation failed, falling back to file storage: {e}")
                self.use_database = False
                self._load_configs()
        
        if business_id in self._configs:
            del self._configs[business_id]
            self._save_configs()
            return True
        return False
    
    def build_system_prompt(self, business_id: str) -> str:
        """
        Builds the complete system prompt for a business by combining
        base instructions with business-specific customizations.
        """
        if self.use_database:
            try:
                return db_manager.build_system_prompt(business_id)
            except Exception as e:
                print(f"[ERROR] Database operation failed, falling back to file storage: {e}")
                self.use_database = False
                self._load_configs()
        
        config = self.get_business(business_id)
        if not config:
            return None
        
        parts = []
        
        # Add business-specific system prompt (main customization)
        if config.get("system_prompt"):
            parts.append(config["system_prompt"])
        
        # Add structured business information
        business_info = []
        if config.get("primary_goal"):
            business_info.append(f"Business Primary Goal: {config['primary_goal']}")
        if config.get("personality"):
            business_info.append(f"Assistant Personality: {config['personality']}")
        if config.get("greeting_message"):
            business_info.append(f"Preferred Greeting Style: \"{config['greeting_message']}\"")
        if config.get("privacy_statement"):
            business_info.append(f"Privacy Statement (use when collecting PII): {config['privacy_statement']}")
        
        if business_info:
            parts.append("BUSINESS CONTEXT:\n" + "\n".join(business_info))
        
        return "\n\n".join(parts) if parts else None


# Global instance
config_manager = BusinessConfigManager()

