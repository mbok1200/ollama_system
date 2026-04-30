import logging
from fastapi import HTTPException
from ollama._types import ResponseError

logger = logging.getLogger(__name__)


class ModelFallbackHelper:
    """Helper for trying models in sequence with fallback support"""

    def __init__(self, ollama_client, config):
        self.ollama_client = ollama_client
        self.config = config

    async def try_models_for_generate(self, models: list[str], prompt: str, system_prompt: str = ""):
        """Try each model in sequence for generate, falling back on failure"""
        errors = []
        for model_name in models:
            try:
                logger.info("Attempting generate with model: %s", model_name)
                result = await self.ollama_client.generate(
                    model_name,
                    system=system_prompt if system_prompt else None,
                    prompt=prompt
                )
                logger.info("Successfully generated with model: %s", model_name)
                return result
            except ResponseError as e:
                error_msg = f"{model_name}: {str(e)}"
                logger.warning("Model %s failed: %s", model_name, e)
                errors.append(error_msg)
            except Exception as e:
                error_msg = f"{model_name}: {str(e)}"
                logger.warning("Model %s errored: %s", model_name, e)
                errors.append(error_msg)

        logger.error("All models failed: %s", errors)
        raise HTTPException(
            status_code=503,
            detail=f"All models unavailable. Errors: {'; '.join(errors)}"
        )

    async def try_models_for_chat(self, models: list[str], messages: list[dict]):
        """Try each model in sequence for chat, falling back on failure"""
        errors = []
        for model_name in models:
            try:
                logger.info("Attempting chat with model: %s", model_name)
                response = ""
                iterator = await self.ollama_client.chat(model_name, messages, stream=True)
                async for part in iterator:
                    content = part.get('message', {}).get('content', '')
                    response += content
                logger.info("Successfully chatted with model: %s", model_name)
                return response
            except ResponseError as e:
                error_msg = f"{model_name}: {str(e)}"
                logger.warning("Model %s failed: %s", model_name, e)
                errors.append(error_msg)
            except Exception as e:
                error_msg = f"{model_name}: {str(e)}"
                logger.warning("Model %s errored: %s", model_name, e)
                errors.append(error_msg)

        logger.error("All models failed: %s", errors)
        raise HTTPException(
            status_code=503,
            detail=f"All models unavailable. Errors: {'; '.join(errors)}"
        )

    async def try_models_for_chat_with_tools(self, models: list[str], messages: list[dict], tools: list[dict]):
        """Try each model in sequence for chat with tools, falling back on failure"""
        errors = []
        for model_name in models:
            try:
                logger.info("Attempting chat with tools using model: %s", model_name)
                result = await self.ollama_client.chat(
                    model=model_name,
                    messages=messages,
                    tools=tools,
                    think=True
                )
                logger.info("Successfully chatted with tools using model: %s", model_name)
                return result
            except ResponseError as e:
                error_msg = f"{model_name}: {str(e)}"
                logger.warning("Model %s failed: %s", model_name, e)
                errors.append(error_msg)
            except Exception as e:
                error_msg = f"{model_name}: {str(e)}"
                logger.warning("Model %s errored: %s", model_name, e)
                errors.append(error_msg)

        logger.error("All models failed: %s", errors)
        raise HTTPException(
            status_code=503,
            detail=f"All models unavailable. Errors: {'; '.join(errors)}"
        )

    def get_free_model_names(self, models_data) -> list[str]:
        """Extract model names from models data, filtering out None values"""
        if not isinstance(models_data, dict):
            return []

        models_list = models_data.get('models')
        if not isinstance(models_list, list):
            return []

        model_names = [m.get('model') or m.get('name')
                      for m in models_list
                      if isinstance(m, dict)]
        return [name for name in model_names if isinstance(name, str)]

    async def try_with_free_fallback(self, primary_model: str, operation: str, **kwargs):
        """
        Try with primary model, fallback to free models on failure

        Args:
            primary_model: Primary model to try
            operation: 'generate', 'chat', or 'chat_with_tools'
            **kwargs: Arguments for the operation (prompt, messages, tools, system_prompt)

        Returns:
            Result from successful model call
        """
        try:
            if operation == 'generate':
                system_prompt = kwargs.get('system_prompt', '')
                return await self.ollama_client.generate(
                    primary_model,
                    system=system_prompt if system_prompt else None,
                    prompt=kwargs['prompt']
                )
            elif operation == 'chat':
                response = ""
                iterator = await self.ollama_client.chat(primary_model, kwargs['messages'], stream=True)
                async for part in iterator:
                    content = part.get('message', {}).get('content', '')
                    response += content
                return response
            elif operation == 'chat_with_tools':
                return await self.ollama_client.chat(
                    model=primary_model,
                    messages=kwargs['messages'],
                    tools=kwargs['tools'],
                    think=True
                )
        except (ResponseError, Exception):
            logger.info("Primary model %s failed, trying free models from config", primary_model)

        # Fallback to free models
        free_models_data = self.config.get_models(free_only=True)
        free_model_names = self.get_free_model_names(free_models_data)
        free_model_names = [n for n in free_model_names if n != primary_model]

        if not free_model_names:
            raise HTTPException(
                status_code=503,
                detail=f"Primary model {primary_model} failed and no free models available"
            )

        if operation == 'generate':
            system_prompt = kwargs.get('system_prompt', '')
            return await self.try_models_for_generate(
                free_model_names,
                kwargs['prompt'],
                system_prompt
            )
        elif operation == 'chat':
            return await self.try_models_for_chat(free_model_names, kwargs['messages'])
        elif operation == 'chat_with_tools':
            return await self.try_models_for_chat_with_tools(
                free_model_names,
                kwargs['messages'],
                kwargs['tools']
            )

        raise ValueError(f"Unknown operation: {operation}")
