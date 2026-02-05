"""
Admin API routes (protected by API key authentication).
"""

import os
import json
import subprocess
import sys
import time
from typing import Dict, Any
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks, Depends
from core.security import get_api_key
from core.config.business_config import config_manager
from core.utils.helpers import convert_config_to_camel

router = APIRouter()


def update_scraping_status(business_id: str, status: str, message: str = "", progress: int = 0):
    """Update scraping status in database for frontend polling."""
    from core.database import scraping_status_db
    
    try:
        success = scraping_status_db.update_status(
            business_id=business_id,
            status=status,
            message=message,
            progress=progress
        )
        if success:
            print(f"[DEBUG] Updated scraping status for {business_id}: {status} - {message} ({progress}%)")
        else:
            print(f"[WARN] Failed to update scraping status for {business_id}, but continuing...")
    except Exception as e:
        print(f"[ERROR] Failed to update scraping status: {e}")
        import traceback
        traceback.print_exc()
        # Don't raise - allow scraping to continue even if status update fails


def trigger_kb_build(business_id: str, website_url: str):
    """
    Background task to build knowledge base for a business website.
    Runs the scraping script asynchronously and updates status.
    """
    print(f"[INFO] Background task started for business: {business_id}, URL: {website_url}")
    try:
        # Use absolute paths to avoid issues with working directory
        # Go up 3 levels: api/routes/admin.py -> api/routes -> api -> project root
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        script_path = os.path.join(base_dir, "scripts", "kb", "build_kb_for_business.py")
        
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
            
            # Update status (categories are stored in DB, not in status file)
            update_scraping_status(business_id, "completed", success_msg, 100)
        else:
            # Prefer last part of stderr (actual exception); strip InsecureRequestWarning so we show real error
            raw = (result.stderr or result.stdout or "").strip()
            lines = [ln for ln in raw.splitlines() if "InsecureRequestWarning" not in ln and "warnings.warn" not in ln]
            raw = "\n".join(lines).strip()
            error_snippet = raw[-500:] if len(raw) > 500 else raw
            if not error_snippet:
                error_snippet = f"Exit code {result.returncode}"
            # Clear message when Playwright browsers are missing (deploy script installs; user may need to re-deploy or set PLAYWRIGHT_BROWSERS_PATH)
            if "Playwright was just installed" in raw or "playwright install" in raw:
                error_snippet = (
                    "Playwright browsers not installed. Re-run deploy script or set PLAYWRIGHT_BROWSERS_PATH in .env and install Chromium; then restart the app and trigger Re-scrape."
                )
            error_msg = f"Scraping failed: {error_snippet}"
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
        
        # Check if business exists for partial update
        existing_business = config_manager.get_business(business_id)
        
        # Accept both camelCase and snake_case for all fields
        website_url = data.get("websiteUrl") or data.get("website_url")
        
        # Build update dict - only include fields that are explicitly provided in the request
        # This prevents overwriting existing values with None when field is not in update request
        update_data = {
            "business_id": business_id,
        }
        
        # Required fields for new businesses, optional for updates
        if not existing_business:
            # For new business, require business_name and system_prompt
            update_data["business_name"] = data.get("businessName") or data.get("business_name") or business_id
            update_data["system_prompt"] = data.get("systemPrompt") or data.get("system_prompt") or ""
        else:
            # For existing business, only update if explicitly provided
            if "businessName" in data or "business_name" in data:
                update_data["business_name"] = data.get("businessName") or data.get("business_name")
            if "systemPrompt" in data or "system_prompt" in data:
                update_data["system_prompt"] = data.get("systemPrompt") or data.get("system_prompt")
        
        # Optional fields - only include if explicitly provided in request
        if "greetingMessage" in data or "greeting_message" in data:
            update_data["greeting_message"] = data.get("greetingMessage") or data.get("greeting_message")
        if "primaryGoal" in data or "primary_goal" in data:
            update_data["primary_goal"] = data.get("primaryGoal") or data.get("primary_goal")
        if "personality" in data:
            update_data["personality"] = data.get("personality")
        if "privacyStatement" in data or "privacy_statement" in data:
            update_data["privacy_statement"] = data.get("privacyStatement") or data.get("privacy_statement")
        if "themeColor" in data or "theme_color" in data:
            update_data["theme_color"] = data.get("themeColor") or data.get("theme_color")
        if "widgetPosition" in data or "widget_position" in data:
            update_data["widget_position"] = data.get("widgetPosition") or data.get("widget_position")
        if "websiteUrl" in data or "website_url" in data:
            update_data["website_url"] = website_url
        if "contactEmail" in data or "contact_email" in data:
            update_data["contact_email"] = data.get("contactEmail") or data.get("contact_email")
        if "contactPhone" in data or "contact_phone" in data:
            update_data["contact_phone"] = data.get("contactPhone") or data.get("contact_phone")
        if "ctaTree" in data or "cta_tree" in data:
            update_data["cta_tree"] = data.get("ctaTree") or data.get("cta_tree")
        if "voiceEnabled" in data or "voice_enabled" in data:
            update_data["voice_enabled"] = data.get("voiceEnabled") if "voiceEnabled" in data else data.get("voice_enabled")
        if "chatbotButtonText" in data or "chatbot_button_text" in data:
            update_data["chatbot_button_text"] = data.get("chatbotButtonText") or data.get("chatbot_button_text")
        if "businessLogo" in data or "business_logo" in data:
            update_data["business_logo"] = data.get("businessLogo") or data.get("business_logo")
        if "enabledCategories" in data or "enabled_categories" in data:
            update_data["enabled_categories"] = data.get("enabledCategories") or data.get("enabled_categories")
            # Clear retriever cache when enabled categories change
            from core.rag import clear_retriever_cache
            clear_retriever_cache(business_id)
        
        # Call with only provided fields - this ensures partial updates don't overwrite with None
        config = config_manager.create_or_update_business(**update_data)
        
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
    Always clears old files and starts a fresh scrape.
    Check /scraping-status endpoint for progress.
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
        
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        index_path = os.path.join(base_dir, "data", business_id, "index.faiss")
        meta_path = os.path.join(base_dir, "data", business_id, "meta.jsonl")
        
        # Clear old KB files to start fresh (status is now in DB, will be updated)
        from core.database import scraping_status_db
        scraping_status_db.delete_status(business_id)  # Clear old status from DB
        
        try:
            for path in (meta_path, index_path):
                if os.path.exists(path):
                    os.remove(path)
                    print(f"[INFO] Deleted {path} for fresh scrape: {business_id}")
        except Exception as e:
            print(f"[WARN] Failed to clear old files: {e}")
        
        # Set initial status immediately (before background task starts)
        update_scraping_status(business_id, "pending", "Starting knowledge base build...", 0)
        print(f"[INFO] Setting initial status for business: {business_id}")
        
        # Trigger knowledge base build in background
        print(f"[INFO] Adding background task for KB build: business_id={business_id}, url={website_url.strip()}")
        background_tasks.add_task(trigger_kb_build, business_id, website_url.strip())
        print(f"[INFO] Background task added. Triggered KB build for business: {business_id}, URL: {website_url}")
        
        return {
            "success": True,
            "message": "Knowledge base scraping started",
            "business_id": business_id
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Failed to start scraping: {e}")
        import traceback
        traceback.print_exc()
        # Update status to failed
        try:
            update_scraping_status(business_id, "failed", f"Failed to start scraping: {str(e)}", 0)
        except:
            pass
        raise HTTPException(status_code=500, detail=f"Failed to start scraping: {str(e)}")


@router.get("/admin/business/{business_id}/scraping-status")
async def get_scraping_status(
    business_id: str, 
    api_key: str = Depends(get_api_key)
):
    """
    Get current scraping status for a business.
    Returns JSON response with status, message, and progress.
    Use X-Admin-API-Key header for authentication.
    """
    from core.database import scraping_status_db
    
    # Check if index file exists (for validation)
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    index_file = os.path.join(base_dir, "data", business_id, "index.faiss")
    index_exists = os.path.exists(index_file)
    
    # Get status from database
    status_data = scraping_status_db.get_status(business_id)
    
    # Default response if no status found
    response = {
        "status": "not_started",
        "message": "No scraping in progress",
        "progress": 0,
        "updated_at": time.time()
    }
    
    if status_data:
        response.update({
            "status": status_data.get("status", "not_started"),
            "message": status_data.get("message", "No scraping in progress"),
            "progress": status_data.get("progress", 0),
            "updated_at": status_data.get("updated_at", time.time())
        })
        
        # If status says "completed" but KB files were deleted, treat as stale
        if status_data.get("status") == "completed" and not index_exists:
            response["status"] = "not_started"
            response["message"] = "Knowledge base was removed. Click Start Scraping to rebuild."
            response["progress"] = 0
            # Delete stale status from DB
            scraping_status_db.delete_status(business_id)
            print(f"[INFO] Removed stale status (KB files missing): {business_id}")
        
        # Auto-fix: If categories exist but status is stuck, update to completed
        # BUT: Don't auto-fix if status was recently set to "pending" (within last 60 seconds)
        elif index_exists:
            db_config = config_manager.get_business(business_id)
            categories_exist = db_config and db_config.get("categories") is not None
            
            updated_at = status_data.get("updated_at", 0)
            status_age = time.time() - updated_at if updated_at else 0
            is_recent_pending = status_data.get("status") == "pending" and status_age < 60
            status_message = status_data.get("message", "").lower()
            is_fresh_start = any(keyword in status_message for keyword in ["starting", "preparing", "beginning"])
            
            # Only auto-fix if:
            # - Categories and index exist
            # - Status is not recently set to pending (>= 60 seconds old)
            # - Message doesn't indicate a fresh start
            if categories_exist and status_data.get("status") in ["pending", "scraping", "categorizing", "indexing"] and not is_recent_pending and not is_fresh_start:
                print(f"[INFO] Auto-fixing stuck status for {business_id}: categories and index exist but status is {status_data.get('status')}")
                scraping_status_db.update_status(
                    business_id=business_id,
                    status="completed",
                    message="Knowledge base built successfully!",
                    progress=100
                )
                response.update({
                    "status": "completed",
                    "message": "Knowledge base built successfully!",
                    "progress": 100,
                    "updated_at": time.time()
                })
                print(f"[SUCCESS] Auto-fixed status for {business_id}")
    
    return response


@router.get("/admin/business/{business_id}")
async def get_business_config(business_id: str, api_key: str = Depends(get_api_key)):
    """Get business configuration by ID. Returns camelCase field names."""
    try:
        config = config_manager.get_business(business_id)
        if not config:
            raise HTTPException(status_code=404, detail="Business not found")
        
        camel_config = convert_config_to_camel(config)
        return {"success": True, "config": camel_config}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Failed to get business config for {business_id}: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to retrieve business configuration: {str(e)}")


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
