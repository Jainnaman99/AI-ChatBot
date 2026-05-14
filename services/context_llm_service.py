"""
LLM service for context-aware chatbot with conversation history.
This is separate from llm_service.py to maintain backward compatibility.
"""

import ollama

from services.context_prompt_service import (
    SYSTEM_PROMPT,
    build_context_aware_prompt
)


def generate_context_aware_answer(question, context, language, conversation_history=None):
    """
    Generate answer using conversation history for context

    Args:
        question: Current user question
        context: Web search results
        language: Detected language
        conversation_history: List of previous message dicts with 'role' and 'content'

    Returns:
        Generated answer string
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
            "num_predict": 300
        }
    )

    return response["message"]["content"]
