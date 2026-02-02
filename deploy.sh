#!/bin/bash
# Deploy script for Chatbot Platform
# Handles both fresh deployments from scratch and redeployments

# Ensure script is run with bash
if [ -z "$BASH_VERSION" ]; then
    echo "❌ This script must be run with bash, not sh"
    echo "   Usage: bash deploy.sh or ./deploy.sh"
    exit 1
fi

set -e

echo "🚀 Chatbot Platform Deployment Script"
echo "=============================="
echo ""

# Check if running as root for service operations
NEED_ROOT=false
if [ -n "$EUID" ] && [ "$EUID" -ne 0 ]; then 
    NEED_ROOT=true
elif [ "$(id -u)" -ne 0 ]; then
    NEED_ROOT=true
fi

# Default values
PROJECT_PATH="/var/www/chatbot"
SERVICE_USER="www-data"
SERVICE_NAME="chatbot.service"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}"
PYTHON_VERSION="3.11"

# ============================================
# HELPER FUNCTIONS
# ============================================

# Get backend port from .env file (BACKEND_PORT is primary, PORT is legacy fallback)
get_env_port() {
    local default_port="${1:-8000}"
    if [ -f ".env" ]; then
        # Read both BACKEND_PORT and PORT in one grep pass (more efficient)
        local backend_port port
        # Extract values, handling quotes and whitespace
        backend_port=$(grep -E '^BACKEND_PORT=' .env 2>/dev/null | cut -d '=' -f2- | sed "s/^[\"']//; s/[\"']$//; s/^[[:space:]]*//; s/[[:space:]]*$//" || echo "")
        port=$(grep -E '^PORT=' .env 2>/dev/null | cut -d '=' -f2- | sed "s/^[\"']//; s/[\"']$//; s/^[[:space:]]*//; s/[[:space:]]*$//" || echo "")
        
        # Use BACKEND_PORT if set, otherwise PORT, otherwise default
        local final_port="${backend_port:-${port:-$default_port}}"
        if [ -n "$final_port" ] && [ "$final_port" -gt 0 ] 2>/dev/null; then
            echo "$final_port"
        else
            echo "$default_port"
        fi
    else
        echo "$default_port"
    fi
}

# Activate virtual environment
activate_venv() {
    if [ -d "venv" ]; then
        . venv/bin/activate 2>/dev/null || source venv/bin/activate 2>/dev/null || true
        echo "$PROJECT_PATH/venv"
    elif [ -d ".venv" ]; then
        . .venv/bin/activate 2>/dev/null || source .venv/bin/activate 2>/dev/null || true
        echo "$PROJECT_PATH/.venv"
    else
        echo ""
    fi
}

# Clear port conflicts
clear_port() {
    local port="$1"
    echo "   Checking for processes using port $port..."
    
    # Stop service first
    systemctl stop $SERVICE_NAME 2>/dev/null || true
    sleep 2
    
    # Find and kill processes using the port
    local port_pids=""
    if command -v lsof >/dev/null 2>&1; then
        port_pids=$(lsof -ti:$port 2>/dev/null || echo "")
    elif command -v fuser >/dev/null 2>&1; then
        fuser -k $port/tcp 2>/dev/null || true
        sleep 2
        return 0
    fi
    
    if [ -n "$port_pids" ]; then
        echo "   Found processes using port $port: $port_pids"
        echo "   Killing processes..."
        echo "$port_pids" | xargs kill -9 2>/dev/null || true
        sleep 2
        
        # Verify port is clear
        local final_check=$(lsof -ti:$port 2>/dev/null || echo "")
        if [ -n "$final_check" ]; then
            echo "⚠️  Port $port is still in use by PID(s): $final_check"
            for pid in $final_check; do
                ps -p $pid -o pid,cmd 2>/dev/null || echo "   PID $pid (process may have terminated)"
            done
            echo ""
            echo "   Manual intervention may be required: sudo lsof -i :$port"
            return 1
        fi
    fi
    echo "✅ Port $port is available"
    return 0
}

