"""LLM factory: returns the right ChatModel based on LLM_PROVIDER setting.

Supports:
  - "openai" : ChatOpenAI using OpenAI's API (gpt-4o-mini, gpt-4o, etc.)
  - "groq"   : ChatOpenAI pointed at Groq's OpenAI-compatible endpoint
  - "gemini" : ChatGoogleGenerativeAI using Google's native API

All return a LangChain BaseChatModel, so callers don't need to know
which provider is active. Switch via LLM_PROVIDER in .env — no code changes.
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

    if settings.llm_provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=settings.chat_model,
            temperature=temperature,
            api_key=settings.openai_api_key,
        )

    # Default: groq (or any OpenAI-compatible endpoint via base_url)
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=settings.chat_model,
        temperature=temperature,
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
    )
