from fastapi import APIRouter

from models.chat_models import ChatRequest
from services.language_service import detect_language
from services.web_search import search_web
from services.llm_service import generate_answer

router = APIRouter()

@router.post("/chat")
async def chat(req: ChatRequest):

    language = detect_language(req.message)

    web_results = search_web(req.message)

    answer = generate_answer(
        question=req.message,
        context=web_results,
        language=language
    )

    return {
        "language": language,
        "answer": answer,
        "sources": web_results
    }