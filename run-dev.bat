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

REM Get port from environment or use default
if "%PORT%"=="" set PORT=8000
echo [*] Using port: %PORT%

REM Ask which mode to run
echo.
echo [?] How would you like to run the server?
echo     1 = Development (uvicorn with auto-reload, foreground)
echo     2 = Development (uvicorn in background)
echo     3 = Production (gunicorn, foreground)
echo     4 = Production (gunicorn in background)
echo     5 = Exit

set /p choice="Enter choice (1-5): "

if "%choice%"=="1" (
    echo [*] Starting development server (foreground)...
    echo [*] Server will be available at http://localhost:%PORT% and http://YOUR_IP:%PORT%
    echo [*] Press Ctrl+C to stop
    echo.
    python -m uvicorn app.main:app --host 0.0.0.0 --port %PORT% --reload
) else if "%choice%"=="2" (
    echo [*] Starting development server (background)...
    echo [*] Server will be available at http://localhost:%PORT% and http://YOUR_IP:%PORT%
    echo [*] Check console.log for output
    echo.
    start "Ollama System - Dev" /MIN python -m uvicorn app.main:app --host 0.0.0.0 --port %PORT% --reload
    timeout /t 2 /nobreak
    echo [+] Server started in background. Open console.log to see output.
) else if "%choice%"=="3" (
    echo [*] Starting production server (foreground)...
    echo [*] Server will be available at http://localhost:%PORT% and http://YOUR_IP:%PORT%
    echo.
    python -m gunicorn -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:%PORT% --workers 1
) else if "%choice%"=="4" (
    echo [*] Starting production server (background)...
    echo [*] Server will be available at http://localhost:%PORT% and http://YOUR_IP:%PORT%
    echo [*] Check console.log for output
    echo.
    start "Ollama System - Prod" /MIN python -m gunicorn -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:%PORT% --workers 1
    timeout /t 2 /nobreak
    echo [+] Server started in background. Open console.log to see output.
) else if "%choice%"=="5" (
    echo [*] Exiting...
    exit /b 0
) else (
    echo [ERROR] Invalid choice
    exit /b 1
)
