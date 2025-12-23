import json
import os
import redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", str(7 * 24 * 3600)))

# decode_responses so we read/write strings
r = redis.Redis.from_url(REDIS_URL, decode_responses=True)


def load_session(user_id: str, default_factory):
    """
    Load a session from Redis. If missing or invalid, return default_factory().
    """
    try:
        raw = r.get(user_id)
        if raw:
            session = json.loads(raw)
            print(f"[DEBUG] Loaded session from Redis for user_id: {user_id}, history length: {len(session.get('history', []))}")
            return session
        else:
            print(f"[DEBUG] No session found in Redis for user_id: {user_id}, creating new session")
    except Exception as e:
        print(f"[DEBUG] Error loading session from Redis for user_id {user_id}: {e}")
    return default_factory()


def save_session(user_id: str, session: dict):
    """
    Persist a session to Redis with TTL.
    """
    try:
        history_len = len(session.get('history', []))
        r.setex(user_id, SESSION_TTL_SECONDS, json.dumps(session))
        print(f"[DEBUG] Saved session to Redis for user_id: {user_id}, history length: {history_len}")
    except Exception as e:
        print(f"[ERROR] Failed to save session for {user_id}: {e}")

