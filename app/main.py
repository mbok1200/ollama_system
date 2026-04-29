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
from helpers.config import Config

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
    models = await asyncio.to_thread(cfg.get_models, refresh=False)
    model = _pick_model(models)
    prompt = payload.get("prompt")
    if not model or not prompt:
        raise HTTPException(status_code=400, detail="Missing 'model' or 'prompt'")
    gm = GenerateMain()
    return await gm.generate(model, prompt)


@app.post("/chat")
@limiter.limit("30/minute")
async def chat_endpoint(request: Request, payload: dict):
    models = await asyncio.to_thread(cfg.get_models, refresh=False)
    model = _pick_model(models)
    messages = payload.get("messages")
    if not model or not messages:
        raise HTTPException(status_code=400, detail="Missing 'model' or 'messages'")
    cm = ChatMain()
    return await cm.chat(model, messages)


@app.post("/tools")
@limiter.limit("10/minute")
async def tools_endpoint(request: Request, payload: dict):
    models = await asyncio.to_thread(cfg.get_models, refresh=False)
    model = _pick_model(models)
    messages = payload.get("messages")
    tool_calls = payload.get("tool_calls")
    if not model or not messages or not tool_calls:
        raise HTTPException(status_code=400, detail="Missing 'model', 'messages' or 'tool_calls'")
    tm = ToolsMain()
    return await tm.tools(model, messages, tool_calls)

@app.get("/models")
@limiter.limit("30/minute")
async def models_endpoint(request: Request, refresh: bool = False):
    cfg = Config()
    models = await asyncio.to_thread(cfg.get_models, refresh, verify_access=True)
    if models is None:
        raise HTTPException(status_code=500, detail=f"Unable to retrieve {models}")
    return models
