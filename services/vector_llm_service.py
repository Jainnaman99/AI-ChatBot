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

# Speed-optimized shorter system prompt for vector search (reduces context size)
FAST_SYSTEM_PROMPT = """You are Ministry of Culture India AI assistant.
Answer ONLY using provided context. If insufficient, say: "I could not find verified information."
Be concise, factual, professional. Use same language as user."""

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

    # Build compact prompt for SPEED (shorter prompts = faster generation)
    if conversation_history:
        # With history, use full prompts
        user_prompt = build_context_aware_prompt(
            question=question,
            language=language,
            context_items=context_items,
            conversation_history=conversation_history
        )
        system_prompt = CONTEXT_SYSTEM_PROMPT
    else:
        # Without history: use minimal prompt for MAXIMUM SPEED
        context_text = "\n\n".join([
            f"Source: {item['title']}\n{item['snippet'][:250]}"  # Limit snippet to 250 chars
            for item in context_items[:3]  # Only top 3 results for speed
        ])
        user_prompt = f"Question: {question}\n\nContext:\n{context_text}\n\nAnswer briefly:"
        system_prompt = FAST_SYSTEM_PROMPT

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

    # Generate response - MAXIMUM SPEED OPTIMIZATION
    # Will auto-switch to fastest available model once downloaded
    # Priority: llama3.2:1b > qwen2.5:1.5b > llama3.2:latest > qwen2.5:3b

    # Try fastest models first
    import subprocess
    available_models = subprocess.run(["ollama", "list"], capture_output=True, text=True).stdout

    if "llama3.2:1b" in available_models:
        model = "llama3.2:1b"  # Fastest - 1B params
    elif "qwen2.5:1.5b" in available_models:
        model = "qwen2.5:1.5b"  # Fast - 1.5B params
    elif "llama3.2:latest" in available_models:
        model = "llama3.2:latest"  # 3B params
    else:
        model = "qwen2.5:3b"  # Fallback

    response = ollama.chat(
        model=model,
        messages=messages,
        options={
            "temperature": 0.1,
            "num_predict": 80,   # Minimal tokens for speed
            "num_ctx": 512,      # Absolute minimum context
            "num_thread": 8,     # Max CPU threads
            "num_batch": 512,    # Batch processing
            "num_gpu": 0         # Force CPU (no GPU available)
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
