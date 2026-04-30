import os
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from slowapi import Limiter
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from datetime import datetime
import asyncio

from classes.search.main import SearchMain
from classes.generate.main import GenerateMain
from classes.chat.main import ChatMain
from classes.tools.main import ToolsMain
from classes.generate_multi.main import GenerateMultiProviderMain
from classes.chat_multi.main import ChatMultiProviderMain
from helpers.config import Config
from helpers.providers_config import ProvidersConfigManager

MAX_BODY_SIZE = int(os.getenv("MAX_BODY_SIZE", 4 * 1024 * 1024))

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(docs_url=None, redoc_url=None, openapi_url="/openapi.json")
app.add_middleware(SlowAPIMiddleware)
app.state.limiter = limiter
cfg = Config()


def _pick_model(models):
    """Return a sensible model identifier from various API responses."""
    if not models:
        return None
    def _parse_modified(item):
        if isinstance(item, dict):
            for k in ('modified_at', 'modified', 'updated_at', 'updated'):
                v = item.get(k)
                if v:
                    try:
                        return datetime.fromisoformat(v)
                    except Exception:
                        try:
                            return datetime.strptime(v, '%Y-%m-%dT%H:%M:%SZ')
                        except Exception:
                            return datetime.fromtimestamp(0)
        return datetime.fromtimestamp(0)

    # dict responses
    if isinstance(models, dict):
        # common pattern: {'models': [...]} or mapping of name->info
        if 'models' in models and isinstance(models['models'], list) and models['models']:
            lst = models['models']
            # prefer entries with modified_at; pick the newest
            # prefer models that are accessible (requires_subscription == False)
            try:
                accessible = [e for e in lst if isinstance(e, dict) and e.get('requires_subscription') is False]
                source = accessible if accessible else lst
                lst_sorted = sorted(source, key=_parse_modified, reverse=True)
                first = lst_sorted[0]
            except Exception:
                first = lst[0]
            if isinstance(first, dict):
                return first.get('model') or first.get('name') or first.get('id')
            return str(first)
        # fallback: mapping keys -> choose most recently modified value if possible
        candidates = []
        for k, v in models.items():
            candidates.append((k, v))
        if candidates:
            # try to pick the value with newest modified_at
            best = None
            best_date = datetime.fromtimestamp(0)
            for k, v in candidates:
                date = _parse_modified(v)
                if date > best_date:
                    best_date = date
                    best = (k, v)
            if best:
                # if value is dict, prefer its model/name
                v = best[1]
                if isinstance(v, dict):
                    # prefer accessible entries when available
                    if v.get('requires_subscription') is False:
                        return v.get('model') or v.get('name') or best[0]
                    # otherwise return the best candidate found
                    return v.get('model') or v.get('name') or best[0]
                return best[0]
        return None

    # list responses
    if isinstance(models, list):
        if not models:
            return None
        try:
            accessible = [e for e in models if isinstance(e, dict) and e.get('requires_subscription') is False]
            source = accessible if accessible else models
            lst_sorted = sorted(source, key=_parse_modified, reverse=True)
            first = lst_sorted[0]
        except Exception:
            first = models[0]
        if isinstance(first, dict):
            return first.get('model') or first.get('name') or first.get('id') or None
        return str(first)

    # other types
    return str(models)

# Trusted hosts from env or wildcard (change for prod)
allowed_hosts = os.getenv("ALLOWED_HOSTS", "*")
if allowed_hosts == "*":
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])
else:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts.split(","))

# CORS - restrict in production via ALLOWED_ORIGINS
allowed_origins = os.getenv("ALLOWED_ORIGINS", "").split(",") if os.getenv("ALLOWED_ORIGINS") else []
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if allowed_origins else ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    if request.headers.get("content-length"):
        try:
            if int(request.headers["content-length"]) > MAX_BODY_SIZE:
                return Response(status_code=413, content="Request body too large")
        except ValueError:
            pass
    resp = await call_next(request)
    resp.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    return resp


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/search")
@limiter.limit("10/minute")
async def search_endpoint(request: Request, payload: dict):
    q = payload.get("query")
    if not q:
        raise HTTPException(status_code=400, detail="Missing 'query' field")
    sm = SearchMain()
    return await sm.search(q)


@app.post("/generate")
@limiter.limit("10/minute")
async def generate_endpoint(request: Request, payload: dict):
    system_prompt = payload.get("system_prompt", "")
    prompt = payload.get("prompt", "")
    gm = GenerateMain()
    return await gm.generate(system_prompt=system_prompt, prompt=prompt)


