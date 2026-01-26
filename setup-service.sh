#!/bin/bash
# Setup GoAccel Systemd Service
# Run on your VPS

set -e

echo "🔧 GoAccel Service Setup"
echo "========================"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Please run with sudo"
    exit 1
fi

# Step 1: Find and stop old services
echo "📋 Step 1: Finding old services..."
echo ""

OLD_SERVICES=$(systemctl list-units --type=service --all | grep -E "(chatbot|warmprospect|goaccel|uvicorn)" | awk '{print $1}' || true)

if [ -n "$OLD_SERVICES" ]; then
    echo "Found these services:"
    echo "$OLD_SERVICES"
    echo ""
    read -p "Stop and disable these? (y/n): " STOP_OLD
    if [ "$STOP_OLD" = "y" ]; then
        for service in $OLD_SERVICES; do
            echo "Stopping $service..."
            systemctl stop $service 2>/dev/null || true
            systemctl disable $service 2>/dev/null || true
        done
    fi
else
    echo "No old services found."
fi

# Also check for running uvicorn processes
UVICORN_PIDS=$(ps aux | grep "uvicorn main:app" | grep -v grep | awk '{print $2}' || true)
if [ -n "$UVICORN_PIDS" ]; then
    echo ""
    echo "Found running uvicorn processes: $UVICORN_PIDS"
    read -p "Kill these processes? (y/n): " KILL_PROC
    if [ "$KILL_PROC" = "y" ]; then
        kill $UVICORN_PIDS
        echo "Processes killed."
    fi
fi

echo ""
echo "📝 Step 2: Configuring new service..."
echo ""

# Get project path
read -p "Enter your project path (e.g., /var/www/goaccel): " PROJECT_PATH
if [ -z "$PROJECT_PATH" ]; then
    echo "❌ Project path is required"
    exit 1
fi

# Get username
read -p "Enter user to run service as (default: www-data): " SERVICE_USER
SERVICE_USER=${SERVICE_USER:-www-data}

# Check if venv exists
if [ -d "$PROJECT_PATH/venv" ]; then
    VENV_PATH="$PROJECT_PATH/venv"
elif [ -d "$PROJECT_PATH/.venv" ]; then
    VENV_PATH="$PROJECT_PATH/.venv"
else
    echo "⚠️  Virtual environment not found. Using system Python."
    VENV_PATH=""
fi

# Create service file
SERVICE_FILE="/etc/systemd/system/goaccel.service"

if [ -n "$VENV_PATH" ]; then
    UVICORN_PATH="$VENV_PATH/bin/uvicorn"
    PYTHON_PATH="$VENV_PATH/bin"
else
    UVICORN_PATH="uvicorn"
    PYTHON_PATH="/usr/bin"
fi

cat > $SERVICE_FILE << EOF
[Unit]
Description=GoAccel Chatbot API
After=network.target postgresql.service redis-server.service
Requires=postgresql.service redis-server.service

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$PROJECT_PATH
Environment="PATH=$PYTHON_PATH"
EnvironmentFile=$PROJECT_PATH/.env
ExecStart=$UVICORN_PATH main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

echo "✅ Service file created at $SERVICE_FILE"
echo ""

# Set permissions
chown root:root $SERVICE_FILE
chmod 644 $SERVICE_FILE

# Reload systemd
echo "🔄 Reloading systemd..."
systemctl daemon-reload

# Enable service
echo "✅ Enabling service..."
systemctl enable goaccel

# Start service
echo "🚀 Starting service..."
systemctl start goaccel

# Wait a moment
sleep 2

# Check status
echo ""
echo "📊 Service Status:"
systemctl status goaccel --no-pager -l

echo ""
echo "✅ Setup complete!"
echo ""
echo "📋 Useful commands:"
echo "  - Status: sudo systemctl status goaccel"
echo "  - Logs: sudo journalctl -u goaccel -f"
echo "  - Restart: sudo systemctl restart goaccel"
echo "  - Stop: sudo systemctl stop goaccel"
