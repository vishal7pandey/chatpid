"""Ingest real DEXPI test cases from the TrainingTestCases repository.

Downloads (if not present) and ingests the official DEXPI 1.3 example P&IDs:
  - C01: DEXPI Reference P&ID (already have this one)
  - C02: Process Column (BASF)
  - C03: Piping (Equinor)

Each is loaded into Neo4j with a unique document_id so they coexist
without clobbering each other.

Usage:
    uv run python scripts/25_ingest_real_dexpi.py
"""

import os
import sys
import urllib.request

from chatpid.ingest import build_graph_abstractions, get_driver, load_dexpi_model, load_graph

# DEXPI 1.3 example P&IDs with XML files available
TEST_CASES = [
    {
        "name": "C01V04-VER.EX01",
        "label": "C01 DEXPI Reference P&ID",
        "url": "https://gitlab.com/dexpi/TrainingTestCases/-/raw/master/"
               "dexpi%201.3/example%20pids/C01%20DEXPI%20Reference%20P%26ID/C01V04-VER.EX01.xml",
    },
    {
        "name": "C02V03-VER.EX02",
        "label": "C02 Process Column (BASF)",
        "url": "https://gitlab.com/dexpi/TrainingTestCases/-/raw/master/"
               "dexpi%201.3/example%20pids/C02%20Process%20Column%20(BASF)/C02V03-VER.EX02.xml",
    },
    {
        "name": "C03V04-VER.EX02",
        "label": "C03 Piping (Equinor)",
        "url": "https://gitlab.com/dexpi/TrainingTestCases/-/raw/master/"
               "dexpi%201.3/example%20pids/C03%20Piping%20(Equinor)/C03V04-VER.EX02.xml",
    },
]

DATA_DIR = os.path.join("data", "dexpi_real")


def download_if_missing(tc: dict) -> str:
    """Download the XML file if not already present. Returns the filename."""
    os.makedirs(DATA_DIR, exist_ok=True)
    filename = tc["name"] + ".xml"
    filepath = os.path.join(DATA_DIR, filename)
    if not os.path.isfile(filepath):
        print(f"  Downloading {filename} from GitLab...")
        urllib.request.urlretrieve(tc["url"], filepath)
    return filename


def main():
    driver = get_driver()

    for tc in TEST_CASES:
        print(f"\n--- {tc['label']} ---")
        filename = download_if_missing(tc)
        filepath = os.path.join(DATA_DIR, filename)

        # Use the filename stem as document_id for reproducibility
        document_id = tc["name"].split("-")[0]  # e.g. "C01", "C02", "C03"

        print(f"  Loading {filename}...")
        model = load_dexpi_model(DATA_DIR, filename)

        print(f"  Building graph abstractions...")
        graphs = build_graph_abstractions(model)

        for level in ("complete", "process", "conceptual"):
            g = getattr(graphs, level)
            print(f"  Pushing '{level}' graph ({g.number_of_nodes()} nodes, "
                  f"{g.number_of_edges()} edges) to Neo4j as document_id={document_id}...")
            load_graph(driver, g, level, document_id=document_id)

        print(f"  Done. document_id={document_id}")

    print("\nAll real DEXPI test cases ingested!")
    print("Query with document_id filter: C01, C02, C03")


if __name__ == "__main__":
    main()
