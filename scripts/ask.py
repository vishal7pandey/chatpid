"""Minimal CLI: ask ChatP&ID a question end-to-end.

Usage:
    uv run python scripts/ask.py "What is the design volume flow rate of pump P4712?"
"""

from __future__ import annotations

import sys

from chatpid.agent import build_agent
from chatpid.ingest import get_driver


def main() -> None:
    if len(sys.argv) < 2:
        print('Usage: python -m chatpid.cli "<question>"')
        raise SystemExit(1)

    question = " ".join(sys.argv[1:])

    driver = get_driver()
    try:
        agent = build_agent(driver)
        result = agent.invoke(
            {"messages": [{"role": "user", "content": question}]},
            config={"recursion_limit": 10},  # bounds the tool-call loop
        )
        print(result["messages"][-1].content)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
