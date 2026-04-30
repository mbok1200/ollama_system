# Multi-Provider LLM Architecture

## Overview

This system provides a unified interface for working with multiple LLM providers with automatic fallback support.

```
┌─────────────────────────────────────────────────────┐
│                User Requests                         │
└─────────────────────┬───────────────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
    Generate        Chat          Tools
   (Single)      (Multi-turn)   (Function)
        │             │             │
        └─────────────┼─────────────┘
                      │
        ┌─────────────▼─────────────┐
        │   Multi-Provider Fallback │
        │   Controller              │
        └─────────────┬─────────────┘
                      │
        ┌─────────────▼──────────────────┐
        │  Providers Configuration       │
        │  - Parse ENV variables        │
        │  - Manage provider list       │
        └─────────────┬──────────────────┘
                      │
        ┌─────────────┼──────────────┬───────────┐
        ▼             ▼              ▼           ▼
    Ollama         OpenAI        Together     Custom
    Provider      Compatible      AI         Provider
```

## Component Structure

### 1. Configuration Layer

**`helpers/providers_config.py`**
- `ProvidersConfigManager`: Manages provider configuration
  - Loads from `PROVIDERS` JSON env var (highest priority)
  - Falls back to individual provider env vars
  - Provides methods to query and manage providers

**Env Variables:**
```
PROVIDERS='[{...}]'           # JSON array of providers (primary)
OLLAMA_HOST                   # Fallback Ollama config
OPENAI_BASE_URL              # Fallback OpenAI config
```

### 2. Fallback Logic Layer

**`helpers/multi_provider_fallback.py`**
- `MultiProviderFallback`: Handles provider fallback
  - `try_all_providers()`: Generic fallback mechanism
  - `test_model_availability()`: Test if model works
  - `try_providers_for_generate()`: Generate with fallback
  - `try_providers_for_chat()`: Chat with fallback
  - `get_available_models()`: Query available models

### 3. Implementation Layer

**For Ollama (Single Provider):**
- `classes/generate/main.py`: GenerateMain
- `classes/chat/main.py`: ChatMain
- `classes/tools/main.py`: ToolsMain
- `helpers/model_fallback.py`: ModelFallbackHelper

**For Multi-Provider:**
- `classes/generate_multi/main.py`: GenerateMultiProviderMain
- `classes/chat_multi/main.py`: ChatMultiProviderMain

## Data Flow Example

### Generate Request with Multi-Provider Fallback

```
1. User Request
   └─ prompt: "Hello"
   └─ system_prompt: "You are helpful"
   └─ model: None (use any available)

2. GenerateMultiProviderMain.generate()
   └─ Calls MultiProviderFallback.try_providers_for_generate()

3. MultiProviderFallback tries each provider in order:
   
   Provider 1: Ollama
   ├─ Get first model: "mistral"
   ├─ Call client.generate("mistral", prompt, system)
   ├─ Success! ✓ Return response
   
   (Provider 2, 3, etc. skipped as we got success)

4. Return generated text to user
```

### Generate with Model Not Found

```
1. User Request
   └─ prompt: "Hello"
   └─ model: "DeepSeek V3" (specific model)

2. GenerateMultiProviderMain._generate_with_model()
   
3. Try each provider that has "DeepSeek V3":
   
   Provider 1: Ollama
   └─ Doesn't have "DeepSeek V3", skip
   
   Provider 2: Claud API
   └─ Has "DeepSeek V3"
   └─ Call client.chat.completions.create()
   └─ Success! ✓ Return response

4. Return response to user
```

### All Providers Fail

```
1. User Request
   └─ Any request that fails

2. Try Provider 1
   └─ Error: Connection timeout
   
3. Try Provider 2
   └─ Error: Invalid API key
   
4. Try Provider 3
   └─ Error: Model not found
   
5. All failed, return 503:
   {
     "detail": "All providers failed. Errors: 
       provider1: Connection timeout; 
       provider2: Invalid API key; 
       provider3: Model not found"
   }
```

