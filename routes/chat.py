from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
import json

from models.chat_models import ChatRequest, ChatContextRequest
from services.language_service import detect_language
from services.web_search import search_web
from services.llm_service import generate_answer
from services.context_llm_service import generate_context_aware_answer
from services.streaming_llm_service import (
    generate_streaming_answer,
    generate_streaming_context_aware_answer
)
from services.conversation_manager import conversation_manager

router = APIRouter()

@router.post("/chat")
async def chat(req: ChatRequest):

    language = detect_language(req.message)

    web_results = await search_web(req.message)

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


@router.post("/chat-context")
async def chat_with_context(req: ChatContextRequest):
    """
    Chat endpoint with conversation history management.
    Maintains context across multiple messages in a session.
    """

    # Generate session ID if not provided
    session_id = req.session_id or conversation_manager.generate_session_id()

    # Get conversation history
    conversation_history = conversation_manager.get_history(session_id)

    # Detect language
    language = detect_language(req.message)

    # Search web for current question
    web_results = await search_web(req.message)

    # Generate answer with conversation context
    answer = generate_context_aware_answer(
        question=req.message,
        context=web_results,
        language=language,
        conversation_history=conversation_history
    )

    # Store user message and assistant response in history
    conversation_manager.add_message(session_id, "user", req.message)
    conversation_manager.add_message(session_id, "assistant", answer)

    return {
        "session_id": session_id,
        "language": language,
        "answer": answer,
        "sources": web_results
    }


@router.delete("/chat-context/{session_id}")
async def clear_session(session_id: str):
    """Clear conversation history for a specific session"""
    conversation_manager.clear_session(session_id)
    return {
        "message": f"Session {session_id} cleared successfully"
    }


@router.delete("/chat-context")
async def clear_all_sessions():
    """Clear all conversation histories"""
    conversation_manager.clear_all_sessions()
    return {
        "message": "All sessions cleared successfully"
    }


@router.get("/chat-context/{session_id}/history")
async def get_session_history(session_id: str):
    """Get conversation history for a specific session"""
    history = conversation_manager.get_history(session_id)
    return {
        "session_id": session_id,
        "message_count": len(history),
        "history": history
    }


@router.get("/chat-context/stats")
async def get_conversation_stats():
    """Get statistics about active conversations"""
    active_sessions = conversation_manager.get_active_session_count()
    return {
        "active_sessions": active_sessions
    }


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """
    Streaming chat endpoint - returns response word by word for faster perceived response
    Uses Server-Sent Events (SSE)
    """
    language = detect_language(req.message)
    web_results = await search_web(req.message)

    async def event_generator():
        # First, send metadata
        yield {
            "event": "metadata",
            "data": json.dumps({
                "language": language,
                "sources": web_results
            })
        }

        # Then stream the answer
        full_answer = ""
        async for chunk in generate_streaming_answer(req.message, web_results, language):
            full_answer += chunk
            yield {
                "event": "message",
                "data": chunk
            }

        # Finally, send completion event
        yield {
            "event": "done",
            "data": json.dumps({"complete": True})
        }

    return EventSourceResponse(event_generator())


@router.post("/chat-context/stream")
async def chat_context_stream(req: ChatContextRequest):
    """
    Streaming chat with context - returns response word by word
    Uses Server-Sent Events (SSE)
    """
    # Generate session ID if not provided
    session_id = req.session_id or conversation_manager.generate_session_id()

    # Get conversation history
    conversation_history = conversation_manager.get_history(session_id)

    # Detect language
    language = detect_language(req.message)

    # Search web for current question
    web_results = await search_web(req.message)

    async def event_generator():
        # First, send metadata
        yield {
            "event": "metadata",
            "data": json.dumps({
                "session_id": session_id,
                "language": language,
                "sources": web_results
            })
        }

        # Then stream the answer
        full_answer = ""
        async for chunk in generate_streaming_context_aware_answer(
            req.message, web_results, language, conversation_history
        ):
            full_answer += chunk
            yield {
                "event": "message",
                "data": chunk
            }

        # Store conversation history
        conversation_manager.add_message(session_id, "user", req.message)
        conversation_manager.add_message(session_id, "assistant", full_answer)

        # Finally, send completion event
        yield {
            "event": "done",
            "data": json.dumps({"complete": True})
        }

    return EventSourceResponse(event_generator())