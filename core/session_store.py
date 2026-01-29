import json
import os
import redis
from core.utils.logger import get_logger

# REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
# For local dev/POC, we can default to localhost if not set, 
# BUT strict production roadmap says we should enforce it.
# Reverting to allow local run without explicit env var, but warning.
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", str(7 * 24 * 3600)))

# Initialize logger
logger = get_logger("session_store")

# Global flag to track Redis availability
REDIS_AVAILABLE = False

try:
    r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    r.ping()
    REDIS_AVAILABLE = True
    logger.info("Connected to Redis successfully")
except Exception as e:
    logger.warning(f"Redis not found at {REDIS_URL}. Using in-memory storage for this session.")
    r = None

# In-memory fallback storage
_in_memory_sessions = {}

def load_session(user_id: str, default_factory):
    """
    Load a session. Tries Redis first, then in-memory.
    """
    if REDIS_AVAILABLE and r:
        try:
            raw = r.get(user_id)
            if raw:
                session = json.loads(raw)
                logger.debug(f"Loaded session from Redis: {user_id}")
                return session
        except Exception as e:
            logger.debug(f"Redis load error: {e}")

    # Fallback to In-Memory
    if user_id in _in_memory_sessions:
        logger.debug(f"Loaded session from In-Memory: {user_id}")
        return _in_memory_sessions[user_id]
    
    logger.debug(f"Creating new session for: {user_id}")
    return default_factory()


def save_session(user_id: str, session: dict):
    """
    Persist a session. Always saves to in-memory, and to Redis if available.
    """
    # Always update in-memory
    _in_memory_sessions[user_id] = session
    
    if REDIS_AVAILABLE and r:
        try:
            r.setex(user_id, SESSION_TTL_SECONDS, json.dumps(session))
            logger.debug(f"Saved session to Redis: {user_id}")
        except Exception as e:
            logger.debug(f"Redis save error: {e}")

