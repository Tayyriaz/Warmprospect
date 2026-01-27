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
    # Use absolute paths to avoid issues with working directory
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    status_file = os.path.join(base_dir, "data", business_id, "scraping_status.json")
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
        # Use absolute paths to avoid issues with working directory
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        script_path = os.path.join(base_dir, "scripts", "build_kb_for_business.py")
        
        print(f"[DEBUG] Base directory: {base_dir}")
        print(f"[DEBUG] Script path: {script_path}")
        print(f"[DEBUG] Script exists: {os.path.exists(script_path)}")
        
        update_scraping_status(business_id, "pending", "Preparing to scrape website...", 0)
        
        if not os.path.exists(script_path):
            error_msg = f"Scraping script not found: {script_path}"
            print(f"[ERROR] {error_msg}")
            update_scraping_status(business_id, "failed", error_msg, 0)
            return
        
        # Run the scraping script in background
        # Use absolute path for script
        abs_script_path = os.path.abspath(script_path)
        
        # Ensure script path is absolute and exists
        if not os.path.isabs(abs_script_path):
            abs_script_path = os.path.abspath(os.path.join(base_dir, script_path))
        
        if not os.path.exists(abs_script_path):
            error_msg = f"Scraping script not found at: {abs_script_path}"
            print(f"[ERROR] {error_msg}")
            print(f"[ERROR] Base dir: {base_dir}, Script path: {script_path}")
            update_scraping_status(business_id, "failed", error_msg, 0)
            return
        
        cmd = [sys.executable, abs_script_path, "--business_id", business_id, "--url", website_url]
        print(f"[INFO] Starting KB build for business: {business_id}, URL: {website_url}")
        print(f"[INFO] Command: {' '.join(cmd)}")
        print(f"[INFO] Working directory will be: {base_dir}")
        print(f"[INFO] Script absolute path: {abs_script_path}")
        update_scraping_status(business_id, "scraping", "Scraping website content... This may take a few minutes.", 10)
        
        # Change to base directory to ensure relative paths work
        original_cwd = os.getcwd()
        try:
            os.chdir(base_dir)
            print(f"[DEBUG] Changed working directory to: {base_dir}")
            print(f"[DEBUG] Current directory: {os.getcwd()}")
            print(f"[DEBUG] Python executable: {sys.executable}")
            print(f"[DEBUG] Script path (absolute): {abs_script_path}")
            print(f"[DEBUG] Script exists: {os.path.exists(abs_script_path)}")
            
            # Check if script is readable
            if not os.access(abs_script_path, os.R_OK):
                raise Exception(f"Script is not readable: {abs_script_path}")
            
            # Increase timeout to 700 seconds (10+ minutes)
            # Use shell=False but ensure paths are absolute
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=700,
                cwd=base_dir,
                env=dict(os.environ, PYTHONUNBUFFERED="1")  # Ensure output is not buffered
            )
        except FileNotFoundError as e:
            error_msg = f"Python executable not found: {sys.executable}. Error: {str(e)}"
            print(f"[ERROR] {error_msg}")
            update_scraping_status(business_id, "failed", error_msg, 0)
            return
        finally:
            os.chdir(original_cwd)
        
        if result.returncode == 0:
            success_msg = "Knowledge base built successfully! Your chatbot is now ready to use."
            print(f"[SUCCESS] KB build completed for business: {business_id}")
            print(f"[SUCCESS] Output: {result.stdout[:500]}")
            update_scraping_status(business_id, "completed", success_msg, 100)
        else:
            error_msg = f"Scraping failed: {result.stderr[:500] if result.stderr else result.stdout[:500]}"
            print(f"[ERROR] KB build failed for business: {business_id}")
            print(f"[ERROR] Return code: {result.returncode}")
            print(f"[ERROR] Error output: {result.stderr}")
            print(f"[ERROR] Standard output: {result.stdout}")
            update_scraping_status(business_id, "failed", error_msg, 0)
    except subprocess.TimeoutExpired:
        error_msg = "Scraping timed out. The website might be too large or slow."
        print(f"[ERROR] KB build timeout for business: {business_id}")
        update_scraping_status(business_id, "failed", error_msg, 0)
    except Exception as e:
        error_msg = f"Failed to build knowledge base: {str(e)}"
        print(f"[ERROR] Failed to trigger KB build for business {business_id}: {e}")
        import traceback
        traceback.print_exc()
        update_scraping_status(business_id, "failed", error_msg, 0)


