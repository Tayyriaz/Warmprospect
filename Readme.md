---
name: ""
overview: ""
todos: []
---

# WarmProspect Chatbot Platform

## Project Overview

**WarmProspect Chatbot Platform** enables businesses to create customized AI assistants. The system uses Google Gemini AI for natural language processing, supports both text and voice interactions, and includes CRM integration capabilities.

## Core Architecture

### Technology Stack

- **Backend Framework**: FastAPI (Python)
- **AI/ML**: Google Gemini API (gemini-2.5-flash, gemini-2.0-flash-exp for voice)
- **Database**: PostgreSQL (with JSON file fallback)
- **Session Storage**: Redis (with in-memory fallback)
- **Voice Services**: Twilio (phone calls), Edge TTS (text-to-speech)
- **RAG**: FAISS vector search with Google embeddings
- **Deployment**: Docker, VPS


## Key Features

- **Multi-Tenant Architecture**
  - Support for multiple businesses with complete isolation
  - Each business has unique `business_id` identifier
  - Business CRUD operations via admin API (create, edit, delete, view)
  - No data or configuration leakage between tenants
  - Chat API requires `business_id`, `session_id`, and `message` parameters
  - Each business instance operates independently

- **Business Configuration & Customization**
  - Unique system prompts and personality traits per business
  - Custom branding (colors, widget positioning, greeting messages)
  - Business-specific call-to-action (CTA) structures
  - Custom business rules and logic for conversation flows
  - Currently static configuration (architecture supports dynamic, rule-based system)
  - Designed for multi-level hierarchical CTAs with context-aware selection

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
  - Support for multiple CRM types: custom systems, ready-made CRMs (Salesforce, HubSpot, etc.), or WarmProspect CRM
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
- **Business configuration**: System prompts, branding, greeting messages, basic CTAs
- **RAG integration**: FAISS vector indexes per business with Google embeddings
- **CRM tool framework**: Function calling structure for contact and deal management
- **Voice API**: Twilio phone call integration with Gemini Live API
- **Twilio integration**: Phone call functionality with WebSocket streaming
- **Security**: API key authentication, CORS configuration, rate limiting
- **Hard guards**: Intro token detection and appointment guard
- **Response formatting**: Paragraph + CTA format enforcement, HTML support

### Tasks To Be Completed 📋

#### High Priority - Dynamic Configuration

- [ ] **Multi-level CTA system**: Implement hierarchical, dynamic CTA structure (primary, secondary, tertiary, nested)
- [ ] **Context-aware CTA selection**: Select CTAs based on conversation flow and user intent
- [ ] **Conditional CTA logic**: CTAs that appear/disappear based on user responses, conversation state, business rules, or metadata
- [ ] **Dynamic CTA generation**: Generate CTAs dynamically based on available services/products
- [ ] **Business rules engine**: Pluggable rule system for conditional logic in conversation flow
- [ ] **Dynamic routing decisions**: Context-aware routing based on business rules
- [ ] **A/B testing framework**: Support for experimentation and testing different configurations

#### Session & Conversation Enhancements

- [ ] **Session metadata support**: Custom attributes and metadata storage per session
- [ ] **Session state machine**: Complex conversation flow management with state transitions
- [ ] **Session analytics**: Tracking and analytics for session data
- [ ] **Conversation state management**: State machine for multi-step conversation flows
- [ ] **Intent detection**: Classify user intent to improve routing and responses
- [ ] **Sentiment analysis**: Personalized responses based on user sentiment
- [ ] **Multi-turn conversation planning**: Better handling of complex, multi-step conversations

#### Chat Engine Improvements

- [ ] **Dynamic CTA integration**: Context-aware CTA selection and injection into responses
- [ ] **Error handling**: More graceful degradation when services fail
- [ ] **Response validation**: Ensure responses meet format requirements before sending
- [ ] **Token management**: Intelligent history summarization instead of hard truncation
- [ ] **Streaming responses**: Support for streaming responses for better UX
- [ ] **Response caching**: Cache common responses to reduce API calls

#### RAG Enhancements

