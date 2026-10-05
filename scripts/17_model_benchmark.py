"""Model x Tool accuracy/cost benchmark.

Replicates the paper's Table 3 shape (model x tool grid) using all models
we have API keys for. Tests which model is the best cost/accuracy sweet
spot for this workload.

Models tested:
  - gpt-4o-mini (OpenAI)
  - llama-3.3-70b-versatile (Groq)
  - gemini-2.5-flash (Google)

Tools tested:
  - ContextRAG (full graph as text)
  - VectorRAG (semantic similarity top-k)
  - PathRAG (path traversal)
  - CypherRAG (NL-to-Cypher)

Usage:
    uv run python scripts/17_model_benchmark.py
    uv run python scripts/17_model_benchmark.py --limit 5  # quick test
    uv run python scripts/17_model_benchmark.py --model gpt-4o-mini --tool contextrag
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from chatpid.benchmark import BENCHMARK_QUESTIONS
from chatpid.context_rag import context_rag
from chatpid.cypher_rag import cypher_rag_text
from chatpid.eval import estimate_cost
from chatpid.ingest import get_driver
from chatpid.llm import get_llm
from chatpid.path_rag import path_rag_text
from chatpid.vector_rag import vector_rag_text

RESULTS_DIR = Path(__file__).resolve().parent.parent / "data"

# (label, provider, model)
# Gemini excluded — free tier rate-limited after ~20 calls (429 RESOURCE_EXHAUSTED).
# Re-add when quota resets or paid key is available.
MODELS = [
    ("gpt-4o-mini", "openai", "gpt-4o-mini"),
    ("gpt-oss-120b", "groq", "openai/gpt-oss-120b"),
    ("gpt-oss-20b", "groq", "openai/gpt-oss-20b"),
]

TOOLS = ["contextrag", "vectorrag", "pathrag", "cypherrag"]

LEVEL = "conceptual"

ANSWER_PROMPT = """\
You are ChatP&ID, answering a question about a P&ID using graph retrieval context.

Question: {question}

Retrieved context (from {tool_name}):
{context}

