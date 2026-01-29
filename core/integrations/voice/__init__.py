"""
Voice Service Integration
Handles voice/phone call functionality via Twilio.
"""

from .voice_service import get_voice_service
from .twilio_voice_manager import get_voice_manager

__all__ = [
    "get_voice_service",
    "get_voice_manager",
]
