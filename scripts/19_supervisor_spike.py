"""Multi-agent supervisor spike.

Instead of a single ReAct agent sequentially picking one tool, a supervisor
coordinates 4 specialized tool-agents in parallel, then aggregates their
outputs into a final answer. Tests whether parallel specialization actually
helps on questions where the single-agent approach struggled.

Architecture:
  1. Fan-out: Call all 4 GraphRAG tools in parallel (ContextRAG, VectorRAG,
     PathRAG, CypherRAG) — each returns its raw retrieval context.
  2. Supervisor: An LLM sees the question + all 4 tool outputs and synthesizes
     a single answer, citing which tool provided which information.

Compared against the single-agent baseline results.

Usage:
    uv run python scripts/19_supervisor_spike.py
    uv run python scripts/19_supervisor_spike.py --limit 5  # quick test
"""

from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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
LEVEL = "conceptual"

SUPERVISOR_PROMPT = """\
You are ChatP&ID Supervisor, an expert assistant that answers questions about \
a Piping and Instrumentation Diagram (P&ID).

You are coordinating 4 specialized retrieval tools that each returned context \
from the P&ID knowledge graph. Your job is to synthesize the best possible \
answer from ALL of their outputs, citing which tool provided which information.

Tool outputs:
{tool_outputs}

Question: {question}

Instructions:
- Use ONLY the information from the tool outputs above — never guess.
- If multiple tools provide the same information, cite the most specific one.
- If one tool returned an error or empty results, rely on the others.
- If none of the tools provide the answer, say so explicitly.
- Be concise and cite specific tags/equipment names.
"""


def run_all_tools_parallel(driver, question: str) -> dict[str, dict]:
    """Run all 4 GraphRAG tools in parallel. Returns tool_name -> {context, error, elapsed}."""

    def _call_tool(name: str, fn):
        t0 = time.time()
        try:
            ctx = fn()
            return {
                "context": ctx,
                "error": None,
                "elapsed": round(time.time() - t0, 2),
                "tokens": len(ctx) // 4,
            }
        except Exception as e:
            return {
                "context": "",
                "error": str(e)[:200],
                "elapsed": round(time.time() - t0, 2),
                "tokens": 0,
            }

    tools = {
        "ContextRAG": lambda: context_rag(driver, level=LEVEL, mode="graph"),
        "VectorRAG": lambda: vector_rag_text(
            driver, question, index="global_semantic_index", top_k=5, level=LEVEL
        ),
        "PathRAG": lambda: path_rag_text(
            driver, question, level=LEVEL, max_depth=3, max_breadth=2
        ),
        "CypherRAG": lambda: cypher_rag_text(driver, question, level=LEVEL),
    }

    results = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(_call_tool, name, fn): name for name, fn in tools.items()
        }
        for future in as_completed(futures):
            name = futures[future]
            results[name] = future.result()

    return results


