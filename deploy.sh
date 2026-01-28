#!/bin/bash
# Deploy script for GoAccel Chatbot
# Handles both initial setup and regular deployments

set -e

echo "🚀 GoAccel Deployment Script"
echo "=============================="
echo ""

# Check if running as root for service operations
NEED_ROOT=false
if [ "$EUID" -ne 0 ]; then 
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
        EXISTING_PORT=$(grep -oP '--port \K\d+' "$SERVICE_FILE" || echo "8001")
        PORT=${EXISTING_PORT:-8001}
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
    source venv/bin/activate
    echo "✅ Virtual environment activated"
elif [ -d ".venv" ]; then
    source .venv/bin/activate
    echo "✅ Virtual environment activated"
else
    echo "⚠️  No virtual environment found, using system Python"
fi

# Step 3: Install/update dependencies
echo ""
echo "📦 Step 3: Installing dependencies..."
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

# Step 4: Restart service
echo ""
echo "🔄 Step 4: Restarting service..."

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
    echo "📊 Step 5: Checking service status..."
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