## Provider Types

### Ollama
- Self-hosted LLM server
- Supports local/remote instances
- Config:
  ```json
  {
    "type": "ollama",
    "base_url": "http://localhost:11434",
    "api_key": "optional",
    "models": ["mistral", "llama2"]
  }
  ```

### OpenAI-Compatible
- Works with any OpenAI-compatible API
- Includes: Claud, Together AI, LocalAI, etc.
- Config:
  ```json
  {
    "type": "openai",
    "base_url": "https://api.claud.io/v1",
    "api_key": "your-key",
    "models": ["DeepSeek V3"]
  }
  ```

## Configuration Examples

### Single Provider (Ollama)
```python
# Minimal .env
OLLAMA_HOST=http://localhost:11434
OLLAMA_API_KEY=key
OLLAMA_MODELS=mistral,llama2
```

### Multiple Providers
```python
# Complex .env
PROVIDERS='[
  {
    "name": "ollama",
    "type": "ollama",
    "base_url": "http://localhost:11434",
    "api_key": "key1",
    "models": ["mistral"]
  },
  {
    "name": "claud",
    "type": "openai",
    "base_url": "https://api.claud.io/v1",
    "api_key": "key2",
    "models": ["DeepSeek V3"]
  }
]'
```

## Usage Patterns

### Pattern 1: Use Any Available Model
```python
generator = GenerateMultiProviderMain()
response = await generator.generate(prompt="Hello")
# Uses first working provider's first model
```

### Pattern 2: Request Specific Model
```python
response = await generator.generate(
    prompt="Hello",
    model="DeepSeek V3"
)
# Searches all providers for "DeepSeek V3"
```

### Pattern 3: Direct Provider Selection (Advanced)
```python
config = ProvidersConfigManager()
provider = config.get_provider("claud_api")
# Manually use specific provider
```

## Error Handling

All operations use consistent error handling:

```python
try:
    response = await generator.generate(prompt)
except HTTPException as e:
    # e.status_code = 503 (service unavailable)
    # e.detail = "All providers failed. Errors: ..."
except Exception as e:
    # Unexpected error
```

## Performance Characteristics

| Operation | Time | Notes |
|-----------|------|-------|
| First try (success) | ~100-500ms | Provider latency |
| First try (fail) + second try | ~200-1000ms | Sequential tries |
| All providers fail | ~5-10s | All tried sequentially |
| Model existence check | ~50-200ms | Light verification |

## Future Enhancements

- [ ] Parallel provider tries (async)
- [ ] Provider health monitoring
- [ ] Request caching/deduplication
- [ ] Cost tracking per provider
- [ ] Load balancing strategies
- [ ] Provider-specific rate limiting
- [ ] Automatic provider ranking
- [ ] Support for Anthropic API
- [ ] Support for Google Vertex AI
- [ ] Support for Hugging Face Inference

## File Structure

```
helpers/
├── config.py                    # Ollama-specific config
├── model_fallback.py           # Ollama fallback logic
├── providers_config.py         # Multi-provider config
└── multi_provider_fallback.py  # Multi-provider fallback

classes/
├── generate/
│   └── main.py                 # Ollama generate
├── generate_multi/
│   └── main.py                 # Multi-provider generate
├── chat/
│   └── main.py                 # Ollama chat
├── chat_multi/
│   └── main.py                 # Multi-provider chat
├── tools/
│   └── main.py                 # Ollama tools
└── tools_multi/
    └── main.py                 # Multi-provider tools (future)
```

## Migration Path

1. **Phase 1:** Ollama only (current)
   - Use existing `GenerateMain`, `ChatMain`
   - Config via `OLLAMA_*` env vars

2. **Phase 2:** Multi-provider support
   - Use new `GenerateMultiProviderMain`
   - Config via `PROVIDERS` JSON env var
   - Backward compatible with `OLLAMA_*` env vars

3. **Phase 3:** Provider-specific optimizations
   - Specialized handlers per provider type
   - Performance improvements
   - Cost optimization
