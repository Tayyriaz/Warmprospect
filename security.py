import os
from typing import Optional
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader
from dotenv import load_dotenv

load_dotenv()

API_KEY_NAME = "X-Admin-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

ADMIN_API_KEY = os.getenv("ADMIN_API_KEY")

async def get_api_key(api_key_header: Optional[str] = Security(api_key_header)):
    """
    Validate admin API key from request header.
    
    Args:
        api_key_header: The API key from X-Admin-API-Key header (can be None if header is missing)
    
    Returns:
        The validated API key string
    
    Raises:
        HTTPException: 500 if ADMIN_API_KEY not configured, 403 if key is invalid or missing
    """
    if not ADMIN_API_KEY:
        # If no key is configured in env, fail secure (or warn, but strictly failing is safer for "locking down")
        # However, to avoid breaking local dev if they haven't set it yet, we might want to log a warning.
        # But for "Roadmap to Production", we should enforce it.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server security misconfiguration: ADMIN_API_KEY not set."
        )

    # Check if API key header is provided
    if not api_key_header:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing API key. Please provide X-Admin-API-Key header."
        )

    # Validate the API key
    if api_key_header == ADMIN_API_KEY:
        return api_key_header
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Invalid API key. Could not validate credentials."
    )
