import logging
from fastapi import HTTPException
from ollama._types import ResponseError
from helpers.providers_config import ProvidersConfigManager
from helpers.multi_provider_fallback import MultiProviderFallback

logger = logging.getLogger(__name__)


class GenerateMultiProviderMain:
    """Generate text using multiple providers with fallback"""

    def __init__(self):
        self.providers_config = ProvidersConfigManager()
        self.fallback = MultiProviderFallback(self.providers_config)

    async def generate(self, prompt: str, system_prompt: str = "", model: str | None = None) -> str:
        """
        Generate text using available providers in fallback order.

        If a specific model is provided, tries to find it across providers.
        Otherwise, uses first available model from first available provider.

        Args:
            prompt: Text prompt to generate from
            system_prompt: Optional system context
            model: Optional specific model to use (tries all providers if not found)

        Returns:
            Generated text
        """
        try:
            if model:
                # Try specific model across all providers
                return await self._generate_with_model(model, prompt, system_prompt)
            else:
                # Use multi-provider fallback
                return await self.fallback.try_providers_for_generate(
                    prompt=prompt,
                    system_prompt=system_prompt
                )

        except ResponseError as e:
            raise HTTPException(status_code=getattr(e, 'status_code', 403), detail=str(e))
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Generate error: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

    async def _generate_with_model(self, model: str, prompt: str, system_prompt: str) -> str:
        """Try to generate with specific model across providers"""
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
                    messages = []
                    if system_prompt:
                        messages.append({"role": "system", "content": system_prompt})
                    messages.append({"role": "user", "content": prompt})

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
                    result = await client.generate(
                        model=model,
                        system=system_prompt if system_prompt else None,
                        prompt=prompt
                    )
                    return result.get('response', '')

            except Exception as e:
                error_msg = f"{provider.name}: {str(e)}"
                logger.warning("Failed with provider %s: %s", provider.name, e)
                errors.append(error_msg)

        # If model not found in any provider, try any provider
        logger.info("Model %s not found in any provider, trying any available", model)
        return await self.fallback.try_providers_for_generate(
            prompt=prompt,
            system_prompt=system_prompt
        )
