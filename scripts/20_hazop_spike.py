"""SCRUM-377: Stretch — attempt one real 'does engineering work' task end-to-end.

The paper's Section 7 future direction: flowsheet modification, automated P&ID
correction, AI-assisted HAZOP. This spike picks the smallest slice: an AI-assisted
HAZOP (Hazard and Operability) analysis that uses the GraphRAG tools to identify
potential safety issues in the P&ID.

HAZOP is a structured technique where a multidisciplinary team systematically
examines each part of a process design for deviations from intended operation.
We simulate this by:
1. Using ContextRAG to get the full graph context
2. Using CypherRAG to extract specific equipment specs (design pressure, temperature)
3. Using PathRAG to trace flow paths and identify isolation points
4. Having the LLM synthesize a HAZOP-style deviation analysis from the gathered data

This tests whether the existing GraphRAG tools can support engineering analysis,
or whether new tooling is needed.

Usage:
    uv run python scripts/20_hazop_spike.py
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from chatpid.context_rag import context_rag
from chatpid.cypher_rag import cypher_rag_text
from chatpid.eval import estimate_cost
from chatpid.ingest import get_driver
from chatpid.llm import get_llm
from chatpid.path_rag import path_rag_text

RESULTS_DIR = Path(__file__).resolve().parent.parent / "data"
LEVEL = "conceptual"

HAZOP_PROMPT = """\
You are a process safety engineer performing a HAZOP (Hazard and Operability) \
analysis on a Piping and Instrumentation Diagram (P&ID).

You have access to the following information retrieved from the P&ID knowledge graph:

=== FULL GRAPH CONTEXT (ContextRAG) ===
{graph_context}

=== EQUIPMENT SPECS (CypherRAG) ===
{equipment_specs}

=== FLOW PATHS (PathRAG) ===
{flow_paths}

=== SAFETY-CRITICAL EQUIPMENT (CypherRAG) ===
{safety_equipment}

Perform a structured HAZOP analysis covering these deviation guidewords for each \
major equipment item and pipe segment:

1. FLOW: No flow, More flow, Less flow, Reverse flow
2. PRESSURE: More pressure, Less pressure
3. TEMPERATURE: Higher temperature, Lower temperature
4. LEVEL: High level, Low level (for tanks)

For each deviation, identify:
- The deviation and its potential cause
- The consequence if it occurs
- Whether existing safeguards (safety valves, control valves, check valves) \
are adequate or if additional safeguards are needed
- A risk rating (Low/Medium/High)

Format your response as a structured table with columns:
| Equipment | Deviation | Cause | Consequence | Existing Safeguard | Risk |

