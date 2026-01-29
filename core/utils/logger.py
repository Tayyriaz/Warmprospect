"""
Structured logging utility for production-ready logging.
"""

import os
import sys
import logging
from typing import Optional
from datetime import datetime

# Environment detection
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
IS_PRODUCTION = ENVIRONMENT in ["production", "prod"]
IS_DEVELOPMENT = not IS_PRODUCTION

# Configure logging format
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Set up root logger
logging.basicConfig(
    level=logging.INFO if IS_PRODUCTION else logging.DEBUG,
    format=LOG_FORMAT,
    datefmt=DATE_FORMAT,
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Create logger instance
logger = logging.getLogger("warmprospect")


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Get a logger instance with optional name."""
    if name:
        return logging.getLogger(f"warmprospect.{name}")
    return logger


def log_error(logger_instance: logging.Logger, error: Exception, context: Optional[dict] = None):
    """Log error with context, hiding sensitive details in production."""
    error_msg = str(error)
    
    if IS_PRODUCTION:
        # In production, log error but don't expose traceback to users
        logger_instance.error(
            f"Error occurred: {error_msg}",
            extra={"context": context or {}}
        )
    else:
        # In development, log full details
        import traceback
        logger_instance.error(
            f"Error occurred: {error_msg}\n{traceback.format_exc()}",
            extra={"context": context or {}}
        )


def log_request(logger_instance: logging.Logger, method: str, path: str, **kwargs):
    """Log HTTP request details."""
    logger_instance.info(
        f"{method} {path}",
        extra=kwargs
    )


def log_response(logger_instance: logging.Logger, status_code: int, **kwargs):
    """Log HTTP response details."""
    logger_instance.info(
        f"Response: {status_code}",
        extra=kwargs
    )
