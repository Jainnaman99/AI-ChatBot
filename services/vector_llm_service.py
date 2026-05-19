"""
LLM service for vector search results
Generates answers using vector-retrieved context
"""

import re
import ollama
import asyncio
import hashlib
from typing import List, Dict

from services.prompt_service import SYSTEM_PROMPT, build_user_prompt
from services.context_prompt_service import SYSTEM_PROMPT as CONTEXT_SYSTEM_PROMPT, build_context_aware_prompt

# Patterns found in scraped Ministry table pages that confuse the LLM
_JUNK_PATTERNS = [
    re.compile(r'Published Year\s*:\s*\d{4}', re.IGNORECASE),
    re.compile(r'SizeType\s*:\s*[\d.]+ MB', re.IGNORECASE),
    re.compile(r'\bSize\s*:\s*[\d.]+ MB\b', re.IGNORECASE),
    re.compile(r'\bViewTitle\s*:', re.IGNORECASE),
    re.compile(r'\bSizeType\b', re.IGNORECASE),
]

def _trim_to_sentence_start(text: str) -> str:
    """If text starts mid-sentence (lowercase/mid-word), trim to the first clean sentence start."""
    if not text:
        return text
    first = text[0]
    if first.islower() or (not first.isalpha() and first not in ('"', "'")):
        match = re.search(r'[.!?।]\s+([A-Z\"\'])', text)
        if match:
            return text[match.start(1):]
    return text

def _clean_retrieved_text(text: str) -> str:
    """Strip document-metadata noise and fix broken chunk starts."""
    for pattern in _JUNK_PATTERNS:
        text = pattern.sub('', text)
    text = re.sub(r'\s{2,}', ' ', text)
    text = text.strip()
    text = _trim_to_sentence_start(text)
    return text

# Speed-optimized shorter system prompt for vector search (reduces context size)
FAST_SYSTEM_PROMPT = """You are Ministry of Culture India AI assistant.
Answer ONLY using provided context. If insufficient, say: "I could not find verified information."
Be detailed, factual, professional. Provide comprehensive answers covering all relevant aspects. Use same language as user.
CRITICAL: NEVER use "Published Year", "Size", or any document/file metadata as facts about museums or monuments. These refer to PDF files, not historical dates. Only state establishment years or founding dates if they are explicitly written as such in the source text."""

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
    # Format vector results as context — clean junk metadata before passing to LLM
    context_items = []
    for result in vector_results:
        context_items.append({
            "title": result.get("title", ""),
            "snippet": _clean_retrieved_text(result.get("text", "")),
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
        # Without history: use compact prompt for speed while maintaining accuracy
        context_text = "\n\n".join([
            f"Source: {item['title']}\n{item['snippet'][:800]}"
            for item in context_items[:5]
        ])
        user_prompt = f"Question: {question}\n\nContext:\n{context_text}\n\nProvide a detailed, comprehensive answer covering all relevant information from the context. WARNING: Fields like 'Published Year', 'Size', 'SizeType' in the context are document/file metadata — do NOT use them as establishment dates, founding years, or museum facts. Only use facts that are explicitly stated as such."
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

    # Generate response - OPTIMIZED FOR SPEED
    # Priority: qwen2.5:1.5b for best speed/accuracy balance
    # Priority: qwen2.5:1.5b > qwen2.5:3b > llama3.2:latest > llama3.2:1b

    # Try models in order of speed (prioritizing 1.5B for performance)
    import subprocess
    available_models = subprocess.run(["ollama", "list"], capture_output=True, text=True).stdout

    # if "qwen2.5:1.5b" in available_models:
    #     model = "qwen2.5:1.5b"  # BEST CHOICE - Fast (986 MB, 1.5B params) with good accuracy
    if "qwen2.5:3b" in available_models:
        model = "qwen2.5:3b"  # Fallback - Slower but more accurate
    elif "llama3.2:latest" in available_models:
        model = "llama3.2:latest"  # Fallback - 3B params
    # elif "llama3.2:1b" in available_models:
    #     model = "llama3.2:1b"  # Last resort - Too weak for complex extraction
    else:
        model = "qwen2.5:3b"  # Default fallback
    # if "qwen2.5:3b" in available_models:
    #     model = "qwen2.5:3b"  # Fallback - Slower but more accurate

    response = ollama.chat(
        model=model,
        messages=messages,
        options={
            "temperature": 0.1,
            "num_predict": 500,
            "num_ctx": 2048,
            "num_thread": 8,      # Max CPU threads
            "num_batch": 512,     # Batch processing
            "num_gpu": 0          # Force CPU (no GPU available)
        }
    )

    return response["message"]["content"]

_FALLBACK_PHRASE = "could not find verified information"


async def _web_search_fallback(question: str, language: str) -> str:
    """Search trusted sites via web and generate an answer from the results."""
    from services.web_search import search_web
    from services.llm_service import generate_answer

    web_results = await search_web(question, max_results=5)
    if web_results:
        return await generate_answer(question=question, context=web_results, language=language)
    return (
        "I could not find relevant information about this topic from trusted "
        "Ministry of Culture sources. Please try rephrasing your question."
    )


async def generate_vector_answer(question, vector_results, language, conversation_history=None):
    """
    Async wrapper for LLM generation with vector search results.
    Falls back to trusted-site web search if vector context is absent or insufficient.
    """
    history_len = len(conversation_history) if conversation_history else 0
    cache_key = _get_cache_key(question, language, history_len)

    if history_len == 0 and cache_key in _vector_response_cache:
        return _vector_response_cache[cache_key]

    # No vector results at all — go straight to web search
    if not vector_results:
        answer = await _web_search_fallback(question, language)
    else:
        answer = await asyncio.to_thread(
            _generate_vector_answer_sync,
            question,
            vector_results,
            language,
            conversation_history
        )
        # LLM couldn't answer from context — retry with web search
        if _FALLBACK_PHRASE in answer.lower():
            web_answer = await _web_search_fallback(question, language)
            if web_answer:
                answer = web_answer

    if history_len == 0:
        if len(_vector_response_cache) >= VECTOR_CACHE_SIZE:
            _vector_response_cache.pop(next(iter(_vector_response_cache)))
        _vector_response_cache[cache_key] = answer

    return answer
