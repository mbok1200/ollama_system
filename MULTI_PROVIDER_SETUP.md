# Multi-Provider LLM System

This system supports multiple LLM providers with automatic fallback. If one provider fails, it automatically tries the next provider in the list.

## Supported Providers

- **ollama**: Self-hosted Ollama instances
- **openai**: OpenAI-compatible APIs (including Claud, Together AI, etc.)

## Configuration

### Method 1: JSON PROVIDERS Environment Variable (Recommended)

Set a single `PROVIDERS` environment variable with a JSON array:

```bash
export PROVIDERS='[
  {
    "name": "ollama_local",
    "type": "ollama",
    "base_url": "http://localhost:11434",
    "api_key": "optional-key",
    "models": ["mistral", "llama2"],
    "enabled": true
  },
  {
    "name": "claud_api",
    "type": "openai",
    "base_url": "https://api.claud.io/v1",
    "api_key": "your-claud-api-key",
    "models": ["DeepSeek V3"],
    "enabled": true
  },
  {
    "name": "together_ai",
    "type": "openai",
    "base_url": "https://api.together.xyz/v1",
    "api_key": "your-together-key",
    "models": ["meta-llama/Llama-3-70b"],
    "enabled": true
  }
]'
```

### Method 2: Individual Environment Variables (Fallback)

If `PROVIDERS` is not set, the system falls back to individual provider configuration:

```bash
# Ollama
export OLLAMA_HOST=http://localhost:11434
export OLLAMA_API_KEY=optional-key
export OLLAMA_MODELS=mistral,llama2

# OpenAI-compatible
export OPENAI_BASE_URL=https://api.claud.io/v1
export OPENAI_API_KEY=your-api-key
export OPENAI_MODELS=DeepSeek V3,Claude 3.5
```

## Usage Examples

### Using GenerateMultiProviderMain

```python
from classes.generate_multi.main import GenerateMultiProviderMain

async def generate_text():
    generator = GenerateMultiProviderMain()
    
    # Try any available model (uses first working provider)
    response = await generator.generate(
        prompt="Explain quantum computing in simple terms",
        system_prompt="You are a helpful assistant"
    )
    
    # Try specific model (searches across all providers)
    response = await generator.generate(
        prompt="Hello",
        model="DeepSeek V3"
    )
    
    return response
```

### Using ChatMultiProviderMain

```python
from classes.chat_multi.main import ChatMultiProviderMain

async def chat():
    chat = ChatMultiProviderMain()
    
    messages = [
        {"role": "user", "content": "What is Python?"}
    ]
    
    # Try any available model
    response = await chat.chat(messages)
    
    # Try specific model
    response = await chat.chat(messages, model="Claude 3.5")
    
    return response
```

## How Fallback Works

1. **Get list of enabled providers** from configuration (in order)
2. **For each provider:**
   - If a specific model was requested, check if provider has it
   - Try to execute operation with the provider
   - If successful, return result immediately
3. **If all providers fail:**
   - Return HTTP 503 with detailed error messages from all failed attempts
4. **Providers are tried in configuration order**, so place preferred providers first

## Model Availability Verification

Use the `MultiProviderFallback.test_model_availability()` method to check if a model is accessible:

```python
from helpers.providers_config import ProvidersConfigManager
from helpers.multi_provider_fallback import MultiProviderFallback

async def check_models():
    config = ProvidersConfigManager()
    fallback = MultiProviderFallback(config)
    
    for provider in config.get_enabled_providers():
        for model in provider.models:
            is_available = await fallback.test_model_availability(provider, model)
            print(f"{provider.name}/{model}: {'✓' if is_available else '✗'}")
```

## Configuration Priority

1. `PROVIDERS` JSON environment variable (highest priority)
2. `OLLAMA_HOST`, `OLLAMA_API_KEY`, `OLLAMA_MODELS` environment variables
3. `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `OPENAI_MODELS` environment variables
4. Empty provider list (lowest priority)

## Error Handling

All operations raise `HTTPException` with status code 503 if all providers fail:

```python
{
    "detail": "All providers failed. Errors: provider1: Connection timeout; provider2: Invalid API key"
}
```

## Performance Considerations

- **First request** to a provider may be slower due to initialization
- **Sequential provider tries** - providers are tried in order, not in parallel
- **Model testing** (if enabled) adds overhead but ensures reliability
- Cache model availability results for better performance

## Troubleshooting

### No providers configured
Ensure `PROVIDERS` environment variable is set or individual provider variables exist.

### Provider connection errors
- Check API keys and base URLs are correct
- Verify network connectivity to provider endpoints
- Check provider status/uptime

### Model not found errors
- Verify model name matches exactly what provider uses
- Some providers use different naming conventions (check documentation)
- Run model availability test to diagnose

### Slow responses
- Try moving preferred provider to front of list
- Disable slow providers temporarily
- Check network latency to provider endpoints
