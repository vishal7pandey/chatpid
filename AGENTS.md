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
| SCRUM-371 | Done | Eval harness: LLM-as-judge + semantic similarity (commit 2993b61). Result: 8/19 correct, 9/19 partial, 2/19 incorrect |
| SCRUM-372 | In Progress | Re-run 19Q benchmark with improved CypherRAG — **blocked on Neo4j (needs reboot)** |
| SCRUM-398 | To Do | Benchmark VectorRAG/PathRAG on dense 3x/5x graphs |
| SCRUM-374 | To Do | Ingest denser P&ID at scale, repeat graph-level comparison |
| SCRUM-392 | To Do | Scaffold chatpid/frontend as Next.js app |

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
