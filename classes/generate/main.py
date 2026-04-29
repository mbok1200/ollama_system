from helpers.config import Config
from fastapi import HTTPException
from ollama._types import ResponseError

class GenerateMain:
    def __init__(self):
        self.config = Config()
        self.ollama_client = self.config.ollama_client

    async def generate(self, model: str|list[str], prompt: str):
        result = []
        if isinstance(model, str):
            try:
                generate = await self.ollama_client.generate(f"{model}", prompt)
                return generate
            except ResponseError as e:
                # model may require subscription or be forbidden
                raise HTTPException(status_code=getattr(e, 'status_code', 403), detail=str(e))
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        elif isinstance(model, list):
            for m in model:
                try:
                    generate = await self.ollama_client.generate(m, prompt)
                    result.append(generate)
                except ResponseError as e:
                    # propagate as HTTP error with context
                    raise HTTPException(status_code=getattr(e, 'status_code', 403), detail=str(e))
                except Exception as e:
                    raise HTTPException(status_code=500, detail=str(e))
            return result