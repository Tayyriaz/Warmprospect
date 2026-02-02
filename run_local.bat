@echo off
echo ========================================
echo Warmprospect Local Setup & Run
echo ========================================
echo.

REM Check if .env exists
if not exist .env (
    echo Creating .env file...
    echo GEMINI_API_KEY=your_gemini_api_key_here > .env
    echo DATABASE_URL=postgresql://postgres:postgres@localhost:5432/warmprospect >> .env
    echo REDIS_URL=redis://localhost:6379/0 >> .env
    echo ADMIN_API_KEY= >> .env
    echo GEMINI_MODEL=gemini-2.5-flash >> .env
    echo PORT=8000 >> .env
    echo.
    echo ⚠️  Please edit .env file and add your GEMINI_API_KEY and ADMIN_API_KEY
    echo.
    pause
)

REM Check if virtual environment exists
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt

REM Initialize database
echo Initializing database...
python -c "from core.database import init_db; init_db()"

REM Generate admin key if not set
python scripts\generate_admin_key.py --env-format

echo.
echo ========================================
echo Starting application...
echo ========================================
echo.
echo Server will start at: http://localhost:8000
echo Admin panel: http://localhost:8000/admin
echo Chatbot: http://localhost:8000/bot
echo.
echo Press Ctrl+C to stop
echo.

python main.py
