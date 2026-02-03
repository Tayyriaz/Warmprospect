"""
Database models.
"""

import json
from typing import Dict, Any
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, Integer, Boolean
from .connection import Base


class BusinessConfig(Base):
    """Database model for business configurations."""
    __tablename__ = "business_configs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    business_id = Column(String(255), unique=True, index=True, nullable=False)
    business_name = Column(String(255), nullable=False)
    system_prompt = Column(Text, nullable=False)
    greeting_message = Column(Text)
    primary_goal = Column(Text)
    personality = Column(Text)
    privacy_statement = Column(Text)
    theme_color = Column(String(50), default="#2563eb")
    widget_position = Column(String(50), default="center")
    website_url = Column(String(500))
    contact_email = Column(String(255))
    contact_phone = Column(String(50))
    cta_tree = Column(Text)  # Stores complete CTA tree structure as JSON
    chatbot_button_text = Column(String(255))
    business_logo = Column(Text)
    voice_enabled = Column(Boolean, default=False)
    enabled_categories = Column(Text)  # JSON array of enabled category names
    categories = Column(Text)  # JSON object with categories list and total_pages
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "business_id": self.business_id,
            "business_name": self.business_name,
            "system_prompt": self.system_prompt,
            "greeting_message": self.greeting_message,
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
