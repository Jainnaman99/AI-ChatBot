import ollama

from services.prompt_service import (
    SYSTEM_PROMPT,
    build_user_prompt
)

def generate_answer(question, context, language):

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
            "num_predict": 300
        }
    )

    return response["message"]["content"]