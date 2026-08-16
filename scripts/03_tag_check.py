"""Quick check: tagName/positionNumber coverage and labels string format."""
from __future__ import annotations
from pathlib import Path
from chatpid.ingest import build_graph_abstractions, load_dexpi_model

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

def main():
    model = load_dexpi_model(DATA_DIR, "C01V04-VER.EX01.xml")
    graphs = build_graph_abstractions(model)

    for level_name in ("complete", "process", "conceptual"):
        graph = getattr(graphs, level_name)
        n = graph.number_of_nodes()
        has_tag = sum(1 for _, d in graph.nodes(data=True) if d.get("tagName"))
        has_pos = sum(1 for _, d in graph.nodes(data=True) if d.get("positionNumber"))
        has_label = sum(1 for _, d in graph.nodes(data=True) if d.get("label"))
        print(f"\n{level_name} ({n} nodes):")
        print(f"  tagName:       {has_tag}/{n}")
        print(f"  positionNumber: {has_pos}/{n}")
        print(f"  label (singular): {has_label}/{n}")

        # Show what 'labels' actually looks like (string vs list)
        for i, (nid, d) in enumerate(graph.nodes(data=True)):
            if i >= 3:
                break
            labels_val = d.get("labels")
            print(f"  labels type={type(labels_val).__name__}, value={str(labels_val)[:100]}")
            tag_val = d.get("tagName")
            pos_val = d.get("positionNumber")
            label_val = d.get("label")
            print(f"    tagName={tag_val}, positionNumber={pos_val}, label={label_val}")

        # Show nodes that have tagName (the ones we care about for ContextRAG)
        print(f"  Nodes with tagName:")
        for nid, d in graph.nodes(data=True):
            tag = d.get("tagName")
            if tag:
                print(f"    {tag} (label={d.get('label')})")

if __name__ == "__main__":
    main()
