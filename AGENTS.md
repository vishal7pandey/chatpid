# ChatP&ID — Project Notes

## Neo4j Setup

**Decision:** Neo4j runs via Docker Compose (`docker-compose.yml` in repo root).

**Issue found 2026-08-17:** Docker Desktop was installed but could not run containers because WSL2 had no Linux distribution installed. Docker CLI would hang when contacting the daemon.

**Fix applied:** Ran `wsl --install -d Ubuntu` — installed successfully but **requires a system reboot** to take effect.

### After reboot, to start Neo4j:
```bash
docker compose up -d
```
This brings up Neo4j on:
- Bolt: `bolt://localhost:7687`
- Browser UI: `http://localhost:7474`
- Credentials: `neo4j` / `chatpid_dev_pw` (set in docker-compose.yml)

### If Docker volume is empty (fresh start), re-ingest the P&ID:
```bash
uv run python scripts/01_ingest.py
```
This loads the DEXPI reference P&ID (C01V04-VER.EX01.xml) into Neo4j at all 3 abstraction levels (complete, process, conceptual).

### Dense graphs also need re-loading if wiped:
```bash
uv run python scripts/12_generate_dense_pid.py
```
This creates 3x (108 nodes) and 5x (180 nodes) dense conceptual graphs.

## LLM Provider

Configured via `LLM_PROVIDER` env var in `.env`:
- `openai` (current default, model: `gpt-4o-mini`)
- `groq` (model: `llama-3.3-70b-versatile`)
- `gemini` (model: `gemini-2.5-flash`, free tier quota limited)

## Sprint 4 Status (as of 2026-08-17)

| Ticket | Status | Notes |
|---|---|---|
| SCRUM-370 | Done | All 4 GraphRAG tools wired into agent (done in Sprint 3) |
| SCRUM-397 | Done | CypherRAG retry/fallback with schema hints + ContextRAG fallback (commit b0cf772) |
| SCRUM-371 | Done | Eval harness: LLM-as-judge + semantic similarity (commit 2993b61) |
| SCRUM-372 | Done | Re-ran 19Q benchmark with all fixes. Final: 19/19 completed, 6/19 correct, 8/19 partial, 5/19 incorrect, $0.011 total. See benchmark results below. |
| SCRUM-398 | Done | Scaling benchmark: VectorRAG/PathRAG on 1x/3x/5x graphs. PathRAG scales O(1), VectorRAG O(log n), ContextRAG O(n). |
| SCRUM-374 | Done | Level scaling comparison: complete/process/conceptual x 1x/3x/5x. "Conceptual wins" generalizes — cost ratio stable at ~3.8x across all scales. |
| SCRUM-392 | Done | Scaffolded chatpid/frontend as Next.js 16 app (App Router, React 19, Tailwind 4, lucide-react). Ported ade's semantic design-token system with light/dark themes. Build passes, dev server runs on localhost:3000. |

### SCRUM-374 Level Scaling Results (2026-08-17)

Results file: `data/level_scaling_20260817_165621.json`

| Graph | Level | Nodes | Tokens/Q | Cost/Q | Ctx Tokens |
|---|---|---|---|---|---|
| 1x | conceptual | 36 | 2,731 | $0.000479 | 1,927 |
| 1x | process | 66 | 4,152 | $0.000699 | 2,932 |
| 1x | complete | 212 | 10,192 | $0.001611 | 8,498 |
| 3x | conceptual | 108 | 7,684 | $0.001230 | 5,782 |
| 3x | process | 198 | 11,909 | $0.001865 | 8,797 |
| 3x | complete | 636 | 29,527 | $0.004510 | 25,052 |
| 5x | conceptual | 180 | 12,623 | $0.001972 | 9,637 |
| 5x | process | 330 | 19,666 | $0.003032 | 14,662 |
| 5x | complete | 1060 | 49,038 | $0.007445 | 41,754 |

**Key findings:**
- "Conceptual wins" generalizes — the complete/conceptual cost ratio is consistently ~3.7-3.9x across all graph sizes
- The ratio is STABLE, not growing — abstraction provides a constant multiplicative benefit
- At 5x scale, complete costs $0.14/benchmark vs conceptual $0.04 (3.8x saving)
- All levels scale linearly O(n) with graph size (ContextRAG serializes entire graph)
- Combined with SCRUM-398: PathRAG and VectorRAG scale sub-linearly, making them essential for production-scale P&IDs

### SCRUM-398 Scaling Results (2026-08-17)

Results file: `data/scaling_vector_path_20260817_162523.json`

| Tool | Graph | Cost/Q | Tokens/Q | Ctx Tokens |
|---|---|---|---|---|
| ContextRAG | 1x (36 nodes) | $0.000498 | 2,760 | 1,927 |
| ContextRAG | 3x (108 nodes) | $0.001254 | 7,722 | 5,782 |
| ContextRAG | 5x (180 nodes) | $0.001993 | 12,656 | 9,637 |
| VectorRAG | 1x | $0.000042 | 168 | 25 |
| VectorRAG | 3x | $0.000065 | 276 | 119 |
| VectorRAG | 5x | $0.000079 | 362 | 207 |
| PathRAG | 1x | $0.000167 | 787 | 423 |
| PathRAG | 3x | $0.000160 | 772 | 419 |
| PathRAG | 5x | $0.000160 | 772 | 419 |

