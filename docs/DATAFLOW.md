# ChatP&ID — Dataflow Diagram

Two phases: **offline ingestion/enrichment** (builds the knowledge graph) and
**online query** (the ReAct agent answers questions via 4 GraphRAG tools).

## Phase 1 — Offline: Ingestion & Enrichment

```mermaid
flowchart TD
    XML["DEXPI / Proteus XML<br/>C01V04-VER.EX01.xml<br/>(~150k tokens of CAD data)"]

    subgraph pydexpi["pydexpi library (DEXPI standard)"]
        PS["ProteusSerializer.load<br/>ingest.py:41"]
        DM["DexpiModel<br/>(typed Pydantic objects:<br/>CentrifugalPump, Tank, Valve...)<br/>~170 equipment classes"]
        GL["GraphLoader.parse_dexpi_to_graph<br/>ingest.py:56"]
        GA["GraphAbstractor<br/>build_complete_graph<br/>build_process_graph<br/>build_conceptual_graph"]
    end

    subgraph nx["networkx MultiDiGraph"]
        CG["complete graph<br/>212 nodes / 348 edges"]
        PG["process graph<br/>66 nodes / 78 edges"]
        KG["conceptual graph<br/>36 nodes / 39 edges"]
    end

    subgraph neo4j["Neo4j Knowledge Graph"]
        N["Nodes<br/>labels = DEXPI class hierarchy<br/>e.g. :CentrifugalPump:Pump:Equipment:Node<br/>props = flat property bag<br/>(tag, designVolumeFlowRate, nominalDiameter...)<br/>+ level + document_id"]
    end

    XML -->|"scripts/00_fetch..."| PS
    PS --> DM
    DM --> GL
    GL -->|"1:1 entity mapping"| CG
    GL --> GA
    GA -->|"piping condensed"| PG
    GA -->|"piping+instr+equip condensed"| KG
    CG -->|"load_graph ingest.py:103<br/>MERGE + SET props"| N
    PG --> N
    KG --> N

    subgraph enrich["Semantic Enrichment (offline, once)"]
        SE["semantic_enrichment.py<br/>enrich_all_nodes"]
        LLM1["LLM (gpt-5.4 via Azure)"]
        GS["global_semantic<br/>'node role in whole flowsheet'<br/>1-2 sentences"]
        LS["local_semantic<br/>'node role vs neighbors'<br/>1-2 sentences"]
    end

    N -->|"read nodes + topology"| SE
    SE -->|"global prompt + flowsheet ctx"| LLM1
    SE -->|"local prompt + neighbor ctx"| LLM1
    LLM1 --> GS
    LLM1 --> LS
    GS -->|"SET n.global_semantic"| N
    LS -->|"SET n.local_semantic"| N

    subgraph embed["Embedding (offline, once)"]
        EMB["vector_rag.py: embed_and_store<br/>HuggingFace all-MiniLM-L6-v2<br/>(384-dim, local, no API key)"]
        VEC["global_semantic_embedding<br/>local_semantic_embedding<br/>(384-dim float vectors on nodes)"]
        IDX["Neo4j vector indexes<br/>global_semantic_index<br/>local_semantic_index<br/>(cosine similarity)"]
    end

    N -->|"read semantic text"| EMB
    EMB --> VEC
    VEC -->|"SET n.*_embedding"| N
    EMB -->|"CREATE VECTOR INDEX"| IDX
```

## Phase 2 — Online: Query via ReAct Agent