# Setup/update Nginx configuration
setup_nginx() {
    if [ ! -f "nginx.conf" ]; then
        echo "⚠️  nginx.conf not found. Skipping Nginx setup."
        return 1
    fi
    
    if [ ! -f ".env" ]; then
        echo "⚠️  .env file not found. Cannot generate Nginx config with environment variables."
        return 1
    fi
    
    local NGINX_SITE="chatbot-api"
    local NGINX_AVAILABLE="/etc/nginx/sites-available/$NGINX_SITE"
    local NGINX_ENABLED="/etc/nginx/sites-enabled/$NGINX_SITE"
    
    # Load environment variables from .env
    set -a
    source .env 2>/dev/null || true
    set +a
    
    # Determine backend port (reuse get_env_port function for consistency)
    local backend_port=$(get_env_port)
    
    # Determine Nginx HTTPS port (default 443)
    local nginx_https_port="${NGINX_HTTPS_PORT:-443}"
    
    # Validate ports don't conflict
    if [ "$nginx_https_port" = "$backend_port" ]; then
        echo "  ❌ ERROR: NGINX_HTTPS_PORT ($nginx_https_port) cannot be the same as BACKEND_PORT ($backend_port)."
        echo "     Please set BACKEND_PORT to a different value (e.g., 8001) in your .env file."
        return 1
    fi
    
    # Expand BACKEND_PORT or PORT in NGINX_PROXY_PASS (handle both patterns)
    NGINX_PROXY_PASS="${NGINX_PROXY_PASS//\${BACKEND_PORT}/$backend_port}"
    NGINX_PROXY_PASS="${NGINX_PROXY_PASS//\${PORT}/$backend_port}"
    
    # Export variables for envsubst
    export NGINX_SERVER_NAME NGINX_SSL_CERT_PATH NGINX_SSL_KEY_PATH NGINX_PROXY_PASS NGINX_HTTPS_PORT NGINX_ADDITIONAL_HTTPS_PORT
    
    # Generate nginx config with environment variable substitution
    echo "  Generating Nginx configuration from template with .env variables..."
    if command -v envsubst >/dev/null 2>&1; then
        # Use envsubst to replace ${VAR} with values from environment
        # Only substitute the variables we want (to avoid issues with $host, $server_name, etc.)
        envsubst '$NGINX_SERVER_NAME $NGINX_SSL_CERT_PATH $NGINX_SSL_KEY_PATH $NGINX_PROXY_PASS $NGINX_HTTPS_PORT $NGINX_ADDITIONAL_HTTPS_PORT' < nginx.conf > "${NGINX_AVAILABLE}.tmp" || {
            echo "⚠️  Failed to generate Nginx config. Falling back to direct copy."
            cp nginx.conf "$NGINX_AVAILABLE" || {
                echo "⚠️  Could not copy nginx.conf. You may need to do this manually."
                return 1
            }
        }
        
        # Check if generated config is different
        if [ -f "$NGINX_AVAILABLE" ] && cmp -s "${NGINX_AVAILABLE}.tmp" "$NGINX_AVAILABLE" 2>/dev/null; then
            rm -f "${NGINX_AVAILABLE}.tmp"
            echo "✅ Nginx configuration is up to date"
            return 0
        fi
        
        # Process additional HTTPS port and clean up old blocks in one sed pass
        if [ -n "$NGINX_ADDITIONAL_HTTPS_PORT" ]; then
            sed -i \
                -e "s/# listen \${NGINX_ADDITIONAL_HTTPS_PORT}/listen ${NGINX_ADDITIONAL_HTTPS_PORT}/g" \
                -e "s/# listen \[::\]:\${NGINX_ADDITIONAL_HTTPS_PORT}/listen [::]:${NGINX_ADDITIONAL_HTTPS_PORT}/g" \
                "${NGINX_AVAILABLE}.tmp"
        else
            # Remove commented additional port lines and old port 8000 block
            sed -i \
                -e '/# listen.*NGINX_ADDITIONAL_HTTPS_PORT/d' \
                -e '/^# HTTPS server on port 8000/,/^# }$/d' \
                "${NGINX_AVAILABLE}.tmp"
        fi
        
        mv "${NGINX_AVAILABLE}.tmp" "$NGINX_AVAILABLE" || {
            echo "⚠️  Could not move generated config. You may need to do this manually."
            return 1
        }
    else
        echo "⚠️  envsubst not found. Copying nginx.conf without variable substitution."
        echo "   Install gettext-base package for environment variable support: apt-get install gettext-base"
        cp nginx.conf "$NGINX_AVAILABLE" || {
            echo "⚠️  Could not copy nginx.conf. You may need to do this manually."
            return 1
        }
    fi
    
    echo "  Enabling Nginx site..."
    ln -sf "$NGINX_AVAILABLE" "$NGINX_ENABLED" || {
        echo "⚠️  Could not enable Nginx site. You may need to do this manually."
        return 1
    }
    
    echo "  Testing Nginx configuration..."
    if nginx -t 2>/dev/null; then
        echo "✅ Nginx configuration is valid"
        
        # Check if Nginx is running
        if systemctl is-active --quiet nginx 2>/dev/null; then
            echo "  Reloading Nginx..."
            systemctl reload nginx 2>/dev/null || {
                echo "⚠️  Could not reload Nginx. Run manually: sudo systemctl reload nginx"
                return 1
            }
        else
            echo "  Starting Nginx (was not running)..."
            systemctl start nginx 2>/dev/null || {
                echo "⚠️  Could not start Nginx. Run manually: sudo systemctl start nginx"
                return 1
            }
        fi
        return 0
    else
        echo "⚠️  Nginx configuration test failed. Check the config manually."
        echo "   Run: sudo nginx -t"
        return 1
    fi
}

