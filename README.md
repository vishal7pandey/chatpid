# ChatP&ID

GraphRAG for engineering diagrams. Converts a P&ID (via the DEXPI standard) into
a Neo4j knowledge graph and gives a LangGraph ReAct agent four ways to query it,
instead of feeding raw images or XML directly to an LLM.

Based on:
- Alimin & Schweidtmann, *"GraphRAG for Engineering Diagrams: ChatP&ID Enables
  LLM Interaction with P&IDs"* (arXiv:2603.22528)
- Alimin, Goldstein, Balhorn & Schweidtmann, *"Talking like Piping and
  Instrumentation Diagrams (P&IDs)"* (arXiv:2502.18928)

## Why graphs, not images or raw XML

A P&ID is already a graph in disguise (equipment + piping + instrumentation +
relationships). Feeding an LLM a raw image forces it to *perceive* that graph
from pixels; feeding it raw DEXPI/Proteus XML forces it to *parse* a
CAD-oriented format with ~150k tokens of mostly irrelevant machinery. Neither
plays to an LLM's strengths. Converting to a knowledge graph up front, then
letting the LLM *retrieve* only the relevant slice via GraphRAG tools, is both
more accurate and dramatically cheaper (paper's headline number:
GPT-5-mini + ContextRAG = 91% accuracy at $0.004/question).

## Architecture

```
P&ID (DEXPI / Proteus XML)
        |
   pyDEXPI (ProteusSerializer, GraphLoader, GraphAbstractor)
        |
        v
  three graph abstraction levels        <- chatpid/ingest.py
  complete -> process -> conceptual
        |
        v
      Neo4j                              <- chatpid/ingest.py (load_graph)
        |
        v
  ChatP&ID agent (LangGraph ReAct)       <- chatpid/agent.py
        |
   +----+----+----+----+
   |    |    |    |
Context Vector Path Cypher                <- chatpid/context_rag.py
 RAG    RAG   RAG   RAG                      chatpid/tools_todo.py
   |    |    |    |
   +----+----+----+
        |
        v
   grounded answer
```

**Flat layout.** This project runs Principal-Data-Scientist-style: a handful
of flat modules you iterate on directly, not a package with clean import
boundaries. `chatpid/ingest.py` (pyDEXPI + Neo4j loader), `chatpid/context_rag.py`
(the implemented tool), `chatpid/agent.py` (ReAct agent + prompt), and
`chatpid/tools_todo.py` (collapsed unimplemented stubs). Structure gets added
only when duplication actually hurts.

**Input source.** The DEXPI standard is the format; `pyDEXPI` (from the same
research group as the paper) is the Python library that reads it and already
implements the three-level graph abstraction (`GraphAbstractor.build_complete_graph
/ build_process_graph / build_conceptual_graph`), so this project wraps it
rather than reimplementing it. The sample P&ID is the DEXPI reference diagram
(`C01V04-VER.EX01.xml`, © DEXPI e.V.) — the same one the paper's own case study
uses — fetched on demand via `scripts/00_fetch_sample_dexpi.py` rather than
committed to the repo. Point `scripts/01_ingest.py --file` at any other
DEXPI/Proteus export to use a different P&ID.

**Three graph levels.** `complete` (1:1 mapping of every pyDEXPI entity),
`process` (piping condensed), `conceptual` (piping + instrumentation +
equipment condensed further). All three can be loaded into Neo4j
simultaneously, tagged with a `level` property, so GraphRAG tools just filter
by level rather than needing separate databases. The paper found the
conceptual graph is the best default for cost/accuracy in nearly every case —
more information isn't automatically better context.

**The agent.** A LangGraph ReAct agent (`langgraph.prebuilt.create_react_agent`)
over the four tools — this matches the paper's own implementation, which is
explicitly built on LangGraph (Section 3.1) and describes exactly a reason →
act → observe → (answer | another tool) loop, capped by a tool-call limit.

**The four tools**, in the order they're worth building:

| Tool | What it does | Status |
|---|---|---|
| `ContextRAG` | Exports one graph level as compact text (paper's best accuracy/cost tradeoff) | **implemented** |
| `VectorRAG` | Cosine similarity search over LLM-generated node embeddings | **implemented** |
| `PathRAG` | VectorRAG to find a starting node, then hop through neighbors ("locate-and-trace") | **implemented** |
| `CypherRAG` | LLM translates the question into a Cypher query; Neo4j validates it | **implemented** |

## Setup

```bash
uv sync
cp .env.example .env   # fill in OPENAI_API_KEY
docker compose up -d   # starts Neo4j on bolt://localhost:7687

uv run python scripts/00_fetch_sample_dexpi.py
uv run python scripts/01_ingest.py
uv run python scripts/ask.py "What is the design volume flow rate of pump P4712?"
```

## Try the demo in 5 minutes (Docker)

The fastest way to see ChatP&ID working — no manual setup, no Python env:

```bash
# 1. Set your OpenAI API key (the only thing you need to provide)
export OPENAI_API_KEY=sk-...

# 2. One command brings up Neo4j + API + frontend + auto-seeds the P&ID
docker compose up --build

# 3. Open the demo UI
#    http://localhost:3000  — chat + graph visualization
#    http://localhost:8000  — API (POST /ask, GET /graph)
#    http://localhost:7474  — Neo4j browser (neo4j / chatpid_dev_pw)
```

> **Security note:** `docker compose config` interpolates variables from `.env`
> and will print your `OPENAI_API_KEY` in plaintext. If you need to inspect the
> resolved compose config (e.g. for debugging), use `docker compose config
> --no-interpolate` to avoid leaking secrets. Never paste `docker compose
> config` output into issues, chats, or logs.

On first boot, the API container automatically:
1. Waits for Neo4j to be ready
2. Fetches the DEXPI reference P&ID (`C01V04-VER.EX01.xml`)
3. Ingests it into Neo4j at all 3 abstraction levels (complete/process/conceptual)
4. Starts the FastAPI server

The frontend loads with 4 suggested questions that hit different GraphRAG tools
(CypherRAG for lookups, PathRAG for flow tracing, ContextRAG for analysis).
Click through them to see the agent pick its own retrieval strategy per question,
with the graph panel highlighting which nodes it touched.

To stop: `docker compose down` (data persists in the `neo4j_data` volume).


## Roadmap

1. ~~Ingestion pipeline (DEXPI → 3 graph levels → Neo4j)~~ — done
2. ~~ContextRAG + LangGraph ReAct agent~~ — done
3. ~~Semantic enrichment — global/local node descriptions via LLM~~ — done
4. ~~Embeddings + Neo4j vector indexes → VectorRAG~~ — done
5. ~~PathRAG (locate-and-trace path exploration)~~ — done
6. ~~CypherRAG (LLM-translated Cypher queries)~~ — done
7. ~~All 4 tools wired into agent~~ — done
8. ~~Eval harness (LLM-as-judge + semantic similarity)~~ — done
9. ~~Denser P&ID graphs + level scaling comparison~~ — done
10. ~~Model x tool benchmark (3 models x 4 tools)~~ — done
11. ~~Multi-agent supervisor spike (parallel tool agents)~~ — done
12. ~~FastAPI wrapper + Next.js frontend (chat + graph panels)~~ — done
13. ~~One-click Docker demo deployment~~ — done
14. Real engineering tasks (flowsheet modification, HAZOP) — future work
