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

# Function to check if database is initialized
# Returns "true" if initialized, "false" if not, "unknown" if check failed
check_db_initialized() {
    local project_path="$1"
    
    # Check if project directory exists and has .env
    if [ ! -d "$project_path" ] || [ ! -f "$project_path/.env" ]; then
        echo "false"
        return
    fi
    
    # Try to check if database tables exist
    cd "$project_path" || {
        echo "unknown"
        return
    }
    
    # Activate venv if it exists
    if [ -d "venv" ]; then
        . venv/bin/activate 2>/dev/null || true
    elif [ -d ".venv" ]; then
        . .venv/bin/activate 2>/dev/null || true
    fi
    
    # Check if required Python packages are available
    if ! python3 -c "import sqlalchemy" 2>/dev/null; then
        echo "unknown"
        return
    fi
    
    # Try to check if business_configs table exists
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
    
    # Ensure psycopg2 driver
    if db_url.startswith('postgresql://') and 'psycopg2' not in db_url and 'asyncpg' not in db_url:
        db_url = db_url.replace('postgresql://', 'postgresql+psycopg2://', 1)
    
    engine = create_engine(db_url, connect_args={'connect_timeout': 5})
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    if 'business_configs' in tables:
        sys.exit(0)  # Database is initialized
    else:
        sys.exit(1)  # Database not initialized
except Exception:
    sys.exit(1)
" 2>/dev/null; then
        echo "true"
    else
        echo "false"
    fi
}

# Detect if this is a fresh deployment
FRESH_DEPLOY=false

# Check multiple indicators (in order of reliability):
# 1. Project directory doesn't exist -> fresh deploy
# 2. .env file doesn't exist -> fresh deploy
# 3. Database tables don't exist -> fresh deploy (most reliable indicator)
# 4. Service doesn't exist -> likely fresh deploy
if [ ! -d "$PROJECT_PATH" ]; then
    FRESH_DEPLOY=true
    echo "🆕 Fresh deployment: Project directory doesn't exist"
elif [ ! -f "$PROJECT_PATH/.env" ]; then
    FRESH_DEPLOY=true
    echo "🆕 Fresh deployment: .env file doesn't exist"
else
    # Check if database is initialized
    DB_STATUS=$(check_db_initialized "$PROJECT_PATH")
    if [ "$DB_STATUS" = "false" ]; then
        FRESH_DEPLOY=true
        echo "🆕 Fresh deployment: Database tables don't exist"
    elif [ "$DB_STATUS" = "unknown" ]; then
        # Can't check database, fall back to service check
        if [ ! -f "$SERVICE_FILE" ]; then
            FRESH_DEPLOY=true
            echo "🆕 Fresh deployment: Service file doesn't exist (database check unavailable)"
        else
            echo "⚠️  Could not verify database status, but service exists. Assuming update."
        fi
    else
        echo "✅ Database is initialized. This appears to be an update."
    fi
fi

