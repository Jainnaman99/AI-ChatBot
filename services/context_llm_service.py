"""
LLM service for context-aware chatbot with conversation history.
This is separate from llm_service.py to maintain backward compatibility.
"""

import ollama
import asyncio
import hashlib

from services.context_prompt_service import (
    SYSTEM_PROMPT,
    build_context_aware_prompt
)

# Simple response cache
_context_response_cache = {}
CONTEXT_CACHE_SIZE = 50

def _get_cache_key(question: str, language: str, history_len: int) -> str:
    """Generate cache key from question, language, and history length"""
    combined = f"{question.lower().strip()}:{language}:{history_len}"
    return hashlib.md5(combined.encode()).hexdigest()

def _generate_context_aware_answer_sync(question, context, language, conversation_history=None):
    """
    Synchronous generation (used internally)
    """
    if not context:
        return """
        I could not find verified information from trusted Ministry of Culture sources for this query.
        Please try rephrasing your question.
        """

    user_prompt = build_context_aware_prompt(
        question=question,
        language=language,
        context_items=context,
        conversation_history=conversation_history
    )

    # Build messages list including conversation history for Ollama
    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        }
    ]

    # Add conversation history (but limit to avoid token overflow)
    if conversation_history:
        # Only include last 6 messages (3 exchanges) to keep context manageable
        recent_history = conversation_history[-6:]
        for msg in recent_history:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })

    # Add current user prompt
    messages.append({
        "role": "user",
        "content": user_prompt
    })

    response = ollama.chat(
        model="qwen2.5:3b",
        messages=messages,
        options={
            "temperature": 0.1,
            "num_predict": 500
        }
    )

    return response["message"]["content"]

async def generate_context_aware_answer(question, context, language, conversation_history=None):
    """
    Async wrapper for context-aware LLM generation with caching
    Runs blocking ollama call in thread pool to avoid blocking event loop

    Args:
        question: Current user question
        context: Web search results
        language: Detected language
        conversation_history: List of previous message dicts with 'role' and 'content'

    Returns:
        Generated answer string
    """
    # Check cache (only cache if no conversation history for simplicity)
    history_len = len(conversation_history) if conversation_history else 0
    cache_key = _get_cache_key(question, language, history_len)

    # Only cache queries without history to keep it simple
    if history_len == 0 and cache_key in _context_response_cache:
        return _context_response_cache[cache_key]

    # Run blocking ollama call in thread pool
    answer = await asyncio.to_thread(
        _generate_context_aware_answer_sync,
        question,
        context,
        language,
        conversation_history
    )

    # Cache the response (only if no history)
    if history_len == 0:
        if len(_context_response_cache) >= CONTEXT_CACHE_SIZE:
            # Remove oldest entry
            _context_response_cache.pop(next(iter(_context_response_cache)))
        _context_response_cache[cache_key] = answer

    return answer
