# Roadmap to Production 🚀

This document outlines the necessary steps to take the **WarmProspect Concierge Bot** from a Proof of Concept (POC) to a production-ready, scalable, and secure application.

---

## 1. Security & Authentication 🔒
**Priority: High**

*   **Secure Admin API:**
    *   **Goal:** Protect `/admin` endpoints from unauthorized access.
    *   **Action:** Implement API Key authentication as a first step (simplest to integrate with existing client setup).
    *   **Code Change:** 
        *   Create `security.py` to handle API key validation.
        *   Add `Depends(get_api_key)` to all routes in `@app.post("/admin/...")` and `@app.delete("/admin/...")`.
        *   Store valid keys in hashed format in `.env` or database.
*   **Lock Down Chat Payload:**
    *   **Goal:** Prevent users/attackers from injecting custom system prompts.
    *   **Action:** Modify `chat_endpoint` in `main.py`.
    *   **Code Change:** 
        *   Remove `system_prompt` from the request body model (or ignore it if present).
        *   Strictly load the prompt using `config_manager.build_system_prompt(business_id)`.
*   **CORS Hardening:**
    *   **Goal:** Prevent unauthorized websites from embedding the chatbot.
    *   **Action:** Configure `CORSMiddleware`.
    *   **Code Change:** Replace `allow_origins=["*"]` with a list of allowed domains loaded from `ALLOWED_ORIGINS` env var.

## 2. Infrastructure & Scalability 🏗️
**Priority: High**

*   **Persistent Session Storage (Redis):**
    *   **Goal:** Ensure zero data loss on restart and support multiple app workers.
    *   **Action:** Enforce Redis usage.
    *   **Code Change:** 
        *   In `session_store.py`, remove the `try-except` block that allows silent failure if Redis connects fail. Raise a critical error instead.
        *   In `main.py`, remove `_in_memory_sessions` fallback.
        *   Ensure `REDIS_URL` is required in environment variables.
*   **Rate Limiting:**
    *   **Goal:** Prevent abuse (DDoS or cost spikes).
    *   **Action:** Integrate `slowapi`.
    *   **Code Change:**
        *   Install `slowapi`.
        *   Add `@limiter.limit("5/minute")` to `/chat` endpoints.
        *   Configure storage for the limiter (Redis).
*   **Asynchronous Tasks:**
    *   Offload long-running tasks (like building the RAG index or processing large voice files) to a background worker queue (e.g., Celery or ARQ).

## 3. Observability & Logging 📊
**Priority: Medium**

*   **Structured Logging:**
    *   **Goal:** Make logs queryable.
    *   **Action:** Implement `structlog`.
    *   **Code Change:**
        *   Configure a global logger in `logging_config.py`.
        *   Replace `print(f"[DEBUG] ...")` with `logger.debug("message", context=...)`.
*   **Monitoring & Alerts:**
    *   Track key metrics:
        *   Chat latency (Gemini API response time).
        *   Error rates (500s, 400s).
        *   Voice transcoding failures.
        *   Redis connection status.

## 4. Database & Data Integrity 🗄️
**Priority: High**

*   **Database Migrations:**
    *   Formalize the use of `alembic` for all database schema changes. Ensure `scripts/migrate_db.py` is integrated into the deployment pipeline.
*   **Connection Pooling:**
    *   Verify SQLAlchemy engine configuration for production connection pooling (pool size, timeout, recycle).
*   **Session Expiry/Cleanup:**
    *   **Goal:** Auto-delete old session data to save memory/storage.
    *   **Action:** Leverage Redis TTL.
    *   **Verification:** Confirm `SESSION_TTL_SECONDS` is set (e.g., 7 days) and `r.setex` is used correctly in `session_store.py`.

## 5. Deployment Pipeline (CI/CD) 🚀
**Priority: Medium**

*   **Docker Optimization:**
    *   Ensure `Dockerfile` uses a multi-stage build to keep the image size small.
    *   Do not run as root user inside the container.
*   **CI/CD Steps:**
    *   **Linting:** `ruff` or `flake8`.
    *   **Testing:** Run unit tests (needs to be created) before deployment.
    *   **Migration:** Run database migrations automatically on deploy.
*   **Deployment Hardening:**
    *   **Goal:** Reduce attack surface.
    *   **Action:**
        *   Set `DEBUG=False` in production.
        *   Use a production-grade ASGI server (e.g., `gunicorn` with `uvicorn` workers) instead of just `uvicorn`.
        *   Ensure secrets are injected at runtime, not built into images.

## 6. Business Logic Improvements 🧠
**Priority: Low (Enhancement)**

*   **Token Management:**
    *   Refine `MAX_HISTORY_TURNS` logic to intelligently summarize history rather than hard truncation.
*   **Voice File Handling:**
    *   Implement a cleanup job for temporary WAV files created in `services/voice_service.py` (though modern OS /tmp helps, explicit cleanup is safer).
