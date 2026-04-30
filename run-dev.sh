#!/usr/bin/env bash
set -euo pipefail

# Quick start script for Linux development

echo "===== Ollama System - Linux Development ====="
echo

# Check if venv exists
if [[ ! -d "venv" ]]; then
    echo "[*] Creating virtual environment..."
    python3 -m venv venv
fi

# Activate venv
echo "[*] Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "[*] Installing dependencies..."
pip install -q -r requirements.txt

# Check for .env file
if [[ ! -f ".env" ]]; then
    echo "[*] .env file not found. Creating from .env.example..."
    if [[ -f ".env.example" ]]; then
        cp .env.example .env
        echo "[*] Please edit .env with your configuration"
    else
        echo "[*] Creating minimal .env..."
        cat > .env << 'CONFIG'
# Ollama Configuration
OLLAMA_HOST=http://localhost:11434
OLLAMA_API_KEY=optional
OLLAMA_MODELS=mistral
LOG_LEVEL=INFO
CONFIG
    fi
    echo "[!] Before running the server, configure your .env file"
fi

echo
echo "[?] How would you like to run the server?"
echo "    1 = Development (uvicorn with auto-reload, foreground)"
echo "    2 = Development (uvicorn in background with nohup)"
echo "    3 = Production (gunicorn, foreground)"
echo "    4 = Production (gunicorn in background with nohup)"
echo "    5 = Exit"
echo

read -p "Enter choice (1-5): " choice

case "$choice" in
    1)
        echo "[*] Starting development server (foreground)..."
        echo "[*] Server will be available at http://localhost:8000 and http://YOUR_IP:8000"
        echo "[*] Press Ctrl+C to stop"
        echo
        python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
        ;;
    2)
        echo "[*] Starting development server (background)..."
        echo "[*] Server will be available at http://localhost:8000 and http://YOUR_IP:8000"
        echo "[*] Check ollama_system.log for output"
        echo
        nohup python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload > ollama_system.log 2>&1 &
        echo "[+] Server started in background (PID: $!)"
        echo "[*] Run 'tail -f ollama_system.log' to see logs"
        echo "[*] Run 'pkill -f uvicorn' to stop the server"
        ;;
    3)
        echo "[*] Starting production server (foreground)..."
        echo "[*] Server will be available at http://localhost:8000 and http://YOUR_IP:8000"
        echo
        python -m gunicorn -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:8000 --workers 1
        ;;
    4)
        echo "[*] Starting production server (background)..."
        echo "[*] Server will be available at http://localhost:8000 and http://YOUR_IP:8000"
        echo "[*] Check ollama_system.log for output"
        echo
        nohup python -m gunicorn -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:8000 --workers 1 > ollama_system.log 2>&1 &
        echo "[+] Server started in background (PID: $!)"
        echo "[*] Run 'tail -f ollama_system.log' to see logs"
        echo "[*] Run 'pkill -f gunicorn' to stop the server"
        ;;
    5)
        echo "[*] Exiting..."
        exit 0
        ;;
    *)
        echo "[ERROR] Invalid choice"
        exit 1
        ;;
esac
