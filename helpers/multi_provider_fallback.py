import logging
from typing import Optional, Callable, Any
from fastapi import HTTPException
from helpers.providers_config import ProvidersConfigManager, ProviderConfig

logger = logging.getLogger(__name__)


class MultiProviderFallback:
    """Handle fallback across multiple LLM providers"""

    def __init__(self, providers_config: ProvidersConfigManager):
        self.providers_config = providers_config

    async def try_all_providers(
        self,
        operation: Callable,
        *args,
        operation_name: str = "operation",
        test_first: bool = True,
        **kwargs
    ) -> Any:
        """
        Try operation across all enabled providers in order.

        Args:
            operation: Async callable that performs the operation
            operation_name: Human-readable name for logging
            test_first: If True, test model availability before full operation
            *args: Positional args for operation
            **kwargs: Keyword args for operation

        Returns:
            Result from first successful provider
        """
        providers = self.providers_config.get_enabled_providers()
        errors = []

        if not providers:
            raise HTTPException(
                status_code=503,
                detail="No providers configured"
            )

        # Filter out providers with no models
        valid_providers = []
        for provider in providers:
            if not provider.models:
                logger.warning("Provider %s has no models configured, skipping", provider.name)
                continue
            valid_providers.append(provider)

        if not valid_providers:
            raise HTTPException(
                status_code=503,
                detail="No providers have models configured"
            )

        for provider in valid_providers:
            logger.info("Trying %s with provider: %s", operation_name, provider.name)

            try:
                result = await operation(provider, *args, **kwargs)
                logger.info("✓ Success with provider: %s", provider.name)
                return result
            except Exception as e:
                error_msg = f"{provider.name}: {str(e)}"
                logger.warning("✗ %s failed with %s: %s", operation_name, provider.name, e)
                errors.append(error_msg)

        logger.error("All providers failed for %s: %s", operation_name, errors)
        raise HTTPException(
            status_code=503,
            detail=f"All providers failed. Errors: {'; '.join(errors)}"
        )

    async def test_model_availability(
        self,
        provider: ProviderConfig,
        model: str,
        test_prompt: str = "hi"
    ) -> bool:
        """
        Test if a model is available in a provider.

        Args:
            provider: Provider configuration
            model: Model name to test
            test_prompt: Short prompt to test with

        Returns:
            True if model is available, False otherwise
        """
        try:
            if provider.type == "openai":
                from openai import OpenAI
                client = OpenAI(
                    base_url=provider.base_url,
                    api_key=provider.api_key
                )
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": test_prompt}],
                    max_tokens=1,
                    timeout=5
                )
                logger.debug("Model %s available in provider %s", model, provider.name)
                return True
            elif provider.type == "ollama":
                import ollama
                client = ollama.AsyncClient(
                    host=provider.base_url,
                    headers={"Authorization": f"Bearer {provider.api_key}"} if provider.api_key else {}
                )
                await client.generate(model, test_prompt)
                logger.debug("Model %s available in provider %s", model, provider.name)
                return True
        except Exception as e:
            logger.debug("Model %s not available in provider %s: %s", model, provider.name, e)
            return False

    async def get_available_models(
        self,
        provider: ProviderConfig,
        verify: bool = True
    ) -> list[str]:
        """
        Get available models from a provider.

        Args:
            provider: Provider configuration
            verify: If True, test each model for actual availability

        Returns:
            List of available model names
        """
        models = provider.models.copy()

        if not verify:
            return models

        available = []
        for model in models:
            if await self.test_model_availability(provider, model):
                available.append(model)

        return available

    async def try_providers_for_generate(
        self,
        prompt: str,
        system_prompt: str = "",
        models_to_test: Optional[list[str]] = None
    ) -> str:
        """
        Try to generate text across providers.

        Args:
            prompt: Text to generate
            system_prompt: System context
            models_to_test: Specific models to test (if None, use all from providers)

        Returns:
            Generated text
        """
        async def generate_op(provider: ProviderConfig, prompt_text: str, sys_prompt: str):
            if not provider.models:
                raise ValueError(f"Provider {provider.name} has no models configured")

            if provider.type == "openai":
                from openai import OpenAI
                client = OpenAI(
                    base_url=provider.base_url,
                    api_key=provider.api_key
                )
                messages = []
                if sys_prompt:
                    messages.append({"role": "system", "content": sys_prompt})
                messages.append({"role": "user", "content": prompt_text})

                response = client.chat.completions.create(
                    model=provider.models[0],  # Use first available model
                    messages=messages
                )
                return response.choices[0].message.content

            elif provider.type == "ollama":
                import ollama
                client = ollama.AsyncClient(
                    host=provider.base_url,
                    headers={"Authorization": f"Bearer {provider.api_key}"} if provider.api_key else {}
                )
                result = await client.generate(
                    model=provider.models[0],
                    system=sys_prompt if sys_prompt else None,
                    prompt=prompt_text
                )
                return result.get('response', '')

        return await self.try_all_providers(
            generate_op,
            prompt,
            system_prompt,
            operation_name="generate"
        )

    async def try_providers_for_chat(
        self,
        messages: list[dict]
    ) -> str:
        """
        Try to chat across providers.

        Args:
            messages: Chat message history

        Returns:
            Chat response
        """
        async def chat_op(provider: ProviderConfig, msgs: list[dict]):
            if not provider.models:
                raise ValueError(f"Provider {provider.name} has no models configured")

            if provider.type == "openai":
                from openai import OpenAI
                client = OpenAI(
                    base_url=provider.base_url,
                    api_key=provider.api_key
                )
                response = client.chat.completions.create(
                    model=provider.models[0],
                    messages=msgs
                )
                return response.choices[0].message.content

            elif provider.type == "ollama":
                import ollama
                client = ollama.AsyncClient(
                    host=provider.base_url,
                    headers={"Authorization": f"Bearer {provider.api_key}"} if provider.api_key else {}
                )
                response = ""
                iterator = await client.chat(provider.models[0], msgs, stream=True)
                async for part in iterator:
                    content = part.get('message', {}).get('content', '')
                    response += content
                return response

        return await self.try_all_providers(
            chat_op,
            messages,
            operation_name="chat"
        )
