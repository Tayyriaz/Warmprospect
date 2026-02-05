"""
Database manager for business configurations.
"""

import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from sqlalchemy.exc import SQLAlchemyError
from .connection import engine, SessionLocal, Session
from .models import BusinessConfig, ScrapingStatus


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


class ScrapingStatusDB:
    """Database manager for scraping status."""
    
    def __init__(self):
        self.engine = engine
        self.SessionLocal = SessionLocal
    
    def _get_session(self) -> Session:
        """Get a new database session."""
        return self.SessionLocal()
    
    def update_status(
        self,
        business_id: str,
        status: str,
        message: str = "",
        progress: int = 0
    ) -> bool:
        """
        Update or create scraping status for a business.
        Returns True if successful, False otherwise.
        """
        db = self._get_session()
        try:
            existing = db.query(ScrapingStatus).filter(
                ScrapingStatus.business_id == business_id
            ).first()
            
            now = datetime.now(timezone.utc)
            
            if existing:
                # Update existing status
                existing.status = status
                existing.message = message
                existing.progress = progress
                existing.updated_at = now
                
                # Set started_at if transitioning to active status
                if status in ["pending", "scraping", "indexing", "categorizing"] and not existing.started_at:
                    existing.started_at = now
                
                # Set completed_at if completed or failed
                if status in ["completed", "failed"]:
                    existing.completed_at = now
                elif status not in ["completed", "failed"]:
                    existing.completed_at = None
            else:
                # Create new status
                started_at = now if status in ["pending", "scraping", "indexing", "categorizing"] else None
                completed_at = now if status in ["completed", "failed"] else None
                
                new_status = ScrapingStatus(
                    business_id=business_id,
                    status=status,
                    message=message,
                    progress=progress,
                    started_at=started_at,
                    completed_at=completed_at,
                    created_at=now,
                    updated_at=now
                )
                db.add(new_status)
            
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            print(f"[ERROR] Failed to update scraping status: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            db.close()
    
    def get_status(self, business_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current scraping status for a business.
        Returns dict with status info or None if not found.
        Raises exception if database error occurs (e.g., table doesn't exist).
        """
        db = self._get_session()
        try:
            status = db.query(ScrapingStatus).filter(
                ScrapingStatus.business_id == business_id
            ).first()
            
            if status:
                return status.to_dict()
            return None
        except SQLAlchemyError as e:
            # Re-raise SQLAlchemy errors so caller can handle them
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            print(f"[ERROR] Failed to get scraping status: {e}")
            raise
        finally:
            db.close()
    
    def delete_status(self, business_id: str) -> bool:
        """Delete scraping status for a business."""
        db = self._get_session()
        try:
            status = db.query(ScrapingStatus).filter(
                ScrapingStatus.business_id == business_id
            ).first()
            
            if status:
                db.delete(status)
                db.commit()
                return True
            return False
        except Exception as e:
            db.rollback()
            print(f"[ERROR] Failed to delete scraping status: {e}")
            return False
        finally:
            db.close()


# Global instances
db_manager = BusinessConfigDB()
scraping_status_db = ScrapingStatusDB()
