import os
from typing import Optional
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader
from dotenv import load_dotenv

load_dotenv()

API_KEY_NAME = "X-Admin-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

ADMIN_API_KEY = os.getenv("ADMIN_API_KEY")


def _validate_api_key(value: Optional[str]):
    """Validate value against ADMIN_API_KEY. Raises HTTPException if invalid."""
    if not ADMIN_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server security misconfiguration: ADMIN_API_KEY not set.",
        )
    if not value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing API key. Please provide X-Admin-API-Key header.",
        )
    if value != ADMIN_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key. Could not validate credentials.",
        )
    return value


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
    return _validate_api_key(api_key_header)


