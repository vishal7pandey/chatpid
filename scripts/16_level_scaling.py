"""Level comparison at scale — complete vs process vs conceptual on 1x/3x/5x graphs.

Repeats the conceptual-vs-process-vs-complete comparison on dense graphs
to test whether "conceptual graph wins on cost" generalizes past the paper's
one small benchmark diagram.

Uses ContextRAG (direct LLM pipeline, no ReAct agent) for fair comparison with
the original results.

Usage:
    uv run python scripts/16_level_scaling.py
    uv run python scripts/16_level_scaling.py --limit 5  # quick test
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from chatpid.benchmark import BENCHMARK_QUESTIONS
from chatpid.context_rag import context_rag
from chatpid.eval import estimate_cost
from chatpid.ingest import get_driver
from chatpid.llm import get_llm

RESULTS_DIR = Path(__file__).resolve().parent.parent / "data"

# (label, level_name, expected_nodes)
GRAPHS = [
    ("1x", "conceptual", 36),
    ("1x", "process", 66),
    ("1x", "complete", 212),
    ("3x", "dense_3x_conceptual", 108),
    ("3x", "dense_3x_process", 198),
    ("3x", "dense_3x_complete", 636),
    ("5x", "dense_5x_conceptual", 180),
    ("5x", "dense_5x_process", 330),
    ("5x", "dense_5x_complete", 1060),
]

DIRECT_SYSTEM_PROMPT = """\
You are ChatP&ID, an assistant that answers questions about a Piping and \
Instrumentation Diagram (P&ID) using a knowledge graph context.

Below is the graph context from the P&ID knowledge graph. Use ONLY this \
context to answer the question. Be concise and cite the specific tags/ \
equipment names your answer is grounded in. If the context does not contain \
the answer, say so.

{graph_context}
"""


def run_benchmark(level_name: str, questions: list[dict], delay: float) -> list[dict]:
    """Run direct ContextRAG benchmark for one level."""
    driver = get_driver()
    llm = get_llm(temperature=0)
    results = []

    graph_context = context_rag(driver, level=level_name, mode="graph")
    ctx_tokens = len(graph_context) // 4
    print(f"  ContextRAG: {len(graph_context):,} chars (~{ctx_tokens:,} tokens)")

    try:
        for q in questions:
            print(f"  [Q{q['id']:02d}] {q['question'][:50]}...", end=" ", flush=True)
            try:
                messages = [
                    SystemMessage(content=DIRECT_SYSTEM_PROMPT.format(graph_context=graph_context)),
                    HumanMessage(content=q["question"]),
                ]
                start = time.time()
                response = llm.invoke(messages)
                elapsed = time.time() - start
                answer = response.content

                usage = getattr(response, "usage_metadata", None) or {}
                pt = usage.get("input_tokens", 0)
                ct = usage.get("output_tokens", 0)
                tt = usage.get("total_tokens", 0)
                cost = estimate_cost("gpt-4o-mini", pt, ct)

                results.append({
                    "id": q["id"], "category": q["category"],
                    "question": q["question"], "reference_answer": q["reference_answer"],
                    "agent_answer": answer, "level": level_name,
                    "tokens": {"prompt_tokens": pt, "completion_tokens": ct, "total_tokens": tt},
                    "cost_usd": round(cost, 6), "latency_seconds": round(elapsed, 2),
                    "context_tokens": ctx_tokens,
                })
                print(f"{tt} tok, ${cost:.6f}, {elapsed:.1f}s")
            except Exception as exc:
                results.append({
                    "id": q["id"], "category": q["category"],
                    "question": q["question"], "reference_answer": q["reference_answer"],
                    "agent_answer": f"ERROR: {exc!s:.200}", "level": level_name,
                    "tokens": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                    "cost_usd": 0.0, "latency_seconds": 0.0, "context_tokens": ctx_tokens,
                    "error": str(exc),
                })
                print(f"ERROR: {exc!s:.100}")

            if delay > 0:
                time.sleep(delay)
    finally:
        driver.close()

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--delay", type=float, default=1.0)
    args = parser.parse_args()

    questions = BENCHMARK_QUESTIONS[:args.limit] if args.limit else BENCHMARK_QUESTIONS
    all_results = {}

    for graph_label, level_name, expected_nodes in GRAPHS:
        abstraction = level_name.replace(f"dense_{graph_label.split('x')[0]}x_", "").replace("dense_", "")
        if "dense" not in level_name:
            abstraction = level_name

        print(f"\n{'='*60}")
        print(f"Graph: {graph_label} | Level: {abstraction} ({level_name}, ~{expected_nodes} nodes)")
        print(f"{'='*60}")

        results = run_benchmark(level_name, questions, args.delay)
        all_results[f"{graph_label}_{abstraction}"] = results

        n = len(results)
        total_cost = sum(r["cost_usd"] for r in results)
        total_tokens = sum(r["tokens"]["total_tokens"] for r in results)
        print(f"\n  Summary: {n} Qs, ${total_cost:.4f}, {total_tokens:,} tokens")

    # Comparison table
    print(f"\n{'='*90}")
    print("LEVEL SCALING COMPARISON: Does 'conceptual wins' generalize at scale?")
    print(f"{'='*90}")
    print(f"{'Graph':<6} {'Level':<14} {'Nodes':>7} {'Total Cost':>12} {'Cost/Q':>10} {'Tokens/Q':>10} {'Ctx Tok':>8}")
    print("-" * 90)

    for graph_label, level_name, expected_nodes in GRAPHS:
        abstraction = level_name.replace(f"dense_{graph_label.split('x')[0]}x_", "").replace("dense_", "")
        if "dense" not in level_name:
            abstraction = level_name

        key = f"{graph_label}_{abstraction}"
        results = all_results.get(key, [])
        if not results:
            continue
        n = len(results)
        total_cost = sum(r["cost_usd"] for r in results)
        total_tokens = sum(r["tokens"]["total_tokens"] for r in results)
        ctx_tok = results[0].get("context_tokens", 0)
        errors = sum(1 for r in results if r.get("error"))
        err_str = f" ({errors} err)" if errors else ""
        print(
            f"{graph_label:<6} {abstraction:<14} {expected_nodes:>7} "
            f"${total_cost:>10.4f} ${total_cost/n:>8.6f} "
            f"{total_tokens/n:>9,.0f} {ctx_tok:>7,}{err_str}"
        )

    # Save results
    RESULTS_DIR.mkdir(exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    outpath = RESULTS_DIR / f"level_scaling_{timestamp}.json"
    outpath.write_text(json.dumps(all_results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nResults saved to: {outpath}")


if __name__ == "__main__":
    main()
