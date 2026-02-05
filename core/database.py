"""
PostgreSQL Database Models and Connection
Handles all database operations for business configurations.

Important:
- We call load_dotenv() here so DATABASE_URL from `.env` is available even when
  this module is imported before `main.py` runs load_dotenv().
"""

import os
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, String, Text, DateTime, Integer, Boolean, ForeignKey
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
from dotenv import load_dotenv

# Import models to ensure they're registered with Base
from core.database.models import BusinessConfig, ScrapingStatus

# Ensure `.env` variables (DATABASE_URL, etc.) are loaded before we read them.
load_dotenv()

# Database connection
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/goaccel_db",
)

# Force synchronous psycopg2 driver (not asyncpg)
# SQLAlchemy might try to use asyncpg if the URL doesn't specify a driver
if DATABASE_URL.startswith("postgresql://") and "psycopg2" not in DATABASE_URL and "asyncpg" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)
elif DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)

# Create engine
engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models (SQLAlchemy 2.0+ style)
class Base(DeclarativeBase):
    pass


class BusinessConfig(Base):
    """Database model for business configurations."""
    __tablename__ = "business_configs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    business_id = Column(String(255), unique=True, index=True, nullable=False)
    business_name = Column(String(255), nullable=False)
    system_prompt = Column(Text, nullable=False)
    greeting_message = Column(Text)
    # appointment_link removed - now handled via CTA tree (redirect action with URL)
    primary_goal = Column(Text)
    personality = Column(Text)
    privacy_statement = Column(Text)
    theme_color = Column(String(50), default="#2563eb")
    widget_position = Column(String(50), default="center")
    website_url = Column(String(500))
    contact_email = Column(String(255))
    contact_phone = Column(String(50))
    cta_tree = Column(Text)  # Stores complete CTA tree structure as JSON
    chatbot_button_text = Column(String(255))  # Text for the chatbot button (e.g., "Chat with us")
    business_logo = Column(Text)  # URL, path, or base64-encoded image data for business logo
    voice_enabled = Column(Boolean, default=False)  # Enable voice bot for this business
    enabled_categories = Column(Text)  # JSON array of enabled category names for knowledge base
    categories = Column(Text)  # JSON object with categories list and total_pages: {"categories": [...], "total_pages": N}
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        def _parse_ctas(value):
            if value is None:
                return None
            if isinstance(value, list):
                return value
            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, list) else None
            except Exception:
                return None

        return {
            "business_id": self.business_id,
            "business_name": self.business_name,
            "system_prompt": self.system_prompt,
            "greeting_message": self.greeting_message,
            # appointment_link removed - use CTA tree instead
            "primary_goal": self.primary_goal,
            "personality": self.personality,
            "privacy_statement": self.privacy_statement,
            "theme_color": self.theme_color,
            "widget_position": self.widget_position,
            "website_url": self.website_url,
            "contact_email": self.contact_email,
            "contact_phone": self.contact_phone,
            "cta_tree": json.loads(self.cta_tree) if self.cta_tree else {},
            "voice_enabled": self.voice_enabled if hasattr(self, 'voice_enabled') else False,
            "chatbot_button_text": self.chatbot_button_text if hasattr(self, 'chatbot_button_text') else None,
            "business_logo": self.business_logo if hasattr(self, 'business_logo') else None,
            "enabled_categories": json.loads(self.enabled_categories) if hasattr(self, 'enabled_categories') and self.enabled_categories else [],
            "categories": json.loads(self.categories) if hasattr(self, 'categories') and self.categories else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


def init_db():
    """Initialize database - create all tables."""
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables created successfully!")
        return True
    except Exception as e:
        print(f"❌ Error creating database tables: {e}")
        return False


def get_db() -> Session:
    """Get database session (for dependency injection)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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
        business_name: str = None,
        system_prompt: str = None,
        greeting_message: str = None,
        # appointment_link removed - use CTA tree instead
        primary_goal: str = None,
        personality: str = None,
        privacy_statement: str = None,
        theme_color: str = None,
        widget_position: str = None,
        website_url: str = None,
        contact_email: str = None,
        contact_phone: str = None,
        cta_tree = None,
        rules = None,
        custom_routes = None,
        available_services = None,
        topic_ctas = None,
        experiments = None,
        voice_enabled = None,
        chatbot_button_text: str = None,
        business_logo: str = None,
        enabled_categories: List[str] = None,
        categories: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Create or update a business configuration."""
        def _serialize_ctas(value):
            if value is None:
                return None
            if isinstance(value, str):
                return value
            try:
                return json.dumps(value, ensure_ascii=False)
            except Exception:
                return None
        
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
            # Check if business exists
            existing = db.query(BusinessConfig).filter(
                BusinessConfig.business_id == business_id
            ).first()
            
            if existing:
                # Update existing - only update fields that are explicitly provided (not None)
                # This prevents overwriting existing values with None when field is not in update request
                if business_name is not None:
                    existing.business_name = business_name
                if system_prompt is not None:
                    existing.system_prompt = system_prompt
                if greeting_message is not None:
                    existing.greeting_message = greeting_message
                # appointment_link removed - use CTA tree instead
                if primary_goal is not None:
                    existing.primary_goal = primary_goal
                if personality is not None:
                    existing.personality = personality
                if privacy_statement is not None:
                    existing.privacy_statement = privacy_statement
                if theme_color is not None:
                    existing.theme_color = theme_color
                if widget_position is not None:
                    existing.widget_position = widget_position
                if website_url is not None:
                    existing.website_url = website_url
                if contact_email is not None:
                    existing.contact_email = contact_email
                if contact_phone is not None:
                    existing.contact_phone = contact_phone
                if cta_tree is not None:
                    existing.cta_tree = _serialize_json(cta_tree)
                # voice_enabled: only update if explicitly provided (not None)
                if voice_enabled is not None:
                    existing.voice_enabled = voice_enabled
                if chatbot_button_text is not None:
                    existing.chatbot_button_text = chatbot_button_text
                if business_logo is not None:
                    existing.business_logo = business_logo
                if enabled_categories is not None and hasattr(existing, 'enabled_categories'):
                    existing.enabled_categories = _serialize_json(enabled_categories)
                if categories is not None and hasattr(existing, 'categories'):
                    existing.categories = _serialize_json(categories)
                existing.updated_at = datetime.now(timezone.utc)
                # Note: rules, custom_routes, available_services, topic_ctas, experiments 
                # are not stored as separate columns - they can be included in cta_tree if needed
                db.commit()
                db.refresh(existing)
                return existing.to_dict()
            else:
                # Create new - require business_name and system_prompt for new businesses
                if business_name is None:
                    raise ValueError("business_name is required for new businesses")
                if system_prompt is None:
                    raise ValueError("system_prompt is required for new businesses")
                
                # Create new - only pass columns that exist in the model
                new_business = BusinessConfig(
                    business_id=business_id,
                    business_name=business_name,
                    system_prompt=system_prompt,
                    greeting_message=greeting_message,
                    # appointment_link removed - use CTA tree instead
                    primary_goal=primary_goal,
                    personality=personality,
                    privacy_statement=privacy_statement,
                    theme_color=theme_color or "#2563eb",
                    widget_position=widget_position or "center",
                    website_url=website_url,
                    contact_email=contact_email,
                    contact_phone=contact_phone,
                    cta_tree=_serialize_json(cta_tree),
                    voice_enabled=voice_enabled if voice_enabled is not None else False,
                    chatbot_button_text=chatbot_button_text,
                    business_logo=business_logo,
                    enabled_categories=_serialize_json(enabled_categories) if enabled_categories else None if hasattr(BusinessConfig, 'enabled_categories') else None,
                    categories=_serialize_json(categories) if categories else None if hasattr(BusinessConfig, 'categories') else None,
                )
                # Note: rules, custom_routes, available_services, topic_ctas, experiments 
                # are not stored as separate columns - they can be included in cta_tree if needed
                db.add(new_business)
                db.commit()
                db.refresh(new_business)
                return new_business.to_dict()
        except SQLAlchemyError as e:
            db.rollback()
            print(f"[ERROR] Database error: {e}")
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
            print(f"[DEBUG] get_all_businesses: queried {len(businesses)} businesses from database")
            result = {b.business_id: b.to_dict() for b in businesses}
            print(f"[DEBUG] get_all_businesses: returning {len(result)} businesses")
            return result
        except Exception as e:
            print(f"[ERROR] get_all_businesses failed: {e}")
            import traceback
            traceback.print_exc()
            raise
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
        except SQLAlchemyError as e:
            db.rollback()
            print(f"[ERROR] Database error: {e}")
            raise
        finally:
            db.close()
    
    def build_system_prompt(self, business_id: str) -> Optional[str]:
        """Builds the complete system prompt for a business."""
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
        from core.database.models import ScrapingStatus
        from datetime import datetime, timezone
        
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
    
    def get_status(self, business_id: str) -> Dict[str, Any]:
        """
        Get current scraping status for a business.
        Returns dict with status info or None if not found.
        """
        from core.database.models import ScrapingStatus
        
        db = self._get_session()
        try:
            status = db.query(ScrapingStatus).filter(
                ScrapingStatus.business_id == business_id
            ).first()
            
            if status:
                return status.to_dict()
            return None
        except Exception as e:
            print(f"[ERROR] Failed to get scraping status: {e}")
            return None
        finally:
            db.close()
    
    def delete_status(self, business_id: str) -> bool:
        """Delete scraping status for a business."""
        from core.database.models import ScrapingStatus
        
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

