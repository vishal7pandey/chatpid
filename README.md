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
| `VectorRAG` | Cosine similarity search over LLM-generated node embeddings | scaffolded, needs enrichment pipeline |
| `PathRAG` | VectorRAG to find a starting node, then hop through neighbors ("locate-and-trace") | scaffolded, needs VectorRAG |
| `CypherRAG` | LLM translates the question into a Cypher query; Neo4j validates it | scaffolded |

## Setup

```bash
uv sync
cp .env.example .env   # fill in OPENAI_API_KEY
docker compose up -d   # starts Neo4j on bolt://localhost:7687

uv run python scripts/00_fetch_sample_dexpi.py
uv run python scripts/01_ingest.py
uv run python scripts/ask.py "What is the design volume flow rate of pump P4712?"
```

## Roadmap

1. ~~Ingestion pipeline (DEXPI → 3 graph levels → Neo4j)~~ — done
2. ~~ContextRAG + LangGraph ReAct agent~~ — done, this is the first thing to
   actually run end to end
3. Semantic enrichment (`chatpid/tools_todo.py` — `enrich_all_nodes`) — generate
   global/local node descriptions via LLM
4. Embeddings + Neo4j vector indexes (`chatpid/tools_todo.py` — `enrich_and_index`) → unblocks
   `VectorRAG`
5. `PathRAG` (builds on VectorRAG)
6. `CypherRAG` (independent — could be pulled forward before 3–5 if you want
   schema-aware querying sooner)
7. Add all implemented tools to `chatpid/agent.py`'s `tools=[...]` list
8. Bigger/real P&IDs; multi-page flowsheets; multi-agent supervisor (paper's
   own stated future direction)
