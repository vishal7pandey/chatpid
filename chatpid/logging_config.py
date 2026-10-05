"""Logging setup for ChatP&ID (CPID-15).

Library modules only create a module logger (`logging.getLogger(__name__)`). Entry points (the API, and
scripts that want log output) call `configure_logging()` once. The level comes from `CHATPID_LOG_LEVEL`
(default INFO). At INFO the code logs events and identifiers (tool names, document ids, counts, timings),
never secrets, full prompts, questions or answers; raw Cypher and per-node detail are DEBUG only.
"""

from __future__ import annotations

import logging
import os

LOG_LEVEL_ENV = "CHATPID_LOG_LEVEL"
DEFAULT_LEVEL = logging.INFO
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"

_HANDLER_NAME = "chatpid-stderr"


def resolve_level(value: str | None) -> int:
    """Map a level name (case-insensitive) to a logging level; anything unknown falls back to INFO."""
    name = (value or "").strip().upper()
    if not name:
        return DEFAULT_LEVEL
    level = logging.getLevelNamesMapping().get(name)
    return level if isinstance(level, int) else DEFAULT_LEVEL


def configure_logging() -> int:
    """Set the `chatpid` logger level from the environment and make sure it has one stderr handler.

    Idempotent. Returns the effective level. If the root logger already has handlers (the application
    configured logging itself), no extra handler is added.
    """
    raw = os.environ.get(LOG_LEVEL_ENV)
    level = resolve_level(raw)
    package_logger = logging.getLogger("chatpid")
    package_logger.setLevel(level)

    has_ours = any(h.get_name() == _HANDLER_NAME for h in package_logger.handlers)
    if not has_ours and not logging.getLogger().handlers:
        handler = logging.StreamHandler()
        handler.set_name(_HANDLER_NAME)
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        package_logger.addHandler(handler)

    if (
        raw
        and raw.strip()
        and raw.strip().upper() not in logging.getLevelNamesMapping()
    ):
        package_logger.warning(
            "Unknown %s value %r, using %s",
            LOG_LEVEL_ENV,
            raw,
            logging.getLevelName(DEFAULT_LEVEL),
        )
    return level
