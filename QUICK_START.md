# Ollama System - Quick Start Guide

## 🚀 Quick Commands

### Linux/Git Bash (Windows)
```bash
# Development - foreground (port 8000)
./run-dev.sh
# Then choose: 1

# Development - background (port 8000)
./run-dev.sh
# Then choose: 2

# Custom port (e.g., 8001)
PORT=8001 ./run-dev.sh
# Then choose: 1 or 2
```

### Windows (CMD/PowerShell)
```batch
# Development - foreground (port 8000)
.\run-dev.bat
# Then choose: 1

# Development - background (port 8000)
.\run-dev.bat
# Then choose: 2

# Custom port (set before running)
set PORT=8001
.\run-dev.bat
```

## 📊 Server Status

The server provides a health check endpoint:
```bash
# Check if server is running
curl http://localhost:8000/health
# Expected response: {"status":"ok"}
```

## 🔗 Access Server

Once running, access the API from:
- **Localhost**: `http://localhost:8000`
- **External IP**: `http://YOUR_IP:8000` (or `http://YOUR_IP:PORT`)

## 🔄 Background Management

### Linux
```bash
# View logs
tail -f ollama_system.log

# Stop server
pkill -f uvicorn
# or
pkill -f gunicorn
```

### Windows
- Server runs in minimized window
- Task Manager → Search for `python` or `gunicorn`
- Close the window or kill the process

## ⚙️ Configuration

Edit `.env` file to configure:
```
OLLAMA_HOST=http://localhost:11434
OLLAMA_API_KEY=optional
OLLAMA_MODELS=mistral
LOG_LEVEL=INFO
```

## 📍 API Endpoints

- `GET /health` - Server health check
- `POST /search` - Search
- `POST /generate` - Generate text
- `POST /chat` - Chat
- `POST /tools` - Tools
- `GET /models` - List models
- `POST /openai/chat/completions` - OpenAI-compatible chat
- `POST /openai/generate` - OpenAI-compatible generate
- `GET /openai/models` - OpenAI-compatible models list

## 🆘 Troubleshooting

**Port already in use:**
```bash
# Use custom port
PORT=8001 ./run-dev.sh
```

**Dependencies missing:**
- Ensure venv is activated
- Run `pip install -r requirements.txt`

**Ollama not found:**
- Ensure Ollama is running and `OLLAMA_HOST` is correct in `.env`