Answer the question using ONLY the context above. Be concise and cite the \
specific tags/equipment names your answer is grounded in. If the context \
does not contain the answer, say so.
"""


def retrieve_context(driver, tool: str, question: str) -> tuple[str, int]:
    """Retrieve context using the specified tool. Returns (context, approx_tokens)."""
    if tool == "contextrag":
        ctx = context_rag(driver, level=LEVEL, mode="graph")
    elif tool == "vectorrag":
        ctx = vector_rag_text(driver, question, index="global_semantic_index", top_k=5, level=LEVEL)
    elif tool == "pathrag":
        ctx = path_rag_text(driver, question, level=LEVEL, max_depth=3, max_breadth=2)
    elif tool == "cypherrag":
        ctx = cypher_rag_text(driver, question, level=LEVEL)
    else:
        raise ValueError(f"Unknown tool: {tool}")
    return ctx, len(ctx) // 4


def run_benchmark(
    driver,
    model_label: str,
    provider: str,
    model: str,
    tool: str,
    questions: list[dict],
    delay: float,
) -> list[dict]:
    """Run benchmark for one model x tool combination."""
    llm = get_llm(temperature=0, provider=provider, model=model)
    results = []

    for q in questions:
        print(f"  [Q{q['id']:02d}] {q['question'][:45]}...", end=" ", flush=True)
        try:
            # Step 1: Retrieve context (always with gpt-4o-mini for fairness)
            t0 = time.time()
            context, ctx_tokens = retrieve_context(driver, tool, q["question"])
            retrieve_time = time.time() - t0

            # Step 2: Generate answer with the target model
            prompt = ANSWER_PROMPT.format(
                question=q["question"], tool_name=tool, context=context,
            )
            messages = [SystemMessage(content="You are ChatP&ID."), HumanMessage(content=prompt)]
            t1 = time.time()
            response = llm.invoke(messages)
            answer_time = time.time() - t1
            answer = response.content

            usage = getattr(response, "usage_metadata", None) or {}
            pt = usage.get("input_tokens", 0)
            ct = usage.get("output_tokens", 0)
            tt = usage.get("total_tokens", 0)
            cost = estimate_cost(model, pt, ct)

            results.append({
                "id": q["id"], "category": q["category"],
                "question": q["question"], "reference_answer": q["reference_answer"],
                "agent_answer": answer,
                "model": model_label, "provider": provider, "tool": tool,
                "tokens": {"prompt_tokens": pt, "completion_tokens": ct, "total_tokens": tt},
                "cost_usd": round(cost, 6),
                "latency_seconds": round(answer_time, 2),
                "retrieve_seconds": round(retrieve_time, 2),
                "context_tokens": ctx_tokens,
            })
            print(f"{tt} tok, ${cost:.6f}, {answer_time:.1f}s")
        except Exception as exc:
            results.append({
                "id": q["id"], "category": q["category"],
                "question": q["question"], "reference_answer": q["reference_answer"],
                "agent_answer": f"ERROR: {exc!s:.200}",
                "model": model_label, "provider": provider, "tool": tool,
                "tokens": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                "cost_usd": 0.0, "latency_seconds": 0.0, "retrieve_seconds": 0.0,
                "context_tokens": 0, "error": str(exc),
            })
            print(f"ERROR: {exc!s:.80}")

        if delay > 0:
            time.sleep(delay)

    return results


def print_grid(all_results: dict) -> None:
    """Print the model x tool comparison grid."""
    print(f"\n{'='*100}")
    print("MODEL x TOOL BENCHMARK GRID")
    print(f"{'='*100}")
    print(f"{'Model':<20} {'Tool':<14} {'Cost/Q':>10} {'Tokens/Q':>10} {'Latency/Q':>10} {'Errors':>7}")
    print("-" * 100)

    for model_label, _, _ in MODELS:
        for tool in TOOLS:
            key = f"{model_label}_{tool}"
            results = all_results.get(key, [])
            if not results:
                continue
            n = len(results)
            total_cost = sum(r["cost_usd"] for r in results)
            total_tokens = sum(r["tokens"]["total_tokens"] for r in results)
            avg_latency = sum(r["latency_seconds"] for r in results) / n
            errors = sum(1 for r in results if r.get("error"))
            print(
                f"{model_label:<20} {tool:<14} "
                f"${total_cost/n:>8.6f} {total_tokens/n:>9,.0f} "
                f"{avg_latency:>8.1f}s {errors:>5}/{n}"
            )
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--model", help="Run only one model (e.g. gpt-4o-mini)")
    parser.add_argument("--tool", choices=TOOLS, help="Run only one tool")
    args = parser.parse_args()

    questions = BENCHMARK_QUESTIONS[:args.limit] if args.limit else BENCHMARK_QUESTIONS
    models = [m for m in MODELS if not args.model or m[0] == args.model]
    tools = [args.tool] if args.tool else TOOLS

    driver = get_driver()
    all_results = {}

    RESULTS_DIR.mkdir(exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    outpath = RESULTS_DIR / f"model_benchmark_{timestamp}.json"

    try:
        for model_label, provider, model in models:
            for tool in tools:
                print(f"\n{'='*60}")
                print(f"Model: {model_label} ({provider}) | Tool: {tool}")
                print(f"{'='*60}")
                results = run_benchmark(
                    driver, model_label, provider, model, tool, questions, args.delay,
                )
                all_results[f"{model_label}_{tool}"] = results

                # Incremental save after each combo
                outpath.write_text(json.dumps(all_results, indent=2, ensure_ascii=False), encoding="utf-8")

                n = len(results)
                total_cost = sum(r["cost_usd"] for r in results)
                total_tokens = sum(r["tokens"]["total_tokens"] for r in results)
                print(f"\n  Summary: {n} Qs, ${total_cost:.4f}, {total_tokens:,} tokens")
    finally:
        driver.close()

    print_grid(all_results)
    print(f"\nResults saved to: {outpath}")


if __name__ == "__main__":
    main()
