from pydantic import BaseModel

class ChatRequest(BaseModel):
    message: str
    # language: str | None = None