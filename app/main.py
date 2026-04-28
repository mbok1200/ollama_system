import os
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from slowapi import Limiter
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from classes.search.main import SearchMain
from classes.generate.main import GenerateMain
from classes.chat.main import ChatMain
from classes.tools.main import ToolsMain

MAX_BODY_SIZE = int(os.getenv("MAX_BODY_SIZE", 4 * 1024 * 1024))

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(docs_url=None, redoc_url=None, openapi_url="/openapi.json")
app.add_middleware(SlowAPIMiddleware)
app.state.limiter = limiter

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
async def search_endpoint(payload: dict):
    q = payload.get("query")
    if not q:
        raise HTTPException(status_code=400, detail="Missing 'query' field")
    sm = SearchMain()
    return await sm.search(q)


@app.post("/generate")
@limiter.limit("10/minute")
async def generate_endpoint(payload: dict):
    model = payload.get("model")
    prompt = payload.get("prompt")
    if not model or not prompt:
        raise HTTPException(status_code=400, detail="Missing 'model' or 'prompt'")
    gm = GenerateMain()
    return await gm.generate(model, prompt)


@app.post("/chat")
@limiter.limit("30/minute")
async def chat_endpoint(payload: dict):
    model = payload.get("model")
    messages = payload.get("messages")
    if not model or not messages:
        raise HTTPException(status_code=400, detail="Missing 'model' or 'messages'")
    cm = ChatMain()
    return await cm.chat(model, messages)


@app.post("/tools")
@limiter.limit("10/minute")
async def tools_endpoint(payload: dict):
    model = payload.get("model")
    messages = payload.get("messages")
    tool_calls = payload.get("tool_calls")
    if not model or not messages or not tool_calls:
        raise HTTPException(status_code=400, detail="Missing 'model', 'messages' or 'tool_calls'")
    tm = ToolsMain()
    return await tm.tools(model, messages, tool_calls)
