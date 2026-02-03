"""
Database manager for business configurations.
"""

import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from sqlalchemy.exc import SQLAlchemyError
from .connection import engine, SessionLocal, Session
from .models import BusinessConfig


class BusinessConfigDB:
    """Database manager for business configurations."""
    
    def __init__(self):
        self.engine = engine
        self.SessionLocal = SessionLocal
    
    def _get_session(self) -> Session:
        """Get a new database session."""
        return self.SessionLocal()
    
    def create_or_update_business(
        self,
        business_id: str,
        business_name: str,
        system_prompt: str,
        greeting_message: str = None,
        primary_goal: str = None,
        personality: str = None,
        privacy_statement: str = None,
        theme_color: str = "#2563eb",
        widget_position: str = "center",
        website_url: str = None,
        contact_email: str = None,
        contact_phone: str = None,
        cta_tree = None,
        rules = None,
        custom_routes = None,
        available_services = None,
        topic_ctas = None,
        experiments = None,
        voice_enabled = False,
        chatbot_button_text: str = None,
        business_logo: str = None,
        enabled_categories: List[str] = None,
        categories: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Create or update a business configuration."""
        def _serialize_json(value):
            """Serialize any JSON-serializable value to string."""
            if value is None:
                return None
            if isinstance(value, str):
                return value
            try:
                return json.dumps(value, ensure_ascii=False)
            except Exception:
                return None

        db = self._get_session()
        try:
            existing = db.query(BusinessConfig).filter(
                BusinessConfig.business_id == business_id
            ).first()
            
            if existing:
                # Update existing
                existing.business_name = business_name
                existing.system_prompt = system_prompt
                existing.greeting_message = greeting_message
                existing.primary_goal = primary_goal
                existing.personality = personality
                existing.privacy_statement = privacy_statement
                existing.theme_color = theme_color
                existing.widget_position = widget_position
                existing.website_url = website_url
                existing.contact_email = contact_email
                existing.contact_phone = contact_phone
                existing.cta_tree = _serialize_json(cta_tree)
                existing.voice_enabled = voice_enabled
                existing.chatbot_button_text = chatbot_button_text
                existing.business_logo = business_logo
                if enabled_categories is not None and hasattr(existing, 'enabled_categories'):
                    existing.enabled_categories = _serialize_json(enabled_categories)
                if categories is not None and hasattr(existing, 'categories'):
                    existing.categories = _serialize_json(categories)
                existing.updated_at = datetime.now(timezone.utc)
                db.commit()
                db.refresh(existing)
                return existing.to_dict()
            else:
                # Create new
                new_business = BusinessConfig(
                    business_id=business_id,
                    business_name=business_name,
                    system_prompt=system_prompt,
                    greeting_message=greeting_message,
                    primary_goal=primary_goal,
                    personality=personality,
                    privacy_statement=privacy_statement,
                    theme_color=theme_color,
                    widget_position=widget_position,
                    website_url=website_url,
                    contact_email=contact_email,
                    contact_phone=contact_phone,
                    cta_tree=_serialize_json(cta_tree),
                    voice_enabled=voice_enabled,
                    chatbot_button_text=chatbot_button_text,
                    business_logo=business_logo,
                    enabled_categories=_serialize_json(enabled_categories) if enabled_categories else None if hasattr(BusinessConfig, 'enabled_categories') else None,
                    categories=_serialize_json(categories) if categories else None if hasattr(BusinessConfig, 'categories') else None,
                )
                db.add(new_business)
                db.commit()
                db.refresh(new_business)
                return new_business.to_dict()
        except SQLAlchemyError as e:
            db.rollback()
            print(f"Database error: {e}")
            raise
        finally:
            db.close()
    
    def get_business(self, business_id: str) -> Optional[Dict[str, Any]]:
        """Get business configuration by ID."""
        db = self._get_session()
        try:
            business = db.query(BusinessConfig).filter(
                BusinessConfig.business_id == business_id
            ).first()
            return business.to_dict() if business else None
        finally:
            db.close()
    
    def get_all_businesses(self) -> Dict[str, Dict[str, Any]]:
        """Get all business configurations."""
        db = self._get_session()
        try:
            businesses = db.query(BusinessConfig).all()
            result = {b.business_id: b.to_dict() for b in businesses}
            return result
        finally:
            db.close()
    
    def delete_business(self, business_id: str) -> bool:
        """Delete a business configuration."""
        db = self._get_session()
        try:
            business = db.query(BusinessConfig).filter(
                BusinessConfig.business_id == business_id
            ).first()
            if business:
                db.delete(business)
                db.commit()
                return True
            return False
        except SQLAlchemyError:
            db.rollback()
            return False
        finally:
            db.close()
    
    def build_system_prompt(self, business_id: str) -> Optional[str]:
        """Build system prompt for a business."""
        config = self.get_business(business_id)
        if config:
            return config.get("system_prompt")
        return None


# Global instance
db_manager = BusinessConfigDB()