# Start or restart service
start_service() {
    local port=$(get_env_port)
    
    # Clear port conflicts first
    clear_port "$port" || true
    
    echo ""
    echo "🚀 Starting service..."
    if systemctl is-active --quiet $SERVICE_NAME 2>/dev/null; then
        systemctl restart $SERVICE_NAME
        echo "✅ Service restarted"
    else
        systemctl start $SERVICE_NAME || {
            echo "❌ Failed to start service. Checking logs..."
            echo ""
            journalctl -u $SERVICE_NAME -n 50 --no-pager
            echo ""
            echo "Common issues:"
            echo "  - Check .env file has correct GEMINI_API_KEY and DATABASE_URL"
            echo "  - Verify PostgreSQL is running: sudo systemctl status postgresql"
            echo "  - Check Python dependencies: cd $PROJECT_PATH && source venv/bin/activate && pip list"
            echo "  - Port $port may be in use: sudo lsof -i :$port"
            return 1
        }
        echo "✅ Service started"
    fi
    
    sleep 3
    
    if systemctl is-active --quiet $SERVICE_NAME; then
        echo "✅ Service is running"
        systemctl status $SERVICE_NAME --no-pager -l | head -15
        return 0
    else
        echo "❌ Service failed to start!"
        echo "   Check logs: sudo journalctl -u $SERVICE_NAME -n 50"
        return 1
    fi
}

# Function to check if database is initialized
check_db_initialized() {
    local project_path="$1"
    
    if [ ! -d "$project_path" ] || [ ! -f "$project_path/.env" ]; then
        echo "false"
        return
    fi
    
    cd "$project_path" || {
        echo "unknown"
        return
    }
    
    local venv_path=$(activate_venv)
    
    if ! python3 -c "import sqlalchemy" 2>/dev/null; then
        echo "unknown"
        return
    fi
    
    if python3 -c "
import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path('$project_path')))
try:
    from dotenv import load_dotenv
    load_dotenv()
    from sqlalchemy import inspect, create_engine
    
    db_url = os.getenv('DATABASE_URL', '')
    if not db_url:
        sys.exit(1)
    
    if db_url.startswith('postgresql://') and 'psycopg2' not in db_url and 'asyncpg' not in db_url:
        db_url = db_url.replace('postgresql://', 'postgresql+psycopg2://', 1)
    
    engine = create_engine(db_url, connect_args={'connect_timeout': 5})
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    sys.exit(0 if 'business_configs' in tables else 1)
except Exception:
    sys.exit(1)
" 2>/dev/null; then
        echo "true"
    else
        echo "false"
    fi
}

# ============================================
# DETECT DEPLOYMENT TYPE
# ============================================

FRESH_DEPLOY=false

if [ ! -d "$PROJECT_PATH" ]; then
    FRESH_DEPLOY=true
    echo "🆕 Fresh deployment: Project directory doesn't exist"