```mermaid
flowchart TD
    USER["User question<br/>'What is the design volume flow<br/>rate of pump P4712?'"]

    subgraph frontend["Frontend (Next.js :3000)"]
        CP["ChatPanel.tsx<br/>chat + suggested questions"]
        GP["GraphPanel.tsx<br/>node-link viz (xyflow)<br/>highlights touched nodes"]
        PV["PidViewer.tsx<br/>DEXPI SVG render"]
    end

    subgraph api["FastAPI API (chatpid/api.py :8000)"]
        ASK["POST /ask<br/>invokes agent, returns<br/>answer + tools_used + graph_node_ids"]
        GRP["GET /graph<br/>returns nodes/edges for viz"]
        SVG["GET /pid/svg<br/>renders DEXPI diagram"]
    end

    subgraph agent["LangGraph ReAct Agent (agent.py)"]
        SP["System Prompt<br/>'pick the ONE best tool'<br/>tool selection guide"]
        REASON["Reasoning Node<br/>decides: answer or call tool?<br/>loop capped at recursion_limit=25"]
    end

    subgraph tools["4 GraphRAG Tools"]
        CTX["ContextRAG<br/>context_rag.py"]
        VEC["VectorRAG<br/>vector_rag.py"]
        PATH["PathRAG<br/>path_rag.py"]
        CYP["CypherRAG<br/>cypher_rag.py"]
    end

    subgraph neo4j["Neo4j Knowledge Graph"]
        N["Nodes + edges<br/>(3 abstraction levels)<br/>+ semantic embeddings<br/>+ vector indexes"]
    end

    subgraph llm["LLM (gpt-5.4 via Azure OpenAI)"]
        L1["Agent reasoning<br/>(tool selection + answer)"]
        L2["Cypher generation<br/>(NL → Cypher)"]
        L3["Answer synthesis<br/>(results → NL answer)"]
    end

    USER --> CP
    CP -->|"POST /ask"| ASK
    ASK --> SP
    SP --> REASON
    REASON -->|"tool call"| CTX
    REASON -->|"tool call"| VEC
    REASON -->|"tool call"| PATH
    REASON -->|"tool call"| CYP
    REASON -->|"final answer"| ASK

    CTX -->|"MATCH nodes+edges<br/>serialize to text"| N
    VEC -->|"embed query<br/>db.index.vector.queryNodes"| N
    PATH -->|"find_starting_nodes<br/>+ get_neighbors traversal"| N
    CYP -->|"get_graph_schema<br/>→ generate Cypher<br/>→ execute_cypher"| N

    REASON --> L1
    CYP --> L2
    CYP --> L3

    ASK -->|"answer + tools_used<br/>+ graph_node_ids"| CP
    CP -->|"touched node tags"| GP
    GP -->|"GET /graph"| GRP
    GRP -->|"nodes/edges"| N
    PV -->|"GET /pid/svg"| SVG
    SVG --> N
```

## Tool Detail — How Each GraphRAG Tool Retrieves Data

```mermaid
flowchart LR
    Q["User question"]

    subgraph ctx["ContextRAG (best accuracy/cost)"]
        C1["MATCH all nodes at level<br/>serialize: [tag] key=val, key=val<br/>+ edges: A --rel--> B<br/>strips metadata + embeddings"]
    end

    subgraph vec["VectorRAG (semantic search)"]
        V1["embed query<br/>(HuggingFace 384-dim)"]
        V2["db.index.vector.queryNodes<br/>cosine similarity, top-k"]
        V3["return tags + labels<br/>+ semantic descriptions + score"]
    end

    subgraph path["PathRAG (locate-and-trace)"]
        P1["find_starting_nodes<br/>text-match query vs tags/labels<br/>(stand-in for VectorRAG)"]
        P2["get_neighbors<br/>traverse up to max_depth=3<br/>max_breadth=2 parallel paths"]
        P3["prefer outgoing (flow direction)<br/>+0.5 score bonus"]
        P4["return paths + node ctx<br/>+ edge types + best path"]
    end

    subgraph cyp["CypherRAG (precise lookup)"]
        CY1["get_graph_schema<br/>introspect labels + props + rels"]
        CY2["LLM: NL → Cypher query<br/>(schema-injected prompt)"]
        CY3["validate read-only<br/>(regex block SET/CREATE/DELETE...)"]
        CY4["execute_cypher"]
        CY5["0 results or syntax error?<br/>→ retry with label hints<br/>→ fallback to ContextRAG"]
        CY6["LLM: results → NL answer"]
    end

    Q --> C1
    Q --> V1 --> V2 --> V3
    Q --> P1 --> P2 --> P3 --> P4
    Q --> CY1 --> CY2 --> CY3 --> CY4 --> CY5 --> CY6
```

## Key Data Transformations

| Stage | Input | Output | Where |
|---|---|---|---|
| XML → pydexpi model | Proteus XML (~150k tokens) | Typed Pydantic objects (DEXPI classes) | `ProteusSerializer.load` |
| pydexpi model → networkx | Typed objects | Labeled-property graph (labels string + attr dict) | `GraphLoader.parse_dexpi_to_graph` |
| networkx → 3 abstractions | Complete graph | complete / process / conceptual graphs | `GraphAbstractor.build_*` |
| networkx → Neo4j | Graph nodes/edges | Neo4j nodes with multi-labels + flat props + level | `load_graph` (ingest.py:103) |
| Neo4j → semantic text | Node + topology | global_semantic + local_semantic (1-2 sentences each) | `enrich_all_nodes` (LLM) |
| Semantic text → vectors | Text descriptions | 384-dim float embeddings on nodes | `embed_and_store` (HuggingFace) |
| Question → answer | NL question | Grounded NL answer + tool trace + touched nodes | ReAct agent + 1 of 4 tools |

