"""
Main FastAPI application entry point.
"""

import os
import json
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from google import genai
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from core.utils.logger import get_logger, IS_PRODUCTION, log_error
from core.middleware import RequestIDMiddleware

# Initialize logger
logger = get_logger("main")

# Database initialization (optional - will use file storage if database not available)
try:
    from core.database import init_db
    # Initialize database tables on startup
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.warning(f"Database initialization failed: {e}. Using file-based storage as fallback.")
except ImportError:
    logger.info("Database module not available. Using file-based storage.")

# Initialize RAG retriever
from core.rag_manager import initialize_default_retriever

# Import route modules
from api.routes import public, admin, business, chat, cta, analytics, voice

# --- SETUP AND CONFIGURATION ---

# Load environment variables (API Key)
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.critical("GEMINI_API_KEY is missing from environment variables.")
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
    title="WarmProspect Chatbot Platform",
    description="Multi-tenant AI chatbot platform with RAG and CRM integration",
    version="1.0.0"
)

# Add request ID middleware
app.add_middleware(RequestIDMiddleware)

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
        logger.warning("Invalid JSON in ALLOWED_ORIGINS. Defaulting based on environment.")
        ALLOWED_ORIGINS = ["*"] if not IS_PRODUCTION else []
else:
    # In production, default to empty (no CORS) unless explicitly set
    ALLOWED_ORIGINS = ["*"] if not IS_PRODUCTION else []
    if IS_PRODUCTION:
        logger.warning("ALLOWED_ORIGINS not set in production. CORS disabled. Set ALLOWED_ORIGINS env var.")

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

# Global exception handler for unhandled errors
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unhandled exceptions globally."""
    log_error(logger, exc, {"path": request.url.path, "method": request.method})
    
    if IS_PRODUCTION:
        # In production, return generic error message
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error. Please try again later."}
        )
    else:
        # In development, return detailed error
        import traceback
        return JSONResponse(
            status_code=500,
            content={
                "error": str(exc),
                "traceback": traceback.format_exc().split('\n')
            }
        )

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
