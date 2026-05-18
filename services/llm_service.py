import ollama
import asyncio
import hashlib

from services.prompt_service import (
    SYSTEM_PROMPT,
    build_user_prompt
)

# Simple response cache
_response_cache = {}
RESPONSE_CACHE_SIZE = 50

def _get_cache_key(question: str, language: str) -> str:
    """Generate cache key from question and language"""
    combined = f"{question.lower().strip()}:{language}"
    return hashlib.md5(combined.encode()).hexdigest()

def _generate_answer_sync(question, context, language):
    """Synchronous LLM generation (used internally)"""
    if not context:
        return """
        I could not find verified information from trusted Ministry of Culture sources for this query.
        Please try rephrasing your question.
        """

    user_prompt = build_user_prompt(
        question=question,
        language=language,
        context_items=context
    )

    response = ollama.chat(
        model="qwen2.5:3b",
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ],
        options={
            "temperature": 0.1,
            "num_predict": 500
        }
    )

    return response["message"]["content"]

async def generate_answer(question, context, language):
    """
    Async wrapper for LLM generation with caching
    Runs blocking ollama call in thread pool to avoid blocking event loop
    """
    # Check cache first
    cache_key = _get_cache_key(question, language)
    if cache_key in _response_cache:
        return _response_cache[cache_key]

    # Run blocking ollama call in thread pool
    answer = await asyncio.to_thread(
        _generate_answer_sync,
        question,
        context,
        language
    )

    # Cache the response
    if len(_response_cache) >= RESPONSE_CACHE_SIZE:
        # Remove oldest entry
        _response_cache.pop(next(iter(_response_cache)))
    _response_cache[cache_key] = answer

    return answer