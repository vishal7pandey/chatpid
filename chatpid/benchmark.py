"""Paper's 19-question benchmark (Appendix B of arXiv:2603.22528).

Four task categories:
  - graph_query_single (8): retrieve a specific attribute from one node
  - graph_query_multi  (2): list all of a component type with specifications
  - path_exploration   (5): trace flow paths, identify isolation valves
  - knowledge_inference(3): synthesize safety/control analysis from the graph
  - graph_summarization(1): describe the full process flow narratively

Reference answers are condensed from the paper's Appendix B Table 1.
The full reference answers are long (especially multi-query and inference);
we keep enough detail to judge correctness without reproducing every line.
"""

from __future__ import annotations

BENCHMARK_QUESTIONS = [
    # --- Graph Query (Single) ---
    {
        "id": 1,
        "category": "graph_query_single",
        "question": "What is the cylinder length of tank T4750?",
        "reference_answer": "4.0 m",
    },
    {
        "id": 2,
        "category": "graph_query_single",
        "question": "What is the design heat transfer area of heat exchanger H1007?",
        "reference_answer": "46.8 m²",
    },
    {
        "id": 3,
        "category": "graph_query_single",
        "question": "What is the design pressure of pump P4711?",
        "reference_answer": "10.0 m (pressure head)",
    },
    {
        "id": 4,
        "category": "graph_query_single",
        "question": "What is the design shaft power of pump P4711?",
        "reference_answer": "60.0 kW",
    },
    {
        "id": 5,
        "category": "graph_query_single",
        "question": "What is the design volume flow rate of pump P4712?",
        "reference_answer": "420.0 m³/h",
    },
    {
        "id": 6,
        "category": "graph_query_single",
        "question": "What is the nominal diameter of valve 66KL21?",
        "reference_answer": "DN 80",
    },
    {
        "id": 7,
        "category": "graph_query_single",
        "question": "What is the set pressure of safety valve SV 104.01?",
        "reference_answer": "6.0 bar",
    },
    {
        "id": 8,
        "category": "graph_query_single",
        "question": "What is the upper design temperature of tank T4750?",
        "reference_answer": "100.0 °C",
    },
    # --- Graph Query (Multi) ---
    {
        "id": 9,
        "category": "graph_query_multi",
        "question": "List all valves in the P&ID along with their specification.",
        "reference_answer": (
            "11 valves total: 3 Globe Valves (C1, actuated by HV4750.01/PV4712.02/TV4750.03), "
            "1 Butterfly Valve (66KL21), 1 Swing Check Valve (75SA21/C2), "
            "5 Ball Valves (73KH12, C4/C2/C5/C7/C10), 1 Spring Loaded Globe Safety Valve (SV 104.01). "
            "Key specs: nominal diameters DN 25-80, piping classes 73HG12/75HB13, fluid codes MNb/MNc/QSb."
        ),
    },
    {
        "id": 10,
        "category": "graph_query_multi",
        "question": "List all pipe fittings in the P&ID along with their specification.",
        "reference_answer": (
            "Pipe Reducers (C3, DN50, 73HG12), Pipe Tees (C3/C1/C4/C8/C9, DN25-50, 75HB13), "
            "Blind Flanges (C6/C11, DN25, 75HB13). All fluid code MNc, line 47124/47126."
        ),
    },
    # --- Path Exploration ---
    {
        "id": 11,
        "category": "path_exploration",
        "question": (
            "If heat exchanger H1007 needs maintenance, can flow still reach tank T4750? "
            "Describe the alternative path."
        ),
        "reference_answer": (
            "If H1007 is bypassed, flow can potentially reach T4750 via H1008 (tubular heat exchanger) "
            "if a tie-in point exists on line MNb47123 or via N3 of T4750. However, H1008 controls "
            "tank temperature, so using it as an alternative path is not recommended. "
            "Currently no bypass tie-in exists."
        ),
    },
    {
        "id": 12,
        "category": "path_exploration",
        "question": (
            "If you need to isolate tank T4750 from all upstream equipment, "
            "which valves would you need to close?"
        ),
        "reference_answer": (
            "Shut the main DN80 feed globe valve (HV4750.01). "
            "Close the DN50 globe valve on the recirculation line (PV4712.02)."
        ),
    },
    {
        "id": 13,
        "category": "path_exploration",
        "question": "Trace the flow path from tank T4750 to pump P4712.",
        "reference_answer": (
            "T4750 (Tank) → 66KL21 (Butterfly valve) → 75SA21 (Swing check valve) → "
            "Pipe reducer (DN80 to DN50) → 73KH12 (Ball valve) → P4712 (Reciprocating pump)"
        ),
    },
    {
        "id": 14,
        "category": "path_exploration",
        "question": (
            "Working backwards from tank T4750, what are the two possible inlet paths "
            "and their source equipment?"
        ),
        "reference_answer": (
            "Path 1: T4750 ← Globe Valve (HV4750.01) ← H1007 (Plate Heat Exchanger) ← P4711 (Centrifugal Pump). "
            "Path 2: T4750 ← Globe Valve (TV4712.02/PV4712.02) ← H1008 (Tubular Heat Exchanger)."
        ),
    },
    {
        "id": 15,
        "category": "path_exploration",
        "question": "What is the flow path from pump P4711 to tank T4750?",
        "reference_answer": (
            "P4711 (Centrifugal Pump) → H1007 (Plate Heat Exchanger) → "
            "HV4750.01 (Globe Valve) → T4750 (Tank)"
        ),
    },
    # --- Knowledge Inference ---
    {
        "id": 16,
        "category": "knowledge_inference",
        "question": "Analyze the flowsheet and give recommendations regarding process safety.",
        "reference_answer": (
            "Key findings: (1) Safety valve SV104.01 set at 6.0 bar but T4750 design pressure is "
            "only 0.1/0.05 bar — PSV provides no effective protection. "
            "(2) Missing pressure relief for P4711/P4712/H1007/H1008 (design pressure up to 60 bar). "
            "(3) Fluid codes MNb/MNc/QSb not defined. "
            "(4) Blind flanges without clear isolation points. "
            "(5) TV4750.03 fail-open may be unsafe if fluid is heating."
        ),
    },
    {
        "id": 17,
        "category": "knowledge_inference",
        "question": (
            "List all control valves along with its control philosophy, why and what ifs fail."
        ),
        "reference_answer": (
            "3 control valves: "
            "HV4750.01 (flow control, fail-close — prevents uncontrolled flow into T4750); "
            "PV4712.02 (pressure control via PICSA 4712.02, fail-close — prevents return to T4750, "
            "may increase downstream pressure); "
            "TV4750.03 (temperature control via TICSA 4750.03 for H1008, fail-open — "
            "ensures continuous cooling/heating medium flow, may cause overcooling/overheating)."
        ),
    },
    {
        "id": 18,
        "category": "knowledge_inference",
        "question": (
            "What would be the effect if the heating fluid temperature in Heat Exchanger H1007 "
            "increased from the design temperature to 120°C?"
        ),
        "reference_answer": (
            "H1007 design: 313 kW, 46.8 m², chamber design temp 100°C. "
            "Effects: (1) Increased heat transfer rate, potentially exceeding 313 kW design. "
            "(2) Exceeds chamber design temperature by 20°C — thermal stress and equipment damage risk. "
            "(3) Downstream T4750 affected, TV4750.03 control loop would need to compensate. "
            "(4) TV4750.03 might need to throttle more."
        ),
    },
    # --- Graph Summarization ---
    {
        "id": 19,
        "category": "graph_summarization",
        "question": (
            "Based on the P&ID, make a narrative to describe the process flow from the inlet to "
            "the final outlet, identifying all major equipment, intermediate streams, and control "
            "points in sequence."
        ),
        "reference_answer": (
            "Inlet → P4711 (centrifugal pump) → H1007 (plate heat exchanger) → "
            "HV4750.01 (globe valve, flow control) → T4750 (tank, temp monitored by TICSA4750.03) → "
            "66KL21 (butterfly valve) → 75SA21 (check valve) → pipe reducer DN80→DN50 → "
            "73KH12 (ball valve) → P4712 (reciprocating pump) → tee with SV104.01 (safety valve, 6 bar) → "
            "H1008 (tubular heat exchanger, temp control via TV4750.03) → "
            "PV4712.02 (return to T4750, pressure control via PICSA 4712.02) → outlet. "
            "Three control loops: flow (HV4750.01), pressure (PV4712.02), temperature (TV4750.03)."
        ),
    },
]

assert len(BENCHMARK_QUESTIONS) == 19, f"Expected 19 questions, got {len(BENCHMARK_QUESTIONS)}"
