"""Run the paper's 19-question benchmark against the ChatP&ID agent.

Usage:
    uv run python scripts/04_run_benchmark.py
    uv run python scripts/04_run_benchmark.py --level conceptual --limit 5

Outputs results to data/benchmark_results.json with per-question:
  - agent answer
  - reference answer
  - token usage (prompt/completion/total)
  - cost estimate
  - latency (seconds)

SCRUM-358: hand-run the 19-question benchmark
SCRUM-359: track $ and tokens per question from the first run
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from chatpid.agent import build_agent
from chatpid.benchmark import BENCHMARK_QUESTIONS
from chatpid.ingest import get_driver

RESULTS_DIR = Path(__file__).resolve().parent.parent / "data"

# Google Gemini pricing (per 1M tokens, as of 2025-2026).
# Update these if pricing changes or you switch models.
GEMINI_PRICING = {
    "gemini-2.5-flash": {"input": 0.30, "output": 2.50},  # per 1M tokens
    "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
}


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Estimate USD cost from token counts and model pricing."""
    pricing = GEMINI_PRICING.get(model, {"input": 0.30, "output": 2.50})
    return (prompt_tokens / 1_000_000 * pricing["input"]) + (
        completion_tokens / 1_000_000 * pricing["output"]
    )


def extract_token_usage(result: dict) -> dict:
    """Extract token usage from LangGraph agent result messages."""
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    for msg in result.get("messages", []):
        # LangChain message objects may have usage_metadata
        meta = getattr(msg, "usage_metadata", None)
        if meta:
            usage["prompt_tokens"] += meta.get("input_tokens", 0)
            usage["completion_tokens"] += meta.get("output_tokens", 0)
            usage["total_tokens"] += meta.get("total_tokens", 0)
        # Also check response_metadata for token counts (Google format)
        resp_meta = getattr(msg, "response_metadata", None)
        if resp_meta and "usage_metadata" in resp_meta:
            u = resp_meta["usage_metadata"]
            if "prompt_token_count" in u:
                usage["prompt_tokens"] += u.get("prompt_token_count", 0)
                usage["completion_tokens"] += u.get("candidates_token_count", 0)
                usage["total_tokens"] += u.get("total_token_count", 0)
    return usage


def run_benchmark(level: str = "conceptual", limit: int | None = None) -> list[dict]:
    """Run the benchmark and return per-question results."""
    from chatpid.config import get_settings

    settings = get_settings()
    driver = get_driver()
    results = []

    questions = BENCHMARK_QUESTIONS[:limit] if limit else BENCHMARK_QUESTIONS

    try:
        agent = build_agent(driver)
        for q in questions:
            print(f"\n[{q['id']}/19] ({q['category']}) {q['question'][:80]}...")

            start = time.time()
            result = agent.invoke(
                {"messages": [{"role": "user", "content": q["question"]}]},
                config={"recursion_limit": 10},
            )
            elapsed = time.time() - start

            answer = result["messages"][-1].content
            usage = extract_token_usage(result)
            cost = estimate_cost(settings.chat_model, usage["prompt_tokens"], usage["completion_tokens"])

            entry = {
                "id": q["id"],
                "category": q["category"],
                "question": q["question"],
                "reference_answer": q["reference_answer"],
                "agent_answer": answer,
                "model": settings.chat_model,
                "level": level,
                "tokens": usage,
                "cost_usd": round(cost, 6),
                "latency_seconds": round(elapsed, 2),
            }
            results.append(entry)
            print(f"  Answer: {answer[:120]}...")
            print(f"  Tokens: {usage['total_tokens']} | Cost: ${cost:.6f} | Time: {elapsed:.1f}s")
    finally:
        driver.close()

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--level",
        default="conceptual",
        choices=["complete", "process", "conceptual"],
        help="Graph abstraction level to test (default: conceptual, paper's best)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Run only the first N questions (default: all 19)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output file (default: data/benchmark_results_{level}_{timestamp}.json)",
    )
    args = parser.parse_args()

    print(f"Running benchmark: level={args.level}, model from .env")
    results = run_benchmark(level=args.level, limit=args.limit)

    # Summary
    total_cost = sum(r["cost_usd"] for r in results)
    total_tokens = sum(r["tokens"]["total_tokens"] for r in results)
    avg_latency = sum(r["latency_seconds"] for r in results) / len(results)

    print(f"\n{'='*60}")
    print(f"BENCHMARK SUMMARY ({len(results)} questions)")
    print(f"  Total cost: ${total_cost:.4f}")
    print(f"  Total tokens: {total_tokens:,}")
    print(f"  Avg cost/question: ${total_cost/len(results):.6f}")
    print(f"  Avg tokens/question: {total_tokens/len(results):,.0f}")
    print(f"  Avg latency: {avg_latency:.1f}s")

    # Per-category breakdown
    categories = {}
    for r in results:
        cat = r["category"]
        if cat not in categories:
            categories[cat] = {"count": 0, "cost": 0.0, "tokens": 0}
        categories[cat]["count"] += 1
        categories[cat]["cost"] += r["cost_usd"]
        categories[cat]["tokens"] += r["tokens"]["total_tokens"]

    print(f"\n  Per-category:")
    for cat, stats in sorted(categories.items()):
        print(
            f"    {cat}: {stats['count']} Qs, "
            f"${stats['cost']:.4f} total (${stats['cost']/stats['count']:.6f}/Q), "
            f"{stats['tokens']:,} tokens"
        )

    # Save results
    if args.output:
        outpath = Path(args.output)
    else:
        RESULTS_DIR.mkdir(exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        outpath = RESULTS_DIR / f"benchmark_results_{args.level}_{timestamp}.json"

    outpath.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  Results saved to: {outpath}")


if __name__ == "__main__":
    main()
