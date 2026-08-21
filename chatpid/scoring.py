"""Eval harness: LLM-as-judge + semantic similarity scoring (Section 4.3 of the paper).

The paper scores answers on four dimensions via an LLM judge:
  - completeness: does the answer cover all aspects of the question?
  - coherence: is the answer well-structured and logically consistent?
  - correctness: is the answer factually correct based on the reference?
  - relatedness: is the answer relevant to the question asked?

It also tracks semantic similarity separately, since the paper found these
disagree specifically on short factual answers (graph-query questions).

This module implements both scoring mechanisms and a combined report.
"""

from __future__ import annotations

import json
from pathlib import Path

from chatpid.llm import get_llm

# --- LLM-as-judge scoring ---

JUDGE_PROMPT = """\
You are an expert judge evaluating answers about a Piping and Instrumentation \
Diagram (P&ID). Score the agent's answer on four dimensions, each 1-5:

1. Completeness: Does the answer cover all aspects of the question?
2. Coherence: Is the answer well-structured and logically consistent?
3. Correctness: Is the answer factually correct based on the reference answer?
4. Relatedness: Is the answer relevant to the question asked?

Question: {question}

Reference answer: {reference}

Agent's answer: {agent}

Respond in this exact format (JSON, no markdown):
{{"completeness": <1-5>, "coherence": <1-5>, "correctness": <1-5>, "relatedness": <1-5>, "verdict": "correct"|"partially_correct"|"incorrect", "explanation": "<one sentence>"}}
"""


def llm_judge_score(question: str, reference_answer: str, agent_answer: str) -> dict:
    """Score an answer using the LLM as a judge.

    Returns dict with completeness, coherence, correctness, relatedness (1-5),
    verdict (correct/partially_correct/incorrect), and explanation.
    """
    prompt = JUDGE_PROMPT.format(
        question=question,
        reference=reference_answer,
        agent=agent_answer,
    )
    llm = get_llm(temperature=0)
    response = llm.invoke(prompt).content.strip()

    # Strip markdown fences if present
    if response.startswith("```"):
        lines = response.split("\n")
        response = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])

    try:
        scores = json.loads(response)
    except json.JSONDecodeError:
        # Fallback: try to extract JSON from the response
        import re
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if match:
            try:
                scores = json.loads(match.group())
            except json.JSONDecodeError:
                scores = {
                    "completeness": 0, "coherence": 0, "correctness": 0,
                    "relatedness": 0, "verdict": "incorrect",
                    "explanation": f"Failed to parse judge response: {response[:200]}",
                }
        else:
            scores = {
                "completeness": 0, "coherence": 0, "correctness": 0,
                "relatedness": 0, "verdict": "incorrect",
                "explanation": f"Failed to parse judge response: {response[:200]}",
            }

    return scores


# --- Semantic similarity scoring ---

_semantic_model = None


def _get_semantic_model():
    """Lazy-load the sentence-transformers model."""
    global _semantic_model
    if _semantic_model is None:
        from sentence_transformers import SentenceTransformer
        _semantic_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _semantic_model


def semantic_similarity(reference_answer: str, agent_answer: str) -> float:
    """Compute cosine similarity between reference and agent answer embeddings.

    Returns a float between 0 and 1.
    """
    import numpy as np

    model = _get_semantic_model()
    embeddings = model.encode([reference_answer, agent_answer])
    ref_emb = embeddings[0]
    agent_emb = embeddings[1]

    # Cosine similarity
    dot = np.dot(ref_emb, agent_emb)
    norm = np.linalg.norm(ref_emb) * np.linalg.norm(agent_emb)
    if norm == 0:
        return 0.0
    return float(dot / norm)


# --- Combined scoring ---

def score_result(entry: dict) -> dict:
    """Score a single benchmark result entry.

    Adds llm_judge scores and semantic_similarity to the entry.
    """
    question = entry["question"]
    reference = entry["reference_answer"]
    agent_answer = entry["agent_answer"]

    # Skip error entries
    if agent_answer.startswith("ERROR"):
        return {
            **entry,
            "llm_judge": {
                "completeness": 0, "coherence": 0, "correctness": 0,
                "relatedness": 0, "verdict": "incorrect",
                "explanation": "Agent returned an error",
            },
            "semantic_similarity": 0.0,
        }

    judge_scores = llm_judge_score(question, reference, agent_answer)
    sim = semantic_similarity(reference, agent_answer)

    return {
        **entry,
        "llm_judge": judge_scores,
        "semantic_similarity": round(sim, 4),
    }


