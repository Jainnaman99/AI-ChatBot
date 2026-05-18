"""
Prompt service for context-aware chatbot with conversation history support.
This is separate from the original prompt_service to maintain backward compatibility.
"""

SYSTEM_PROMPT = """
You are the official AI assistant for Ministry of Culture India.

STRICT RULES:

1. ONLY answer using the provided trusted-source context.

2. NEVER invent facts, schemes, websites, museums, or historical information.

3. NEVER generate generic fallback responses.

4. If context is missing or insufficient, say:
   "I could not find verified information from trusted Ministry sources."

5. ALWAYS prioritize factual information from provided sources.

6. Keep responses clear, factual, detailed, and professional. Provide thorough answers.

7. DO NOT behave like a casual chatbot.

8. DO NOT rewrite the user's question.

9. DO NOT ask unnecessary follow-up questions.

10. Mention source titles naturally when relevant.

11. If user asks for list-type information, return structured bullet points.

12. Respond in the SAME language as the user.

13. If user writes in Hinglish, respond in Hinglish professionally.

14. NEVER say:
   - "Okay okay"
   - "Sure thing"
   - "I think"
   - "Maybe"
   - "You can check website"

15. If context exists, ALWAYS use it before model knowledge.

16. Your primary purpose is factual cultural assistance for India.

17. Use conversation history to understand context references like "it", "that place", "the scheme mentioned earlier".

18. Maintain conversation continuity while staying factual.
"""


def build_context(context_items):
    """Build formatted context from search results"""
    if not context_items:
        return ""

    formatted_context = ""

    for index, item in enumerate(context_items, start=1):
        formatted_context += f"""
SOURCE {index}

Title:
{item.get('title', '')}

Description:
{item.get('snippet', '')}

Website:
{item.get('link', '')}

-----------------------------------
"""

    return formatted_context


def build_conversation_history(history_messages):
    """
    Build formatted conversation history string

    Args:
        history_messages: List of message dicts with 'role' and 'content'

    Returns:
        Formatted conversation history string
    """
    if not history_messages:
        return ""

    formatted_history = "=== Previous Conversation ===\n\n"
    for msg in history_messages:
        role = "User" if msg["role"] == "user" else "Assistant"
        formatted_history += f"{role}: {msg['content']}\n\n"

    formatted_history += "=== End of Previous Conversation ===\n\n"
    return formatted_history


def build_context_aware_prompt(question, language, context_items, conversation_history=None):
    """
    Build prompt with conversation history support

    Args:
        question: Current user question
        language: Detected language
        context_items: Web search results
        conversation_history: List of previous messages

    Returns:
        Formatted prompt string
    """
    context_text = build_context(context_items)
    history_text = build_conversation_history(conversation_history) if conversation_history else ""

    if not context_text:
        return f"""
{history_text}
Current User Question:
{question}

IMPORTANT:
No trusted Ministry context was found for the current question.

If answer is uncertain, clearly say:
"I could not find verified information from trusted Ministry sources."

You may use conversation history for context, but do NOT invent new information.
"""

    return f"""
User Language:
{language}

{history_text}
Trusted Ministry Context (for current question):
{context_text}

Current User Question:
{question}

INSTRUCTIONS:

1. Answer ONLY using the trusted context provided above.

2. Use conversation history to understand references (like "it", "that place", "the scheme").

3. If the user refers to something from previous messages, acknowledge it naturally.

4. Keep the response factual and professional.

5. Do NOT generate generic chatbot responses.

6. If schemes/services/programs are mentioned, list them clearly using bullet points.

7. If location is asked, provide direct location answer first.

8. Respond in the same language as the user.

9. Provide a detailed, thorough response covering all relevant aspects from the context.
"""
