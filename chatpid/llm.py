"""LLM factory: returns the right ChatModel based on LLM_PROVIDER setting.

Supports:
  - "openai" : ChatOpenAI using OpenAI's API (gpt-4o-mini, gpt-4o, etc.)
  - "groq"   : ChatOpenAI pointed at Groq's OpenAI-compatible endpoint
  - "gemini" : ChatGoogleGenerativeAI using Google's native API

All return a LangChain BaseChatModel, so callers don't need to know
which provider is active. Switch via LLM_PROVIDER in .env — no code changes.

For multi-model benchmarks, pass provider= and model= overrides to get_llm().
"""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel

from chatpid.config import get_settings


def get_llm(
    temperature: float = 0,
    provider: str | None = None,
    model: str | None = None,
) -> BaseChatModel:
    """Return a chat LLM instance.

    By default, uses LLM_PROVIDER and CHATPID_CHAT_MODEL from .env.
    Pass provider= and model= to override for multi-model benchmarks.
    """
    settings = get_settings()
    prov = provider or settings.llm_provider
    mdl = model or settings.chat_model

    if prov == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=mdl,
            temperature=temperature,
            google_api_key=settings.google_api_key,
        )

    if prov == "openai":
        from langchain_openai import ChatOpenAI

        # If OPENAI_BASE_URL is set, point ChatOpenAI at it — this enables
        # Azure OpenAI (and any other OpenAI-compatible endpoint) via the
        # same "openai" provider, matching the jeeves/sddforge pattern.
        kwargs: dict[str, object] = {
            "model": mdl,
            "temperature": temperature,
            "api_key": settings.openai_api_key,
        }
        if settings.openai_base_url:
            kwargs["base_url"] = settings.openai_base_url
        return ChatOpenAI(**kwargs)

    # Default: groq (or any OpenAI-compatible endpoint via base_url)
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=mdl,
        temperature=temperature,
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
    )