def score_results(results: list[dict]) -> list[dict]:
    """Score a list of benchmark result entries."""
    scored = []
    for i, entry in enumerate(results):
        print(f"  Scoring Q{entry.get('id', i+1)}...", end=" ", flush=True)
        scored_entry = score_result(entry)
        scored.append(scored_entry)
        verdict = scored_entry["llm_judge"].get("verdict", "?")
        sim = scored_entry.get("semantic_similarity", 0)
        print(f"{verdict} (sim={sim:.3f})")
    return scored


def print_score_summary(scored: list[dict]) -> None:
    """Print a summary of scored results."""
    n = len(scored)
    if n == 0:
        print("No results to summarize.")
        return

    # LLM judge verdicts
    verdicts = [s["llm_judge"]["verdict"] for s in scored]
    correct = verdicts.count("correct")
    partial = verdicts.count("partially_correct")
    incorrect = verdicts.count("incorrect")

    # LLM judge dimension scores
    dims = ["completeness", "coherence", "correctness", "relatedness"]
    avg_dims = {}
    for dim in dims:
        scores = [s["llm_judge"][dim] for s in scored]
        avg_dims[dim] = sum(scores) / n

    # Semantic similarity
    sims = [s.get("semantic_similarity", 0) for s in scored]
    avg_sim = sum(sims) / n

    print(f"\n{'='*60}")
    print(f"EVAL SUMMARY ({n} questions)")
    print(f"  LLM Judge Verdicts:")
    print(f"    Correct:           {correct}/{n} ({correct/n*100:.0f}%)")
    print(f"    Partially Correct: {partial}/{n} ({partial/n*100:.0f}%)")
    print(f"    Incorrect:          {incorrect}/{n} ({incorrect/n*100:.0f}%)")
    print(f"  LLM Judge Dimensions (avg 1-5):")
    for dim in dims:
        print(f"    {dim:20s}: {avg_dims[dim]:.2f}")
    print(f"  Semantic Similarity: {avg_sim:.4f} (avg cosine)")

    # Per-category breakdown
    categories = {}
    for s in scored:
        cat = s.get("category", "unknown")
        if cat not in categories:
            categories[cat] = {"count": 0, "correct": 0, "sim_sum": 0.0}
        categories[cat]["count"] += 1
        categories[cat]["correct"] += 1 if s["llm_judge"]["verdict"] == "correct" else 0
        categories[cat]["sim_sum"] += s.get("semantic_similarity", 0)

    print(f"\n  Per-category:")
    for cat, stats in sorted(categories.items()):
        acc = stats["correct"] / stats["count"] * 100
        avg_cat_sim = stats["sim_sum"] / stats["count"]
        print(f"    {cat:25s}: {stats['correct']}/{stats['count']} ({acc:.0f}%), sim={avg_cat_sim:.3f}")

    # Disagreements (high semantic similarity but incorrect verdict, or vice versa)
    print(f"\n  Disagreements (sim > 0.7 but verdict != correct, or sim < 0.3 but verdict == correct):")
    disagreements = []
    for s in scored:
        sim = s.get("semantic_similarity", 0)
        verdict = s["llm_judge"]["verdict"]
        if (sim > 0.7 and verdict != "correct") or (sim < 0.3 and verdict == "correct"):
            disagreements.append(s)
    if disagreements:
        for d in disagreements:
            print(f"    Q{d.get('id', '?')}: sim={d.get('semantic_similarity', 0):.3f}, verdict={d['llm_judge']['verdict']}")
    else:
        print(f"    (none)")


def save_scored_results(scored: list[dict], filepath: str | Path) -> None:
    """Save scored results to a JSON file."""
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(scored, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nSaved scored results to {filepath}")


def load_results(filepath: str | Path) -> list[dict]:
    """Load benchmark results from a JSON file."""
    with open(filepath, encoding="utf-8") as f:
        return json.load(f)
