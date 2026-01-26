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
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Text, DateTime, Integer, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
from dotenv import load_dotenv

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
engine = create_engine(DATABASE_URL, echo=False)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


class BusinessConfig(Base):
    """Database model for business configurations."""
    __tablename__ = "business_configs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    business_id = Column(String(255), unique=True, index=True, nullable=False)
    business_name = Column(String(255), nullable=False)
    system_prompt = Column(Text, nullable=False)
    greeting_message = Column(Text)
    appointment_link = Column(String(500))
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
    business_logo = Column(String(500))  # URL or path to business logo image
    voice_enabled = Column(Boolean, default=False)  # Enable voice bot for this business
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
            "appointment_link": self.appointment_link,
            "primary_goal": self.primary_goal,
            "personality": self.personality,
            "privacy_statement": self.privacy_statement,
            "theme_color": self.theme_color,
            "widget_position": self.widget_position,
            "website_url": self.website_url,
            "contact_email": self.contact_email,
            "contact_phone": self.contact_phone,
            "cta_tree": json.loads(self.cta_tree) if hasattr(self, 'cta_tree') and self.cta_tree else {},
            "tertiary_ctas": _parse_ctas(self.tertiary_ctas) if hasattr(self, 'tertiary_ctas') else None,
            "nested_ctas": json.loads(self.nested_ctas) if hasattr(self, 'nested_ctas') and self.nested_ctas else {},
            "rules": json.loads(self.rules) if hasattr(self, 'rules') and self.rules else [],
            "custom_routes": json.loads(self.custom_routes) if hasattr(self, 'custom_routes') and self.custom_routes else {},
            "available_services": json.loads(self.available_services) if hasattr(self, 'available_services') and self.available_services else [],
            "topic_ctas": json.loads(self.topic_ctas) if hasattr(self, 'topic_ctas') and self.topic_ctas else {},
            "experiments": json.loads(self.experiments) if hasattr(self, 'experiments') and self.experiments else [],
            "voice_enabled": getattr(self, 'voice_enabled', False) if hasattr(self, 'voice_enabled') else False,
            "chatbot_button_text": getattr(self, 'chatbot_button_text', None) if hasattr(self, 'chatbot_button_text') else None,
            "business_logo": getattr(self, 'business_logo', None) if hasattr(self, 'business_logo') else None,
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
        cta_tree = None,
        tertiary_ctas = None,
        nested_ctas = None,
        rules = None,
        custom_routes = None,
        available_services = None,
        topic_ctas = None,
        experiments = None,
        voice_enabled = False,
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
                # Update existing
                existing.business_name = business_name
                existing.system_prompt = system_prompt
                existing.greeting_message = greeting_message
                existing.appointment_link = appointment_link
                existing.primary_goal = primary_goal
                existing.personality = personality
                existing.privacy_statement = privacy_statement
                existing.theme_color = theme_color
                existing.widget_position = widget_position
                existing.website_url = website_url
                existing.contact_email = contact_email
                existing.contact_phone = contact_phone
                if hasattr(existing, 'cta_tree'):
                    existing.cta_tree = _serialize_json(cta_tree)
                # Store new dynamic fields as JSON strings
                if hasattr(existing, 'tertiary_ctas'):
                    existing.tertiary_ctas = _serialize_json(tertiary_ctas)
                if hasattr(existing, 'nested_ctas'):
                    existing.nested_ctas = _serialize_json(nested_ctas)
                if hasattr(existing, 'rules'):
                    existing.rules = _serialize_json(rules)
                if hasattr(existing, 'custom_routes'):
                    existing.custom_routes = _serialize_json(custom_routes)
                if hasattr(existing, 'available_services'):
                    existing.available_services = _serialize_json(available_services)
                if hasattr(existing, 'topic_ctas'):
                    existing.topic_ctas = _serialize_json(topic_ctas)
                if hasattr(existing, 'experiments'):
                    existing.experiments = _serialize_json(experiments)
                if hasattr(existing, 'voice_enabled'):
                    existing.voice_enabled = voice_enabled
                if hasattr(existing, 'chatbot_button_text'):
                    existing.chatbot_button_text = chatbot_button_text
                if hasattr(existing, 'business_logo'):
                    existing.business_logo = business_logo
                existing.updated_at = datetime.utcnow()
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
                    appointment_link=appointment_link,
                    primary_goal=primary_goal,
                    personality=personality,
                    privacy_statement=privacy_statement,
                    theme_color=theme_color,
                    widget_position=widget_position,
                    website_url=website_url,
                    contact_email=contact_email,
                    contact_phone=contact_phone,
                    cta_tree=_serialize_json(cta_tree),
                    tertiary_ctas=_serialize_json(tertiary_ctas),
                    nested_ctas=_serialize_json(nested_ctas),
                    rules=_serialize_json(rules),
                    custom_routes=_serialize_json(custom_routes),
                    available_services=_serialize_json(available_services),
                    topic_ctas=_serialize_json(topic_ctas),
                    experiments=_serialize_json(experiments),
                    voice_enabled=voice_enabled if hasattr(BusinessConfig, 'voice_enabled') else False,
                    chatbot_button_text=chatbot_button_text if hasattr(BusinessConfig, 'chatbot_button_text') else None,
                    business_logo=business_logo if hasattr(BusinessConfig, 'business_logo') else None,
                )
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
            return {b.business_id: b.to_dict() for b in businesses}
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


# Global instance
db_manager = BusinessConfigDB()