- [ ] **Real-time knowledge base updates**: Update knowledge bases without full rebuild
- [ ] **Multi-source aggregation**: Intelligently aggregate information from multiple sources
- [ ] **Knowledge base versioning**: Track versions for rollback capability
- [ ] **Confidence scoring**: Score retrieval confidence and filter low-confidence results
- [ ] **Hybrid search**: Combine vector search with keyword/BM25 search
- [ ] **Re-ranking**: Re-rank retrieved results using cross-encoder models
- [ ] **Chunk optimization**: Better chunking strategies (semantic chunking, overlap handling)
- [ ] **Metadata filtering**: Filter by metadata (date, category, source type)
- [ ] **Query expansion**: Expand user queries for better retrieval
- [ ] **Incremental indexing**: Add/update documents without full index rebuild
- [ ] **Index health monitoring**: Monitor index quality and retrieval performance
- [ ] **Multi-modal support**: Support for images, PDFs, and other document types

#### CRM Integration

- [ ] **Dynamic CRM connector system**: Per-tenant CRM integration configuration
  - Support for multiple CRM types (custom systems, Salesforce, HubSpot, WarmProspect CRM, etc.)
  - Configurable API endpoints and authentication per business
  - CRM connector plugins/adapters for different CRM systems
- [ ] **CRM configuration management**: Admin API for businesses to configure their CRM integration
  - API endpoint configuration
  - Authentication credentials (API keys, OAuth, etc.)
  - Field mapping between chatbot and CRM fields
  - Custom field support
- [ ] **Real CRM API integration**: Replace placeholder implementations with dynamic connector system
- [ ] **Contact deduplication**: Advanced logic for finding and merging duplicate contacts
- [ ] **Deal pipeline management**: Integration with deal stages and pipeline workflows
- [ ] **CRM webhooks**: Support for CRM events and updates (bidirectional sync)
- [ ] **CRM adapter framework**: Pluggable adapter system for easy integration with new CRM systems

#### Production Hardening

- [ ] **Enforce Redis**: Remove in-memory fallback, require Redis in production
- [ ] **Structured logging**: Replace print statements with structured logging (structlog)
- [ ] **Database migrations**: Automate migrations in CI/CD pipeline
- [ ] **Connection pooling**: Optimize database connection pooling configuration
- [ ] **Monitoring & metrics**: Set up monitoring, metrics, and alerting
- [ ] **Error tracking**: Implement error tracking and reporting
- [ ] **Performance optimization**: Optimize RAG retrieval and API response times

#### Testing & Quality

- [ ] **Unit tests**: Write unit tests for core functionality
- [ ] **Integration tests**: Create integration tests for API endpoints
- [ ] **End-to-end tests**: Add E2E tests for chat flows
- [ ] **Test coverage**: Implement test coverage reporting
- [ ] **Load testing**: Performance and load testing

#### Voice Enhancements

- [ ] **Per-tenant phone call configuration**: Each business can configure their own Twilio integration
  - Business-specific Twilio phone number configuration
  - Webhook routing per business (business routes their Twilio calls to platform)
  - Business-specific voice personality and greeting messages
  - Apply same business prompts, CTAs, and knowledge base to voice calls
- [ ] **Dynamic voice routing**: Route incoming calls to correct business chatbot based on phone number or business_id
- [ ] **Lower latency**: Migrate to Gemini Live WebSocket for real-time voice
- [ ] **Audio format support**: Expand support for more audio formats
- [ ] **Voice quality optimization**: Improve audio processing and quality
- [ ] **Voice call session management**: Manage voice call sessions with same business_id:session_id isolation

## Data Flow

### Chat Request Flow

```javascript
User Message → FastAPI /chat endpoint
  ↓
Load Business Config (PostgreSQL)
  ↓
Build System Instruction (Base + Business-specific)
  ↓
Get/Create Chat Session (Gemini SDK with history)
  ↓
RAG Retrieval (if business KB exists)
  ↓
Send to Gemini with Tools + Context
  ↓
Handle Function Calls (CRM tools)
  ↓
Return Response → Client Application
```



### Voice Request Flow (Twilio Phone Calls)

```javascript
Incoming Phone Call → Business's Twilio Phone Number
  ↓
Twilio → POST /voice/incoming (webhook with business_id)
  ↓
Load Business Config → Build System Instruction
  ↓
Return TwiML → Connect to WebSocket /media-stream
  ↓
WebSocket Audio Stream → Gemini Audio APIs
  ↓
Gemini Bot (with business personality, prompts, CTAs, knowledge base)
  ↓
Audio Response → Twilio WebSocket
  ↓
Phone Call (business-specific chatbot)
```


## API Endpoints

> **Note**: This platform provides API endpoints only. Frontend UIs (chat widget and admin panel) are included for testing purposes only and are not used in production. Production integrations should use the API endpoints directly.

