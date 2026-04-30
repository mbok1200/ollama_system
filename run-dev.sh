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
echo "    1 = Development (uvicorn with auto-reload)"
echo "    2 = Production (gunicorn)"
echo "    3 = Exit"
echo

read -p "Enter choice (1-3): " choice

case "$choice" in
    1)
        echo "[*] Starting development server..."
        echo "[*] Server will be available at http://localhost:8000"
        echo "[*] Press Ctrl+C to stop"
        echo
        python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
        ;;
    2)
        echo "[*] Starting production server..."
        echo "[*] Server will be available at http://127.0.0.1:8000"
        echo
        python -m gunicorn -k uvicorn.workers.UvicornWorker app.main:app --bind 127.0.0.1:8000 --workers 1
        ;;
    3)
        echo "[*] Exiting..."
        exit 0
        ;;
    *)
        echo "[ERROR] Invalid choice"
        exit 1
        ;;
esac
