from helpers.config import Config

class GenerateMain:
    def __init__(self):
        self.config = Config()
        self.ollama_client = self.config.ollama_client

    async def generate(self, model: str|list[str], prompt: str):
        result = []
        if model is str:
           generate = await self.ollama_client.generate(model, prompt)
           return generate
        elif model is list[str]:
            for m in model:
                generate = await self.ollama_client.generate(m, prompt)
                result.append(generate)
            return result