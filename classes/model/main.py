import inspect
from helpers.config import Config


class ModelsMain:
    def __init__(self):
        self.config = Config()
        self.ollama = self.config.ollama
        self.ollama_client = self.config.ollama_client

    async def list_models(self):
        """Return available models from the Ollama client or fallback to HTTP if necessary.

        Tries several common method names on the configured AsyncClient and calls the
        first one that exists. If none are found, performs an HTTP GET to
        '<host>/api/models' using aiohttp as a last resort.
        """
        client = self.ollama_client

        # try common method names
        candidates = ["list_models", "models", "get_models", "listModels", "available_models"]
        for name in candidates:
            fn = getattr(client, name, None)
            if fn:
                try:
                    result = fn()
                    if inspect.isawaitable(result):
                        return await result
                    return result
                except TypeError:
                    # try calling without parentheses if it's a property
                    try:
                        prop = getattr(client, name)
                        return prop
                    except Exception:
                        raise

        # fallback to HTTP GET
        try:
            import aiohttp
        except Exception as e:
            raise RuntimeError("aiohttp is required for HTTP fallback; please install aiohttp") from e

        # try to read host and headers from client
        host = getattr(client, "host", None) or getattr(self.config, "ollama", None) or "https://ollama.com"
        # client may store headers in attribute 'headers'
        headers = getattr(client, "headers", None) or {}
        url = f"{str(host).rstrip('/')}/api/models"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                resp.raise_for_status()
                return await resp.json()