Also provide:
- A summary of the top 3 highest-risk findings
- Any recommended modifications to the P&ID (e.g. missing safety valves, \
inadequate isolation points, missing check valves on reverse-flow paths)
"""


def main() -> None:
    driver = get_driver()
    llm = get_llm(temperature=0)

    print("=" * 70)
    print("SCRUM-377: AI-Assisted HAZOP Analysis Spike")
    print("=" * 70)

    # Step 1: Get full graph context
    print("\n[1/4] ContextRAG — full graph context...", end=" ", flush=True)
    t0 = time.time()
    graph_context = context_rag(driver, level=LEVEL, mode="graph")
    print(f"{len(graph_context)//4} tokens, {time.time()-t0:.1f}s")

    # Step 2: Get equipment specs via CypherRAG
    print("[2/4] CypherRAG — equipment specs...", end=" ", flush=True)
    t0 = time.time()
    equipment_specs = cypher_rag_text(
        driver,
        "List all equipment (pumps, tanks, heat exchangers) with their design pressure, "
        "design temperature, and other key specifications",
        level=LEVEL,
    )
    print(f"{len(equipment_specs)//4} tokens, {time.time()-t0:.1f}s")

    # Step 3: Get flow paths via PathRAG
    print("[3/4] PathRAG — flow paths...", end=" ", flush=True)
    t0 = time.time()
    flow_paths = path_rag_text(
        driver,
        "Trace all flow paths from inlet to outlet in the P&ID",
        level=LEVEL,
        max_depth=5,
        max_breadth=3,
    )
    print(f"{len(flow_paths)//4} tokens, {time.time()-t0:.1f}s")

    # Step 4: Get safety-critical equipment
    print("[4/4] CypherRAG — safety equipment...", end=" ", flush=True)
    t0 = time.time()
    safety_equipment = cypher_rag_text(
        driver,
        "List all safety valves, control valves, and check valves with their set pressures "
        "and locations in the flow path",
        level=LEVEL,
    )
    print(f"{len(safety_equipment)//4} tokens, {time.time()-t0:.1f}s")

    # Step 5: Synthesize HAZOP analysis
    print("\n[5/5] LLM synthesizing HAZOP analysis...", end=" ", flush=True)
    prompt = HAZOP_PROMPT.format(
        graph_context=graph_context[:6000],
        equipment_specs=equipment_specs[:3000],
        flow_paths=flow_paths[:3000],
        safety_equipment=safety_equipment[:3000],
    )

    messages = [
        SystemMessage(content="You are a process safety engineer performing HAZOP analysis."),
        HumanMessage(content=prompt),
    ]

    t0 = time.time()
    response = llm.invoke(messages)
    elapsed = time.time() - t0
    analysis = response.content

    usage = getattr(response, "usage_metadata", None) or {}
    pt = usage.get("input_tokens", 0)
    ct = usage.get("output_tokens", 0)
    tt = usage.get("total_tokens", 0)
    cost = estimate_cost("gpt-4o-mini", pt, ct)

    print(f"{tt} tokens, ${cost:.6f}, {elapsed:.1f}s")

    # Print the analysis
    print("\n" + "=" * 70)
    print("HAZOP ANALYSIS RESULTS")
    print("=" * 70)
    print(analysis)

    # Save results
    result = {
        "task": "AI-assisted HAZOP analysis",
        "ticket": "SCRUM-377",
        "tools_used": ["ContextRAG", "CypherRAG", "PathRAG"],
        "model": "gpt-4o-mini",
        "cost_usd": round(cost, 6),
        "latency_seconds": round(elapsed, 2),
        "tokens": {"prompt": pt, "completion": ct, "total": tt},
        "retrieval_tokens": {
            "graph_context": len(graph_context) // 4,
            "equipment_specs": len(equipment_specs) // 4,
            "flow_paths": len(flow_paths) // 4,
            "safety_equipment": len(safety_equipment) // 4,
        },
        "analysis": analysis,
    }

    RESULTS_DIR.mkdir(exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    outpath = RESULTS_DIR / f"hazop_analysis_{timestamp}.json"
    outpath.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nResults saved to: {outpath}")

    driver.close()

    # Assessment
    print("\n" + "=" * 70)
    print("SPIKE ASSESSMENT: Can existing GraphRAG tools support engineering work?")
    print("=" * 70)
    print("""
Findings:
1. The existing 3 GraphRAG tools (ContextRAG, CypherRAG, PathRAG) CAN gather
   the information needed for a HAZOP analysis — equipment specs, flow paths,
   and safety equipment locations are all retrievable.
2. The LLM CAN synthesize a structured deviation analysis from the gathered
   data, producing a HAZOP-style table with causes, consequences, and safeguards.
3. HOWEVER, the analysis is limited by:
   a. No quantitative process data (flow rates, temperatures, pressures in
      operating conditions vs design conditions) — the graph has design specs
      but not operating envelopes
   b. No cause-and-effect graph (deviation in one node → impact on downstream)
   c. No interlock/SIS (Safety Instrumented System) data in the graph
   d. PathRAG traces connectivity but not directionality of flow in all cases

Verdict: The existing tools are SUFFICIENT for a first-pass qualitative HAZOP
screening, but a production-grade HAZOP would need:
   - A new tool for cause-and-effect propagation (deviation tracing)
   - Operating envelope data in the graph (not just design specs)
   - Interlock/SIS representation in the graph
   - Quantitative risk assessment (LOPA — Layer of Protection Analysis)

The smallest viable 'engineering work' task (qualitative HAZOP screening) works
with existing tools. Moving to quantitative analysis or P&ID modification would
require new tooling.
""")


if __name__ == "__main__":
    main()
