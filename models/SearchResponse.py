from pydantic import BaseModel
from typing import List, Sequence
from ollama._types import WebSearchResult

class SearchResponse(BaseModel):
    results: Sequence[WebSearchResult]