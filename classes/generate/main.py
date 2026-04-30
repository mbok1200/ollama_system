from helpers.config import Config
from helpers.model_fallback import ModelFallbackHelper
from fastapi import HTTPException
from ollama._types import ResponseError
import logging

logger = logging.getLogger(__name__)

class GenerateMain:
    def __init__(self):
        self.config = Config()
        self.ollama_client = self.config.ollama_client
        self.fallback = ModelFallbackHelper(self.ollama_client, self.config)

    async def generate(self, model: str | list[str] | None = None, system_prompt: str = "", prompt: str = ""):
        try:
            if model:
                if isinstance(model, str):
                    return await self.fallback.try_with_free_fallback(
                        model,
                        'generate',
                        prompt=prompt,
                        system_prompt=system_prompt
                    )
                elif isinstance(model, list):
                    return await self.fallback.try_models_for_generate(model, prompt, system_prompt)
            else:
                # Use free models from config
                free_models = self.config.get_models(free_only=True)
                free_model_names = self.fallback.get_free_model_names(free_models)
                if free_model_names:
                    return await self.fallback.try_models_for_generate(free_model_names, prompt, system_prompt)
                raise HTTPException(status_code=503, detail="No free models available")

        except ResponseError as e:
            raise HTTPException(status_code=getattr(e, 'status_code', 403), detail=str(e))
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))