# Quick Start Guide - Local Development

## Prerequisites

- **Python 3.8+**
- **pip** (Python package manager)
- **Git** (for cloning)
- Optional: **Docker** (for Ollama if not already running)

## Windows Quick Start (Development)

### 1. Clone and Setup

```powershell
# Clone the repository (or navigate to it)
cd C:\path\to\ollama_system

# Create virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file in project root:

```ini
# Ollama Configuration
OLLAMA_HOST=http://localhost:11434
OLLAMA_API_KEY=optional-key
OLLAMA_MODELS=mistral,neural-chat

# Or use Multi-Provider (JSON)
PROVIDERS='[
  {
    "name": "ollama_local",
    "type": "ollama",
    "base_url": "http://localhost:11434",
    "api_key": "optional",
    "models": ["mistral"],
    "enabled": true
  }
]'

# Logging
LOG_LEVEL=INFO
```

### 3. Run the Server

```powershell
# Option A: Using uvicorn directly
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# Option B: Using the provided wrapper
# First make sure you're in venv, then:
python -c "import subprocess; subprocess.run(['.\deploy\gunicorn_start.sh'], shell=True)"
```

Server will be available at: **http://localhost:8000**

### 4. Test the API

```powershell
# Health check
curl http://localhost:8000/health

# OpenAI-compatible endpoint
$body = @{
    model = "mistral"
    messages = @(@{role = "user"; content = "Hello"})
} | ConvertTo-Json

curl -X POST http://localhost:8000/openai/chat/completions `
  -Headers @{"Content-Type"="application/json"} `
  -Body $body
```

---

## Linux Quick Start (Development)

### 1. Clone and Setup

```bash
# Clone the repository
cd /path/to/ollama_system

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your configuration
nano .env
```

Or set environment variables:

```bash
export OLLAMA_HOST=http://localhost:11434
export OLLAMA_API_KEY=optional-key
export OLLAMA_MODELS=mistral,neural-chat
```

### 3. Run the Server

```bash
# Option A: Using uvicorn directly
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# Option B: Using the provided script
chmod +x deploy/gunicorn_start.sh
./deploy/gunicorn_start.sh
```

Server will be available at: **http://localhost:8000**

### 4. Test the API

```bash
# Health check
curl http://localhost:8000/health

# Generate text
curl -X POST http://localhost:8000/openai/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Hello, world!",
    "model": "mistral"
  }'

# List models
curl http://localhost:8000/openai/models
```

---

## Raspberry Pi / Linux Server Deployment

### Automated Deployment

**From Linux/Mac:**

```bash
cd /path/to/ollama_system

# Deploy to remote Pi
./deploy/pi_setup_and_deploy.sh --host pi.local --domain example.com --email you@example.com

# Or local deployment on Pi
./deploy/pi_setup_and_deploy.sh --local --domain example.com --email you@example.com
```

**From Windows:**

```powershell
cd C:\path\to\ollama_system

# Deploy to remote Pi (requires tar and ssh)
.\deploy\pi_setup_and_deploy.ps1 -HostName pi.local -Domain example.com -Email you@example.com
```

### Manual Deployment

If automated script fails:

```bash
# 1. SSH into Pi
ssh pi@pi.local

# 2. Create user
sudo adduser --disabled-password --gecos "" bradi
sudo usermod -aG sudo bradi

# 3. Copy project
sudo mkdir -p /home/bradi/ollama_system
sudo rsync -az ./ /home/bradi/ollama_system/
sudo chown -R bradi:bradi /home/bradi/ollama_system

# 4. Setup environment
cd /home/bradi/ollama_system
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 5. Setup systemd service
sudo cp deploy/systemd/ollama_system.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ollama_system

# 6. Setup nginx
sudo cp deploy/nginx/ollama_system_nossl.conf /etc/nginx/sites-available/ollama_system
sudo ln -sf /etc/nginx/sites-available/ollama_system /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# 7. Check logs
sudo journalctl -u ollama_system -f
```

---

## Docker Development

If you prefer Docker for Ollama:

```bash
# Start Ollama container
docker run -d -p 11434:11434 \
  -e OLLAMA_HOST=0.0.0.0:11434 \
  --name ollama \
  ollama/ollama

# Pull a model
docker exec ollama ollama pull mistral

# Then configure .env:
OLLAMA_HOST=http://host.docker.internal:11434  # From Docker on Windows/Mac
# OR
OLLAMA_HOST=http://localhost:11434  # From host on Linux
```

---

## Testing

### Manual API Testing

**Python:**

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/openai",
    api_key="dummy"
)

response = client.chat.completions.create(
    model="mistral",
    messages=[{"role": "user", "content": "Hello"}]
)

print(response.choices[0].message.content)
```

**cURL:**

```bash
# Chat
curl -X POST http://localhost:8000/openai/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mistral",
    "messages": [{"role": "user", "content": "Hello"}]
  }' | jq

# Generate
curl -X POST http://localhost:8000/openai/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Hello",
    "model": "mistral"
  }' | jq
```

### Running Tests

```bash
# Unit tests (if available)
pytest tests/

# Type checking
mypy app/ helpers/ classes/

# Linting
flake8 app/ helpers/ classes/
```

---

## Troubleshooting

### Port 8000 Already in Use

```bash
# Find process using port 8000
lsof -i :8000  # Linux/Mac
netstat -ano | findstr :8000  # Windows

# Kill process
kill -9 <PID>  # Linux/Mac
taskkill /PID <PID> /F  # Windows
```

### Ollama Connection Error

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama (if installed)
ollama serve

# Or via Docker
docker run -d -p 11434:11434 ollama/ollama
```

### Models Not Found

```bash
# Check configured models
curl http://localhost:8000/openai/models

# Check Ollama directly
curl http://localhost:11434/api/tags

# Pull a model
ollama pull mistral
```

### Permission Denied (Linux)

```bash
# Make scripts executable
chmod +x deploy/*.sh

# Check project permissions
ls -la | grep ollama_system
```

---

## Production Considerations

### SSL/TLS

- Use `ollama_system.conf` with certbot
- Let's Encrypt certificates auto-renew via certbot

### Performance

- Adjust `WORKERS` in systemd service for your CPU count
- Use nginx for load balancing multiple instances
- Monitor with `journalctl -u ollama_system -f`

### Monitoring

```bash
# View logs
sudo journalctl -u ollama_system -f

# Check service status
sudo systemctl status ollama_system

# Restart service
sudo systemctl restart ollama_system
```

---

## Next Steps

1. Read [API_ROUTES.md](API_ROUTES.md) for complete API documentation
2. Read [MULTI_PROVIDER_SETUP.md](MULTI_PROVIDER_SETUP.md) for multi-provider configuration
3. Read [ARCHITECTURE.md](ARCHITECTURE.md) for system design
4. Configure your providers in `.env`
5. Start developing!

---

## Support

For issues:
1. Check logs: `journalctl -u ollama_system -f` (Linux) or output (dev mode)
2. Verify Ollama is running and models are available
3. Check `.env` configuration
4. Ensure ports 8000, 80, 443 are available