# Check if service exists
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
    
    # Get project path
    read -p "Enter project path (default: $PROJECT_PATH): " INPUT_PATH
    PROJECT_PATH=${INPUT_PATH:-$PROJECT_PATH}
    
    # Create project directory if it doesn't exist
    if [ ! -d "$PROJECT_PATH" ]; then
        echo "📁 Creating project directory: $PROJECT_PATH"
        mkdir -p "$PROJECT_PATH"
    fi
    
    cd "$PROJECT_PATH"
    
    # Check if git repo exists
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
    
    # Check for Python
    echo ""
    echo "🐍 Checking Python installation..."
    if ! command -v python3 &> /dev/null; then
        echo "❌ Python 3 is not installed. Installing Python 3..."
        apt-get update
        apt-get install -y python3 python3-pip python3-venv
    fi
    
    PYTHON_VERSION_INSTALLED=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
    echo "✅ Python $PYTHON_VERSION_INSTALLED found"
    
    # Create virtual environment if it doesn't exist
    echo ""
    echo "📦 Setting up virtual environment..."
    if [ ! -d "venv" ] && [ ! -d ".venv" ]; then
        echo "  Creating virtual environment..."
        python3 -m venv venv
        echo "✅ Virtual environment created"
    else
        echo "✅ Virtual environment already exists"
    fi
    
    # Activate virtual environment
    if [ -d "venv" ]; then
        . venv/bin/activate || source venv/bin/activate
        VENV_PATH="$PROJECT_PATH/venv"
    elif [ -d ".venv" ]; then
        . .venv/bin/activate || source .venv/bin/activate
        VENV_PATH="$PROJECT_PATH/.venv"
    fi
    
    # Upgrade pip
    echo "  Upgrading pip..."
    pip install --upgrade pip setuptools wheel -q
    
    # Install system dependencies if needed
    echo ""
    echo "🔧 Checking system dependencies..."
    
    # Check for PostgreSQL client libraries
    if ! python3 -c "import psycopg2" 2>/dev/null; then
        echo "  Installing PostgreSQL client libraries..."
        apt-get install -y libpq-dev postgresql-client || {
            echo "⚠️  Could not install PostgreSQL libraries. Install manually if needed."
        }
    fi
    
    # Check for Redis
    if ! command -v redis-cli &> /dev/null; then
        echo "  Redis not found. Installing Redis..."
        apt-get install -y redis-server || {
            echo "⚠️  Could not install Redis. Install manually if needed."
        }
    fi
    
    # Install Python dependencies
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
    
    # Create .env file if it doesn't exist
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
PORT=8000
EOF
            echo "✅ Basic .env file created"
            echo "⚠️  IMPORTANT: Edit .env file and set required values!"
        fi
    else
        echo "✅ .env file already exists"
    fi
    
    # Set up database
    echo ""
    echo "🗄️  Setting up database..."
    read -p "Run database migration? (y/n, default: y): " RUN_MIGRATION
    RUN_MIGRATION=${RUN_MIGRATION:-y}
    if [ "$RUN_MIGRATION" = "y" ] || [ "$RUN_MIGRATION" = "Y" ]; then
        python scripts/db/migrate_db.py || {
            echo "⚠️  Database migration failed. Check your DATABASE_URL in .env"
        }
    fi
    
    # Create necessary directories
    echo ""
    echo "📁 Creating necessary directories..."
    mkdir -p data
    mkdir -p static
    echo "✅ Directories created"
    
    # Get service user
    read -p "Enter user to run service as (default: $SERVICE_USER): " INPUT_USER
    SERVICE_USER=${INPUT_USER:-$SERVICE_USER}
    
    # Ensure service user exists
    if ! id "$SERVICE_USER" &>/dev/null; then
        echo "  Creating service user: $SERVICE_USER"
        useradd -r -s /bin/false "$SERVICE_USER" || {
            echo "⚠️  Could not create user. User may already exist."
        }
    fi
    
    # Set ownership
    echo ""
    echo "🔐 Setting up permissions..."
    chown -R $SERVICE_USER:$SERVICE_USER "$PROJECT_PATH"
    chmod 755 "$PROJECT_PATH"
    chmod 600 "$PROJECT_PATH/.env" 2>/dev/null || true
    echo "✅ Permissions set"
    
    # Determine paths for service file
    if [ -n "$VENV_PATH" ]; then
        UVICORN_PATH="$VENV_PATH/bin/uvicorn"
        # Include both venv and system paths for proper execution
        PYTHON_PATH="$VENV_PATH/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    else
        UVICORN_PATH="uvicorn"
        PYTHON_PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    fi
    
    # Get port from .env
    PORT=8000
    if [ -f ".env" ]; then
        ENV_PORT=$(grep -E '^PORT=' .env | cut -d '=' -f2 | tr -d '"' | tr -d "'" || echo "")
        if [ -n "$ENV_PORT" ] && [ "$ENV_PORT" -gt 0 ] 2>/dev/null; then
            PORT=$ENV_PORT
        fi
    fi
    
    # Create service file
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
Environment="PORT=${PORT:-8000}"
EnvironmentFile=$PROJECT_PATH/.env
ExecStart=/bin/sh -c 'exec $UVICORN_PATH main:app --host 127.0.0.1 --port \${PORT:-8000}'
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
    
    # Reload systemd
    echo "🔄 Reloading systemd..."
    systemctl daemon-reload
    
    # Enable service
    echo "✅ Enabling service..."
    systemctl enable $SERVICE_NAME
    
    echo ""
    echo "✅ Fresh deployment setup complete!"
    echo ""
    echo "⚠️  NEXT STEPS:"
    echo "   1. Edit $PROJECT_PATH/.env and set all required values"
    echo "   2. Ensure PostgreSQL and Redis are running"
    echo "   3. Run 'sudo systemctl start $SERVICE_NAME' to start the service"
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
    
    # Navigate to project directory
    if [ ! -d "$PROJECT_PATH" ]; then
        echo "❌ Project directory not found: $PROJECT_PATH"
        exit 1
    fi
    
    cd "$PROJECT_PATH"
    echo "📂 Working directory: $(pwd)"
    
    # Step 1: Pull latest changes
    echo ""
    echo "📥 Step 1: Pulling latest changes from git..."
    if [ -d ".git" ]; then
        # Detect current branch
        CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
        
        if [ -z "$CURRENT_BRANCH" ]; then
            echo "⚠️  Could not detect git branch, trying common branches..."
            # Try to pull from common branch names
            if git pull origin main 2>/dev/null; then
                echo "✅ Git pull successful (main branch)"
            elif git pull origin master 2>/dev/null; then
                echo "✅ Git pull successful (master branch)"
            else
                echo "⚠️  Git pull failed. Continuing with existing code..."
            fi
        else
            echo "  Current branch: $CURRENT_BRANCH"
            
            # Check if there are uncommitted changes
            if [ -n "$(git status --porcelain)" ]; then
                echo "⚠️  You have uncommitted changes. Stashing them..."
                git stash || true
            fi
            
            # Fetch latest changes
            echo "  Fetching latest changes..."
            git fetch origin "$CURRENT_BRANCH" 2>/dev/null || git fetch origin 2>/dev/null || true
            
            # Pull latest changes
            if git pull origin "$CURRENT_BRANCH" 2>/dev/null; then
                echo "✅ Git pull successful"
            elif git pull origin main 2>/dev/null; then
                echo "✅ Git pull successful (fallback to main)"
            elif git pull origin master 2>/dev/null; then
                echo "✅ Git pull successful (fallback to master)"
            else
                echo "⚠️  Git pull had issues, but continuing with existing code..."
                echo "   You may want to manually run: git pull origin $CURRENT_BRANCH"
            fi
        fi
    else
        echo "⚠️  Not a git repository, skipping git pull"
    fi
    
    # Step 2: Setup Python environment
    echo ""
    echo "🐍 Step 2: Setting up Python environment..."
    
    # Create venv if it doesn't exist
    if [ ! -d "venv" ] && [ ! -d ".venv" ]; then
        echo "  Creating virtual environment..."
        python3 -m venv venv
    fi
    
    # Activate virtual environment
    if [ -d "venv" ]; then
        . venv/bin/activate || source venv/bin/activate
        echo "✅ Virtual environment activated"
    elif [ -d ".venv" ]; then
        . .venv/bin/activate || source .venv/bin/activate
        echo "✅ Virtual environment activated"
    else
        echo "⚠️  No virtual environment found, using system Python"
    fi
    
    # Upgrade pip
    pip install --upgrade pip setuptools wheel -q
    
    # Step 3: Clean up deprecated files
    echo ""
    echo "🧹 Step 3: Cleaning up deprecated files..."
    if [ -f "business_configs.json" ]; then
        rm -f business_configs.json
        echo "✅ Removed deprecated business_configs.json"
    fi
    
    # Step 4: Ensure data directory exists and is writable
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
    
    # Step 5: Install/update dependencies
    echo ""
    echo "📦 Step 5: Installing/updating dependencies..."
    if [ -f "requirements.txt" ]; then
        pip install -q --upgrade -r requirements.txt
        echo "✅ requirements.txt installed/updated"
    else
        echo "⚠️  requirements.txt not found"
    fi
    
    if [ -f "requirements_voice.txt" ]; then
        pip install -q --upgrade -r requirements_voice.txt
        echo "✅ requirements_voice.txt installed/updated"
    fi
    
    # Step 6: Run database migrations
    echo ""
    echo "🗄️  Step 6: Running database migrations..."
    if [ -f "scripts/db/migrate_db.py" ]; then
        python scripts/db/migrate_db.py || {
            echo "⚠️  Database migration had issues. Check your DATABASE_URL"
        }
        echo "✅ Database migrations complete"
    else
        echo "⚠️  Migration script not found, skipping"
    fi
    
    # Step 7: Update service file if needed
    if [ "$SERVICE_EXISTS" = true ] && [ "$NEED_ROOT" = false ]; then
        echo ""
        echo "📝 Step 7: Checking service configuration..."
        
        # Check if PORT changed in .env
        CURRENT_PORT=$(grep -oP '--port \$\{PORT:-?\K\d+' "$SERVICE_FILE" 2>/dev/null || grep -oP '--port \K\d+' "$SERVICE_FILE" 2>/dev/null || echo "8000")
        ENV_PORT=8000
        if [ -f ".env" ]; then
            ENV_PORT=$(grep -E '^PORT=' .env | cut -d '=' -f2 | tr -d '"' | tr -d "'" || echo "8000")
        fi
        
        if [ "$CURRENT_PORT" != "$ENV_PORT" ]; then
            echo "  Port changed from $CURRENT_PORT to $ENV_PORT. Updating service..."
            # Update service file with new port
            sed -i "s/--port [0-9]*/--port \${PORT:-$ENV_PORT}/g" "$SERVICE_FILE" || {
                echo "⚠️  Could not update service file port. Update manually."
            }
            systemctl daemon-reload
            echo "✅ Service configuration updated"
        fi
    fi
    
    # Step 7.5: Check for port conflicts
    echo ""
    echo "🔍 Step 7.5: Checking for port conflicts..."
    ENV_PORT=8000
    if [ -f ".env" ]; then
        ENV_PORT=$(grep -E '^PORT=' .env | cut -d '=' -f2 | tr -d '"' | tr -d "'" || echo "8000")
    fi
    
    # Check if port is in use
    if command -v lsof >/dev/null 2>&1; then
        PORT_IN_USE=$(lsof -ti:$ENV_PORT 2>/dev/null || echo "")
    elif command -v netstat >/dev/null 2>&1; then
        PORT_IN_USE=$(netstat -tuln 2>/dev/null | grep ":$ENV_PORT " | awk '{print $7}' | cut -d'/' -f1 | head -1 || echo "")
    elif command -v ss >/dev/null 2>&1; then
        PORT_IN_USE=$(ss -tuln 2>/dev/null | grep ":$ENV_PORT " | awk '{print $6}' | cut -d':' -f1 | head -1 || echo "")
    else
        PORT_IN_USE=""
    fi
    
    if [ -n "$PORT_IN_USE" ]; then
        # Check if it's the chatbot service itself
        SERVICE_PID=$(systemctl show -p MainPID --value $SERVICE_NAME 2>/dev/null || echo "")
        if [ "$PORT_IN_USE" = "$SERVICE_PID" ] || [ -z "$SERVICE_PID" ]; then
            echo "⚠️  Port $ENV_PORT is in use by PID $PORT_IN_USE"
            echo "   Stopping any existing chatbot processes..."
            systemctl stop $SERVICE_NAME 2>/dev/null || true
            # Kill any remaining processes on the port
            if command -v lsof >/dev/null 2>&1; then
                lsof -ti:$ENV_PORT | xargs kill -9 2>/dev/null || true
            fi
            sleep 2
            echo "✅ Port cleared"
        else
            echo "⚠️  Port $ENV_PORT is already in use by PID $PORT_IN_USE (not chatbot service)"
            echo "   Process info:"
            ps -p $PORT_IN_USE -o pid,cmd 2>/dev/null || echo "   Could not get process info"
            echo ""
            echo "   You may need to:"
            echo "   1. Stop the process using port $ENV_PORT"
            echo "   2. Change PORT in .env file to a different port"
            echo "   3. Or manually kill: sudo kill -9 $PORT_IN_USE"
        fi
    else
        echo "✅ Port $ENV_PORT is available"
    fi
    
    # Step 8: Restart service
    echo ""
    echo "🔄 Step 8: Restarting service..."
    
    if [ "$NEED_ROOT" = true ]; then
        echo "⚠️  Root access required to restart service."
        echo "   Please run manually: sudo systemctl restart $SERVICE_NAME"
    else
        if systemctl is-active --quiet $SERVICE_NAME; then
            systemctl restart $SERVICE_NAME
            echo "✅ Service restarted"
        else
            echo "⚠️  Service is not running. Starting it..."
            systemctl start $SERVICE_NAME || {
                echo "❌ Failed to start service. Checking logs..."
                echo ""
                journalctl -u $SERVICE_NAME -n 50 --no-pager
                echo ""
                echo "Common issues:"
                echo "  - Check .env file has correct GEMINI_API_KEY and DATABASE_URL"
                echo "  - Verify PostgreSQL is running: sudo systemctl status postgresql"
                echo "  - Check Python dependencies: cd $PROJECT_PATH && source venv/bin/activate && pip list"
                echo "  - Port $ENV_PORT may be in use: sudo lsof -i :$ENV_PORT"
                exit 1
            }
        fi
        
        # Wait for service to start
        sleep 3
        
        # Check status
        echo ""
        echo "📊 Step 9: Checking service status..."
        if systemctl is-active --quiet $SERVICE_NAME; then
            echo "✅ Service is running"
            systemctl status $SERVICE_NAME --no-pager -l | head -15
        else
            echo "❌ Service failed to start!"
            echo "   Check logs: sudo journalctl -u $SERVICE_NAME -n 50"
            exit 1
        fi
    fi
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
