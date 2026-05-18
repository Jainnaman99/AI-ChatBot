from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
import json
import time

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
from services.vector_search_service import get_vector_search_service
from services.vector_llm_service import generate_vector_answer
from services.translation_service import get_translation_service

router = APIRouter()

# ---------------------------------------------------------------------------
# Conversational intent detection
# ---------------------------------------------------------------------------

_GREETINGS = {
    "hi", "hey", "hello", "hola", "howdy", "greetings", "sup", "heya",
    "namaste", "namaskar", "salam", "assalamualaikum", "jai hind",
    "good morning", "good afternoon", "good evening", "good night",
}

_THANKS = {
    "thanks", "thank you", "thankyou", "thank u", "thx", "ty",
    "dhanyawad", "shukriya", "bahut shukriya", "bahut dhanyawad",
}

_FAREWELLS = {
    "bye", "goodbye", "good bye", "see you", "see ya", "later", "take care",
    "alvida", "phir milenge",
}

_HOW_ARE_YOU = {
    "how are you", "how r u", "how are u", "hows it going", "how's it going",
    "what's up", "whats up", "wassup",
}

_WHAT_CAN_YOU_DO = {
    "what can you do", "what do you do", "who are you", "what are you",
    "tell me about yourself", "help", "help me",
}

def _normalise(text: str) -> str:
    import re
    return re.sub(r"[^\w\s]", "", text.lower()).strip()

def detect_conversational_intent(message: str):
    """
    Returns (intent, reply) if the message is purely conversational,
    or (None, None) if it should go through the normal search pipeline.
    intent can be: 'greeting' | 'thanks' | 'farewell' | 'how_are_you' | 'what_can_you_do'
    """
    norm = _normalise(message)

    if norm in _GREETINGS or any(norm.startswith(g) for g in _GREETINGS):
        return "greeting", (
            "Hello! Welcome to the Ministry of Culture India Assistant. 🙏\n\n"
            "I can help you with:\n"
            "• Information about Indian cultural heritage, monuments, and museums\n"
            "• Government schemes and programs by the Ministry of Culture\n"
            "• Details about festivals, art forms, and cultural events\n"
            "• Information about archaeological sites and protected monuments\n\n"
            "Feel free to ask me anything about India's rich culture and heritage!"
        )

    if norm in _HOW_ARE_YOU or any(norm.startswith(h) for h in _HOW_ARE_YOU):
        return "how_are_you", (
            "I'm doing great and ready to help! 😊\n\n"
            "I'm the Ministry of Culture India Assistant. You can ask me about "
            "Indian heritage, monuments, museums, cultural schemes, festivals, and much more.\n\n"
            "What would you like to know today?"
        )

    if norm in _WHAT_CAN_YOU_DO or any(norm.startswith(w) for w in _WHAT_CAN_YOU_DO):
        return "what_can_you_do", (
            "I'm the official AI Assistant for the Ministry of Culture, India. Here's what I can help you with:\n\n"
            "🏛️ **Monuments & Heritage Sites** — Taj Mahal, Qutub Minar, Hampi, and more\n"
            "🏺 **Museums** — National Museum, regional museums, and their collections\n"
            "🎭 **Art & Culture** — Classical dance, music, folk arts, and crafts\n"
            "📜 **Government Schemes** — Cultural grants, fellowships, and programs\n"
            "🎉 **Festivals & Events** — National festivals and cultural events\n"
            "🌐 **Intangible Heritage** — UNESCO-listed traditions and practices\n\n"
            "Just ask your question and I'll find the most accurate information for you!"
        )

    if norm in _THANKS or any(norm.startswith(t) for t in _THANKS):
        return "thanks", (
            "You're welcome! 😊 I'm happy to help.\n\n"
            "Feel free to ask if you have more questions about Indian culture, heritage, or Ministry of Culture schemes."
        )

    if norm in _FAREWELLS or any(norm.startswith(f) for f in _FAREWELLS):
        return "farewell", (
            "Goodbye! It was a pleasure assisting you. 🙏\n\n"
            "Come back anytime you have questions about India's culture and heritage. Jai Hind!"
        )

    return None, None

