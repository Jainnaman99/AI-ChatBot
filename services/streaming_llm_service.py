"""
Streaming LLM service for real-time responses
"""

import ollama
import json

from services.prompt_service import (
    SYSTEM_PROMPT,
    build_user_prompt
)
from services.context_prompt_service import (
    SYSTEM_PROMPT as CONTEXT_SYSTEM_PROMPT,
    build_context_aware_prompt
)


async def generate_streaming_answer(question, context, language):
    """
    Generate streaming answer without conversation history

    Yields chunks of the response as they're generated
    Buffers small tokens for smoother streaming experience
    """
    if not context:
        yield """I could not find verified information from trusted Ministry of Culture sources for this query. Please try rephrasing your question."""
        return

    user_prompt = build_user_prompt(
        question=question,
        language=language,
        context_items=context
    )

    stream = ollama.chat(
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
            "num_predict": 300
        },
        stream=True
    )

    buffer = ""
    for chunk in stream:
        if chunk.get("message", {}).get("content"):
            token = chunk["message"]["content"]
            buffer += token

            # Yield when we have accumulated enough content or hit punctuation
            if len(buffer) >= 5 or token in ['.', '!', '?', '\n', '।']:
                yield buffer
                buffer = ""

    # Yield any remaining content
    if buffer:
        yield buffer


async def generate_streaming_context_aware_answer(question, context, language, conversation_history=None):
    """
    Generate streaming answer with conversation history

    Yields chunks of the response as they're generated
    Buffers small tokens for smoother streaming experience
    """
    if not context:
        yield """I could not find verified information from trusted Ministry of Culture sources for this query. Please try rephrasing your question."""
        return

    user_prompt = build_context_aware_prompt(
        question=question,
        language=language,
        context_items=context,
        conversation_history=conversation_history
    )

    # Build messages list including conversation history
    messages = [
        {
            "role": "system",
            "content": CONTEXT_SYSTEM_PROMPT
        }
    ]

    # Add conversation history (but limit to avoid token overflow)
    if conversation_history:
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

    stream = ollama.chat(
        model="qwen2.5:3b",
        messages=messages,
        options={
            "temperature": 0.1,
            "num_predict": 300
        },
        stream=True
    )

    buffer = ""
    for chunk in stream:
        if chunk.get("message", {}).get("content"):
            token = chunk["message"]["content"]
            buffer += token

            # Yield when we have accumulated enough content or hit punctuation
            if len(buffer) >= 5 or token in ['.', '!', '?', '\n', '।']:
                yield buffer
                buffer = ""

    # Yield any remaining content
    if buffer:
        yield buffer
