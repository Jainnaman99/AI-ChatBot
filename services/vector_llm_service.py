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
    # Empty collection-browser pages from museumsofindia.gov.in
    re.compile(r'\d+\s+records\s+Browse\s+Records', re.IGNORECASE),
    re.compile(r"We couldn'?t find any matches[!.]?", re.IGNORECASE),
    re.compile(r'\d+\s*-\s*\d+\s+of\s+\d+\s+records', re.IGNORECASE),
    re.compile(r'Show more\s*\d*\s*records?', re.IGNORECASE),
    re.compile(r'Browse\s+Records', re.IGNORECASE),
    re.compile(r'National Portal\s*(?:&|and)?\s*Digital Repository', re.IGNORECASE),
    re.compile(r'Filters\s+Clear\s+all\s+State\s+Museum\s+Type\s+Owner', re.IGNORECASE),
    re.compile(r'Search\s+Results\s+\d+\s+\d+\s+\d+\s+\d+', re.IGNORECASE),
    re.compile(r'Explore\s+Collection\s+Searchable\s+PDF', re.IGNORECASE),
]

# Minimum useful content length after cleaning — chunks shorter than this are discarded
_MIN_CHUNK_LENGTH = 60


def _is_useful_chunk(text: str) -> bool:
    """Return False if the chunk is essentially empty or all boilerplate after cleaning."""
    return len(text.strip()) >= _MIN_CHUNK_LENGTH

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
Answer ONLY using provided context. Be detailed, factual, professional. Use same language as user.
CRITICAL RULES:
- NEVER open your answer with "I could not find" or any disclaimer when sources are provided. Start directly with the answer.
- Say "I could not find verified information." ONLY if context is completely absent or entirely off-topic.
- For lists (museums, tenders, schemes): list every item found in context using bullet points, then include the source URL.
- NEVER use "Published Year", "Size", "SizeType", or file metadata as facts. Only use dates explicitly stated as establishment/founding years."""

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
    # Format vector results as context — clean junk metadata, discard empty chunks
    context_items = []
    for result in vector_results:
        cleaned = _clean_retrieved_text(result.get("text", ""))
        if not _is_useful_chunk(cleaned):
            continue
        context_items.append({
            "title": result.get("title", ""),
            "snippet": cleaned,
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
        user_prompt = f"Question: {question}\n\nContext:\n{context_text}\n\nStart your answer directly — do NOT open with 'I could not find' or any disclaimer. List every museum/item found in context using bullet points. Include source URL at the end. WARNING: 'Published Year', 'Size', 'SizeType' are PDF metadata — ignore them as facts."
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

# Minimum chars of real content that makes a response worth keeping
_MIN_CONTENT_LENGTH = 80


def _strip_fallback_phrase(answer: str) -> tuple:
    """
    Remove the fallback phrase whether it appears at the start or end of the answer.

    Returns (cleaned_answer, phrase_found).
    Cases handled:
      - Phrase at END  : "Here are museums... I could not find..." → keep content before phrase
      - Phrase at START: "I could not find... Here are museums..." → keep content after phrase
      - Phrase only    : whole answer is the phrase → keep as-is (triggers web fallback)
    """
    lower = answer.lower()
    pos = lower.find(_FALLBACK_PHRASE)
    if pos == -1:
        return answer, False

    content_before = answer[:pos].strip()

    # Find where the text resumes after the phrase (skip trailing punctuation/newlines)
    after_pos = pos + len(_FALLBACK_PHRASE)
    while after_pos < len(answer) and answer[after_pos] in '.\n\r !?':
        after_pos += 1
    content_after = answer[after_pos:].strip()

    # Phrase at END — real content came before it
    if len(content_before) >= _MIN_CONTENT_LENGTH:
        return content_before, True

    # Phrase at START — real content follows it
    if len(content_after) >= _MIN_CONTENT_LENGTH:
        return content_after, True

    # Whole answer is essentially just the phrase — signal true fallback needed
    return answer, True


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

        # LLM appended the fallback phrase — try to strip it first
        cleaned, phrase_found = _strip_fallback_phrase(answer)
        if phrase_found:
            if len(cleaned.strip()) >= _MIN_CONTENT_LENGTH:
                # Good content exists — just drop the trailing phrase
                answer = cleaned
            else:
                # Genuinely couldn't answer — try web search
                web_answer = await _web_search_fallback(question, language)
                if web_answer:
                    answer = web_answer

    if history_len == 0:
        if len(_vector_response_cache) >= VECTOR_CACHE_SIZE:
            _vector_response_cache.pop(next(iter(_vector_response_cache)))
        _vector_response_cache[cache_key] = answer

    return answer
