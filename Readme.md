---
name: ""
overview: ""
todos: []
---

# Chatbot Platform

## Project Overview

**Chatbot Platform** enables businesses to create customized AI assistants. The system uses Google Gemini AI for natural language processing, supports both text and voice interactions, and includes CRM integration capabilities.

## Core Architecture

### Technology Stack

- **Backend Framework**: FastAPI (Python)
- **AI/ML**: Google Gemini API (gemini-2.5-flash, gemini-2.0-flash-exp for voice)
- **Database**: PostgreSQL (database-only, no file fallback)
- **Session Storage**: Redis (with in-memory fallback)
- **Voice Services**: Twilio (phone calls), Edge TTS (text-to-speech)
- **RAG**: FAISS vector search with Google embeddings
- **Deployment**: Docker, VPS (with automated deploy.sh script)


## Key Features

- **Multi-Tenant Architecture**
  - Support for multiple businesses with complete isolation
  - Each business has unique `business_id` identifier
  - Business CRUD operations via admin API (create, edit, delete, view)
  - No data or configuration leakage between tenants
  - Chat API requires `business_id`, `user_id` (or `session_id`), and `message` parameters
  - Each business instance operates independently

- **Business Configuration & Customization**
  - Unique system prompts and personality traits per business
  - Custom branding (colors, widget positioning, greeting messages, logo)
  - Business-specific hierarchical CTA tree structure (cta_tree)
  - Custom business rules and logic for conversation flows
  - Database-only storage (PostgreSQL) - no file-based fallback
  - Multi-level hierarchical CTAs with context-aware selection
  - Separate knowledge base scraping endpoint (not automatic on save)

- **Session & Conversation Management**
  - Sessions uniquely identified by `business_id:session_id` combination
  - Redis-based persistent session storage with configurable TTL (default 7 days)
  - Stores conversation context, PII (name, email, phone), and CRM data (contact IDs, deal IDs)
  - Google Gemini SDK automatically manages full conversation history
  - Field locking prevents repeating questions for already-collected PII
  - History trimming (MAX_HISTORY_TURNS = 20) to manage token usage
  - Complete isolation between businesses and users

- **AI-Powered Chat Engine**
  - Google Gemini Chat API for natural language understanding and generation
  - Combines base guardrails with business-specific system prompts
  - Function calling for CRM integration (contact search, creation, deal management)
  - RAG context injection from business-specific knowledge bases
  - Hard guards for intro tokens and appointment-related queries
  - Strict response formatting: paragraph + CTA format, limited HTML support
  - Inline bold echo for user values, no bullets in replies
  - Rate limiting (5 requests/minute per user) to prevent abuse

- **Knowledge Base & RAG Integration**
  - Independent knowledge base per business using Retrieval-Augmented Generation (RAG)
  - FAISS vector indexes stored per business (`data/{business_id}/index.faiss`)
  - Google text-embedding-004 for embeddings
  - Top-K retrieval (default 5-8 results) with source citations
  - Support for website content, product catalogs, FAQs, and custom knowledge bases
  - Metadata storage (URL, title, timestamp) for each document chunk
  - Fallback to default index if business-specific knowledge unavailable

- **CRM Integration**
  - Per-tenant CRM integration configuration (each business can connect to their own CRM system)
  - Support for multiple CRM types: custom systems, ready-made CRMs (Salesforce, HubSpot, etc.), or custom CRM systems
  - Dynamic CRM connector system allowing businesses to configure their own API endpoints and authentication
  - CRM tools exposed to AI through function calling
  - Standard CRM operations: contact search (by email or phone), contact creation with PII validation, deal creation linked to contacts
  - Business-specific CRM field mapping and custom field support
  - Currently placeholder implementations (architecture supports dynamic, configurable CRM connectors per business)

