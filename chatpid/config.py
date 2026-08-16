"""Central settings, loaded once from the environment / .env file.

Supports two LLM providers, switchable via LLM_PROVIDER env var:
  - "groq"   : uses GROQ_API_KEY, langchain-openai ChatOpenAI
  - "gemini" : uses GOOGLE_API_KEY, langchain-google-genai ChatGoogleGenerativeAI

No code changes needed to switch — just update .env and restart.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    # LLM provider config
    llm_provider: str  # "groq" | "gemini"
    chat_model: str
    embedding_model: str
    # OpenAI-compatible endpoints (groq, openai, etc.)
    llm_base_url: str
    llm_api_key: str  # GROQ_API_KEY or OPENAI_API_KEY
    # Gemini-specific
    google_api_key: str


@lru_cache
def get_settings() -> Settings:
    provider = os.environ.get("LLM_PROVIDER", "groq").lower().strip()
    return Settings(
        neo4j_uri=os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
        neo4j_user=os.environ.get("NEO4J_USER", "neo4j"),
        neo4j_password=os.environ.get("NEO4J_PASSWORD", "chatpid_dev_pw"),
        llm_provider=provider,
        chat_model=os.environ.get("CHATPID_CHAT_MODEL", "llama-3.3-70b-versatile"),
        embedding_model=os.environ.get(
            "CHATPID_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        ),
        llm_base_url=os.environ.get(
            "CHATPID_LLM_BASE_URL", "https://api.groq.com/openai/v1"
        ),
        llm_api_key=os.environ.get("GROQ_API_KEY", ""),
        google_api_key=os.environ.get("GOOGLE_API_KEY", ""),
    )
