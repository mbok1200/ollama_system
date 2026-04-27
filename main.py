from helpers.config import Config
from classes.search.main import SearchMain
from classes.generate.main import GenerateMain
from classes.chat.main import ChatMain

import asyncio
class Main:
    def __init__(self):
        self.config = Config()
        self.ollama = self.config.ollama
    async def search(self, query):
        search_main = SearchMain()
        return await search_main.search(query)
    async def generate(self, model: str|list[str], prompt: str):
        gen = GenerateMain()
        return await gen.generate(model, prompt)
    async def chat(self, model: str, messages: list[dict]):
        chat_main = ChatMain()
        return await chat_main.chat(model, messages)
    async def tools(self, tool_calls: list[dict]):
        pass
if __name__ == "__main__":
    main = Main()
    asyncio.run(main.search("What is the capital of France?"))
    asyncio.run(main.generate("gpt-4", "What is the capital of France?"))
    asyncio.run(main.chat("gpt-4", [{"role": "user", "content": "What is the capital of France?"}]))