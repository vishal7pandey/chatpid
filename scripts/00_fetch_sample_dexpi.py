"""Fetch the DEXPI reference P&ID used by pyDEXPI and by the ChatP&ID paper's
own case study (Section 4.1: "the DEXPIEX01.xml from Theissen and Wiedau, 2021").

Source: process-intelligence-research/pyDEXPI, data/C01V04-VER.EX01.xml
(c) DEXPI e.V. - not redistributed in this repo, fetched on demand instead.

Usage:
    uv run python scripts/00_fetch_sample_dexpi.py
"""

from __future__ import annotations

import urllib.request
from pathlib import Path

RAW_URL = (
    "https://raw.githubusercontent.com/process-intelligence-research/"
    "pyDEXPI/master/data/C01V04-VER.EX01.xml"
)
DEST = Path(__file__).resolve().parent.parent / "data" / "raw" / "C01V04-VER.EX01.xml"


def main() -> None:
    DEST.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {RAW_URL}\n         -> {DEST}")
    urllib.request.urlretrieve(RAW_URL, DEST)
    print("Done.")


if __name__ == "__main__":
    main()
