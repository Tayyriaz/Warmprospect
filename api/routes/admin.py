"""
Admin API routes (protected by API key authentication).
"""

import os
import json
import subprocess
import sys
import time
import asyncio
from typing import Dict, Any
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse
from core.security import get_api_key, get_api_key_header_or_query
from core.config.business_config import config_manager
from core.utils.helpers import convert_config_to_camel

router = APIRouter()


def update_scraping_status(business_id: str, status: str, message: str = "", progress: int = 0, categories_data: Dict[str, Any] = None):
    """Update scraping status in a JSON file for frontend polling."""
    try:
        # Use absolute paths to avoid issues with working directory
        # Go up 3 levels: api/routes/admin.py -> api/routes -> api -> project root
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        status_file = os.path.join(base_dir, "data", business_id, "scraping_status.json")
        status_dir = os.path.dirname(status_file)
        
        # Create directory if it doesn't exist
        try:
            os.makedirs(status_dir, exist_ok=True)
        except PermissionError as pe:
            print(f"[ERROR] Cannot create directory {status_dir}: Permission denied.")
            print(f"[ERROR] Run 'sudo chown -R www-data:www-data {base_dir}/data/' to fix permissions.")
            print(f"[ERROR] Status updates will be skipped, but scraping may still work.")
            return  # Don't raise - allow scraping to continue
        
        status_data = {
            "status": status,  # "pending", "scraping", "indexing", "completed", "failed"
            "message": message,
            "progress": progress,  # 0-100
            "updated_at": time.time()
        }
        
        # Include categories if provided
        if categories_data:
            # Get enabled categories from database
            config = config_manager.get_business(business_id)
            enabled_categories = config.get("enabled_categories", []) if config else []
            
            # Update category enabled status based on database
            categories = categories_data.get("categories", [])
            for cat in categories:
                cat["enabled"] = cat["name"] in enabled_categories if enabled_categories else True
            
            status_data["categories"] = categories
            status_data["total_pages"] = categories_data.get("total_pages", 0)
        
        # Write status file
        try:
            with open(status_file, "w", encoding="utf-8") as f:
                json.dump(status_data, f)
                f.flush()  # Ensure data is written immediately
                os.fsync(f.fileno())  # Force write to disk
            print(f"[DEBUG] Updated scraping status for {business_id}: {status} - {message} ({progress}%)")
        except PermissionError as pe:
            print(f"[ERROR] Cannot write status file {status_file}: Permission denied.")
            print(f"[ERROR] Run 'sudo chown -R www-data:www-data {base_dir}/data/' to fix permissions.")
            print(f"[ERROR] Status updates will be skipped, but scraping may still work.")
            return  # Don't raise - allow scraping to continue
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
            
            # Load categories from database
            categories_data = None
            try:
                config = config_manager.get_business(business_id)
                if config and config.get("categories"):
                    categories_data = config["categories"]
                    print(f"[SUCCESS] Loaded categories from DB: {len(categories_data.get('categories', []))} categories")
            except Exception as e:
                print(f"[WARN] Failed to load categories from DB: {e}")
            
            # Update status with categories included
            update_scraping_status(business_id, "completed", success_msg, 100, categories_data)
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
        
        # Call with only provided fields - this ensures partial updates don't overwrite with None
        config = config_manager.create_or_update_business(**update_data)
        
        return {
            "success": True, 
            "config": convert_config_to_camel(config)
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/admin/business/{business_id}/scrape")
async def trigger_scraping(business_id: str, request: Request, background_tasks: BackgroundTasks, api_key: str = Depends(get_api_key)):
    """
    Manually trigger knowledge base scraping for a business.
    Requires the business to have a websiteUrl configured.
    Returns categories when scraping completes (check status endpoint for progress).
    If force=true in request body, will re-scrape even if already completed.
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
        
        # Check for force parameter
        force_rescrape = False
        try:
            body = await request.json()
            force_rescrape = body.get("force", False)
        except:
            pass  # No body or invalid JSON, continue normally
        
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        status_file = os.path.join(base_dir, "data", business_id, "scraping_status.json")
        index_path = os.path.join(base_dir, "data", business_id, "index.faiss")
        
        response = {
            "success": True,
            "message": "Knowledge base scraping started",
            "business_id": business_id,
            "website_url": website_url
        }
        
        # If forcing re-scrape, clear old status and KB files so build runs from scratch
        if force_rescrape:
            try:
                if os.path.exists(status_file):
                    os.remove(status_file)
                    print(f"[INFO] Deleted old status file for force re-scrape: {business_id}")
                meta_path = os.path.join(base_dir, "data", business_id, "meta.jsonl")
                for path in (meta_path, index_path):
                    if os.path.exists(path):
                        os.remove(path)
                        print(f"[INFO] Deleted {path} for force re-scrape: {business_id}")
            except Exception as e:
                print(f"[WARN] Failed to clear old files for re-scrape: {e}")
        
        # If scraping was already completed and NOT forcing re-scrape, check if KB files actually exist
        # If KB files are missing, treat as stale status and start scraping anyway
        if not force_rescrape:
            try:
                if os.path.exists(status_file):
                    with open(status_file, "r", encoding="utf-8") as f:
                        status_data = json.load(f)
                        if status_data.get("status") == "completed":
                            # Only return early if KB files actually exist
                            # If KB files were deleted, status is stale - start scraping
                            if os.path.exists(index_path):
                                # KB files exist, so scraping is truly completed - return existing categories
                                db_config = config_manager.get_business(business_id)
                                if db_config and db_config.get("categories"):
                                    categories_data = db_config["categories"]
                                    enabled_categories = db_config.get("enabled_categories", [])
                                    
                                    # Update category enabled status
                                    categories = categories_data.get("categories", [])
                                    for cat in categories:
                                        cat["enabled"] = cat["name"] in enabled_categories if enabled_categories else True
                                    
                                    response["categories"] = categories
                                    response["total_pages"] = categories_data.get("total_pages", 0)
                                    response["message"] = "Scraping already completed. Categories included."
                                    return response
                            else:
                                # Status says "completed" but KB files are missing - stale status, start scraping
                                print(f"[INFO] Status file says 'completed' but KB files missing for {business_id}. Starting fresh scrape.")
                                # Delete stale status file so scraping can proceed
                                try:
                                    os.remove(status_file)
                                    print(f"[INFO] Deleted stale status file for {business_id}")
                                except Exception as e:
                                    print(f"[WARN] Failed to delete stale status file: {e}")
            except Exception as e:
                print(f"[WARN] Failed to check existing status: {e}")
        
        # Set initial status immediately (before background task starts)
        update_scraping_status(business_id, "pending", "Starting knowledge base build...", 0)
        print(f"[INFO] Setting initial status for business: {business_id} (force={force_rescrape})")
        print(f"[INFO] Status file should be at: {os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'data', business_id, 'scraping_status.json')}")
        
        # Trigger knowledge base build in background
        print(f"[INFO] Adding background task for KB build: business_id={business_id}, url={website_url.strip()}")
        background_tasks.add_task(trigger_kb_build, business_id, website_url.strip())
        print(f"[INFO] Background task added. Manually triggered KB build for business: {business_id}, URL: {website_url}")
        
        return response
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
        # Go up 3 levels: api/routes/admin.py -> api/routes -> api -> project root
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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
        
        # Set initial status immediately (before background task starts)
        update_scraping_status(business_id, "pending", "Starting knowledge base refresh...", 0)
        print(f"[INFO] Setting initial status for refresh: {business_id}")
        
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
async def get_scraping_status(
    business_id: str, 
    request: Request,
    stream: bool = False,
    api_key: str = Depends(get_api_key_header_or_query)
):
    """
    Get current scraping status for a business, including categories if available.
    
    Supports both JSON response and Server-Sent Events (SSE) streaming:
    - Default: Returns JSON response
    - Set ?stream=true or Accept: text/event-stream header for SSE streaming
    """
    # Check if SSE is requested (via query param or Accept header)
    accept_header = request.headers.get("accept", "")
    use_sse = stream or "text/event-stream" in accept_header
    
    if use_sse:
        # Return SSE stream
        async def event_generator():
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            status_file = os.path.join(base_dir, "data", business_id, "scraping_status.json")
            index_file = os.path.join(base_dir, "data", business_id, "index.faiss")
            last_status = None
            last_sent_time = 0
            
            # Helper function to read and process status
            def read_status():
                status_data = {
                    "status": "not_started",
                    "message": "No scraping in progress",
                    "progress": 0
                }
                
                db_config = config_manager.get_business(business_id)
                categories_exist = db_config and db_config.get("categories") is not None
                index_exists = os.path.exists(index_file)
                
                if os.path.exists(status_file):
                    try:
                        with open(status_file, "r", encoding="utf-8") as f:
                            file_status = json.load(f)
                            status_data.update(file_status)
                            
                            # Stale: status says "completed" but KB files were deleted
                            if file_status.get("status") == "completed" and not index_exists:
                                status_data["status"] = "not_started"
                                status_data["message"] = "Knowledge base was removed. Click Re-scrape to rebuild."
                                status_data["progress"] = 0
                                for key in ["categories", "total_pages"]:
                                    status_data.pop(key, None)
                            # Auto-fix: stuck status when index exists
                            elif index_exists:
                                status_age = time.time() - file_status.get("updated_at", 0)
                                is_recent_pending = file_status.get("status") == "pending" and status_age < 60
                                status_message = file_status.get("message", "").lower()
                                is_fresh_start = any(keyword in status_message for keyword in ["starting", "preparing", "beginning"])
                                if categories_exist and file_status.get("status") in ["pending", "scraping", "categorizing", "indexing"] and not is_recent_pending and not is_fresh_start:
                                    categories_data = db_config.get("categories")
                                    status_data["status"] = "completed"
                                    status_data["message"] = "Knowledge base built successfully!"
                                    status_data["progress"] = 100
                                    status_data["categories"] = categories_data.get("categories", [])
                                    status_data["total_pages"] = categories_data.get("total_pages", 0)
                    except Exception as e:
                        print(f"[ERROR] Failed to read status file in SSE: {e}")
                
                # Add categories from database if available
                if categories_exist:
                    try:
                        categories_data = db_config.get("categories")
                        enabled_categories = db_config.get("enabled_categories", [])
                        
                        categories = categories_data.get("categories", [])
                        for cat in categories:
                            cat["enabled"] = cat["name"] in enabled_categories if enabled_categories else True
                        
                        status_data["categories"] = categories
                        status_data["total_pages"] = categories_data.get("total_pages", 0)
                    except Exception as e:
                        print(f"[ERROR] Failed to read categories from DB in SSE: {e}")
                
                # Add timestamp for "updated X seconds ago" display
                current_time = time.time()
                updated_at = status_data.get("updated_at", current_time)
                status_data["updated_at"] = updated_at
                status_data["updated_ago"] = int(current_time - updated_at)
                
                return status_data
            
            # Send initial connection message
            yield f"data: {json.dumps({'type': 'connected', 'message': 'Connected to status stream'})}\n\n"
            
            # Send initial status immediately (don't wait for loop)
            initial_status = read_status()
            last_status = (initial_status.get("status"), initial_status.get("progress"))
            last_sent_time = time.time()
            yield f"data: {json.dumps(initial_status)}\n\n"
            
            # Stop streaming if already completed or failed
            if initial_status.get("status") in ["completed", "failed"]:
                return
            
            while True:
                try:
                    # Read status
                    status_data = read_status()
                    
                    # Send update if status/progress changed OR heartbeat every 2s
                    current_status_key = (status_data.get("status"), status_data.get("progress"))
                    current_time = time.time()
                    should_send = (
                        current_status_key != last_status or
                        (current_time - last_sent_time) >= 2
                    )
                    
                    if should_send:
                        last_status = current_status_key
                        last_sent_time = current_time
                        yield f"data: {json.dumps(status_data)}\n\n"
                        
                        # Stop streaming if completed or failed
                        if status_data.get("status") in ["completed", "failed"]:
                            break
                    
                    await asyncio.sleep(1)
                    
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    print(f"[ERROR] SSE error: {e}")
                    yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
                    await asyncio.sleep(1)
        
        return StreamingResponse(
            event_generator(), 
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"  # Disable nginx buffering
            }
        )
    
    # Regular JSON response (existing logic)
    # Use absolute paths to avoid issues with working directory
    # Go up 3 levels: api/routes/admin.py -> api/routes -> api -> project root
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    status_file = os.path.join(base_dir, "data", business_id, "scraping_status.json")
    index_file = os.path.join(base_dir, "data", business_id, "index.faiss")
    
    response = {
        "status": "not_started",
        "message": "No scraping in progress",
        "progress": 0
    }
    
    # Check if categories exist in database and index file exists
    db_config = config_manager.get_business(business_id)
    categories_exist = db_config and db_config.get("categories") is not None
    index_exists = os.path.exists(index_file)
    
    if os.path.exists(status_file):
        try:
            with open(status_file, "r", encoding="utf-8") as f:
                status_data = json.load(f)
                response.update(status_data)
                
                # If status says "completed" but KB files were deleted, treat as stale (don't show Complete!)
                if status_data.get("status") == "completed" and not index_exists:
                    response["status"] = "not_started"
                    response["message"] = "Knowledge base was removed. Click Re-scrape to rebuild."
                    response["progress"] = 0
                    if "categories" in response:
                        del response["categories"]
                    if "total_pages" in response:
                        del response["total_pages"]
                    try:
                        os.remove(status_file)
                        print(f"[INFO] Removed stale status file (KB files missing): {business_id}")
                    except Exception:
                        pass
                # Auto-fix: If categories exist but status is stuck, update to completed
                # BUT: Don't auto-fix if status was recently set to "pending" (within last 60 seconds)
                # This prevents auto-completing a fresh re-scrape
                elif index_exists:
                    status_age = time.time() - status_data.get("updated_at", 0)
                    is_recent_pending = status_data.get("status") == "pending" and status_age < 60
                    status_message = status_data.get("message", "").lower()
                    is_fresh_start = any(keyword in status_message for keyword in ["starting", "preparing", "beginning"])
                    # Only auto-fix if:
                    # - Categories and index exist
                    # - Status is not recently set to pending (>= 60 seconds old)
                    # - Message doesn't indicate a fresh start
                    if categories_exist and status_data.get("status") in ["pending", "scraping", "categorizing", "indexing"] and not is_recent_pending and not is_fresh_start:
                        print(f"[INFO] Auto-fixing stuck status for {business_id}: categories and index exist but status is {status_data.get('status')}")
                        try:
                            # Load categories from database
                            categories_data = db_config.get("categories")
                            
                            # Update status to completed
                            status_data["status"] = "completed"
                            status_data["message"] = "Knowledge base built successfully!"
                            status_data["progress"] = 100
                            status_data["updated_at"] = time.time()
                            status_data["categories"] = categories_data.get("categories", [])
                            status_data["total_pages"] = categories_data.get("total_pages", 0)
                            
                            # Write updated status
                            with open(status_file, "w", encoding="utf-8") as f:
                                json.dump(status_data, f, indent=2)
                            
                            response.update(status_data)
                            print(f"[SUCCESS] Auto-fixed status for {business_id}")
                        except Exception as e:
                            print(f"[WARN] Failed to auto-fix status: {e}")
        except Exception as e:
            print(f"[ERROR] Failed to read status file: {e}")
    
    # Add categories if available from database (only when KB exists, so we don't show stale "1 page" after user deleted files)
    if categories_exist and index_exists:
        try:
            categories_data = db_config.get("categories")
            enabled_categories = db_config.get("enabled_categories", [])
            
            # Update category enabled status based on database
            categories = categories_data.get("categories", [])
            for cat in categories:
                cat["enabled"] = cat["name"] in enabled_categories if enabled_categories else True
            
            response["categories"] = categories
            response["total_pages"] = categories_data.get("total_pages", 0)
        except Exception as e:
            print(f"[ERROR] Failed to read categories from database: {e}")
    
    return response


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


@router.post("/admin/business/{business_id}/categories")
async def update_enabled_categories(
    business_id: str, 
    request: Request,
    api_key: str = Depends(get_api_key)
):
    """Update enabled categories for a business's knowledge base."""
    try:
        data = await request.json()
        enabled_categories = data.get("enabled_categories", [])
        
        if not isinstance(enabled_categories, list):
            raise HTTPException(status_code=400, detail="enabled_categories must be a list")
        
        # Get current config
        config = config_manager.get_business(business_id)
        if not config:
            raise HTTPException(status_code=404, detail="Business not found")
        
        # Update enabled categories in database
        from core.database import BusinessConfigDB
        from core.rag import clear_retriever_cache
        db_manager = BusinessConfigDB()
        
        # Get all current config values
        updated_config = db_manager.create_or_update_business(
            business_id=config["business_id"],
            business_name=config["business_name"],
            system_prompt=config["system_prompt"],
            greeting_message=config.get("greeting_message"),
            primary_goal=config.get("primary_goal"),
            personality=config.get("personality"),
            privacy_statement=config.get("privacy_statement"),
            theme_color=config.get("theme_color"),
            widget_position=config.get("widget_position"),
            website_url=config.get("website_url"),
            contact_email=config.get("contact_email"),
            contact_phone=config.get("contact_phone"),
            cta_tree=config.get("cta_tree"),
            voice_enabled=config.get("voice_enabled", False),
            chatbot_button_text=config.get("chatbot_button_text"),
            business_logo=config.get("business_logo"),
            enabled_categories=enabled_categories,
        )
        
        # Clear retriever cache so it reloads with new categories
        clear_retriever_cache(business_id)
        
        return {
            "success": True,
            "message": "Enabled categories updated",
            "business_id": business_id,
            "enabled_categories": enabled_categories
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Failed to update enabled categories: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to update enabled categories: {str(e)}")


@router.get("/admin")
async def admin_panel():
    """Serve the admin configuration panel."""
    from fastapi.responses import FileResponse
    return FileResponse("static/admin.html")
