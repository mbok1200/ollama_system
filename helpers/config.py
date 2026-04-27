import ollama
import os
from dotenv import load_dotenv
load_dotenv("../.env")
class Config:
    def __init__(self):
        self.ollama = ollama
        self.ollama_client = ollama.AsyncClient(
            host='https://ollama.com',
            headers={'Authorization': f'Bearer {os.getenv("OLLAMA_API_KEY")}'}
        )