### Public Endpoints

- `GET /` - Chat widget UI (testing only, not for production)
- `GET /health` - Health check
- `POST /chat` - Main chat endpoint (rate limited)
  - **Request Body**:
    - `business_id` (required) - Identifies which business's chatbot to use
    - `session_id` (required) - Unique identifier for the conversation session
    - `message` (required) - User's message/input
  - **Response**: 
    - `response` - AI-generated response text
    - `ctas` (optional) - Call-to-action buttons if applicable
- `GET /api/business/{business_id}/config` - Widget configuration
  - Returns business-specific configuration (branding, CTAs, greeting message, etc.)
  - Used by client applications to fetch business configuration

### Admin Endpoints (API Key Protected)

- `GET /admin` - Admin panel UI (testing only, not for production)
- `POST /admin/business` - Create/update business
  - **Request Body**: Business configuration (business_id, business_name, system_prompt, CTAs, etc.)
  - **Response**: Created/updated business configuration
- `GET /admin/business` - List all businesses
  - **Response**: Dictionary of all businesses keyed by business_id
- `GET /admin/business/{business_id}` - Get business config
  - **Response**: Complete business configuration object
- `DELETE /admin/business/{business_id}` - Delete business
  - **Response**: Success confirmation

### Voice Endpoints (Twilio Integration)

- `POST /voice/incoming` - Twilio webhook (TwiML)
  - **Request**: Twilio webhook payload (business routes their Twilio calls here)
  - **Query Parameter**: `business_id` (required) - Identifies which business's chatbot to use
  - **Response**: TwiML XML to start media stream
  - Handles incoming phone calls routed from business's Twilio account
- `WebSocket /media-stream` - Twilio media stream
  - **Query Parameter**: `business_id` (required) - Identifies which business's chatbot to use
  - Bidirectional WebSocket connecting Gemini bot with Gemini audio APIs
  - Real-time audio streaming between Twilio phone number and Gemini
  - Uses business-specific chatbot configuration (personality, prompts, CTAs, knowledge base)

## Setup & Configuration

### Environment Variables

The platform requires several environment variables to be configured. Create a `.env` file in the project root:

```env
# Required
GEMINI_API_KEY=your_gemini_api_key_here
DATABASE_URL=postgresql://user:password@localhost:5432/warmprospect
REDIS_URL=redis://localhost:6379/0

# Admin API Key (Required for admin endpoints)
ADMIN_API_KEY=your_admin_api_key_here

# Optional
GEMINI_MODEL=gemini-2.5-flash
MAX_HISTORY_TURNS=20
PORT=8000
ALLOWED_ORIGINS=["*"]  # JSON array, e.g., ["https://example.com", "https://app.example.com"]
DEFAULT_APPOINTMENT_LINK=https://calendly.com/example

# Twilio (per-tenant configuration - each business configures their own)
# Platform-level Twilio credentials (if needed for platform operations)
TWILIO_ACCOUNT_SID=...  # Optional: for platform-level operations
TWILIO_AUTH_TOKEN=...   # Optional: for platform-level operations
# Note: Each business configures their own Twilio integration and routes calls to platform webhook
```

### Generating Admin API Key

To generate a secure admin API key, use the provided script:

```bash
# Generate a key (default: 32 bytes, hex format)
python3 scripts/generate_admin_key.py

# Generate with custom length (64 bytes = 128 hex characters)
python3 scripts/generate_admin_key.py --length 64

# Generate in base64 format
python3 scripts/generate_admin_key.py --format base64

# Generate in .env file format (ready to copy-paste)
python3 scripts/generate_admin_key.py --env-format
```

**Example output:**
```
Generated Admin API Key:
32de014f3e9155c37a948ac120893f157dc087d2084e6e438bb6d31fec79c921

# Add to your .env file as:
ADMIN_API_KEY=32de014f3e9155c37a948ac120893f157dc087d2084e6e438bb6d31fec79c921
```

Copy the generated key and add it to your `.env` file as `ADMIN_API_KEY=...`. This key is required to access admin endpoints and should be kept secure.

**Security Notes:**
- Use a strong, randomly generated key (minimum 32 bytes recommended)
- Never commit the `.env` file to version control
- Rotate keys periodically in production
- Use different keys for development and production environments

**Commands **
cd /var/www/chatbot && git pull && source venv/bin/activate && python scripts/migrate_db.py && sudo systemctl restart goaccel.service
