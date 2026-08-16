"""Shared evaluation utilities: run benchmark, track cost/tokens, print summaries.

Used by scripts/04_run_benchmark.py and scripts/05_compare_levels.py.
"""

from __future__ import annotations

import time

from chatpid.agent import build_agent
from chatpid.benchmark import BENCHMARK_QUESTIONS
from chatpid.config import get_settings
from chatpid.ingest import get_driver

# Pricing tables (per 1M tokens). Used for cost estimation.
# Groq: https://groq.com/pricing/
GROQ_PRICING = {
    "llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79},
    "llama-3.1-8b-instant": {"input": 0.05, "output": 0.08},
    "llama-3.1-70b-versatile": {"input": 0.59, "output": 0.79},
    "mixtral-8x7b-32768": {"input": 0.24, "output": 0.24},
    "gemma2-9b-it": {"input": 0.20, "output": 0.20},
    "openai/gpt-oss-20b": {"input": 0.05, "output": 0.08},
    "openai/gpt-oss-120b": {"input": 0.59, "output": 0.79},
}

# Gemini: https://ai.google.dev/pricing
GEMINI_PRICING = {
    "gemini-2.5-flash": {"input": 0.30, "output": 2.50},
    "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
}

# Merge all pricing into one lookup
ALL_PRICING = {**GROQ_PRICING, **GEMINI_PRICING}


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    pricing = ALL_PRICING.get(model, {"input": 0.59, "output": 0.79})
    return (prompt_tokens / 1_000_000 * pricing["input"]) + (
        completion_tokens / 1_000_000 * pricing["output"]
    )


def extract_token_usage(result: dict) -> dict:
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    for msg in result.get("messages", []):
        meta = getattr(msg, "usage_metadata", None)
        if meta:
            usage["prompt_tokens"] += meta.get("input_tokens", 0)
            usage["completion_tokens"] += meta.get("output_tokens", 0)
            usage["total_tokens"] += meta.get("total_tokens", 0)
        resp_meta = getattr(msg, "response_metadata", None)
        if resp_meta and "usage_metadata" in resp_meta:
            u = resp_meta["usage_metadata"]
            if "prompt_token_count" in u:
                usage["prompt_tokens"] += u.get("prompt_token_count", 0)
                usage["completion_tokens"] += u.get("candidates_token_count", 0)
                usage["total_tokens"] += u.get("total_token_count", 0)
    return usage


def run_benchmark(
    level: str = "conceptual",
    limit: int | None = None,
    delay: float = 5.0,
    skip_ids: list[int] | None = None,
) -> list[dict]:
    """Run the benchmark and return per-question results.

    Args:
        level: graph abstraction level to test.
        limit: run only the first N questions.
        delay: seconds to wait between questions (rate-limit protection).
        skip_ids: question IDs to skip (for resuming after a partial run).
    """
    settings = get_settings()
    driver = get_driver()
    results = []
    skip = set(skip_ids or [])

    questions = BENCHMARK_QUESTIONS[:limit] if limit else BENCHMARK_QUESTIONS

    try:
        agent = build_agent(driver)
        for q in questions:
            if q["id"] in skip:
                print(f"\n[{q['id']}/19] SKIP (already completed)")
                continue

            print(f"\n[{q['id']}/19] ({q['category']}) {q['question'][:80]}...")

            try:
                start = time.time()
                result = agent.invoke(
                    {"messages": [{"role": "user", "content": q["question"]}]},
                    config={"recursion_limit": 10},
                )
                elapsed = time.time() - start

                answer = result["messages"][-1].content
                usage = extract_token_usage(result)
                cost = estimate_cost(
                    settings.chat_model,
                    usage["prompt_tokens"],
                    usage["completion_tokens"],
                )

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
            except Exception as exc:
                # Save partial result with error info so we can resume later
                entry = {
                    "id": q["id"],
                    "category": q["category"],
                    "question": q["question"],
                    "reference_answer": q["reference_answer"],
                    "agent_answer": f"ERROR: {type(exc).__name__}: {exc!s:.200}",
                    "model": settings.chat_model,
                    "level": level,
                    "tokens": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                    "cost_usd": 0.0,
                    "latency_seconds": 0.0,
                    "error": str(exc),
                }
                results.append(entry)
                print(f"  ERROR: {exc!s:.200}")
                # If it's a rate limit error, stop trying more questions
                if "rate_limit" in str(exc).lower() or "429" in str(exc):
                    print("  Rate limit hit — stopping. Partial results saved.")
                    break

            # Rate-limit protection: wait between questions
            if delay > 0:
                time.sleep(delay)
    finally:
        driver.close()

    return results


def print_summary(results: list[dict], level: str = "") -> None:
    total_cost = sum(r["cost_usd"] for r in results)
    total_tokens = sum(r["tokens"]["total_tokens"] for r in results)
    avg_latency = sum(r["latency_seconds"] for r in results) / len(results)

    print(f"\n{'='*60}")
    print(f"BENCHMARK SUMMARY ({len(results)} questions, level={level})")
    print(f"  Total cost: ${total_cost:.4f}")
    print(f"  Total tokens: {total_tokens:,}")
    print(f"  Avg cost/question: ${total_cost / len(results):.6f}")
    print(f"  Avg tokens/question: {total_tokens / len(results):,.0f}")
    print(f"  Avg latency: {avg_latency:.1f}s")

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
            f"${stats['cost']:.4f} total (${stats['cost'] / stats['count']:.6f}/Q), "
            f"{stats['tokens']:,} tokens"
        )
