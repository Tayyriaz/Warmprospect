#!/bin/bash
# Deploy script for GoAccel Chatbot
# Handles both initial setup and regular deployments

# Ensure script is run with bash
if [ -z "$BASH_VERSION" ]; then
    echo "❌ This script must be run with bash, not sh"
    echo "   Usage: bash deploy.sh or ./deploy.sh"
    exit 1
fi

set -e

echo "🚀 GoAccel Deployment Script"
echo "=============================="
echo ""

# Check if running as root for service operations
NEED_ROOT=false
# Check EUID (Effective User ID) - available in bash
if [ -n "$EUID" ] && [ "$EUID" -ne 0 ]; then 
    NEED_ROOT=true
elif [ "$(id -u)" -ne 0 ]; then
    # Fallback if EUID not available
    NEED_ROOT=true
fi

# Default values
PROJECT_PATH="/var/www/chatbot"
SERVICE_USER="www-data"
SERVICE_NAME="goaccel.service"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}"

# Check if service exists
SERVICE_EXISTS=false
if [ -f "$SERVICE_FILE" ]; then
    SERVICE_EXISTS=true
    echo "✅ Service file exists: $SERVICE_FILE"
else
    echo "⚠️  Service file not found: $SERVICE_FILE"
fi

# If service doesn't exist, create it
if [ "$SERVICE_EXISTS" = false ]; then
    echo ""
    echo "📝 Setting up new service..."
    
    if [ "$NEED_ROOT" = true ]; then
        echo "❌ Root access required to create service. Please run with sudo."
        exit 1
    fi
    
    # Get project path if not default
    read -p "Enter project path (default: $PROJECT_PATH): " INPUT_PATH
    PROJECT_PATH=${INPUT_PATH:-$PROJECT_PATH}
    
    if [ ! -d "$PROJECT_PATH" ]; then
        echo "❌ Project directory not found: $PROJECT_PATH"
        exit 1
    fi
    
    # Get service user
    read -p "Enter user to run service as (default: $SERVICE_USER): " INPUT_USER
    SERVICE_USER=${INPUT_USER:-$SERVICE_USER}
    
    # Detect virtual environment
    if [ -d "$PROJECT_PATH/venv" ]; then
        VENV_PATH="$PROJECT_PATH/venv"
    elif [ -d "$PROJECT_PATH/.venv" ]; then
        VENV_PATH="$PROJECT_PATH/.venv"
    else
        echo "⚠️  Virtual environment not found. Using system Python."
        VENV_PATH=""
    fi
    
    # Determine paths
    if [ -n "$VENV_PATH" ]; then
        UVICORN_PATH="$VENV_PATH/bin/uvicorn"
        PYTHON_PATH="$VENV_PATH/bin"
    else
        UVICORN_PATH="uvicorn"
        PYTHON_PATH="/usr/bin"
    fi
    
    # Get port from existing service or default to 8001 (matching goaccel.service)
    PORT=8001
    if [ -f "$SERVICE_FILE" ]; then
        EXISTING_PORT=$(grep -oP '--port \K\d+' "$SERVICE_FILE" 2>/dev/null || echo "8001")
        if [ -n "$EXISTING_PORT" ] && [ "$EXISTING_PORT" -gt 0 ] 2>/dev/null; then
            PORT=$EXISTING_PORT
        fi
    fi
    
    # Create service file
    cat > $SERVICE_FILE << EOF
