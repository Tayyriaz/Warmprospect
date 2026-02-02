#!/bin/bash

echo "========================================"
echo "Warmprospect Local Setup & Run"
echo "========================================"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "Creating .env file..."
    cat > .env << EOF
GEMINI_API_KEY=your_gemini_api_key_here
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/warmprospect
REDIS_URL=redis://localhost:6379/0
ADMIN_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
PORT=8000
EOF
    echo ""
    echo "⚠️  Please edit .env file and add your GEMINI_API_KEY and ADMIN_API_KEY"
    echo ""
    read -p "Press Enter to continue..."
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Initialize database
echo "Initializing database..."
python -c "from core.database import init_db; init_db()"

# Generate admin key if not set
python scripts/generate_admin_key.py --env-format

echo ""
echo "========================================"
echo "Starting application..."
echo "========================================"
echo ""
echo "Server will start at: http://localhost:8000"
echo "Admin panel: http://localhost:8000/admin"
echo "Chatbot: http://localhost:8000/bot"
echo ""
echo "Press Ctrl+C to stop"
echo ""

python main.py