def synthesize_answer(llm, question: str, tool_results: dict) -> tuple[str, dict]:
    """Supervisor LLM synthesizes answer from all tool outputs."""
    # Format tool outputs
    tool_parts = []
    for name, result in tool_results.items():
        ctx = result.get("context", "")
        err = result.get("error")
        if err:
            tool_parts.append(f"--- {name} (ERROR: {err}) ---\n[no data]")
        elif ctx:
            tool_parts.append(
                f"--- {name} ({result['tokens']} tokens, {result['elapsed']}s) ---\n{ctx[:8000]}"
            )
        else:
            tool_parts.append(f"--- {name} (empty) ---\n[no data]")

    tool_outputs = "\n\n".join(tool_parts)
    prompt = SUPERVISOR_PROMPT.format(tool_outputs=tool_outputs, question=question)

    messages = [
        SystemMessage(
            content="You are ChatP&ID Supervisor, coordinating multiple retrieval tools."
        ),
        HumanMessage(content=prompt),
    ]

    t0 = time.time()
    response = llm.invoke(messages)
    elapsed = time.time() - t0
    answer = response.content

    usage = getattr(response, "usage_metadata", None) or {}
    pt = usage.get("input_tokens", 0)
    ct = usage.get("output_tokens", 0)
    tt = usage.get("total_tokens", 0)

    return answer, {
        "prompt_tokens": pt,
        "completion_tokens": ct,
        "total_tokens": tt,
        "latency": round(elapsed, 2),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--delay", type=float, default=1.0)
    args = parser.parse_args()

    questions = BENCHMARK_QUESTIONS[: args.limit] if args.limit else BENCHMARK_QUESTIONS
    driver = get_driver()
    llm = get_llm(temperature=0)  # supervisor LLM

    results = []

    try:
        for q in questions:
            print(f"\n[Q{q['id']:02d}] {q['question'][:60]}...")

            # Step 1: Fan-out — run all 4 tools in parallel
            print("  Fanning out 4 tools in parallel...", end=" ", flush=True)
            t0 = time.time()
            tool_results = run_all_tools_parallel(driver, q["question"])
            fanout_time = time.time() - t0

            tool_summary = ", ".join(
                f"{name}: {r['tokens']}tok{'(ERR)' if r['error'] else ''}"
                for name, r in tool_results.items()
            )
            print(f"{fanout_time:.1f}s | {tool_summary}")

            # Step 2: Supervisor synthesizes answer
            print("  Supervisor synthesizing...", end=" ", flush=True)
            answer, usage = synthesize_answer(llm, q["question"], tool_results)
            cost = estimate_cost(
                "gpt-4o-mini", usage["prompt_tokens"], usage["completion_tokens"]
            )

            print(f"{usage['total_tokens']} tok, ${cost:.6f}, {usage['latency']}s")
            print(f"  Answer: {answer[:120]}...")

            entry = {
                "id": q["id"],
                "category": q["category"],
                "question": q["question"],
                "reference_answer": q["reference_answer"],
                "agent_answer": answer,
                "model": "gpt-4o-mini",
                "mode": "supervisor",
                "tokens": {
                    "prompt_tokens": usage["prompt_tokens"],
                    "completion_tokens": usage["completion_tokens"],
                    "total_tokens": usage["total_tokens"],
                },
                "cost_usd": round(cost, 6),
                "latency_seconds": round(fanout_time + usage["latency"], 2),
                "fanout_seconds": round(fanout_time, 2),
                "synthesis_seconds": usage["latency"],
                "tool_results": {
                    name: {
                        "tokens": r["tokens"],
                        "elapsed": r["elapsed"],
                        "error": r["error"],
                    }
                    for name, r in tool_results.items()
                },
            }
            results.append(entry)

            # Incremental save
            RESULTS_DIR.mkdir(exist_ok=True)
            timestamp = "latest"
            outpath = RESULTS_DIR / f"supervisor_benchmark_{timestamp}.json"
            outpath.write_text(
                json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
            )

            if args.delay > 0:
                time.sleep(args.delay)
    finally:
        driver.close()

    # Summary
    print(f"\n{'=' * 70}")
    print("SUPERVISOR SPIKE SUMMARY")
    print(f"{'=' * 70}")
    n = len(results)
    total_cost = sum(r["cost_usd"] for r in results)
    total_tokens = sum(r["tokens"]["total_tokens"] for r in results)
    avg_fanout = sum(r["fanout_seconds"] for r in results) / n
    avg_synth = sum(r["synthesis_seconds"] for r in results) / n
    avg_total = sum(r["latency_seconds"] for r in results) / n

    print(f"  Questions: {n}")
    print(f"  Total cost: ${total_cost:.4f} (${total_cost / n:.6f}/Q)")
    print(f"  Total tokens: {total_tokens:,} ({total_tokens / n:,.0f}/Q)")
    print(f"  Avg fanout time: {avg_fanout:.1f}s")
    print(f"  Avg synthesis time: {avg_synth:.1f}s")
    print(f"  Avg total latency: {avg_total:.1f}s")

    # Tool usage stats
    print("\n  Tool availability (non-error):")
    for tool_name in ["ContextRAG", "VectorRAG", "PathRAG", "CypherRAG"]:
        success = sum(
            1 for r in results if not r["tool_results"].get(tool_name, {}).get("error")
        )
        avg_tok = (
            sum(r["tool_results"].get(tool_name, {}).get("tokens", 0) for r in results)
            / n
        )
        print(f"    {tool_name}: {success}/{n} succeeded, avg {avg_tok:.0f} tokens")

    # Save final
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    outpath = RESULTS_DIR / f"supervisor_benchmark_{timestamp}.json"
    outpath.write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nResults saved to: {outpath}")


if __name__ == "__main__":
    main()
