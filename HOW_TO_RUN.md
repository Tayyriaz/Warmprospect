# How to Run WarmProspect Chatbot Platform

## Prerequisites

- Python 3.11+ (for local development)
- PostgreSQL 15+ (or use Docker)
- Redis (or use Docker)
- Docker & Docker Compose (optional, for containerized setup)

## Method 1: Local Development (Recommended for Development)

### Step 1: Install Dependencies

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Linux/Mac:
source venv/bin/activate

# Install Python packages
pip install -r requirements.txt
pip install -r requirements_voice.txt
```

### Step 2: Setup Environment Variables

Create a `.env` file in the project root:

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
ALLOWED_ORIGINS=["*"]
```

**Generate Admin API Key:**
```bash
python scripts/generate_admin_key.py --env-format
```

Copy the output and add it to your `.env` file.

### Step 3: Setup Database

**Option A: Using PostgreSQL (Recommended)**
```bash
# Make sure PostgreSQL is running
# Create database
createdb warmprospect

# Run migrations
python scripts/migrate_db.py
```

**Option B: Using Docker for Database & Redis**
```bash
# Start only PostgreSQL and Redis
docker-compose up -d postgres redis

# Wait for services to be ready, then run migrations
python scripts/migrate_db.py
```

### Step 4: Run the Application

```bash
# Make sure virtual environment is activated
python main.py
```

Or using uvicorn directly:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The application will be available at:
- **API**: http://localhost:8000
- **Landing Page**: http://localhost:8000/
- **Admin Panel**: http://localhost:8000/admin
- **Chatbot**: http://localhost:8000/bot?business_id=your_business_id
- **API Docs**: http://localhost:8000/docs

---

## Method 2: Docker Compose (Recommended for Production)

### Step 1: Create `.env` File

Create a `.env` file in the project root with all required variables (same as Method 1).

### Step 2: Run with Docker Compose

```bash
# Build and start all services (PostgreSQL, Redis, App)
docker-compose up -d --build

# View logs
docker-compose logs -f app

# Check status
docker-compose ps

# Stop services
docker-compose stop

# Stop and remove containers
docker-compose down

# Stop and remove containers + volumes (clean slate)
docker-compose down -v
```

**Or use the provided script:**
```bash
chmod +x docker-start.sh
./docker-start.sh
```

The application will be available at http://localhost:8000

---

## Method 3: Production Deployment (Systemd Service)

### Step 1: Setup on VPS

```bash
# Clone repository
cd /var/www
git clone <your-repo-url> warmprospect
cd warmprospect

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements_voice.txt

# Create .env file
nano .env
# Add all required environment variables

# Setup database
python scripts/migrate_db.py
```

### Step 2: Setup Systemd Service

```bash
# Run setup script (requires sudo)
sudo chmod +x setup-service.sh
sudo ./setup-service.sh

# Or manually create service file
sudo nano /etc/systemd/system/goaccel.service
```

**Service file template:**
```ini
[Unit]
Description=GoAccel Chatbot API
After=network.target postgresql.service redis-server.service
Requires=postgresql.service redis-server.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/var/www/warmprospect
Environment="PATH=/var/www/warmprospect/venv/bin"
EnvironmentFile=/var/www/warmprospect/.env
ExecStart=/var/www/warmprospect/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### Step 3: Start Service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service (start on boot)
sudo systemctl enable goaccel

# Start service
sudo systemctl start goaccel

# Check status
sudo systemctl status goaccel

# View logs
sudo journalctl -u goaccel -f

# Restart service
sudo systemctl restart goaccel
```

### Step 4: Update Application

```bash
cd /var/www/warmprospect
git pull
source venv/bin/activate
python scripts/migrate_db.py
sudo systemctl restart goaccel
```

---

## Quick Start Commands

### Local Development
```bash
# Setup
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
pip install -r requirements_voice.txt

# Create .env file with required variables

# Run
python main.py
```

### Docker
```bash
# Create .env file
# Run
docker-compose up -d --build
```

### Production Update
```bash
cd /var/www/warmprospect
git pull
source venv/bin/activate
python scripts/migrate_db.py
sudo systemctl restart goaccel
```

---

## Verify Installation

1. **Check Health Endpoint:**
   ```bash
   curl http://localhost:8000/health
   ```

2. **Access Admin Panel:**
   - Open http://localhost:8000/admin
   - Use your `ADMIN_API_KEY` in the API Key field

3. **Create a Business:**
   - Click "Create New Business" in admin panel
   - Fill in business details
   - Save

4. **Test Chatbot:**
   - Open http://localhost:8000/bot?business_id=your_business_id
   - Send a test message

---

## Troubleshooting

### Database Connection Issues
- Check PostgreSQL is running: `pg_isready` or `docker-compose ps`
- Verify `DATABASE_URL` in `.env` is correct
- Check database exists: `psql -l`

### Redis Connection Issues
- Check Redis is running: `redis-cli ping` or `docker-compose ps`
- Verify `REDIS_URL` in `.env` is correct

### API Key Issues
- Verify `GEMINI_API_KEY` is set in `.env`
- Verify `ADMIN_API_KEY` is set in `.env`
- Check API key is valid

### Port Already in Use
- Change `PORT` in `.env` to a different port
- Or stop the process using port 8000

### Import Errors
- Make sure virtual environment is activated
- Reinstall dependencies: `pip install -r requirements.txt`

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GEMINI_API_KEY` | ✅ Yes | - | Google Gemini API key |
| `DATABASE_URL` | ✅ Yes | - | PostgreSQL connection string |
| `REDIS_URL` | ✅ Yes | - | Redis connection string |
| `ADMIN_API_KEY` | ✅ Yes | - | Admin API authentication key |
| `GEMINI_MODEL` | No | `gemini-2.5-flash` | Gemini model to use |
| `MAX_HISTORY_TURNS` | No | `20` | Max conversation history turns |
| `PORT` | No | `8000` | Application port |
| `ALLOWED_ORIGINS` | No | `["*"]` | CORS allowed origins (JSON array) |

---

## Next Steps

1. Create your first business in the admin panel
2. Configure system prompt and CTAs
3. Build knowledge base (scrape website or upload documents)
4. Test chatbot interface
5. Integrate with your CRM (create `crm_{business_id}.py` file)
