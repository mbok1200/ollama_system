import logging
from fastapi import HTTPException
from ollama._types import ResponseError
from helpers.providers_config import ProvidersConfigManager
from helpers.multi_provider_fallback import MultiProviderFallback

logger = logging.getLogger(__name__)


class ChatMultiProviderMain:
    """Chat using multiple providers with fallback"""

    def __init__(self):
        self.providers_config = ProvidersConfigManager()
        self.fallback = MultiProviderFallback(self.providers_config)

    async def chat(self, messages: list[dict], model: str | None = None) -> str:
        """
        Chat using available providers in fallback order.

        If a specific model is provided, tries to find it across providers.
        Otherwise, uses first available model from first available provider.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Optional specific model to use

        Returns:
            Chat response text
        """
        try:
            if not messages:
                messages = []

            if model:
                return await self._chat_with_model(model, messages)
            else:
                return await self.fallback.try_providers_for_chat(messages)

        except ResponseError as e:
            raise HTTPException(status_code=getattr(e, 'status_code', 403), detail=str(e))
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Chat error: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

    async def _chat_with_model(self, model: str, messages: list[dict]) -> str:
        """Try to chat with specific model across providers"""
        from openai import OpenAI
        import ollama

        providers = self.providers_config.get_enabled_providers()
        errors = []

        for provider in providers:
            if model not in provider.models:
                continue

            try:
                logger.info("Trying model %s with provider %s", model, provider.name)

                if provider.type == "openai":
                    client = OpenAI(
                        base_url=provider.base_url,
                        api_key=provider.api_key
                    )
                    response = client.chat.completions.create(
                        model=model,
                        messages=messages
                    )
                    return response.choices[0].message.content

                elif provider.type == "ollama":
                    client = ollama.AsyncClient(
                        host=provider.base_url,
                        headers={"Authorization": f"Bearer {provider.api_key}"} if provider.api_key else {}
                    )
                    response = ""
                    iterator = await client.chat(model, messages, stream=True)
                    async for part in iterator:
                        content = part.get('message', {}).get('content', '')
                        response += content
                    return response

            except Exception as e:
                error_msg = f"{provider.name}: {str(e)}"
                logger.warning("Failed with provider %s: %s", provider.name, e)
                errors.append(error_msg)

        # If model not found in any provider, try any provider
        logger.info("Model %s not found in any provider, trying any available", model)
        return await self.fallback.try_providers_for_chat(messages)
