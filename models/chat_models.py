from pydantic import BaseModel
from typing import Optional

class ChatRequest(BaseModel):
    message: str
    # language: str | None = None

class ChatContextRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

class SearchRequest(BaseModel):
    query: str
    page: int = 1
    page_size: int = 10