**Key findings:**
- **PathRAG scales O(1)** — constant cost/tokens regardless of graph size (traverses fixed depth/breadth)
- **VectorRAG scales sub-linearly** — top-k results are constant, but vector index scan grows slightly
- **ContextRAG scales O(n)** — cost grows linearly with graph size (serializes entire graph)
- At 5x scale, ContextRAG costs 25x more than VectorRAG and 12x more than PathRAG
- This confirms the paper's Section 6 scaling concern and validates targeted retrieval for production

### SCRUM-372 Benchmark Results (2026-08-17)

Final run: `data/benchmark_results_conceptual_20260817_144314.json`
Scored: `data/benchmark_results_conceptual_20260817_144314_scored.json`

| Metric | Value |
|---|---|
| Questions completed | 19/19 (0 errors) |
| Correct | 6/19 (32%) |
| Partially correct | 8/19 (42%) |
| Incorrect | 5/19 (26%) |
| Total cost | $0.011 |
| Avg cost/question | $0.00058 |
| Avg tokens/question | 3,299 |
| Avg latency | 7.6s |

Per-category accuracy:
- graph_query_single: 6/8 (75%) — strong on attribute lookups
- graph_query_multi: 0/2 (0%) — listing questions need improvement
- path_exploration: 0/5 (0%) — PathRAG direction/reasoning issues
- knowledge_inference: 0/3 (0%) — needs better domain understanding
- graph_summarization: 0/1 (0%) — broad narrative needs full graph

Key fixes applied during SCRUM-372:
1. **Agent error handling** — wrapped all tools in `_safe_tool` so exceptions return error strings instead of crashing the agent
2. **PathRAG embedding fix** — filtered out 384-dim float embedding vectors from PathRAG output (was causing 67k token bloat and Q14 context overflow)
3. **Vector indexes created** — ran semantic enrichment + embedding + vector index creation so VectorRAG works
4. **System prompt tuning** — balanced prompt directs path questions to PathRAG (cheaper) while allowing ContextRAG for broad questions
5. **Recursion limit** — increased from 10 to 25 to give agent room to retry with different tools

## Sprint 5 Status (as of 2026-08-17)

| Ticket | Status | Notes |
|---|---|---|
| SCRUM-373 | Done | Model x tool benchmark: 3 models x 4 tools, 228 LLM calls |
| SCRUM-376 | To Do | Multi-agent supervisor spike |

### SCRUM-373 Model x Tool Results (2026-08-17)

Results file: `data/model_benchmark_20260817_181522_scored.json`

Accuracy (correct/19):
| Model | ContextRAG | VectorRAG | PathRAG | CypherRAG |
|---|---|---|---|---|
| gpt-4o-mini | 6/19 | 0/19 | 1/19 | 6/19 |
| gpt-oss-120b | 8/19 | 0/19 | 1/19 | 6/19 |
| gpt-oss-20b | 7/19 | 0/19 | 1/19 | 6/19 |

Cost per question:
| Model | ContextRAG | VectorRAG | PathRAG | CypherRAG |
|---|---|---|---|---|
| gpt-4o-mini | $0.000492 | $0.000037 | $0.000160 | $0.000097 |
| gpt-oss-120b | $0.001916 | $0.000193 | $0.000566 | $0.000249 |
| gpt-oss-20b | $0.000174 | $0.000016 | $0.000046 | $0.000026 |

**Key findings:**
- ContextRAG is the clear accuracy winner across all models (6-8/19 correct)
- CypherRAG matches ContextRAG on specific factual questions but fails on path/flow (6 syntax errors)
- VectorRAG and PathRAG score 0-1/19 standalone — they're retrieval tools meant to feed the agent, not answer directly
- gpt-oss-120b is the accuracy leader (8/19) but costs 4x more than gpt-4o-mini
- gpt-oss-20b is the cost leader ($0.000016/Q) but less accurate
- **gpt-4o-mini remains the best accuracy/cost sweet spot** for ContextRAG
- Gemini excluded — free tier rate-limited after ~20 calls (429 RESOURCE_EXHAUSTED)

Known issues:
- Q6 (nominal diameter of valve 66KL21): data not in conceptual graph, agent loops trying to find it
- Q8 (upper design temperature): data not in conceptual graph
- Q13 (flow path direction): PathRAG returns paths in wrong direction
- Q17 (control valves): agent lists all valves as "control valves" instead of just ActuatingFunction nodes

## Key Commands

```bash
# Run the full agent benchmark (19 questions)
uv run python scripts/04_run_benchmark.py --level conceptual

# Score benchmark results with LLM-as-judge
uv run python scripts/14_score_benchmark.py --latest

# Direct benchmark (no ReAct agent, cheaper)
uv run python scripts/06_direct_benchmark.py

# Scaling benchmark on dense graphs
uv run python scripts/13_scaling_benchmark.py

# Ask a single question interactively
uv run python scripts/ask.py "What is the cylinder length of tank T4750?"
```
