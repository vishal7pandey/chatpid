"""Compare ContextRAG accuracy/cost across all 3 graph abstraction levels.

The paper's headline claim is "conceptual graph wins on cost and
often accuracy." That was measured on exactly one small P&ID. This script runs
the same 19 questions against complete/process/conceptual levels using the
direct LLM pipeline (no ReAct agent overhead) and prints a comparison table.

Usage:
    uv run python scripts/05_compare_levels.py
    uv run python scripts/05_compare_levels.py --limit 5  # quick test
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from chatpid.eval import estimate_cost
from chatpid.ingest import get_driver
from chatpid.llm import get_llm
from chatpid.benchmark import BENCHMARK_QUESTIONS
from chatpid.context_rag import context_rag
from langchain_core.messages import HumanMessage, SystemMessage

LEVELS = ("complete", "process", "conceptual")
RESULTS_DIR = Path(__file__).resolve().parent.parent / "data"

DIRECT_SYSTEM_PROMPT = """\
You are ChatP&ID, an assistant that answers questions about a Piping and \
Instrumentation Diagram (P&ID) using a knowledge graph context.

Below is the graph context from the P&ID knowledge graph. Use ONLY this \
context to answer the question. Be concise and cite the specific tags/ \
equipment names your answer is grounded in. If the context does not contain \
the answer, say so.

{graph_context}
"""


def run_level_benchmark(level: str, limit: int | None = None, delay: float = 1.0) -> list[dict]:
    """Run direct benchmark for one level."""
    driver = get_driver()
    llm = get_llm(temperature=0)
    results = []
    questions = BENCHMARK_QUESTIONS[:limit] if limit else BENCHMARK_QUESTIONS

    graph_context = context_rag(driver, level=level, mode="graph")
    print(f"ContextRAG output: {len(graph_context)} chars (~{len(graph_context)//4} tokens)")

    try:
        for q in questions:
            print(f"\n  [{q['id']}/19] ({q['category']}) {q['question'][:70]}...")

            try:
                messages = [
                    SystemMessage(content=DIRECT_SYSTEM_PROMPT.format(graph_context=graph_context)),
                    HumanMessage(content=q["question"]),
                ]
                start = time.time()
                response = llm.invoke(messages)
                elapsed = time.time() - start
                answer = response.content

                usage_meta = getattr(response, "usage_metadata", None) or {}
                prompt_tokens = usage_meta.get("input_tokens", 0)
                completion_tokens = usage_meta.get("output_tokens", 0)
                total_tokens = usage_meta.get("total_tokens", 0)
                cost = estimate_cost("gpt-4o-mini", prompt_tokens, completion_tokens)

                entry = {
                    "id": q["id"],
                    "category": q["category"],
                    "question": q["question"],
                    "reference_answer": q["reference_answer"],
                    "agent_answer": answer,
                    "model": "gpt-4o-mini",
                    "level": level,
                    "mode": "direct",
                    "tokens": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens, "total_tokens": total_tokens},
                    "cost_usd": round(cost, 6),
                    "latency_seconds": round(elapsed, 2),
                }
                results.append(entry)
                print(f"    Tokens: {total_tokens} | Cost: ${cost:.6f} | Time: {elapsed:.1f}s")
                print(f"    Answer: {answer[:100]}...")
            except Exception as exc:
                entry = {
                    "id": q["id"], "category": q["category"], "question": q["question"],
                    "reference_answer": q["reference_answer"], "agent_answer": f"ERROR: {exc!s:.200}",
                    "model": "gpt-4o-mini", "level": level, "mode": "direct",
                    "tokens": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                    "cost_usd": 0.0, "latency_seconds": 0.0, "error": str(exc),
                }
                results.append(entry)
                print(f"    ERROR: {exc!s:.200}")
                if "rate_limit" in str(exc).lower() or "429" in str(exc):
                    print("    Rate limit — stopping.")
                    break

            if delay > 0:
                time.sleep(delay)
    finally:
        driver.close()

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None, help="Run only first N questions per level")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between questions (seconds)")
    args = parser.parse_args()

    all_results = {}
    for level in LEVELS:
        print(f"\n{'='*60}")
        print(f"Running benchmark: level={level}")
        print(f"{'='*60}")
        results = run_level_benchmark(level=level, limit=args.limit, delay=args.delay)
        all_results[level] = results

        total_cost = sum(r["cost_usd"] for r in results)
        total_tokens = sum(r["tokens"]["total_tokens"] for r in results)
        n = len(results)
        print(f"\n  Summary ({level}): {n} Qs, ${total_cost:.4f}, {total_tokens:,} tokens, ${total_cost/n:.6f}/Q")

    # Comparison table
    print(f"\n{'='*60}")
    print("LEVEL COMPARISON TABLE")
    print(f"{'='*60}")
    print(f"{'Level':<15} {'Total Cost':>12} {'Avg Cost/Q':>12} {'Avg Tokens/Q':>14} {'Avg Latency':>12}")
    print("-" * 67)

    for level in LEVELS:
        results = all_results[level]
        total_cost = sum(r["cost_usd"] for r in results)
        total_tokens = sum(r["tokens"]["total_tokens"] for r in results)
        avg_latency = sum(r["latency_seconds"] for r in results) / len(results)
        n = len(results)
        print(
            f"{level:<15} "
            f"${total_cost:>10.4f} "
            f"${total_cost / n:>10.6f} "
            f"{total_tokens / n:>13,.0f} "
            f"{avg_latency:>10.1f}s"
        )

    RESULTS_DIR.mkdir(exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    outpath = RESULTS_DIR / f"level_comparison_{timestamp}.json"
    outpath.write_text(json.dumps(all_results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nResults saved to: {outpath}")


if __name__ == "__main__":
    main()
