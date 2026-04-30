# API Routes Documentation

## Base Routes (Ollama/Single Provider)

### POST /generate
Generate text using Ollama.

**Request:**
```json
{
  "prompt": "What is machine learning?",
  "system_prompt": "You are a helpful assistant"
}
```

**Response:**
```json
{
  "response": "Machine learning is...",
  "model": "mistral"
}
```

### POST /chat
Chat with streaming support.

**Request:**
```json
{
  "messages": [
    {"role": "user", "content": "Hello"}
  ]
}
```

**Response:**
```json
{
  "response": "Hello! How can I help?"
}
```

### POST /tools
Execute tools/functions with model.

**Request:**
```json
{
  "messages": [...],
  "tool_calls": [...]
}
```

**Response:**
```json
{
  "messages": [...]
}
```

### GET /models
Get list of available models.

**Query Parameters:**
- `refresh` (bool): Force refresh from API

**Response:**
```json
{
  "models": [
    {
      "name": "mistral",
      "model": "mistral",
      "requires_subscription": false
    }
  ]
}
```

### GET /health
Health check endpoint.

**Response:**
```json
{
  "status": "ok"
}
```

---

## OpenAI-Compatible Routes (Multi-Provider)

### POST /openai/chat/completions
OpenAI-compatible chat completions endpoint.

**Request:**
```json
{
  "model": "DeepSeek V3",
  "messages": [
    {"role": "user", "content": "Hello"}
  ]
}
```

**Response:**
```json
{
  "object": "chat.completion",
  "choices": [
    {
      "message": {
        "role": "assistant",
        "content": "Hello! How can I help?"
      },
      "finish_reason": "stop",
      "index": 0
    }
  ],
  "model": "DeepSeek V3",
  "usage": {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0
  }
}
```

**Notes:**
- Compatible with OpenAI SDK: `client = OpenAI(base_url="http://localhost:8000/openai", api_key="dummy")`
- If `model` is not specified, uses first available model from first available provider
- Automatically falls back to next provider if current fails

### POST /openai/generate
Generate text using multi-provider system.

**Request:**
```json
{
  "prompt": "Explain quantum computing",
  "system_prompt": "You are a physicist",
  "model": "DeepSeek V3"
}
```

**Response:**
```json
{
  "object": "text_completion",
  "choices": [
    {
      "text": "Quantum computing is...",
      "finish_reason": "stop",
      "index": 0
    }
  ],
  "model": "DeepSeek V3",
  "usage": {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0
  }
}
```

**Parameters:**
- `prompt` (required): Text to generate
- `system_prompt` (optional): System context
- `model` (optional): Specific model to use

### POST /openai/chat
Simple chat endpoint.

**Request:**
```json
{
  "messages": [
    {"role": "user", "content": "What is Python?"}
  ],
  "model": "Claude 3.5"
}
```

**Response:**
```json
{
  "response": "Python is a programming language...",
  "model": "Claude 3.5"
}
```

### GET /openai/models
List all available models across all providers.

**Response:**
```json
{
  "object": "list",
  "data": [
    {
      "id": "mistral",
      "object": "model",
      "created": 0,
      "owned_by": "ollama",
      "permission": [],
      "root": "mistral",
      "parent": null,
      "provider": "ollama",
      "provider_type": "ollama"
    },
    {
      "id": "DeepSeek V3",
      "object": "model",
      "created": 0,
      "owned_by": "claud_api",
      "permission": [],
      "root": "DeepSeek V3",
      "parent": null,
      "provider": "claud_api",
      "provider_type": "openai"
    }
  ]
}
```

### GET /openai/providers
List all configured providers and their models.

**Response:**
```json
{
  "providers": [
    {
      "name": "ollama",
      "type": "ollama",
      "enabled": true,
      "models": ["mistral", "llama2"]
    },
    {
      "name": "claud_api",
      "type": "openai",
      "enabled": true,
      "models": ["DeepSeek V3"]
    }
  ],
  "total": 2
}
```

### POST /openai/test-model
Test if a model is available in any provider.

**Request:**
```json
{
  "model": "DeepSeek V3"
}
```

**Response:**
```json
{
  "model": "DeepSeek V3",
  "available": true,
  "providers": [
    {
      "provider": "ollama",
      "model": "DeepSeek V3",
      "available": false
    },
    {
      "provider": "claud_api",
      "model": "DeepSeek V3",
      "available": true
    }
  ]
}
```

---

## Rate Limiting

All endpoints have rate limiting enabled:

| Endpoint | Limit |
|----------|-------|
| /search | 10/minute |
| /generate, /openai/generate | 10/minute |
| /chat, /openai/chat* | 30/minute |
| /tools | 10/minute |
| /models, /openai/models, /openai/providers | 30/minute |
| /openai/test-model | 10/minute |

---

## Error Responses

### 400 Bad Request
Missing required field.

```json
{
  "detail": "Missing 'messages' field"
}
```

### 503 Service Unavailable
All providers failed.

```json
{
  "detail": "All providers failed. Errors: provider1: Connection timeout; provider2: Invalid API key"
}
```

### 413 Request Entity Too Large
Request body exceeds limit (default 4MB).

```
Request body too large
```

---

## Example: Using with OpenAI Python SDK

```python
from openai import OpenAI

# Point to your local server
client = OpenAI(
    base_url="http://localhost:8000/openai",
    api_key="dummy"  # Not used, but required by SDK
)

# Use chat completions (will try all configured providers)
response = client.chat.completions.create(
    model="DeepSeek V3",  # Can be any model in any provider
    messages=[
        {"role": "user", "content": "Hello"}
    ]
)

print(response.choices[0].message.content)
```

---

## Example: Direct HTTP Requests

### Generate with cURL
```bash
curl -X POST http://localhost:8000/openai/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Hello",
    "model": "DeepSeek V3"
  }'
```

### Chat with cURL
```bash
curl -X POST http://localhost:8000/openai/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "DeepSeek V3",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

### List Models with cURL
```bash
curl http://localhost:8000/openai/models
```

---

## Fallback Behavior

When a request is made:

1. **If model specified:** Searches all providers for that model
2. **If model not specified:** Uses first available model from first working provider
3. **If provider fails:** Tries next provider in order
4. **If all fail:** Returns 503 with error details from all attempts

---

## Configuration for Clients

### Python OpenAI SDK
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/openai",
    api_key="dummy"
)
```

### Node.js
```javascript
const OpenAI = require('openai');

const client = new OpenAI({
  baseURL: 'http://localhost:8000/openai',
  apiKey: 'dummy',
});
```

### cURL
```bash
BASE_URL="http://localhost:8000/openai"
MODEL="DeepSeek V3"

curl -X POST "$BASE_URL/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{"model":"'$MODEL'","messages":[{"role":"user","content":"Hello"}]}'
```