elif [ ! -f "$PROJECT_PATH/.env" ]; then
    FRESH_DEPLOY=true
    echo "🆕 Fresh deployment: .env file doesn't exist"
else
    DB_STATUS=$(check_db_initialized "$PROJECT_PATH")
    if [ "$DB_STATUS" = "false" ]; then
        FRESH_DEPLOY=true
        echo "🆕 Fresh deployment: Database tables don't exist"
    elif [ "$DB_STATUS" = "unknown" ]; then
        if [ ! -f "/etc/systemd/system/${SERVICE_NAME}" ]; then
            FRESH_DEPLOY=true
            echo "🆕 Fresh deployment: Service file doesn't exist (database check unavailable)"
        else
            echo "⚠️  Could not verify database status, but service exists. Assuming update."
        fi
    else
        echo "✅ Database is initialized. This appears to be an update."
    fi
fi

SERVICE_EXISTS=false
if [ -f "$SERVICE_FILE" ]; then
    SERVICE_EXISTS=true
    echo "✅ Service file exists: $SERVICE_FILE"
else
    echo "⚠️  Service file not found: $SERVICE_FILE"
fi

# ============================================
# FRESH DEPLOYMENT SETUP
# ============================================
if [ "$FRESH_DEPLOY" = true ]; then
    echo ""
    echo "🆕 FRESH DEPLOYMENT DETECTED"
    echo "=============================="
    
    if [ "$NEED_ROOT" = true ]; then
        echo "❌ Root access required for fresh deployment. Please run with sudo."
        exit 1
    fi
    
    read -p "Enter project path (default: $(pwd)): " INPUT_PATH
    PROJECT_PATH=${INPUT_PATH:-$(pwd)}
    
    if [ ! -d "$PROJECT_PATH" ]; then
        echo "📁 Creating project directory: $PROJECT_PATH"
        mkdir -p "$PROJECT_PATH"
    fi
    
    cd "$PROJECT_PATH"
    
    if [ ! -d ".git" ]; then
        echo ""
        echo "📥 Initializing git repository..."
        read -p "Enter git repository URL (or press Enter to skip): " GIT_REPO
        if [ -n "$GIT_REPO" ]; then
            git clone "$GIT_REPO" . || {
                echo "⚠️  Git clone failed. Continuing with manual setup..."
            }
        else
            echo "⚠️  No git repository provided. You'll need to set up the code manually."
        fi
    fi
    
    echo ""
    echo "🐍 Checking Python installation..."
    if ! command -v python3 &> /dev/null; then
        echo "❌ Python 3 is not installed. Installing Python 3..."
        apt-get update
        apt-get install -y python3 python3-pip python3-venv
    fi
    
    PYTHON_VERSION_INSTALLED=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
    echo "✅ Python $PYTHON_VERSION_INSTALLED found"
    
    echo ""
    echo "📦 Setting up virtual environment..."
    if [ ! -d "venv" ] && [ ! -d ".venv" ]; then
        echo "  Creating virtual environment..."
        python3 -m venv venv
        echo "✅ Virtual environment created"
    else
        echo "✅ Virtual environment already exists"
    fi
    
    VENV_PATH=$(activate_venv)
    
    echo "  Upgrading pip..."
    pip install --upgrade pip setuptools wheel -q
    
    echo ""
    echo "🔧 Checking system dependencies..."
    if ! python3 -c "import psycopg2" 2>/dev/null; then
        echo "  Installing PostgreSQL client libraries..."
        apt-get install -y libpq-dev postgresql-client || {
            echo "⚠️  Could not install PostgreSQL libraries. Install manually if needed."
        }
    fi
    
    if ! command -v redis-cli &> /dev/null; then
        echo "  Redis not found. Installing Redis..."
        apt-get install -y redis-server || {
            echo "⚠️  Could not install Redis. Install manually if needed."
        }
    fi
    
    # Check for envsubst (needed for nginx config generation)
    if ! command -v envsubst &> /dev/null; then
        echo "  Installing gettext-base for environment variable substitution..."
        apt-get install -y gettext-base || {
            echo "⚠️  Could not install gettext-base. Nginx config may not use .env variables."
        }
    fi
    
    echo ""
    echo "📦 Installing Python dependencies..."
    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt
        echo "✅ requirements.txt installed"
    else
        echo "⚠️  requirements.txt not found"
    fi
    
    if [ -f "requirements_voice.txt" ]; then
        pip install -r requirements_voice.txt
        echo "✅ requirements_voice.txt installed"
    fi
    
    echo ""
    echo "⚙️  Setting up environment configuration..."
    if [ ! -f ".env" ]; then
        echo "  Creating .env file from .env.example..."
        if [ -f ".env.example" ]; then
            cp .env.example .env
            echo "✅ .env file created from template"
            echo "⚠️  IMPORTANT: Edit .env file and set required values:"
            echo "   - GEMINI_API_KEY"
            echo "   - ADMIN_API_KEY"
            echo "   - DATABASE_URL"
            echo "   - PORT (default: 8000)"
        else
            echo "⚠️  .env.example not found. Creating basic .env file..."
            cat > .env << EOF
