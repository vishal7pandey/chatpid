# ChatP&ID — GraphRAG Question Benchmark & Tool Selection Guide

This guide documents the exhaustive set of test questions for ChatP&ID, categorized by their primary GraphRAG tool, intent, expected reasoning path, and abstraction level.

---

## 1. Tool Selection Architecture

ChatP&ID uses a LangGraph ReAct agent that evaluates question intent and selects the optimal GraphRAG tool:

```
                  ┌───────────────── Question Intent ─────────────────┐
                  │                                                   │
      ┌───────────┴───────────┬───────────────────────┼───────────────┴───────────┐
      ▼                       ▼                       ▼                           ▼
[Exact Attribute]     [Multi-Hop Flow]       [Semantic Role]            [Broad Synthesis]
   CypherRAG              PathRAG                VectorRAG                  ContextRAG
```

---

## 2. Exhaustive Question Set by Tool

### A. CypherRAG (Exact Attribute Lookups, Counts, & Filtered Lists)
*Best for: Factual lookups, specific equipment specifications, counting, and grouping components.*

| # | Question | Expected Graph Layer | Why it triggers CypherRAG |
|---|---|---|---|
| 1 | **What is the cylinder length of tank T4750?** | `conceptual` / `complete` | Direct attribute lookup on a specific node (`n.cylinderLength`). |
| 2 | **What is the design heat transfer area of heat exchanger H1007?** | `conceptual` / `complete` | Direct numerical specification lookup (`n.heatTransferArea`). |
| 3 | **What is the design shaft power of pump P4711?** | `conceptual` / `complete` | Specific mechanical attribute lookup (`n.shaftPower`). |
| 4 | **What is the set pressure of safety valve SV 104.01?** | `conceptual` / `complete` | Safety setpoint lookup (`n.setPressure`). |
| 5 | **What type of pump is P4711 vs P4712?** | `conceptual` | Label comparison (`CentrifugalPump` vs `ReciprocatingPump`). |
| 6 | **List all valves in the P&ID along with their types.** | `conceptual` / `process` | Type-filtered aggregation across all valve nodes. |
| 7 | **How many tanks and pumps are present in the plant?** | `conceptual` | Label count aggregation (`MATCH (n:Pump) RETURN count(n)`). |
| 8 | **What is the nominal diameter of valve 66KL21?** | `complete` | Attribute lookup on detailed valve component (`n.nominalDiameter`). |

---

### B. PathRAG (Flow Paths, Multi-Hop Tracing, & Isolation)
*Best for: Tracing connections from source to target, upstream/downstream flow, and finding boundary isolation valves.*

| # | Question | Expected Graph Layer | Why it triggers PathRAG |
|---|---|---|---|
| 9 | **Trace the flow path from tank T4750 to pump P4712.** | `conceptual` / `process` | Multi-hop directed graph traversal across pipeline connections. |
| 10 | **What is the flow path from pump P4711 to tank T4750?** | `conceptual` / `process` | Traces path through heat exchanger `H1007` and control valve `HV4750.01`. |
| 11 | **Working backwards from tank T4750, what are the two possible inlet paths?** | `conceptual` / `process` | Reverse (upstream) traversal to find source equipment. |
| 12 | **If you need to isolate tank T4750 from all upstream equipment, which valves must be closed?** | `conceptual` / `process` | Boundary path traversal identifying all inline isolation/control valves. |
| 13 | **If heat exchanger H1007 is blocked, is there an alternative route to tank T4750?** | `conceptual` / `process` | Path exploration to detect bypasses or secondary headers. |

---

### C. VectorRAG (Semantic Similarity & Functional Discovery)
*Best for: Finding equipment by functional description when the exact tag or standard label is unknown.*

| # | Question | Expected Graph Layer | Why it triggers VectorRAG |
|---|---|---|---|
| 14 | **Find equipment responsible for heating or cooling process fluids.** | `conceptual` | Cosine similarity over semantic descriptions of heat exchangers. |
| 15 | **Which component functions as a primary liquid storage unit?** | `conceptual` | Semantic search resolves functional role to tank `T4750`. |
| 16 | **Find all devices that measure temperature or trigger alarms.** | `conceptual` / `process` | Matches semantic descriptions of sensor & transmitter functions (`TT4750.03`, etc.). |
| 17 | **Which components provide overpressure protection?** | `conceptual` | Matches safety valve semantic embeddings. |

---

### D. ContextRAG (Broad Flowsheet Summaries, HAZOP, & Safety Reviews)
*Best for: High-level narrative summaries, multi-subsystem synthesis, and qualitative safety analysis.*

| # | Question | Expected Graph Layer | Why it triggers ContextRAG |
|---|---|---|---|
| 18 | **Analyze the flowsheet and give recommendations regarding process safety.** | `conceptual` | Full graph topology + specs to detect mismatched design pressures (e.g., PSV set at 6 bar on a 0.1 bar tank). |
| 19 | **Describe the overall process flow in this P&ID from inlet to outlet.** | `conceptual` / `process` | Summarizes entire flowsheet sequentially. |
| 20 | **List all control valves along with their control philosophy, why, and what happens if they fail.** | `conceptual` | Synthesizes multiple instrumentation loops (`HV4750.01`, `PV4712.02`, `TV4750.03`) and fail-action states. |
| 21 | **What would happen if the heating medium temperature in H1007 increased to 120°C?** | `conceptual` | System-wide inference across heat exchanger limits and downstream tanks. |

---

## 3. Multi-P&ID Document Scope

When querying multi-document graphs in Neo4j:

| Document ID | P&ID Title | Industry Source | Typical Test Questions |
|---|---|---|---|
| `C01V04` | DEXPI Reference P&ID | DEXPI e.V. Reference | Questions 1–21 above (Tanks, Pumps, HX, Safety Loops) |
| `C02V03` | Process Column | BASF | *"What type of equipment is K 2750?"*, *"What measurement loops are tied to the column?"* |
| `C03V04` | Piping Flowsheet | Equinor | *"List all flanges and restriction orifices in the Equinor piping diagram."* |
