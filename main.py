"""
Main FastAPI application entry point.
"""

import os
import json
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Database initialization (optional - will use file storage if database not available)
try:
    from core.database import init_db
    # Initialize database tables on startup
    try:
        init_db()
        print("✅ Database initialized successfully!")
    except Exception as e:
        print(f"[WARNING] Database initialization failed: {e}")
        print("[INFO] Using file-based storage as fallback.")
except ImportError:
    print("[INFO] Database module not available. Using file-based storage.")

# Initialize RAG retriever
from core.rag_manager import initialize_default_retriever

# Import route modules
from api.routes import public, admin, business, chat, cta, analytics, voice

# --- SETUP AND CONFIGURATION ---

# Load environment variables (API Key)
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("!!! [CRITICAL ERROR] GEMINI_API_KEY is missing from environment variables.")
    print("!!! Please ensure .env file exists and contains GEMINI_API_KEY.")
    raise ValueError("GEMINI_API_KEY not found in .env file.")

client = genai.Client(api_key=GEMINI_API_KEY)
# Using GEMINI_MODEL from .env or defaulting to gemini-2.5-flash
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Port configuration (for deployment platforms like Render)
PORT = int(os.getenv("PORT", "8000")) 

# Clamp how many history turns we send to Gemini to control token use
MAX_HISTORY_TURNS = int(os.getenv("MAX_HISTORY_TURNS", "20"))

# Initialize FastAPI App
app = FastAPI(
    title="GoAccel Concierge Bot API",
    description="API for managing chatbot businesses, scraping websites, and handling conversations",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure API key authentication for Swagger UI
from fastapi.openapi.utils import get_openapi

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    
    # Add security scheme for API key
    if "components" not in openapi_schema:
        openapi_schema["components"] = {}
    if "securitySchemes" not in openapi_schema["components"]:
        openapi_schema["components"]["securitySchemes"] = {}
    
    openapi_schema["components"]["securitySchemes"]["ApiKeyAuth"] = {
        "type": "apiKey",
        "in": "header",
        "name": "X-Admin-API-Key",
        "description": "Enter your Admin API Key from .env file (ADMIN_API_KEY)"
    }
    
    # Apply security to all admin endpoints
    for path, methods in openapi_schema.get("paths", {}).items():
        if "/admin" in path:
            for method_name, method_info in methods.items():
                if isinstance(method_info, dict) and method_name.lower() in ["get", "post", "put", "delete", "patch"]:
                    if "security" not in method_info:
                        method_info["security"] = []
                    # Add API key security if not already present
                    if {"ApiKeyAuth": []} not in method_info["security"]:
                        method_info["security"].append({"ApiKeyAuth": []})
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# Rate Limiter Setup
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add CORS middleware to allow frontend requests
# Hardened CORS: Use env var or default to specific domains, not wildcard in production
allowed_origins_env = os.getenv("ALLOWED_ORIGINS")
if allowed_origins_env:
    try:
        ALLOWED_ORIGINS = json.loads(allowed_origins_env)
    except json.JSONDecodeError:
        print(f"[WARNING] Invalid JSON in ALLOWED_ORIGINS. Defaulting to ['*']")
        ALLOWED_ORIGINS = ["*"]
else:
    ALLOWED_ORIGINS = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize default RAG retriever
initialize_default_retriever()

# Initialize chat router with dependencies
chat.init_chat_router(client, MODEL_NAME, MAX_HISTORY_TURNS)

# Note: Limiters in routers will use app.state.limiter automatically via request
# The limiter decorator accesses app.state.limiter through the request object

# Serve static frontend
app.mount("/static", StaticFiles(directory="static"), name="static")

# Register route modules
app.include_router(public.router)
app.include_router(admin.router)
app.include_router(business.router)
app.include_router(chat.router)
app.include_router(cta.router)
app.include_router(analytics.router)
app.include_router(voice.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