# Chatbot Platform Configuration
GEMINI_API_KEY=your_gemini_api_key_here
ADMIN_API_KEY=your_admin_api_key_here
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/chatbot_db
BACKEND_PORT=8000
EOF
            echo "✅ Basic .env file created"
            echo "⚠️  IMPORTANT: Edit .env file and set required values!"
        fi
    else
        echo "✅ .env file already exists"
    fi
    
    echo ""
    echo "🗄️  Setting up database..."
    read -p "Run database migration? (y/n, default: y): " RUN_MIGRATION
    RUN_MIGRATION=${RUN_MIGRATION:-y}
    if [ "$RUN_MIGRATION" = "y" ] || [ "$RUN_MIGRATION" = "Y" ]; then
        MIGRATE_PYTHON="${VENV_PATH}/bin/python"
        [ -z "$VENV_PATH" ] && MIGRATE_PYTHON="python3"
        "$MIGRATE_PYTHON" scripts/db/migrate_db.py || {
            echo "⚠️  Database migration failed. Check your DATABASE_URL in .env"
        }
    fi
    
    echo ""
    echo "📁 Creating necessary directories..."
    mkdir -p data static
    echo "✅ Directories created"
    
    # Default SERVICE_USER to owner of PROJECT_PATH (if directory exists)
    if [ -d "$PROJECT_PATH" ]; then
        DEFAULT_USER=$(stat -c '%U' "$PROJECT_PATH" 2>/dev/null || echo "$SERVICE_USER")
    else
        DEFAULT_USER="$SERVICE_USER"
    fi
    
    read -p "Enter user to run service as (default: $DEFAULT_USER): " INPUT_USER
    SERVICE_USER=${INPUT_USER:-$DEFAULT_USER}
    
    if ! id "$SERVICE_USER" &>/dev/null; then
        echo "  Creating service user: $SERVICE_USER"
        useradd -r -s /bin/false "$SERVICE_USER" || {
            echo "⚠️  Could not create user. User may already exist."
        }
    fi
    
    echo ""
    echo "🔐 Setting up permissions..."
    chown -R $SERVICE_USER:$SERVICE_USER "$PROJECT_PATH"
    chmod 755 "$PROJECT_PATH"
    chmod 600 "$PROJECT_PATH/.env" 2>/dev/null || true
    echo "✅ Permissions set"
    
    if [ -n "$VENV_PATH" ]; then
        UVICORN_PATH="$VENV_PATH/bin/uvicorn"
        PYTHON_PATH="$VENV_PATH/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    else
        UVICORN_PATH="uvicorn"
        PYTHON_PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    fi
    
    BACKEND_PORT=$(get_env_port)
    
    echo ""
    echo "📝 Creating systemd service..."
    cat > $SERVICE_FILE << EOF