@router.post("/chat")
async def chat(req: ChatRequest):

    language = detect_language(req.message)

    web_results = await search_web(req.message)

    answer = await generate_answer(
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
    answer = await generate_context_aware_answer(
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


@router.post("/chat-vector")
async def chat_vector(req: ChatRequest):
    """
    Chat endpoint using vector search (semantic search on scraped content)
    Fast, offline, and more accurate than web search
    """
    language = detect_language(req.message)

    # Get vector search service
    vector_service = get_vector_search_service()

    # Search vector database
    vector_results = await vector_service.search(req.message, top_k=5)

    # Generate answer using vector results
    answer = await generate_vector_answer(
        question=req.message,
        vector_results=vector_results,
        language=language
    )

    # Format sources for response
    sources = []
    for result in vector_results:
        sources.append({
            "title": result["title"],
            "snippet": result["text"][:200] + "..." if len(result["text"]) > 200 else result["text"],
            "link": result["url"],
            "relevance": result["similarity"]
        })

    return {
        "language": language,
        "answer": answer,
        "sources": sources,
        "search_type": "vector"
    }


@router.post("/chat-vector-context")
async def chat_vector_with_context(req: ChatContextRequest):
    """
    Chat with vector search AND conversation history
    Combines semantic search with conversation context
    """
    # Start timing
    start_time = time.time()

    # Generate session ID if not provided
    session_id = req.session_id or conversation_manager.generate_session_id()

    # Get conversation history
    conversation_history = conversation_manager.get_history(session_id)

    # Detect language
    language = detect_language(req.message)

    # Get vector search service
    vector_service = get_vector_search_service()

    # Enhance query with conversation context for vague queries
    search_query = req.message
    if conversation_history and len(conversation_history) > 0:
        # Check if query is vague (pronouns, short queries, follow-up questions)
        vague_indicators = [
            "it", "that", "this", "they", "them", "more", "tell me", "what about",
            "where", "when", "who", "how", "why", "which"  # Question words for follow-ups
        ]

        # Check if it's a short query (< 8 words) starting with question word or containing vague pronouns
        is_short = len(req.message.split()) < 8
        starts_with_question = any(req.message.lower().startswith(q) for q in ["where", "when", "who", "how", "why", "which", "what"])
        has_vague_word = any(indicator in req.message.lower() for indicator in vague_indicators)

        is_vague = is_short and (starts_with_question or has_vague_word)

        if is_vague:
            # Extract keywords from recent user messages (last 2 user messages)
            recent_user_messages = [msg["content"] for msg in conversation_history if msg["role"] == "user"][-2:]
            if recent_user_messages:
                # Combine previous context with current query
                search_query = f"{' '.join(recent_user_messages)} {req.message}"

    # Search vector database with enhanced query
    vector_results = await vector_service.search(search_query, top_k=5)

    # Generate answer with conversation context
    answer = await generate_vector_answer(
        question=req.message,
        vector_results=vector_results,
        language=language,
        conversation_history=conversation_history
    )

    # Store conversation history
    conversation_manager.add_message(session_id, "user", req.message)
    conversation_manager.add_message(session_id, "assistant", answer)

    # Format sources
    sources = []
    for result in vector_results:
        sources.append({
            "title": result["title"],
            "snippet": result["text"][:200] + "..." if len(result["text"]) > 200 else result["text"],
            "link": result["url"],
            "relevance": result["similarity"]
        })

    # Calculate response time
    response_time = round(time.time() - start_time, 2)

    return {
        "session_id": session_id,
        "language": language,
        "answer": answer,
        "sources": sources,
        "search_type": "vector",
        "response_time_seconds": response_time
    }


@router.post("/chat-hybrid")
async def chat_hybrid(req: ChatRequest):
    """
    Hybrid search: Try vector search first, fallback to web search
    Best of both worlds - fast when possible, comprehensive when needed
    """
    language = detect_language(req.message)

    # Try vector search first
    vector_service = get_vector_search_service()
    vector_results = await vector_service.search(req.message, top_k=5, min_similarity=0.75)

    if vector_results and len(vector_results) >= 2:
        # Good vector results found, use them
        answer = await generate_vector_answer(
            question=req.message,
            vector_results=vector_results,
            language=language
        )

        sources = []
        for result in vector_results:
            sources.append({
                "title": result["title"],
                "snippet": result["text"][:200] + "..." if len(result["text"]) > 200 else result["text"],
                "link": result["url"],
                "relevance": result["similarity"]
            })

        return {
            "language": language,
            "answer": answer,
            "sources": sources,
            "search_type": "vector"
        }
    else:
        # Fallback to web search
        web_results = await search_web(req.message)

        answer = await generate_answer(
            question=req.message,
            context=web_results,
            language=language
        )

        return {
            "language": language,
            "answer": answer,
            "sources": web_results,
            "search_type": "web_fallback"
        }


@router.post("/chat-hybrid-context")
async def chat_hybrid_context(req: ChatContextRequest):
    """
    Context-aware hybrid search with conversation history
    1. First tries vector search from local database
    2. If insufficient results, falls back to real-time web scraping
    3. Maintains conversation context for follow-up questions

    Best of both worlds:
    - Fast responses from vector DB when data exists
    - Comprehensive real-time data when local data is insufficient
    - Full conversation context support
    """
    # Start timing
    start_time = time.time()

    # Generate session ID if not provided
    session_id = req.session_id or conversation_manager.generate_session_id()

    # Get conversation history
    conversation_history = conversation_manager.get_history(session_id)

    # Detect language
    language = detect_language(req.message)

    # --- Conversational short-circuit ---
    intent, greeting_reply = detect_conversational_intent(req.message)
    if intent:
        translator = get_translation_service()
        reply = translator.from_english(greeting_reply, language) if language != "en" else greeting_reply
        conversation_manager.add_message(session_id, "user", req.message)
        conversation_manager.add_message(session_id, "assistant", reply)
        response_time = round(time.time() - start_time, 2)
        return {
            "session_id": session_id,
            "language": language,
            "answer": reply,
            "sources": [],
            "search_type": "conversational",
            "response_time_seconds": response_time
        }

    # Get translation service
    translator = get_translation_service()

    # Translate query to English for better vector search (if not English)
    english_query = translator.to_english(req.message, language) if language != "en" else req.message

    # Get vector search service
    vector_service = get_vector_search_service()

    # Enhance query with conversation context for vague queries
    search_query = english_query
    if conversation_history and len(conversation_history) > 0:
        # Check if query is vague (pronouns, short queries, follow-up questions)
        vague_indicators = [
            "it", "that", "this", "they", "them", "more", "tell me", "what about",
            "where", "when", "who", "how", "why", "which"  # Question words for follow-ups
        ]

        # Check if it's a short query (< 8 words) starting with question word or containing vague pronouns
        is_short = len(req.message.split()) < 8
        starts_with_question = any(req.message.lower().startswith(q) for q in ["where", "when", "who", "how", "why", "which", "what"])
        has_vague_word = any(indicator in req.message.lower() for indicator in vague_indicators)

        is_vague = is_short and (starts_with_question or has_vague_word)

        if is_vague:
            # Extract keywords from recent user messages (last 2 user messages)
            recent_user_messages = [msg["content"] for msg in conversation_history if msg["role"] == "user"][-2:]
            if recent_user_messages:
                # Combine previous context with current query
                search_query = f"{' '.join(recent_user_messages)} {req.message}"

    # Try vector search first with reasonable similarity threshold
    vector_results = await vector_service.search(search_query, top_k=5, min_similarity=0.50)

    # Decide if vector results are good enough
    # Consider results good if we have at least 2 results with similarity > 0.50
    use_vector = vector_results and len(vector_results) >= 2

    if use_vector:
        # Vector search has good results - use them
        # Generate answer in English (vector DB has English content)
        answer_english = await generate_vector_answer(
            question=english_query,
            vector_results=vector_results,
            language="en",  # Force English for generation
            conversation_history=conversation_history
        )

        # Translate answer back to original language
        answer = translator.from_english(answer_english, language) if language != "en" else answer_english

        # Store conversation history
        conversation_manager.add_message(session_id, "user", req.message)
        conversation_manager.add_message(session_id, "assistant", answer)

        # Format sources — import inline to avoid circular deps
        from services.vector_llm_service import _clean_retrieved_text
        sources = []
        for result in vector_results:
            clean = _clean_retrieved_text(result["text"])
            sources.append({
                "title": result["title"],
                "snippet": clean[:200] + "..." if len(clean) > 200 else clean,
                "link": result["url"],
                "relevance": result["similarity"]
            })

        # Calculate response time
        response_time = round(time.time() - start_time, 2)

        return {
            "session_id": session_id,
            "language": language,
            "answer": answer,
            "sources": sources,
            "search_type": "vector",
            "response_time_seconds": response_time
        }
    else:
        # Vector search insufficient - fallback to real-time web search
        web_results = await search_web(req.message)

        # Generate answer with conversation context
        # Build context for web results
        context_items = web_results

        if conversation_history:
            # Use context-aware prompt
            from services.context_prompt_service import build_context_aware_prompt
            user_prompt = build_context_aware_prompt(
                question=req.message,
                language=language,
                context_items=context_items,
                conversation_history=conversation_history
            )

            # Generate with context
            answer = await generate_answer(
                question=req.message,
                context=web_results,
                language=language
            )
        else:
            # No conversation history, use standard generation
            answer = await generate_answer(
                question=req.message,
                context=web_results,
                language=language
            )

        # Store conversation history
        conversation_manager.add_message(session_id, "user", req.message)
        conversation_manager.add_message(session_id, "assistant", answer)

        # Calculate response time
        response_time = round(time.time() - start_time, 2)

        return {
            "session_id": session_id,
            "language": language,
            "answer": answer,
            "sources": web_results,
            "search_type": "web_fallback",
            "response_time_seconds": response_time
        }


@router.get("/vector-stats")
async def get_vector_stats():
    """Get vector database statistics"""
    vector_service = get_vector_search_service()
    stats = vector_service.get_stats()
    return stats


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