@router.post("/admin/business")
async def create_or_update_business(request: Request, background_tasks: BackgroundTasks, api_key: str = Depends(get_api_key)):
    """
    Create or update a business configuration.
    Clients can use this to configure their chatbot.
    Accepts camelCase field names (standardized).
    Note: Knowledge base scraping must be triggered separately using the /scrape endpoint.
    """
    try:
        data = await request.json()
        
        # Accept both camelCase (businessId) and snake_case (business_id) for compatibility
        business_id = data.get("businessId") or data.get("business_id")
        if not business_id:
            raise HTTPException(
                status_code=400, 
                detail="businessId (or business_id) is required. Please include either 'businessId' or 'business_id' in your request."
            )
        
        # Accept both camelCase and snake_case for all fields
        website_url = data.get("websiteUrl") or data.get("website_url")
        
        config = config_manager.create_or_update_business(
            business_id=business_id,
            business_name=data.get("businessName") or data.get("business_name") or business_id,
            system_prompt=data.get("systemPrompt") or data.get("system_prompt") or "",
            greeting_message=data.get("greetingMessage") or data.get("greeting_message"),
            appointment_link=data.get("appointmentLink") or data.get("appointment_link"),
            primary_goal=data.get("primaryGoal") or data.get("primary_goal"),
            personality=data.get("personality"),
            privacy_statement=data.get("privacyStatement") or data.get("privacy_statement"),
            theme_color=data.get("themeColor") or data.get("theme_color") or "#2563eb",
            widget_position=data.get("widgetPosition") or data.get("widget_position") or "center",
            website_url=website_url,
            contact_email=data.get("contactEmail") or data.get("contact_email"),
            contact_phone=data.get("contactPhone") or data.get("contact_phone"),
            cta_tree=data.get("ctaTree") or data.get("cta_tree"),
            tertiary_ctas=data.get("tertiaryCtas") or data.get("tertiary_ctas"),
            nested_ctas=data.get("nestedCtas") or data.get("nested_ctas"),
            rules=data.get("rules"),
            custom_routes=data.get("customRoutes") or data.get("custom_routes"),
            available_services=data.get("availableServices") or data.get("available_services"),
            topic_ctas=data.get("topicCtas") or data.get("topic_ctas"),
            experiments=data.get("experiments"),
            voice_enabled=data.get("voiceEnabled") if "voiceEnabled" in data else (data.get("voice_enabled") if "voice_enabled" in data else False),
            chatbot_button_text=data.get("chatbotButtonText") or data.get("chatbot_button_text"),
            business_logo=data.get("businessLogo") or data.get("business_logo"),
        )
        
        return {
            "success": True, 
            "config": convert_config_to_camel(config)
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/admin/business/{business_id}/scrape")
async def trigger_scraping(business_id: str, background_tasks: BackgroundTasks, api_key: str = Depends(get_api_key)):
    """
    Manually trigger knowledge base scraping for a business.
    Requires the business to have a websiteUrl configured.
    """
    try:
        # Get business config to check if website_url exists
        config = config_manager.get_business(business_id)
        if not config:
            raise HTTPException(status_code=404, detail="Business not found")
        
        website_url = config.get("website_url")
        if not website_url or not website_url.strip():
            raise HTTPException(
                status_code=400, 
                detail="Business must have a websiteUrl configured to build knowledge base. Please set websiteUrl in the configuration first."
            )
        
        # Trigger knowledge base build in background
        background_tasks.add_task(trigger_kb_build, business_id, website_url.strip())
        print(f"[INFO] Manually triggered KB build for business: {business_id}, URL: {website_url}")
        
        return {
            "success": True,
            "message": "Knowledge base scraping started",
            "business_id": business_id,
            "website_url": website_url
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start scraping: {str(e)}")


@router.post("/admin/business/{business_id}/refresh-kb")
async def refresh_knowledge_base(business_id: str, background_tasks: BackgroundTasks, api_key: str = Depends(get_api_key)):
    """
    Refresh/rebuild the knowledge base for a business.
    This will re-scrape the website and rebuild the knowledge base from scratch.
    Useful when website content has been updated.
    """
    try:
        # Get business config to check if website_url exists
        config = config_manager.get_business(business_id)
        if not config:
            raise HTTPException(status_code=404, detail="Business not found")
        
        website_url = config.get("website_url")
        if not website_url or not website_url.strip():
            raise HTTPException(
                status_code=400, 
                detail="Business must have a websiteUrl configured to refresh knowledge base. Please set websiteUrl in the configuration first."
            )
        
        # Optional: Clear old index files before rebuilding
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        index_path = os.path.join(base_dir, "data", business_id, "index.faiss")
        meta_path = os.path.join(base_dir, "data", business_id, "meta.jsonl")
        
        # Clear old files if they exist
        if os.path.exists(index_path):
            try:
                os.remove(index_path)
                print(f"[INFO] Removed old index: {index_path}")
            except Exception as e:
                print(f"[WARNING] Could not remove old index: {e}")
        
        if os.path.exists(meta_path):
            try:
                os.remove(meta_path)
                print(f"[INFO] Removed old metadata: {meta_path}")
            except Exception as e:
                print(f"[WARNING] Could not remove old metadata: {e}")
        
        # Trigger knowledge base build in background
        background_tasks.add_task(trigger_kb_build, business_id, website_url.strip())
        print(f"[INFO] Refreshing KB for business: {business_id}, URL: {website_url}")
        
        return {
            "success": True,
            "message": "Knowledge base refresh started. Old content has been cleared and will be rebuilt.",
            "business_id": business_id,
            "website_url": website_url
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to refresh knowledge base: {str(e)}")


@router.get("/admin/business/{business_id}/scraping-status")
async def get_scraping_status(business_id: str, api_key: str = Depends(get_api_key)):
    """Get current scraping status for a business."""
    # Use absolute paths to avoid issues with working directory
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    status_file = os.path.join(base_dir, "data", business_id, "scraping_status.json")
    
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
        print(f"[DEBUG] list_all_businesses: calling config_manager.get_all_businesses()")
        businesses = config_manager.get_all_businesses()
        print(f"[DEBUG] list_all_businesses: config_manager returned {len(businesses)} businesses")
        print(f"[DEBUG] list_all_businesses: business IDs: {list(businesses.keys())}")
        
        # Convert all business configs to camelCase
        camel_businesses = {}
        for business_id, config in businesses.items():
            camel_businesses[business_id] = convert_config_to_camel(config)
        
        print(f"[DEBUG] list_all_businesses: returning {len(camel_businesses)} businesses in camelCase")
        return {"success": True, "businesses": camel_businesses}
    except Exception as e:
        print(f"[ERROR] list_all_businesses failed: {e}")
        import traceback
        traceback.print_exc()
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