[Unit]
Description=Chatbot API
After=network.target postgresql.service redis-server.service
Requires=postgresql.service
Wants=redis-server.service

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$PROJECT_PATH
Environment="PATH=$PYTHON_PATH"
EnvironmentFile=$PROJECT_PATH/.env
# Port is baked in at deploy time (run deploy again if you change BACKEND_PORT in .env)
ExecStart=$UVICORN_PATH main:app --host 127.0.0.1 --port $BACKEND_PORT
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
    
    chown root:root $SERVICE_FILE
    chmod 644 $SERVICE_FILE
    echo "✅ Service file created at $SERVICE_FILE"
    
    echo "🔄 Reloading systemd..."
    systemctl daemon-reload
    
    echo "✅ Enabling service..."
    systemctl enable $SERVICE_NAME
    
    echo ""
    echo "🔍 Checking for port conflicts before starting service..."
    clear_port "$BACKEND_PORT" || true
    
    start_service || {
        echo "⚠️  Service start failed. Check logs and configuration."
    }
    
    echo ""
    echo "🌐 Setting up Nginx configuration..."
    setup_nginx || true
    
    echo ""
    echo "✅ Fresh deployment setup complete!"
    echo ""
    echo "📋 NEXT STEPS:"
    echo "   1. Verify .env file has all required values (GEMINI_API_KEY, DATABASE_URL, etc.)"
    echo "   2. Ensure PostgreSQL and Redis are running:"
    echo "      sudo systemctl status postgresql"
    echo "      sudo systemctl status redis"
    echo "   3. Check service status: sudo systemctl status $SERVICE_NAME"
    echo "   4. Check service logs: sudo journalctl -u $SERVICE_NAME -f"
    echo "   5. Verify Nginx is running: sudo systemctl status nginx"
    echo ""
    echo "📋 Useful commands:"
    echo "   - View logs:    sudo journalctl -u $SERVICE_NAME -f"
    echo "   - Check status: sudo systemctl status $SERVICE_NAME"
    echo "   - Restart:      sudo systemctl restart $SERVICE_NAME"
    echo ""
    
    SERVICE_EXISTS=true
fi

