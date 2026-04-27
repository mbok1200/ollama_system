from helpers.config import Config

from models.SearchResponse import SearchResponse


class SearchMain:
    def __init__(self):
        self.config = Config()
        self.ollama = self.config.ollama
        self.ollama_client = self.config.ollama_client
        print("Search Main Initialized!")
    async def search(self, query):
        response = await self.ollama_client.web_search(query)
        return SearchResponse.model_validate(response)
        