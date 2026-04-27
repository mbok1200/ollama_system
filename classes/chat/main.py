from helpers.config import Config


class ChatMain:
    def __init__(self):
        self.config = Config()
        self.ollama = self.config.ollama
        self.ollama_client = self.config.ollama_client
    async def chat(self, model: str, messages: list[dict]):
        response = ""
        iterator = await self.ollama_client.chat(model, messages, stream=True)
        async for part in iterator:
            content = part.get('message', {}).get('content', '')
            response += content
        return response