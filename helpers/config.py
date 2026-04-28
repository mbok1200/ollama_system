import ollama
import os
import json
import time
from pathlib import Path
from dotenv import load_dotenv
import requests

load_dotenv("../.env")


class Config:
    def __init__(self):
        self.ollama = ollama
        self.ollama_client = ollama.AsyncClient(
            host=os.getenv("OLLAMA_HOST", "https://ollama.com"),
            headers={"Authorization": f"Bearer {os.getenv('OLLAMA_API_KEY')}"}
        )

        # cache and models
        self.project_root = Path(__file__).resolve().parents[1]
        self._models_cache_file = self.project_root / ".models_cache.json"
        self._models_cache_ttl = int(os.getenv("MODEL_CACHE_TTL", 3600))
        self.available_models = None

    def _read_cache(self):
        if not self._models_cache_file.exists():
            return None
        try:
            data = json.loads(self._models_cache_file.read_text())
            ts = data.get("_cached_at", 0)
            if time.time() - ts > self._models_cache_ttl:
                return None
            return data.get("models")
        except Exception:
            return None

    def _write_cache(self, models):
        payload = {"_cached_at": int(time.time()), "models": models}
        try:
            self._models_cache_file.write_text(json.dumps(payload))
        except Exception:
            pass

    def get_models(self, refresh: bool = False):
        """Return available models. Use cache unless refresh=True or cache expired.

        This is a synchronous helper that prefers a cached JSON file and falls back
        to doing an HTTP request to the Ollama host. The result is stored in
        `self.available_models` and cached on disk.
        """
        if not refresh:
            cached = self._read_cache()
            if cached is not None:
                self.available_models = cached
                return cached

        # perform synchronous HTTP request to Ollama API
        host = getattr(self.ollama_client, "host", os.getenv("OLLAMA_HOST", "https://ollama.com"))
        headers = getattr(self.ollama_client, "headers", {}) or {"Authorization": f"Bearer {os.getenv('OLLAMA_API_KEY')}"}
        url = f"{str(host).rstrip('/')}/api/models"
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            models = resp.json()
            self.available_models = models
            self._write_cache(models)
            return models
        except Exception:
            # fallback: return whatever is currently in memory
            return self.available_models