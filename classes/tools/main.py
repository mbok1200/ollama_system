from helpers.config import Config
from helpers.model_fallback import ModelFallbackHelper
from ollama import ChatResponse
from classes.tools import available_functions
from fastapi import HTTPException
from ollama._types import ResponseError
import logging

logger = logging.getLogger(__name__)

class ToolsMain:
    def __init__(self):
        self.config = Config()
        self.ollama = self.config.ollama
        self.ollama_client = self.config.ollama_client
        self.fallback = ModelFallbackHelper(self.ollama_client, self.config)
        self.list_available_functions = available_functions.LIST_AVAILABLE_FUNCTIONS
        self.available_functions = available_functions

    async def tools(self, messages: list | None = None, tool_calls: list[dict] | None = None):
        try:
            if not messages:
                messages = []
            if not tool_calls:
                tool_calls = []

            free_models = self.config.get_models(free_only=True)
            models_to_use = self.fallback.get_free_model_names(free_models)
            if not models_to_use:
                raise HTTPException(status_code=503, detail="No free models available")

            return await self._execute_tools_with_models(models_to_use, messages, tool_calls)

        except ResponseError as e:
            raise HTTPException(status_code=getattr(e, 'status_code', 403), detail=str(e))
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def _execute_tools_with_models(self, models: list[str], messages: list, tool_calls: list[dict]):
        """Execute tools with fallback to next model on failure"""
        errors = []

        for model_name in models:
            try:
                logger.info("Attempting tools with model: %s", model_name)
                return await self._tools_loop(model_name, messages, tool_calls)
            except (ResponseError, Exception) as e:
                error_msg = f"{model_name}: {str(e)}"
                logger.warning("Model %s failed: %s", model_name, e)
                errors.append(error_msg)

        logger.error("All models failed for tools: %s", errors)
        raise HTTPException(
            status_code=503,
            detail=f"All models unavailable. Errors: {'; '.join(errors)}"
        )

    async def _tools_loop(self, model: str, messages: list, tool_calls: list[dict]):
        """Execute tools loop with a specific model"""
        while True:
            response: ChatResponse = await self.ollama_client.chat(
                model=model,
                messages=messages,
                tools=tool_calls,
                think=True
            )
            messages.append(response.message)
            if response.message.tool_calls:
                for tc in response.message.tool_calls:
                    if tc.function.name in self.list_available_functions:
                        logger.info("Calling %s with arguments %s", tc.function.name, tc.function.arguments)
                        result = self.list_available_functions[tc.function.name](**tc.function.arguments)
                        logger.info("Result: %s", result)
                        messages.append({'role': 'tool', 'tool_name': tc.function.name, 'content': str(result)})
            else:
                break

        return messages
