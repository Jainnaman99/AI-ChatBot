"""
LLM service for vector search results
Generates answers using vector-retrieved context
"""

import ollama
import asyncio
import hashlib
from typing import List, Dict

from services.prompt_service import SYSTEM_PROMPT, build_user_prompt
from services.context_prompt_service import SYSTEM_PROMPT as CONTEXT_SYSTEM_PROMPT, build_context_aware_prompt

# Response cache for vector search
_vector_response_cache = {}
VECTOR_CACHE_SIZE = 100

def _get_cache_key(question: str, language: str, history_len: int) -> str:
    """Generate cache key"""
    combined = f"vector:{question.lower().strip()}:{language}:{history_len}"
    return hashlib.md5(combined.encode()).hexdigest()

def _generate_vector_answer_sync(question, vector_results, language, conversation_history=None):
    """
    Synchronous LLM generation using vector search results

    Args:
        question: User question
        vector_results: Vector search results (list of dicts)
        language: Detected language
        conversation_history: Optional conversation history

    Returns:
        Generated answer string
    """
    if not vector_results:
        return """
        I could not find verified information from trusted Ministry of Culture sources for this query.
        Please try rephrasing your question.
        """

    # Format vector results as context (similar to web search format)
    context_items = []
    for result in vector_results:
        context_items.append({
            "title": result.get("title", ""),
            "snippet": result.get("text", ""),
            "link": result.get("url", "")
        })

    # Build appropriate prompt based on whether we have conversation history
    if conversation_history:
        user_prompt = build_context_aware_prompt(
            question=question,
            language=language,
            context_items=context_items,
            conversation_history=conversation_history
        )
        system_prompt = CONTEXT_SYSTEM_PROMPT
    else:
        user_prompt = build_user_prompt(
            question=question,
            language=language,
            context_items=context_items
        )
        system_prompt = SYSTEM_PROMPT

    # Build messages
    messages = [
        {
            "role": "system",
            "content": system_prompt
        }
    ]

    # Add conversation history if provided
    if conversation_history:
        recent_history = conversation_history[-6:]
        for msg in recent_history:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })

    # Add current prompt
    messages.append({
        "role": "user",
        "content": user_prompt
    })

    # Generate response
    response = ollama.chat(
        model="qwen2.5:3b",
        messages=messages,
        options={
            "temperature": 0.1,
            "num_predict": 250
        }
    )

    return response["message"]["content"]

async def generate_vector_answer(question, vector_results, language, conversation_history=None):
    """
    Async wrapper for LLM generation with vector search results

    Args:
        question: User question
        vector_results: Vector search results
        language: Detected language
        conversation_history: Optional conversation history

    Returns:
        Generated answer string
    """
    # Check cache (only cache if no conversation history)
    history_len = len(conversation_history) if conversation_history else 0
    cache_key = _get_cache_key(question, language, history_len)

    if history_len == 0 and cache_key in _vector_response_cache:
        return _vector_response_cache[cache_key]

    # Run blocking ollama call in thread pool
    answer = await asyncio.to_thread(
        _generate_vector_answer_sync,
        question,
        vector_results,
        language,
        conversation_history
    )

    # Cache response (only if no history)
    if history_len == 0:
        if len(_vector_response_cache) >= VECTOR_CACHE_SIZE:
            # Remove oldest entry
            _vector_response_cache.pop(next(iter(_vector_response_cache)))
        _vector_response_cache[cache_key] = answer

    return answer
