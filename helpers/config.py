import ollama
import os
import json
import time
from pathlib import Path
from dotenv import load_dotenv, find_dotenv
import requests
import logging

logger = logging.getLogger(__name__)

# Prefer a .env file located at the project root (one level above helpers/)
try:
    _proj_root = Path(__file__).resolve().parents[1]
    _env_path = _proj_root / ".env"
    if _env_path.exists():
        load_dotenv(_env_path)
        logger.info("Loaded environment from %s", _env_path)
    else:
        # fallback to any .env found by dotenv
        _found = find_dotenv()
        if _found:
            load_dotenv(_found)
            logger.info("Loaded environment from %s", _found)
        else:
            logger.info("No .env file found in project; relying on environment variables")
except Exception:
    # don't fail import if env loading has problems
    logger.exception("Error while attempting to load .env file")


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

    def _annotate_model_access(self, models_list, src_url, headers):
        """Annotate each model dict in-place with access check results.

        Adds keys: `requires_subscription` (True/False) or `access_check_error` on failure.
        """
        url_generate = f"{str(os.getenv('OLLAMA_HOST') or getattr(self.ollama_client, 'host', '')).rstrip('/')}/api/generate"
        for entry in models_list:
            try:
                model_name = None
                if isinstance(entry, dict):
                    model_name = entry.get('model') or entry.get('name')
                if not model_name:
                    entry['requires_subscription'] = None
                    entry['access_check_error'] = 'no model name'
                    continue
                # lightweight probe: short prompt and small timeout
                probe = {"model": model_name, "prompt": "hi", "max_tokens": 1}
                try:
                    r = requests.post(url_generate, headers=headers, json=probe, timeout=5)
                    if r.status_code == 403:
                        entry['requires_subscription'] = True
                    else:
                        entry['requires_subscription'] = False
                except requests.exceptions.RequestException as e:
                    entry['requires_subscription'] = None
                    entry['access_check_error'] = str(e)
            except Exception as e:
                entry['requires_subscription'] = None
                entry['access_check_error'] = str(e)

    def get_models(self, refresh: bool = False, verify_access: bool | None = None, free_only: bool = False):
        """Return available models. Use cache unless refresh=True or cache expired.

        This is a synchronous helper that prefers a cached JSON file and falls back
        to doing an HTTP request to the Ollama host. The result is stored in
        `self.available_models` and cached on disk.

        Args:
            refresh: Force refresh from API instead of using cache
            verify_access: Check if models require subscription (may be slow)
            free_only: Return only models with requires_subscription == False
        """
        if not refresh:
            cached = self._read_cache()
            if cached is not None:
                self.available_models = cached
                return self._filter_free_models(cached) if free_only else cached

        # perform synchronous HTTP request to Ollama API
        # Prefer explicit OLLAMA_HOST env var, then client.host, then default.
        host = os.getenv("OLLAMA_HOST") or getattr(self.ollama_client, "host", None) or "https://ollama.com"
        api_key = os.getenv("OLLAMA_API_KEY")
        client_headers = getattr(self.ollama_client, "headers", None)
        if client_headers:
            headers = client_headers
        else:
            headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        url_models = f"{str(host).rstrip('/')}/api/models"
        url_tags = f"{str(host).rstrip('/')}/api/tags"

        # Always verify access if free_only is requested
        if free_only:
            verify_access = True
        elif verify_access is None:
            verify_access = str(os.getenv("MODEL_VERIFY_ACCESS", "false")).lower() in ("1", "true", "yes")

        # Try the canonical /api/models endpoint first, then fallback to /api/tags
        try:
            logger.info("Attempting to fetch models from %s", url_models)
            resp = requests.get(url_models, headers=headers, timeout=10)
            resp.raise_for_status()
            models = resp.json()
            # verify access for each model before caching
            if verify_access and isinstance(models, dict) and isinstance(models.get('models'), list):
                self._annotate_model_access(models['models'], url_models, headers)
            # Filter to free models if requested
            if free_only:
                models = self._filter_free_models(models)
            self.available_models = models
            self._write_cache(models)
            return models
        except requests.exceptions.HTTPError as he:
            # If /api/models returns 404, try /api/tags
            logger.warning("/api/models not available (%s), trying /api/tags", he)
        except Exception:
            logger.exception("Failed to fetch models from %s", url_models)

        # Fallback to /api/tags
        try:
            logger.info("Attempting to fetch tags from %s", url_tags)
            resp = requests.get(url_tags, headers=headers, timeout=10)
            resp.raise_for_status()
            tags = resp.json()
            # verify access for each tag-derived model before caching
            if verify_access and isinstance(tags, dict) and isinstance(tags.get('models'), list):
                self._annotate_model_access(tags['models'], url_tags, headers)
            # Filter to free models if requested - IMPORTANT: save only free models to cache
            if free_only:
                tags = self._filter_free_models(tags)
            self.available_models = tags
            self._write_cache(tags)
            return tags
        except Exception:
            logger.exception("Failed to fetch models from %s", url_tags)
            # try to return whatever is in the cache file (even if expired)
            try:
                if self._models_cache_file.exists():
                    data = json.loads(self._models_cache_file.read_text())
                    models = data.get("models")
                    self.available_models = models
                    return self._filter_free_models(models) if free_only else models
            except Exception:
                logger.exception("Failed to read models cache file %s", self._models_cache_file)

            # final fallback: return in-memory value or empty list
            result = self.available_models if self.available_models is not None else []
            return self._filter_free_models(result) if free_only else result

    def _filter_free_models(self, models_data):
        """Filter models list to only include models with requires_subscription == False"""
        if not isinstance(models_data, dict):
            return models_data

        models_list = models_data.get('models')
        if not isinstance(models_list, list):
            return models_data

        # Filter to only free models
        free_models = [m for m in models_list
                      if isinstance(m, dict) and m.get('requires_subscription') == False]

        # Return filtered copy
        return {**models_data, 'models': free_models}