# ============================================
# REDEPLOYMENT / UPDATE
# ============================================
if [ "$FRESH_DEPLOY" = false ]; then
    echo ""
    echo "🔄 REDEPLOYMENT / UPDATE"
    echo "=============================="
    
    if [ ! -d "$PROJECT_PATH" ]; then
        echo "❌ Project directory not found: $PROJECT_PATH"
        exit 1
    fi
    
    cd "$PROJECT_PATH"
    echo "📂 Working directory: $(pwd)"
    
    echo ""
    echo "📥 Step 1: Pulling latest changes from git..."
    if [ -d ".git" ]; then
        CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
        
        if [ -z "$CURRENT_BRANCH" ]; then
            echo "⚠️  Could not detect git branch, trying common branches..."
            if git pull origin main 2>/dev/null || git pull origin master 2>/dev/null; then
                echo "✅ Git pull successful"
            else
                echo "⚠️  Git pull failed. Continuing with existing code..."
            fi
        else
            echo "  Current branch: $CURRENT_BRANCH"
            
            if [ -n "$(git status --porcelain)" ]; then
                echo "⚠️  You have uncommitted changes. Stashing them..."
                git stash || true
            fi
            
            echo "  Fetching latest changes..."
            git fetch origin "$CURRENT_BRANCH" 2>/dev/null || git fetch origin 2>/dev/null || true
            
            if git pull origin "$CURRENT_BRANCH" 2>/dev/null || \
               git pull origin main 2>/dev/null || \
               git pull origin master 2>/dev/null; then
                echo "✅ Git pull successful"
            else
                echo "⚠️  Git pull had issues, but continuing with existing code..."
                echo "   You may want to manually run: git pull origin $CURRENT_BRANCH"
            fi
        fi
    else
        echo "⚠️  Not a git repository, skipping git pull"
    fi
    
    echo ""
    echo "🐍 Step 2: Setting up Python environment..."
    if [ ! -d "venv" ] && [ ! -d ".venv" ]; then
        echo "  Creating virtual environment..."
        python3 -m venv venv
    fi
    
    activate_venv >/dev/null
    
    echo "  Upgrading pip..."
    pip install --upgrade pip setuptools wheel -q
    
    echo ""
    echo "🧹 Step 3: Cleaning up deprecated files..."
    if [ -f "business_configs.json" ]; then
        rm -f business_configs.json
        echo "✅ Removed deprecated business_configs.json"
    fi
    
    echo ""
    echo "📁 Step 4: Ensuring data directory is writable..."
    mkdir -p data
    if [ "$NEED_ROOT" = false ]; then
        chown -R $SERVICE_USER:$SERVICE_USER data/ 2>/dev/null || true
        chmod -R 755 data/ 2>/dev/null || true
        echo "✅ Data directory permissions set"
    else
        echo "⚠️  Run 'sudo chown -R $SERVICE_USER:$SERVICE_USER data/' to fix permissions"
    fi
    
    echo ""
    echo "📦 Step 5: Installing/updating dependencies..."
    if [ -f "requirements.txt" ]; then
        echo "  Installing from requirements.txt..."
        pip install --upgrade -r requirements.txt || {
            echo "⚠️  Some packages failed to install. Continuing..."
        }
        echo "✅ requirements.txt installed/updated"
    else
        echo "⚠️  requirements.txt not found"
    fi
    
    if [ -f "requirements_voice.txt" ]; then
        echo "  Installing from requirements_voice.txt..."
        pip install --upgrade -r requirements_voice.txt || {
            echo "⚠️  Some voice packages failed to install. Continuing..."
        }
        echo "✅ requirements_voice.txt installed/updated"
    fi
    
    echo ""
    echo "🗄️  Step 6: Running database migrations..."
    if [ -f "scripts/db/migrate_db.py" ]; then
        (command -v python3 &>/dev/null && python3 scripts/db/migrate_db.py || python scripts/db/migrate_db.py) || {
            echo "⚠️  Database migration had issues. Check your DATABASE_URL"
        }
        echo "✅ Database migrations complete"
    else
        echo "⚠️  Migration script not found, skipping"
    fi
    
    if [ "$SERVICE_EXISTS" = true ] && [ "$NEED_ROOT" = false ]; then
        echo ""
        echo "📝 Step 7: Checking service configuration..."
        CURRENT_PORT=$(grep -oP '--port \$\{BACKEND_PORT:-?\K\d+' "$SERVICE_FILE" 2>/dev/null || \
                      grep -oP '--port \$\{PORT:-?\K\d+' "$SERVICE_FILE" 2>/dev/null || \
                      grep -oP '--port \K\d+' "$SERVICE_FILE" 2>/dev/null || echo "8000")
        ENV_PORT=$(get_env_port)
        # Force update if current port is invalid (e.g. concatenated value like 800180018001...)
        NEED_PORT_UPDATE=false
        if [ "$CURRENT_PORT" != "$ENV_PORT" ]; then NEED_PORT_UPDATE=true; fi
        if [ -n "$CURRENT_PORT" ] && [ "$CURRENT_PORT" -gt 65535 ] 2>/dev/null; then NEED_PORT_UPDATE=true; fi
        if [ "$NEED_PORT_UPDATE" = true ]; then
            echo "  Port changed from $CURRENT_PORT to $ENV_PORT. Updating service..."
            # Replace entire ExecStart line so no $VAR in .env can concatenate (systemd expands EnvFile into ExecStart)
            UVICORN_PATH="$PROJECT_PATH/venv/bin/uvicorn"
            [ ! -x "$UVICORN_PATH" ] && UVICORN_PATH="uvicorn"
            sed -i "s|^ExecStart=.*|ExecStart=$UVICORN_PATH main:app --host 127.0.0.1 --port $ENV_PORT|" "$SERVICE_FILE" || {
                echo "⚠️  Could not update service file. Update ExecStart manually to: --port $ENV_PORT"
            }
            systemctl daemon-reload
            echo "✅ Service configuration updated"
        fi
    fi
    
    echo ""
    echo "🔍 Step 7.5: Checking for port conflicts..."
    ENV_PORT=$(get_env_port)
    clear_port "$ENV_PORT" || true
    
    echo ""
    echo "🔄 Step 8: Restarting service..."
    if [ "$NEED_ROOT" = true ]; then
        echo "⚠️  Root access required to restart service."
        echo "   Please run manually: sudo systemctl restart $SERVICE_NAME"
    else
        start_service || exit 1
    fi
    
    echo ""
    echo "🌐 Step 9: Updating Nginx configuration..."
    setup_nginx || true
fi

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📋 Useful commands:"
echo "  - View logs:    sudo journalctl -u $SERVICE_NAME -f"
echo "  - Check status: sudo systemctl status $SERVICE_NAME"
echo "  - Restart:      sudo systemctl restart $SERVICE_NAME"
echo "  - Stop:         sudo systemctl stop $SERVICE_NAME"
echo "  - Start:        sudo systemctl start $SERVICE_NAME"
