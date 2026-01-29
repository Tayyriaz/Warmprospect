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
            print(f"[DEBUG] Updated scraping status for {business_id}: {status} - {message}")
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
            
            # Load categories if available
            categories_file = os.path.join(base_dir, "data", business_id, "categories.json")
            categories_data = None
            if os.path.exists(categories_file):
                try:
                    with open(categories_file, "r", encoding="utf-8") as f:
                        categories_data = json.load(f)
                        print(f"[SUCCESS] Loaded categories: {len(categories_data.get('categories', []))} categories")
                except Exception as e:
                    print(f"[WARN] Failed to load categories file: {e}")
            
            # Update status with categories included
            update_scraping_status(business_id, "completed", success_msg, 100, categories_data)
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
            # appointment_link removed - use CTA tree with redirect action instead
            primary_goal=data.get("primaryGoal") or data.get("primary_goal"),
            personality=data.get("personality"),
            privacy_statement=data.get("privacyStatement") or data.get("privacy_statement"),
            theme_color=data.get("themeColor") or data.get("theme_color") or "#2563eb",
            widget_position=data.get("widgetPosition") or data.get("widget_position") or "center",
            website_url=website_url,
            contact_email=data.get("contactEmail") or data.get("contact_email"),
            contact_phone=data.get("contactPhone") or data.get("contact_phone"),
            cta_tree=data.get("ctaTree") or data.get("cta_tree"),
            rules=data.get("rules"),
            custom_routes=data.get("customRoutes") or data.get("custom_routes"),
            available_services=data.get("availableServices") or data.get("available_services"),
            topic_ctas=data.get("topicCtas") or data.get("topic_ctas"),
            experiments=data.get("experiments"),
            voice_enabled=data.get("voiceEnabled") if "voiceEnabled" in data else (data.get("voice_enabled") if "voice_enabled" in data else False),
            chatbot_button_text=data.get("chatbotButtonText") or data.get("chatbot_button_text"),
            business_logo=data.get("businessLogo") or data.get("business_logo"),
            enabled_categories=data.get("enabledCategories") or data.get("enabled_categories"),
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
    Returns categories when scraping completes (check status endpoint for progress).
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
        
        # Check if scraping is already completed and return categories if available
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        status_file = os.path.join(base_dir, "data", business_id, "scraping_status.json")
        categories_file = os.path.join(base_dir, "data", business_id, "categories.json")
        
        response = {
            "success": True,
            "message": "Knowledge base scraping started",
            "business_id": business_id,
            "website_url": website_url
        }
        
        # If scraping was already completed, include categories in response
        if os.path.exists(status_file) and os.path.exists(categories_file):
            try:
                with open(status_file, "r", encoding="utf-8") as f:
                    status_data = json.load(f)
                    if status_data.get("status") == "completed":
                        with open(categories_file, "r", encoding="utf-8") as cf:
                            categories_data = json.load(cf)
                            enabled_categories = config.get("enabled_categories", [])
                            
                            # Update category enabled status
                            categories = categories_data.get("categories", [])
                            for cat in categories:
                                cat["enabled"] = cat["name"] in enabled_categories if enabled_categories else True
                            
                            response["categories"] = categories
                            response["total_pages"] = categories_data.get("total_pages", 0)
                            response["message"] = "Scraping already completed. Categories included."
                            return response
            except Exception as e:
                print(f"[WARN] Failed to load existing categories: {e}")
        
        # Set initial status immediately (before background task starts)
        update_scraping_status(business_id, "pending", "Starting knowledge base build...", 0)
        print(f"[INFO] Setting initial status for business: {business_id}")
        
        # Trigger knowledge base build in background
        background_tasks.add_task(trigger_kb_build, business_id, website_url.strip())
        print(f"[INFO] Manually triggered KB build for business: {business_id}, URL: {website_url}")
        
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
async def get_scraping_status(business_id: str, api_key: str = Depends(get_api_key)):
    """Get current scraping status for a business, including categories if available."""
    # Use absolute paths to avoid issues with working directory
    # Go up 3 levels: api/routes/admin.py -> api/routes -> api -> project root
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    status_file = os.path.join(base_dir, "data", business_id, "scraping_status.json")
    categories_file = os.path.join(base_dir, "data", business_id, "categories.json")
    index_file = os.path.join(base_dir, "data", business_id, "index.faiss")
    
    response = {
        "status": "not_started",
        "message": "No scraping in progress",
        "progress": 0
    }
    
    # Check if categories.json exists - this indicates scraping completed
    categories_exist = os.path.exists(categories_file)
    index_exists = os.path.exists(index_file)
    
    if os.path.exists(status_file):
        try:
            with open(status_file, "r", encoding="utf-8") as f:
                status_data = json.load(f)
                response.update(status_data)
                
                # Auto-fix: If categories exist but status is stuck, update to completed
                if categories_exist and index_exists and status_data.get("status") in ["pending", "scraping", "categorizing", "indexing"]:
                    print(f"[INFO] Auto-fixing stuck status for {business_id}: categories and index exist but status is {status_data.get('status')}")
                    try:
                        with open(categories_file, "r", encoding="utf-8") as cf:
                            categories_data = json.load(cf)
                        
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
    
    # Add categories if available
    if categories_exist:
        try:
            with open(categories_file, "r", encoding="utf-8") as f:
                categories_data = json.load(f)
                # Get enabled categories from database
                config = config_manager.get_business(business_id)
                enabled_categories = config.get("enabled_categories", []) if config else []
                
                # Update category enabled status based on database
                for cat in categories_data.get("categories", []):
                    cat["enabled"] = cat["name"] in enabled_categories if enabled_categories else True
                
                response["categories"] = categories_data.get("categories", [])
                response["total_pages"] = categories_data.get("total_pages", 0)
        except Exception as e:
            print(f"[ERROR] Failed to read categories file: {e}")
    
    return response
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
        from core.rag_manager import clear_retriever_cache
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