@app.post("/chat")
@limiter.limit("30/minute")
async def chat_endpoint(request: Request, payload: dict):
    messages = payload.get("messages")
    cm = ChatMain()
    return await cm.chat(messages)


@app.post("/tools")
@limiter.limit("10/minute")
async def tools_endpoint(request: Request, payload: dict):
    messages = payload.get("messages")
    tool_calls = payload.get("tool_calls")
    tm = ToolsMain()
    return await tm.tools(messages, tool_calls)

@app.get("/models")
@limiter.limit("30/minute")
async def models_endpoint(request: Request, refresh: bool = False):
    cfg = Config()
    models = await asyncio.to_thread(cfg.get_models, refresh, verify_access=True)
    if models is None:
        raise HTTPException(status_code=500, detail=f"Unable to retrieve {models}")
    return models


# ===== Multi-Provider OpenAI-Compatible Routes =====

@app.post("/openai/chat/completions")
@limiter.limit("30/minute")
async def openai_chat_completions(request: Request, payload: dict):
    """OpenAI-compatible chat completions endpoint"""
    messages = payload.get("messages", [])
    model = payload.get("model")

    if not messages:
        raise HTTPException(status_code=400, detail="Missing 'messages' field")

    cm = ChatMultiProviderMain()
    response = await cm.chat(messages=messages, model=model)

    return {
        "object": "chat.completion",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": response
                },
                "finish_reason": "stop",
                "index": 0
            }
        ],
        "model": model or "unknown",
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }
    }


@app.post("/openai/generate")
@limiter.limit("10/minute")
async def openai_generate(request: Request, payload: dict):
    """Generate text using multi-provider system"""
    prompt = payload.get("prompt", "")
    system_prompt = payload.get("system_prompt", "")
    model = payload.get("model")

    if not prompt:
        raise HTTPException(status_code=400, detail="Missing 'prompt' field")

    gm = GenerateMultiProviderMain()
    response = await gm.generate(
        prompt=prompt,
        system_prompt=system_prompt,
        model=model
    )

    return {
        "object": "text_completion",
        "choices": [
            {
                "text": response,
                "finish_reason": "stop",
                "index": 0
            }
        ],
        "model": model or "unknown",
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }
    }


@app.post("/openai/chat")
@limiter.limit("30/minute")
async def openai_chat(request: Request, payload: dict):
    """Chat endpoint for multi-provider system"""
    messages = payload.get("messages", [])
    model = payload.get("model")

    if not messages:
        raise HTTPException(status_code=400, detail="Missing 'messages' field")

    cm = ChatMultiProviderMain()
    response = await cm.chat(messages=messages, model=model)

    return {
        "response": response,
        "model": model or "unknown"
    }


@app.get("/openai/models")
@limiter.limit("30/minute")
async def openai_models_endpoint(request: Request):
    """List available models from all configured providers"""
    config = ProvidersConfigManager()
    providers = config.get_enabled_providers()

    models = []
    for provider in providers:
        for model_name in provider.models:
            models.append({
                "id": model_name,
                "object": "model",
                "created": 0,
                "owned_by": provider.name,
                "permission": [],
                "root": model_name,
                "parent": None,
                "provider": provider.name,
                "provider_type": provider.type
            })

    return {
        "object": "list",
        "data": models
    }


@app.get("/openai/providers")
@limiter.limit("30/minute")
async def openai_providers_endpoint(request: Request):
    """List all configured providers and their models"""
    config = ProvidersConfigManager()
    providers = config.get_enabled_providers()

    providers_data = []
    for provider in providers:
        providers_data.append({
            "name": provider.name,
            "type": provider.type,
            "enabled": provider.enabled,
            "models": provider.models
        })

    return {
        "providers": providers_data,
        "total": len(providers_data)
    }


@app.post("/openai/test-model")
@limiter.limit("10/minute")
async def openai_test_model(request: Request, payload: dict):
    """Test if a model is available in any provider"""
    model_name = payload.get("model")

    if not model_name:
        raise HTTPException(status_code=400, detail="Missing 'model' field")

    from helpers.multi_provider_fallback import MultiProviderFallback
    config = ProvidersConfigManager()
    fallback = MultiProviderFallback(config)

    results = []
    for provider in config.get_enabled_providers():
        is_available = await fallback.test_model_availability(provider, model_name)
        results.append({
            "provider": provider.name,
            "model": model_name,
            "available": is_available
        })

    any_available = any(r["available"] for r in results)

    return {
        "model": model_name,
        "available": any_available,
        "providers": results
    }
