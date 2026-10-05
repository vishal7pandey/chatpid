"""Scaling benchmark — run the 19 questions on 1x, 3x, and 5x graph sizes.

Tests the paper's biggest caveat (Section 6: "the scaling problem is real").
Uses the direct LLM pipeline (no ReAct agent) for cost efficiency.

Usage:
    uv run python scripts/13_scaling_benchmark.py
    uv run python scripts/13_scaling_benchmark.py --limit 5  # quick test
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

LEVELS = [
    ("1x (36 nodes)", "conceptual"),
    ("3x (108 nodes)", "dense_3x_conceptual"),
    ("5x (180 nodes)", "dense_5x_conceptual"),
]

SYSTEM_PROMPT = """\
You are ChatP&ID, an assistant that answers questions about a Piping and \
Instrumentation Diagram (P&ID) using a knowledge graph context.

Below is the graph context from the P&ID knowledge graph. Use ONLY this \
context to answer the question. Be concise and cite the specific tags/ \
equipment names your answer is grounded in. If the context does not contain \
the answer, say so.

{graph_context}
"""


def run_benchmark_for_level(level_name: str, limit: int | None, delay: float) -> list[dict]:
    driver = get_driver()
    llm = get_llm(temperature=0)
    results = []
    questions = BENCHMARK_QUESTIONS[:limit] if limit else BENCHMARK_QUESTIONS

    graph_context = context_rag(driver, level=level_name, mode="graph")
    print(f"ContextRAG: {len(graph_context)} chars (~{len(graph_context)//4} tokens)")

    try:
        for q in questions:
            print(f"  [{q['id']}/19] {q['question'][:60]}...", end=" ", flush=True)
            try:
                messages = [
                    SystemMessage(content=SYSTEM_PROMPT.format(graph_context=graph_context)),
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
                    "id": q["id"], "category": q["category"], "question": q["question"],
                    "reference_answer": q["reference_answer"], "agent_answer": answer,
                    "level": level_name, "tokens": {"prompt_tokens": pt, "completion_tokens": ct, "total_tokens": tt},
                    "cost_usd": round(cost, 6), "latency_seconds": round(elapsed, 2),
                })
                print(f"{tt} tok, ${cost:.6f}, {elapsed:.1f}s")
            except Exception as exc:
                results.append({
                    "id": q["id"], "category": q["category"], "question": q["question"],
                    "reference_answer": q["reference_answer"], "agent_answer": f"ERROR: {exc!s:.200}",
                    "level": level_name, "tokens": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                    "cost_usd": 0.0, "latency_seconds": 0.0, "error": str(exc),
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
    parser.add_argument("--delay", type=float, default=0.5)
    args = parser.parse_args()

    all_results = {}
    for label, level_name in LEVELS:
        print(f"\n{'='*60}")
        print(f"Scaling benchmark: {label} (level={level_name})")
        print(f"{'='*60}")
        results = run_benchmark_for_level(level_name, args.limit, args.delay)
        all_results[label] = results

        total_cost = sum(r["cost_usd"] for r in results)
        total_tokens = sum(r["tokens"]["total_tokens"] for r in results)
        n = len(results)
        print(f"\n  Summary: {n} Qs, ${total_cost:.4f}, {total_tokens:,} tokens, ${total_cost/n:.6f}/Q")

    # Comparison table
    print(f"\n{'='*60}")
    print("SCALING COMPARISON TABLE")
    print(f"{'='*60}")
    print(f"{'Graph Size':<20} {'Total Cost':>12} {'Avg Cost/Q':>12} {'Avg Tokens/Q':>14} {'Avg Latency':>12}")
    print("-" * 72)

    for label, _ in LEVELS:
        results = all_results[label]
        total_cost = sum(r["cost_usd"] for r in results)
        total_tokens = sum(r["tokens"]["total_tokens"] for r in results)
        avg_latency = sum(r["latency_seconds"] for r in results) / len(results)
        n = len(results)
        print(f"{label:<20} ${total_cost:>10.4f} ${total_cost/n:>10.6f} {total_tokens/n:>13,.0f} {avg_latency:>10.1f}s")

    RESULTS_DIR.mkdir(exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    outpath = RESULTS_DIR / f"scaling_benchmark_{timestamp}.json"
    outpath.write_text(json.dumps(all_results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nResults saved to: {outpath}")


if __name__ == "__main__":
    main()
