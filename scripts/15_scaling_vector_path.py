"""Scaling benchmark for VectorRAG and PathRAG on dense 3x/5x graphs.

Tests how VectorRAG and PathRAG scale with graph size, compared to ContextRAG.
Uses the direct LLM pipeline (no ReAct agent) for cost efficiency and
isolation of individual tool performance.

For each graph size (1x, 3x, 5x) and each tool (ContextRAG, VectorRAG, PathRAG):
  1. Retrieve context using the tool
  2. Feed context + question to LLM
  3. Measure tokens, cost, latency, and answer quality

Usage:
    uv run python scripts/15_scaling_vector_path.py
    uv run python scripts/15_scaling_vector_path.py --limit 5  # quick test
    uv run python scripts/15_scaling_vector_path.py --tool vectorrag --level dense_3x_conceptual
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
from chatpid.path_rag import path_rag_text
from chatpid.vector_rag import vector_rag_text

RESULTS_DIR = Path(__file__).resolve().parent.parent / "data"

# (label, neo4j level name)
LEVELS = [
    ("1x", "conceptual"),
    ("3x", "dense_3x_conceptual"),
    ("5x", "dense_5x_conceptual"),
]

TOOLS = ["contextrag", "vectorrag", "pathrag"]

ANSWER_PROMPT = """\
You are ChatP&ID, answering a question about a P&ID using graph retrieval context.

Question: {question}

Retrieved context (from {tool_name} on {graph_size} graph):
{context}

Answer the question using ONLY the context above. Be concise and cite the \
specific tags/equipment names your answer is grounded in. If the context \
does not contain the answer, say so.
"""


def retrieve_context(
    driver,
    tool: str,
    question: str,
    level: str,
) -> tuple[str, int]:
    """Retrieve context using the specified tool. Returns (context_text, approx_tokens)."""
    if tool == "contextrag":
        ctx = context_rag(driver, level=level, mode="graph")
    elif tool == "vectorrag":
        ctx = vector_rag_text(driver, question, index="global_semantic_index", top_k=5, level=level)
    elif tool == "pathrag":
        ctx = path_rag_text(driver, question, level=level, max_depth=3, max_breadth=2)
    else:
        raise ValueError(f"Unknown tool: {tool}")
    return ctx, len(ctx) // 4  # rough token estimate


def run_benchmark(
    driver,
    tool: str,
    level_name: str,
    graph_label: str,
    questions: list[dict],
    delay: float,
) -> list[dict]:
    """Run benchmark for one tool on one graph level."""
    llm = get_llm(temperature=0)
    results = []

    for q in questions:
        print(f"  [Q{q['id']:02d}] {q['question'][:50]}...", end=" ", flush=True)
        try:
            # Step 1: Retrieve context
            t0 = time.time()
            context, ctx_tokens = retrieve_context(driver, tool, q["question"], level_name)
            retrieve_time = time.time() - t0

            # Step 2: Generate answer
            prompt = ANSWER_PROMPT.format(
                question=q["question"],
                tool_name=tool,
                graph_size=graph_label,
                context=context,
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
            cost = estimate_cost("gpt-4o-mini", pt, ct)

            results.append({
                "id": q["id"],
                "category": q["category"],
                "question": q["question"],
                "reference_answer": q["reference_answer"],
                "agent_answer": answer,
                "tool": tool,
                "level": level_name,
                "graph_size": graph_label,
                "context_tokens": ctx_tokens,
                "tokens": {"prompt_tokens": pt, "completion_tokens": ct, "total_tokens": tt},
                "cost_usd": round(cost, 6),
                "latency_seconds": round(answer_time, 2),
                "retrieve_seconds": round(retrieve_time, 2),
            })
            print(f"{tt} tok, ${cost:.6f}, {answer_time:.1f}s")
        except Exception as exc:
            results.append({
                "id": q["id"],
                "category": q["category"],
                "question": q["question"],
                "reference_answer": q["reference_answer"],
                "agent_answer": f"ERROR: {exc!s:.200}",
                "tool": tool,
                "level": level_name,
                "graph_size": graph_label,
                "context_tokens": 0,
                "tokens": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                "cost_usd": 0.0,
                "latency_seconds": 0.0,
                "retrieve_seconds": 0.0,
                "error": str(exc),
            })
            print(f"ERROR: {exc!s:.100}")

        if delay > 0:
            time.sleep(delay)

    return results


def print_comparison_table(all_results: dict) -> None:
    """Print a comparison table across tools and graph sizes."""
    print(f"\n{'='*90}")
    print("SCALING COMPARISON: VectorRAG vs PathRAG vs ContextRAG")
    print(f"{'='*90}")
    print(f"{'Tool':<14} {'Graph':<6} {'Total Cost':>12} {'Cost/Q':>10} {'Tokens/Q':>10} {'Latency/Q':>10} {'Ctx Tokens':>12}")
    print("-" * 90)

    for tool in TOOLS:
        for label, _ in LEVELS:
            key = f"{tool}_{label}"
            if key not in all_results:
                continue
            results = all_results[key]
            n = len(results)
            if n == 0:
                continue
            total_cost = sum(r["cost_usd"] for r in results)
            total_tokens = sum(r["tokens"]["total_tokens"] for r in results)
            avg_latency = sum(r["latency_seconds"] for r in results) / n
            avg_ctx = sum(r["context_tokens"] for r in results) / n
            errors = sum(1 for r in results if r.get("error"))
            err_str = f" ({errors} err)" if errors else ""
            print(
                f"{tool:<14} {label:<6} ${total_cost:>10.4f} ${total_cost/n:>8.6f} "
                f"{total_tokens/n:>9,.0f} {avg_latency:>8.1f}s {avg_ctx:>10,.0f}{err_str}"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None, help="Run only first N questions")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between questions (s)")
    parser.add_argument("--tool", choices=TOOLS, help="Run only one tool")
    parser.add_argument("--level", help="Run only one graph level (e.g. dense_3x_conceptual)")
    args = parser.parse_args()

    questions = BENCHMARK_QUESTIONS[:args.limit] if args.limit else BENCHMARK_QUESTIONS
    tools = [args.tool] if args.tool else TOOLS
    levels = [(l, n) for l, n in LEVELS if not args.level or n == args.level]

    driver = get_driver()
    all_results = {}

    try:
        for tool in tools:
            for label, level_name in levels:
                print(f"\n{'='*60}")
                print(f"Tool: {tool} | Graph: {label} ({level_name})")
                print(f"{'='*60}")
                results = run_benchmark(driver, tool, level_name, label, questions, args.delay)
                all_results[f"{tool}_{label}"] = results

                n = len(results)
                total_cost = sum(r["cost_usd"] for r in results)
                total_tokens = sum(r["tokens"]["total_tokens"] for r in results)
                print(f"\n  Summary: {n} Qs, ${total_cost:.4f}, {total_tokens:,} tokens")
    finally:
        driver.close()

    print_comparison_table(all_results)

    # Save results
    RESULTS_DIR.mkdir(exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    outpath = RESULTS_DIR / f"scaling_vector_path_{timestamp}.json"
    outpath.write_text(json.dumps(all_results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nResults saved to: {outpath}")


if __name__ == "__main__":
    main()
