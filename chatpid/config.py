"""Central settings, loaded once from the environment / .env file."""

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
    chat_model: str
    embedding_model: str


@lru_cache
def get_settings() -> Settings:
    return Settings(
        neo4j_uri=os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
        neo4j_user=os.environ.get("NEO4J_USER", "neo4j"),
        neo4j_password=os.environ.get("NEO4J_PASSWORD", "chatpid_dev_pw"),
        chat_model=os.environ.get("CHATPID_CHAT_MODEL", "gpt-5-mini"),
        embedding_model=os.environ.get(
            "CHATPID_EMBEDDING_MODEL", "text-embedding-3-small"
        ),
    )
