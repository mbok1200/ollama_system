import os
import json
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class ProviderConfig:
    """Configuration for a single provider"""
    name: str
    type: str  # 'ollama', 'openai', 'anthropic', etc.
    base_url: str
    api_key: str
    models: list[str]
    enabled: bool = True

    def to_dict(self):
        return {
            'name': self.name,
            'type': self.type,
            'base_url': self.base_url,
            'api_key': self.api_key,
            'models': self.models,
            'enabled': self.enabled
        }


class ProvidersConfigManager:
    """Manage multiple LLM providers configuration"""

    def __init__(self):
        self.providers: list[ProviderConfig] = []
        self._load_from_env()

    def _load_from_env(self):
        """Load providers from environment variables"""
        # Example ENV format:
        # PROVIDERS='[{"name":"ollama","type":"ollama","base_url":"https://ollama.com","api_key":"key1","models":["model1","model2"]},...]'
        providers_json = os.getenv("PROVIDERS", "[]")
        try:
            providers_data = json.loads(providers_json)
            for p in providers_data:
                provider = ProviderConfig(
                    name=p.get('name', 'unknown'),
                    type=p.get('type', 'unknown'),
                    base_url=p.get('base_url', ''),
                    api_key=p.get('api_key', ''),
                    models=p.get('models', []),
                    enabled=p.get('enabled', True)
                )
                self.providers.append(provider)
                logger.info("Loaded provider: %s (%s) with %d models",
                           provider.name, provider.type, len(provider.models))
        except json.JSONDecodeError:
            logger.warning("Failed to parse PROVIDERS env variable, starting with empty providers list")

        # Also support individual provider env vars (OLLAMA_*, OPENAI_*, etc.)
        self._load_ollama_from_env()
        self._load_openai_from_env()

    def _load_ollama_from_env(self):
        """Load Ollama provider from env if not already present"""
        if self._has_provider('ollama'):
            return

        host = os.getenv("OLLAMA_HOST")
        api_key = os.getenv("OLLAMA_API_KEY")

        if host and api_key:
            models = os.getenv("OLLAMA_MODELS", "").split(",") if os.getenv("OLLAMA_MODELS") else []
            models = [m.strip() for m in models if m.strip()]

            # If no models specified in env, try to fetch them from Ollama API
            if not models:
                try:
                    import requests
                    url = f"{host.rstrip('/')}/api/tags"
                    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
                    resp = requests.get(url, headers=headers, timeout=5)
                    if resp.status_code == 200:
                        data = resp.json()
                        if isinstance(data, dict) and 'models' in data:
                            models = [m.get('model') or m.get('name')
                                     for m in data['models']
                                     if isinstance(m, dict)]
                            models = [m for m in models if m]
                            logger.info("Auto-discovered %d models from Ollama", len(models))
                except Exception as e:
                    logger.warning("Failed to auto-discover Ollama models: %s", e)

            provider = ProviderConfig(
                name="ollama",
                type="ollama",
                base_url=host,
                api_key=api_key,
                models=models,
                enabled=True
            )
            self.providers.append(provider)
            logger.info("Loaded Ollama provider from env with %d models", len(models))

    def _load_openai_from_env(self):
        """Load OpenAI-compatible provider from env if not already present"""
        if self._has_provider('openai'):
            return

        base_url = os.getenv("OPENAI_BASE_URL")
        api_key = os.getenv("OPENAI_API_KEY")

        if base_url and api_key:
            models = os.getenv("OPENAI_MODELS", "").split(",") if os.getenv("OPENAI_MODELS") else []
            models = [m.strip() for m in models if m.strip()]

            provider = ProviderConfig(
                name="openai",
                type="openai",
                base_url=base_url,
                api_key=api_key,
                models=models,
                enabled=True
            )
            self.providers.append(provider)
            logger.info("Loaded OpenAI provider from env with %d models", len(models))

    def _has_provider(self, provider_type: str) -> bool:
        """Check if provider of given type already exists"""
        return any(p.type == provider_type for p in self.providers)

    def get_enabled_providers(self) -> list[ProviderConfig]:
        """Get list of enabled providers"""
        return [p for p in self.providers if p.enabled]

    def get_provider(self, name: str) -> Optional[ProviderConfig]:
        """Get provider by name"""
        return next((p for p in self.providers if p.name == name), None)

    def get_providers_by_type(self, provider_type: str) -> list[ProviderConfig]:
        """Get all providers of a specific type"""
        return [p for p in self.providers if p.type == provider_type and p.enabled]

    def add_provider(self, config: ProviderConfig):
        """Add a new provider"""
        if self._has_provider(config.type):
            logger.warning("Provider type %s already exists", config.type)
        self.providers.append(config)

    def disable_provider(self, name: str):
        """Disable a provider"""
        provider = self.get_provider(name)
        if provider:
            provider.enabled = False
            logger.info("Disabled provider: %s", name)

    def enable_provider(self, name: str):
        """Enable a provider"""
        provider = self.get_provider(name)
        if provider:
            provider.enabled = True
            logger.info("Enabled provider: %s", name)
