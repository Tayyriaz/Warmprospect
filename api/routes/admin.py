"""
Admin API routes (protected by API key authentication).
"""

import os
import json
import subprocess
import sys
import time
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks, Depends
from core.security import get_api_key
from core.config.business_config import config_manager
from core.utils.helpers import convert_config_to_camel

router = APIRouter()


def update_scraping_status(business_id: str, status: str, message: str = "", progress: int = 0):
    """Update scraping status in a JSON file for frontend polling."""
    status_file = os.path.join("data", business_id, "scraping_status.json")
    os.makedirs(os.path.dirname(status_file), exist_ok=True)
    
    status_data = {
        "status": status,  # "pending", "scraping", "indexing", "completed", "failed"
        "message": message,
        "progress": progress,  # 0-100
        "updated_at": time.time()
    }
    
    with open(status_file, "w", encoding="utf-8") as f:
        json.dump(status_data, f)


def trigger_kb_build(business_id: str, website_url: str):
    """
    Background task to build knowledge base for a business website.
    Runs the scraping script asynchronously and updates status.
    """
    try:
        update_scraping_status(business_id, "pending", "Preparing to scrape website...", 0)
        
        script_path = os.path.join("scripts", "build_kb_for_business.py")
        if not os.path.exists(script_path):
            error_msg = f"Scraping script not found: {script_path}"
            print(f"[WARNING] {error_msg}")
            update_scraping_status(business_id, "failed", error_msg, 0)
            return
        
        # Run the scraping script in background
        cmd = [sys.executable, script_path, "--business_id", business_id, "--url", website_url]
        print(f"[INFO] Starting KB build for business: {business_id}, URL: {website_url}")
        update_scraping_status(business_id, "scraping", "Scraping website content... This may take a few minutes.", 10)
        
        # Increase timeout to 700 seconds (10+ minutes)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=700)
        
        if result.returncode == 0:
            success_msg = "Knowledge base built successfully! Your chatbot is now ready to use."
            print(f"[SUCCESS] KB build completed for business: {business_id}")
            update_scraping_status(business_id, "completed", success_msg, 100)
        else:
            error_msg = f"Scraping failed: {result.stderr[:200]}"
            print(f"[ERROR] KB build failed for business: {business_id}")
            print(f"[ERROR] Error output: {result.stderr}")
            update_scraping_status(business_id, "failed", error_msg, 0)
    except subprocess.TimeoutExpired:
        error_msg = "Scraping timed out. The website might be too large or slow."
        print(f"[ERROR] KB build timeout for business: {business_id}")
        update_scraping_status(business_id, "failed", error_msg, 0)
    except Exception as e:
        error_msg = f"Failed to build knowledge base: {str(e)}"
        print(f"[ERROR] Failed to trigger KB build for business {business_id}: {e}")
        update_scraping_status(business_id, "failed", error_msg, 0)


@router.post("/admin/business")
async def create_or_update_business(request: Request, background_tasks: BackgroundTasks, api_key: str = Depends(get_api_key)):
    """
    Create or update a business configuration.
    Clients can use this to configure their chatbot.
    Accepts camelCase field names (standardized).
    If websiteUrl is provided, automatically triggers knowledge base scraping.
    """
    try:
        data = await request.json()
        
        business_id = data.get("businessId")
        if not business_id:
            raise HTTPException(status_code=400, detail="businessId is required")
        
        website_url = data.get("websiteUrl")
        
        config = config_manager.create_or_update_business(
            business_id=business_id,
            business_name=data.get("businessName", business_id),
            system_prompt=data.get("systemPrompt", ""),
            greeting_message=data.get("greetingMessage"),
            appointment_link=data.get("appointmentLink"),
            primary_goal=data.get("primaryGoal"),
            personality=data.get("personality"),
            privacy_statement=data.get("privacyStatement"),
            theme_color=data.get("themeColor", "#2563eb"),
            widget_position=data.get("widgetPosition", "center"),
            website_url=website_url,
            contact_email=data.get("contactEmail"),
            contact_phone=data.get("contactPhone"),
            cta_tree=data.get("ctaTree"),
            tertiary_ctas=data.get("tertiaryCtas"),
            nested_ctas=data.get("nestedCtas"),
            rules=data.get("rules"),
            custom_routes=data.get("customRoutes"),
            available_services=data.get("availableServices"),
            topic_ctas=data.get("topicCtas"),
            experiments=data.get("experiments"),
            voice_enabled=data.get("voiceEnabled", False),
            chatbot_button_text=data.get("chatbotButtonText"),
            business_logo=data.get("businessLogo"),
        )
        
        # Trigger knowledge base build in background if website_url is provided
        scraping_started = False
        if website_url and website_url.strip():
            background_tasks.add_task(trigger_kb_build_wrapper, business_id, website_url.strip())
            print(f"[INFO] Queued KB build for business: {business_id}, URL: {website_url}")
            scraping_started = True
        
        return {
            "success": True, 
            "config": convert_config_to_camel(config),
            "scrapingStarted": scraping_started
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/admin/business/{business_id}/scraping-status")
async def get_scraping_status(business_id: str, api_key: str = Depends(get_api_key)):
    """Get current scraping status for a business."""
    status_file = os.path.join("data", business_id, "scraping_status.json")
    
    if not os.path.exists(status_file):
        return {
            "status": "not_started",
            "message": "No scraping in progress",
            "progress": 0
        }
    
    try:
        with open(status_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error reading status: {str(e)}",
            "progress": 0
        }


@router.get("/admin/business/{business_id}")
async def get_business_config(business_id: str, api_key: str = Depends(get_api_key)):
    """Get business configuration by ID. Returns camelCase field names."""
    config = config_manager.get_business(business_id)
    if not config:
        raise HTTPException(status_code=404, detail="Business not found")
    camel_config = convert_config_to_camel(config)
    return {"success": True, "config": camel_config}


@router.get("/admin/business")
async def list_all_businesses(api_key: str = Depends(get_api_key)):
    """List all configured businesses. Returns camelCase field names."""
    try:
        businesses = config_manager.get_all_businesses()
        print(f"[DEBUG] list_all_businesses: found {len(businesses)} businesses")
        # Convert all business configs to camelCase
        camel_businesses = {}
        for business_id, config in businesses.items():
            camel_businesses[business_id] = convert_config_to_camel(config)
        return {"success": True, "businesses": camel_businesses}
    except Exception as e:
        print(f"[ERROR] list_all_businesses failed: {e}")
        return {"success": False, "businesses": {}, "error": str(e)}


@router.delete("/admin/business/{business_id}")
async def delete_business_config(business_id: str, api_key: str = Depends(get_api_key)):
    """Delete a business configuration."""
    success = config_manager.delete_business(business_id)
    if success:
        return {"success": True, "message": f"Business {business_id} deleted"}
    else:
        raise HTTPException(status_code=404, detail="Business not found")


@router.get("/admin")
async def admin_panel():
    """Serve the admin configuration panel."""
    from fastapi.responses import FileResponse
    return FileResponse("static/admin.html")
