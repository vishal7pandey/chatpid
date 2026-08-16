"""LLM factory: returns the right ChatModel based on LLM_PROVIDER setting.

Supports:
  - "groq"   : ChatOpenAI pointed at Groq's OpenAI-compatible endpoint
  - "gemini" : ChatGoogleGenerativeAI using Google's native API

Both return a LangChain BaseChatModel, so callers don't need to know
which provider is active.
"""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel

from chatpid.config import get_settings


def get_llm(temperature: float = 0) -> BaseChatModel:
    """Return a chat LLM instance based on the LLM_PROVIDER env var."""
    settings = get_settings()

    if settings.llm_provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=settings.chat_model,
            temperature=temperature,
            google_api_key=settings.google_api_key,
        )

    # Default: groq (or any OpenAI-compatible endpoint)
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=settings.chat_model,
        temperature=temperature,
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
    )