- **Voice Capabilities (Twilio Integration)**
  - Per-tenant Twilio phone call configuration (each business connects their Twilio phone number to the platform)
  - Businesses route their Twilio phone calls to the chatbot platform webhook
  - Connect Gemini bot with Gemini audio APIs through Twilio phone number
  - Incoming calls handled by chatbot using business-specific personality, prompts, CTAs, and knowledge base
  - Real-time bidirectional audio streaming via Twilio WebSocket
  - Session management: Voice calls use same `business_id:session_id` isolation as text chat

- **Security & Rate Limiting**
  - API key authentication for admin endpoints
  - Customizable CORS configuration via environment variables
  - System prompt injection prevention (locked-down request handling)
  - Rate limiting via slowapi to prevent abuse and cost spikes
  - Strict input validation and sanitization

## Implementation Status

### Completed Features ✅

- **Multi-tenant business management**: CRUD operations for businesses via admin API
- **Session management**: Redis-based storage with TTL, session isolation by business_id:session_id
- **Chat engine**: Gemini Chat API integration with automatic history management
- **Business configuration**: System prompts, branding, greeting messages, hierarchical CTA tree
- **RAG integration**: FAISS vector indexes per business with Google embeddings
- **CRM tool framework**: Function calling structure for contact and deal management
- **Voice API**: Twilio phone call integration with Gemini Live API
- **Twilio integration**: Phone call functionality with WebSocket streaming
- **Security**: API key authentication, CORS configuration, rate limiting
- **Hard guards**: Intro token detection and appointment guard
- **Response formatting**: Paragraph + CTA format enforcement, HTML support
- **Session metadata**: Custom attributes and metadata storage per session
- **Session state machine**: Complex conversation flow management with state transitions
- **Session analytics**: Tracking and analytics for session data with API endpoints
- **Intent detection**: Classify user intent to improve routing and responses
- **Sentiment analysis**: Personalized responses based on user sentiment
- **Multi-turn conversation planning**: Better handling of complex, multi-step conversations
- **Business rules engine**: Pluggable rule system for conditional logic in conversation flow
- **A/B testing framework**: Support for experimentation and testing different configurations
- **Dynamic CTA integration**: Context-aware CTA selection and injection into responses

## Deployment

### VPS Deployment

The platform includes an automated deployment script (`deploy.sh`) that handles both fresh deployments and updates:

**Features:**
- Automatic detection of fresh vs. existing deployment (checks database initialization)
- Git pull with branch detection and conflict handling
- Virtual environment setup and activation
- Dependency installation and updates
- Database schema synchronization
- Port conflict detection and resolution
- Systemd service creation and management
- Nginx configuration with environment variable substitution
- Permission setup and data directory management
- Service startup and health checks

**Quick Deploy:**
```bash
cd /var/www/chatbot
sudo bash deploy.sh
```

**What the script does:**

**Fresh Deployment:**
- Creates project directory
- Sets up Python virtual environment
- Installs system dependencies (PostgreSQL, Redis, gettext-base)
- Installs Python dependencies
- Creates `.env` file from template
- Sets up database (with migration prompt)
- Creates systemd service file
- Configures Nginx reverse proxy
- Starts the service automatically

**Redeployment/Update:**
- Pulls latest code from git (auto-detects branch)
- Updates Python dependencies
- Runs database migrations
- Updates service configuration if needed
- Clears port conflicts
- Restarts service
- Updates Nginx configuration if changed

**Manual Deploy (if needed):**
```bash
cd /var/www/chatbot
git pull
source venv/bin/activate
pip install -r requirements.txt
python scripts/db/migrate_db.py
sudo systemctl restart chatbot.service
```

**Database Migration:**
Database migrations run automatically during deployment. To run manually:
```bash
cd /var/www/chatbot
source venv/bin/activate
python scripts/db/migrate_db.py
```

**Nginx Configuration:**
The deploy script automatically generates nginx configuration from `nginx.conf` template using environment variables from `.env`. Make sure to set:
- `NGINX_SERVER_NAME`
- `NGINX_SSL_CERT_PATH`
- `NGINX_SSL_KEY_PATH`
- `NGINX_PROXY_PASS` (uses `${PORT}` automatically)