[Unit]
Description=GoAccel Chatbot API
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
ExecStart=$UVICORN_PATH main:app --host 127.0.0.1 --port $PORT
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
    
    echo "✅ Service file created at $SERVICE_FILE"
    
    # Set permissions
    chown root:root $SERVICE_FILE
    chmod 644 $SERVICE_FILE
    
    # Reload systemd
    echo "🔄 Reloading systemd..."
    systemctl daemon-reload
    
    # Enable service
    echo "✅ Enabling service..."
    systemctl enable $SERVICE_NAME
    
    # Step: Set up permissions for first-time deployment
    echo ""
    echo "🔐 Setting up permissions (first-time setup)..."
    
    # Set ownership of project directory
    echo "  Setting ownership of project directory..."
    chown -R $SERVICE_USER:$SERVICE_USER "$PROJECT_PATH" 2>/dev/null || {
        echo "  ⚠️  Could not set ownership. Run manually: sudo chown -R $SERVICE_USER:$SERVICE_USER $PROJECT_PATH"
    }
    
    # Ensure data directory exists and is writable
    echo "  Creating data directory..."
    mkdir -p "$PROJECT_PATH/data"
    chown -R $SERVICE_USER:$SERVICE_USER "$PROJECT_PATH/data" 2>/dev/null || {
        echo "  ⚠️  Could not set data directory ownership. Run manually: sudo chown -R $SERVICE_USER:$SERVICE_USER $PROJECT_PATH/data"
    }
    chmod -R 755 "$PROJECT_PATH/data" 2>/dev/null || {
        echo "  ⚠️  Could not set data directory permissions. Run manually: sudo chmod -R 755 $PROJECT_PATH/data"
    }
    
    # Ensure logs directory is writable (if it exists)
    if [ -d "$PROJECT_PATH/logs" ]; then
        echo "  Setting up logs directory..."
        chown -R $SERVICE_USER:$SERVICE_USER "$PROJECT_PATH/logs" 2>/dev/null || true
        chmod -R 755 "$PROJECT_PATH/logs" 2>/dev/null || true
    fi
    
    # Ensure .env file is readable by service user
    if [ -f "$PROJECT_PATH/.env" ]; then
        echo "  Setting .env file permissions..."
        chown $SERVICE_USER:$SERVICE_USER "$PROJECT_PATH/.env" 2>/dev/null || true
        chmod 600 "$PROJECT_PATH/.env" 2>/dev/null || true
    fi
    
    # Remove deprecated files
    echo "  Cleaning up deprecated files..."
    if [ -f "$PROJECT_PATH/business_configs.json" ]; then
        rm -f "$PROJECT_PATH/business_configs.json"
        echo "  ✅ Removed deprecated business_configs.json"
    fi
    
    echo "✅ Permissions setup complete"
    
    SERVICE_EXISTS=true
fi

# Navigate to project directory
if [ ! -d "$PROJECT_PATH" ]; then
    echo "❌ Project directory not found: $PROJECT_PATH"
    exit 1
fi

cd "$PROJECT_PATH"
echo ""
echo "📂 Working directory: $(pwd)"

# Step 1: Pull latest changes
echo ""
echo "📥 Step 1: Pulling latest changes from git..."
if git pull origin main; then
    echo "✅ Git pull successful"
else
    echo "⚠️  Git pull had issues, but continuing..."
fi

# Step 2: Activate virtual environment
echo ""
echo "🐍 Step 2: Setting up Python environment..."
if [ -d "venv" ]; then
    # Use . instead of source for better compatibility, but source should work in bash
    . venv/bin/activate || source venv/bin/activate
    echo "✅ Virtual environment activated"
elif [ -d ".venv" ]; then
    . .venv/bin/activate || source .venv/bin/activate
    echo "✅ Virtual environment activated"
else
    echo "⚠️  No virtual environment found, using system Python"
fi

# Step 3: Clean up deprecated files
echo ""
echo "🧹 Step 3: Cleaning up deprecated files..."
# Remove old file-based config (now using database only)
if [ -f "business_configs.json" ]; then
    rm -f business_configs.json
    echo "✅ Removed deprecated business_configs.json (now using database only)"
fi

# Step 4: Ensure data directory exists and is writable
echo ""
echo "📁 Step 4: Ensuring data directory is writable..."
if [ "$NEED_ROOT" = false ]; then
    mkdir -p data
    chown -R $SERVICE_USER:$SERVICE_USER data/ 2>/dev/null || true
    chmod -R 755 data/ 2>/dev/null || true
    echo "✅ Data directory permissions set"
else
    echo "⚠️  Run 'sudo chown -R $SERVICE_USER:$SERVICE_USER data/' to fix permissions"
fi

# Step 5: Install/update dependencies
echo ""
echo "📦 Step 5: Installing dependencies..."
if [ -f "requirements.txt" ]; then
    pip install -q -r requirements.txt
    echo "✅ requirements.txt installed"
else
    echo "⚠️  requirements.txt not found"
fi

if [ -f "requirements_voice.txt" ]; then
    pip install -q -r requirements_voice.txt
    echo "✅ requirements_voice.txt installed"
fi

# Step 6: Restart service
echo ""
echo "🔄 Step 6: Restarting service..."

if [ "$NEED_ROOT" = true ]; then
    echo "⚠️  Root access required to restart service."
    echo "   Please run manually: sudo systemctl restart $SERVICE_NAME"
else
    systemctl restart $SERVICE_NAME
    echo "✅ Service restarted"
    
    # Wait a moment for service to start
    sleep 3
    
    # Check status
    echo ""
    echo "📊 Step 7: Checking service status..."
    systemctl status $SERVICE_NAME --no-pager -l | head -20
fi

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📋 Useful commands:"
echo "  - View logs:    sudo journalctl -u $SERVICE_NAME -f"
echo "  - Check status: sudo systemctl status $SERVICE_NAME"
echo "  - Restart:      sudo systemctl restart $SERVICE_NAME"
echo "  - Stop:         sudo systemctl stop $SERVICE_NAME"
