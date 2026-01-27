"""
Business configuration API routes (public widget endpoints).
"""

from fastapi import APIRouter, HTTPException
from core.config.business_config import config_manager

router = APIRouter()


@router.get("/api/business/{business_id}/config")
async def get_business_config_for_widget(business_id: str):
    """
    Get business configuration for frontend widget.
    This endpoint is used by the chat widget to load business-specific settings.
    Returns all fields that match the POST endpoint for consistency.
    """
    config = config_manager.get_business(business_id)
    if not config:
        raise HTTPException(status_code=404, detail="Business not found")
    
    # Return all fields matching POST endpoint structure
    return {
        "businessId": config.get("business_id"),
        "businessName": config.get("business_name"),
        "businessPrimaryGoal": config.get("primary_goal"),
        "personalityPrompt": config.get("personality"),
        "greetingMessage": config.get("greeting_message"),
        "privacyStatement": config.get("privacy_statement"),
        "themeColor": config.get("theme_color", "#2563eb"),
        "widgetPosition": config.get("widget_position", "center"),
        # appointmentLink removed - use CTA tree with redirect action instead
        "websiteUrl": config.get("website_url"),
        "contactEmail": config.get("contact_email"),
        "contactPhone": config.get("contact_phone"),
        "ctaTree": config.get("cta_tree"),
        "voiceEnabled": config.get("voice_enabled", False),
        "chatbotButtonText": config.get("chatbot_button_text"),
        "businessLogo": config.get("business_logo"),
    }
