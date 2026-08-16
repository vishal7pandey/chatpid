"""Direct LLM + ContextRAG pipeline (no ReAct agent overhead).

The ReAct agent adds ~8K tokens of overhead per question (tool schemas,
multi-turn conversation, tool call/result wrapping). For ContextRAG-only
questions, we can bypass the agent and send the graph context directly to
the LLM in a single call. This cuts token usage from ~12K to ~3K per question,
which fits within Groq's free-tier rate limits.

Usage:
    uv run python scripts/06_direct_benchmark.py
    uv run python scripts/06_direct_benchmark.py --level conceptual --limit 5
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from neo4j import Driver

from chatpid.benchmark import BENCHMARK_QUESTIONS
from chatpid.config import get_settings
from chatpid.context_rag import context_rag
from chatpid.ingest import get_driver

RESULTS_DIR = Path(__file__).resolve().parent.parent / "data"

# Groq pricing (per 1M tokens)
GROQ_PRICING = {
    "llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79},
    "llama-3.1-8b-instant": {"input": 0.05, "output": 0.08},
    "openai/gpt-oss-120b": {"input": 0.59, "output": 0.79},
    "openai/gpt-oss-20b": {"input": 0.05, "output": 0.08},
}

DIRECT_SYSTEM_PROMPT = """\
You are ChatP&ID, an assistant that answers questions about a Piping and \
Instrumentation Diagram (P&ID) using a knowledge graph context.

Below is the complete graph context from the P&ID knowledge graph. \
Answer the user's question using ONLY this context. Be concise and cite \
the specific tags/equipment names your answer is grounded in.

Graph context:
"""


def run_direct_benchmark(
    level: str = "conceptual",
    limit: int | None = None,
    delay: float = 5.0,
    skip_ids: list[int] | None = None,
    model: str | None = None,
) -> list[dict]:
    """Run the benchmark with direct LLM + ContextRAG (no agent overhead)."""
    settings = get_settings()
    chat_model = model or settings.chat_model
    driver = get_driver()
    results = []
    skip = set(skip_ids or [])

    questions = BENCHMARK_QUESTIONS[:limit] if limit else BENCHMARK_QUESTIONS

    # Get ContextRAG output once (same graph for all questions)
    graph_context = context_rag(driver, level=level, mode="graph")
    print(f"ContextRAG output: {len(graph_context)} chars (~{len(graph_context)//4} tokens)")

    llm = ChatOpenAI(
        model=chat_model,
        temperature=0,
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
    )

    try:
        for q in questions:
            if q["id"] in skip:
                print(f"\n[{q['id']}/19] SKIP (already completed)")
                continue

            print(f"\n[{q['id']}/19] ({q['category']}) {q['question'][:80]}...")

            try:
                messages = [
                    SystemMessage(content=DIRECT_SYSTEM_PROMPT + graph_context),
                    HumanMessage(content=q["question"]),
                ]

                start = time.time()
                response = llm.invoke(messages)
                elapsed = time.time() - start

                answer = response.content
                # Extract token usage
                usage_meta = getattr(response, "usage_metadata", None) or {}
                prompt_tokens = usage_meta.get("input_tokens", 0)
                completion_tokens = usage_meta.get("output_tokens", 0)
                total_tokens = usage_meta.get("total_tokens", 0)

                pricing = GROQ_PRICING.get(chat_model, {"input": 0.59, "output": 0.79})
                cost = (prompt_tokens / 1_000_000 * pricing["input"]) + (
                    completion_tokens / 1_000_000 * pricing["output"]
                )

                entry = {
                    "id": q["id"],
                    "category": q["category"],
                    "question": q["question"],
                    "reference_answer": q["reference_answer"],
                    "agent_answer": answer,
                    "model": chat_model,
                    "level": level,
                    "mode": "direct",
                    "tokens": {
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": total_tokens,
                    },
                    "cost_usd": round(cost, 6),
                    "latency_seconds": round(elapsed, 2),
                }
                results.append(entry)
                print(f"  Answer: {answer[:120]}...")
                print(f"  Tokens: {total_tokens} | Cost: ${cost:.6f} | Time: {elapsed:.1f}s")
            except Exception as exc:
                entry = {
                    "id": q["id"],
                    "category": q["category"],
                    "question": q["question"],
                    "reference_answer": q["reference_answer"],
                    "agent_answer": f"ERROR: {type(exc).__name__}: {exc!s:.200}",
                    "model": chat_model,
                    "level": level,
                    "mode": "direct",
                    "tokens": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                    "cost_usd": 0.0,
                    "latency_seconds": 0.0,
                    "error": str(exc),
                }
                results.append(entry)
                print(f"  ERROR: {exc!s:.200}")
                if "rate_limit" in str(exc).lower() or "429" in str(exc) or "413" in str(exc):
                    print("  Rate limit hit — stopping. Partial results saved.")
                    break

            if delay > 0:
                time.sleep(delay)
    finally:
        driver.close()

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--level",
        default="conceptual",
        choices=["complete", "process", "conceptual"],
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--delay", type=float, default=5.0)
    parser.add_argument("--model", default=None, help="Override chat model from .env")
    parser.add_argument("--resume", default=None, help="Resume from previous results JSON")
    args = parser.parse_args()

    previous_results = []
    skip_ids = []
    if args.resume:
        resume_path = Path(args.resume)
        if resume_path.exists():
            previous_results = json.loads(resume_path.read_text(encoding="utf-8"))
            skip_ids = [
                r["id"] for r in previous_results if not r.get("agent_answer", "").startswith("ERROR")
            ]
            print(f"Resuming: {len(skip_ids)} completed, {19 - len(skip_ids)} remaining")

    print(f"Direct benchmark: level={args.level}, delay={args.delay}s")
    new_results = run_direct_benchmark(
        level=args.level, limit=args.limit, delay=args.delay,
        skip_ids=skip_ids, model=args.model,
    )

    all_results = previous_results + new_results
    seen = {}
    for r in all_results:
        seen[r["id"]] = r
    merged = sorted(seen.values(), key=lambda r: r["id"])

    # Summary
    valid = [r for r in merged if not r.get("agent_answer", "").startswith("ERROR")]
    total_cost = sum(r["cost_usd"] for r in valid)
    total_tokens = sum(r["tokens"]["total_tokens"] for r in valid)
    print(f"\n{'='*60}")
    print(f"DIRECT BENCHMARK SUMMARY ({len(valid)}/{len(merged)} questions completed)")
    print(f"  Total cost: ${total_cost:.4f}")
    print(f"  Total tokens: {total_tokens:,}")
    if valid:
        print(f"  Avg cost/question: ${total_cost/len(valid):.6f}")
        print(f"  Avg tokens/question: {total_tokens/len(valid):,.0f}")

    RESULTS_DIR.mkdir(exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    outpath = RESULTS_DIR / f"direct_benchmark_{args.level}_{timestamp}.json"
    outpath.write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  Results saved to: {outpath}")


if __name__ == "__main__":
    main()
