@echo off
REM Quick start script for Windows development

echo ===== Ollama System - Windows Development =====
echo.

REM Check if venv exists
if not exist "venv\" (
    echo [*] Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create venv. Make sure Python 3.8+ is installed.
        exit /b 1
    )
)

REM Activate venv
echo [*] Activating virtual environment...
call venv\Scripts\activate.bat

REM Install dependencies
echo [*] Installing dependencies...
pip install -q -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    exit /b 1
)

REM Check for .env file
if not exist ".env" (
    echo [*] .env file not found. Creating from .env.example...
    if exist ".env.example" (
        copy .env.example .env
        echo [*] Please edit .env with your configuration
    ) else (
        echo [*] Creating minimal .env...
        (
            echo # Ollama Configuration
            echo OLLAMA_HOST=http://localhost:11434
            echo OLLAMA_API_KEY=optional
            echo OLLAMA_MODELS=mistral
            echo LOG_LEVEL=INFO
        ) > .env
    )
    echo [!] Before running the server, configure your .env file
)

REM Ask which mode to run
echo.
echo [?] How would you like to run the server?
echo     1 = Development (uvicorn with auto-reload)
echo     2 = Production (gunicorn)
echo     3 = Exit

set /p choice="Enter choice (1-3): "

if "%choice%"=="1" (
    echo [*] Starting development server...
    echo [*] Server will be available at http://localhost:8000
    echo [*] Press Ctrl+C to stop
    echo.
    python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
) else if "%choice%"=="2" (
    echo [*] Starting production server...
    echo [*] Server will be available at http://127.0.0.1:8000
    echo.
    python -m gunicorn -k uvicorn.workers.UvicornWorker app.main:app --bind 127.0.0.1:8000 --workers 1
) else if "%choice%"=="3" (
    echo [*] Exiting...
    exit /b 0
) else (
    echo [ERROR] Invalid choice
    exit /b 1
)
