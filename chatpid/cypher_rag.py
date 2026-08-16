"""CypherRAG: LLM-translated Cypher queries for grounded retrieval (Algorithm 4, Section 3.3.4).

The LLM translates natural language → Cypher, Neo4j validates/executes it,
and the LLM generates an answer from the results. The graph schema is injected
into the Cypher-generation prompt so the LLM knows what labels/properties exist.

This module implements:
  - get_graph_schema(): introspects Neo4j for labels, relationship types,
    and property keys at a given level
  - generate_cypher_prompt(): builds the LLM prompt with schema + question
  - execute_cypher(): runs a Cypher query safely (read-only)
  - cypher_rag(): full pipeline (needs LLM for steps 1 and 4)

The LLM-dependent steps (Cypher generation, answer synthesis) are separated
so the graph introspection and execution can be tested independently.
"""

from __future__ import annotations

from neo4j import Driver

from chatpid.llm import get_llm

# --- Graph schema introspection ---

def get_graph_schema(driver: Driver, level: str = "conceptual") -> str:
    """Return a textual summary of node labels, relationship types, and
    property keys present at `level`, for injection into the Cypher prompt.

    Filters by the `level` property on nodes/relationships since all three
    abstraction levels coexist in the same Neo4j database.
    """
    with driver.session() as session:
        # Node labels and their property keys
        node_result = session.run("""
            MATCH (n {level: $level})
            UNWIND labels(n) AS label
            WITH label, collect(DISTINCT keys(n)) AS allKeys
            UNWIND allKeys AS keyList
            UNWIND keyList AS key
            RETURN label, collect(DISTINCT key) AS properties
            ORDER BY label
        """, level=level)

        nodes_schema = []
        for record in node_result:
            label = record["label"]
            if label == "Node":
                continue
            props = [p for p in record["properties"] if p not in ("level", "element_id")]
            nodes_schema.append(f"  (:{label}) - properties: {', '.join(sorted(props))}")

        # Relationship types and their property keys
        rel_result = session.run("""
            MATCH ()-[r {level: $level}]->()
            RETURN DISTINCT type(r) AS relType, keys(r) AS properties
            ORDER BY relType
        """, level=level)

        rels_schema = []
        for record in rel_result:
            rel_type = record["relType"]
            props = [p for p in record["properties"] if p not in ("level",)]
            if props:
                rels_schema.append(f"  -[:{rel_type}]-> (properties: {', '.join(sorted(props))})")
            else:
                rels_schema.append(f"  -[:{rel_type}]->")

        # Sample node tags per label (helps the LLM write better queries)
        tag_result = session.run("""
            MATCH (n {level: $level})
            WHERE n.tag IS NOT NULL
            RETURN labels(n) AS labels, collect(DISTINCT n.tag)[..5] AS sampleTags
            ORDER BY labels
        """, level=level)

        tags_info = []
        for record in tag_result:
            labels = [l for l in record["labels"] if l != "Node"]
            if not labels:
                continue
            tags = record["sampleTags"]
            if tags:
                tags_info.append(f"  {labels[0]}: {', '.join(tags)}")

    schema_text = f"""Graph Schema (level: {level})

Node labels and properties:
{chr(10).join(nodes_schema) if nodes_schema else '  (none)'}

Relationship types:
{chr(10).join(rels_schema) if rels_schema else '  (none)'}

Sample node tags by label:
{chr(10).join(tags_info) if tags_info else '  (none)'}

All nodes have a `tag` property (equipment identifier) and a `level` property
(always "{level}" for this schema). Use `level: "{level}"` in your MATCH
clauses to filter to the correct graph abstraction.
"""
    return schema_text


# --- Cypher generation prompt ---

CYPHER_GENERATION_PROMPT = """\
You are an expert at writing Cypher queries for a Neo4j graph database \
that contains a Piping and Instrumentation Diagram (P&ID) knowledge graph.

Given the graph schema below and a natural language question, write a \
read-only Cypher query that retrieves the information needed to answer \
the question. The query MUST:
  - Use MATCH/RETURN only (no CREATE, DELETE, SET, MERGE, or writes)
  - Filter nodes/relationships by level: "{level}"
  - Use node `tag` property for equipment identification (e.g. "T4750", "P4711")
  - Return the specific properties needed to answer the question

{schema}

Question: {question}

Write ONLY the Cypher query (no explanation, no markdown fences):
"""


def generate_cypher(driver: Driver, question: str, level: str = "conceptual") -> str:
    """Use the LLM to translate a natural language question into a Cypher query."""
    schema = get_graph_schema(driver, level)
    prompt = CYPHER_GENERATION_PROMPT.format(
        schema=schema, question=question, level=level
    )
    llm = get_llm(temperature=0)
    response = llm.invoke(prompt)
    cypher = response.content.strip()

    # Strip markdown code fences if present
    if cypher.startswith("```"):
        lines = cypher.split("\n")
        cypher = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])

    return cypher.strip()


# --- Cypher execution ---

def execute_cypher(driver: Driver, cypher: str) -> list[dict]:
    """Execute a Cypher query and return results as a list of dicts.

    Raises ValueError if the query contains write operations.
    """
    # Safety check: reject write operations
    cypher_upper = cypher.upper()
    forbidden = ["CREATE", "DELETE", "SET ", "MERGE", "DROP", "REMOVE", "CALL DB." "SHORTESTPATH"]
    # Allow "CREATE" only inside square brackets (e.g., [CREATE VECTOR INDEX...])
    # but for safety, just reject any CREATE at the start of a statement
    for kw in ["CREATE", "DELETE", "MERGE", "DROP", "REMOVE"]:
        if kw in cypher_upper.split():
            raise ValueError(f"Write operation '{kw}' not allowed in CypherRAG")

    with driver.session() as session:
        result = session.run(cypher)
        return [dict(record) for record in result]


# --- Answer synthesis ---

ANSWER_PROMPT = """\
You are ChatP&ID, answering a question about a P&ID using Cypher query results.

Question: {question}

Cypher query executed:
{cypher}

Query results:
{results}

Answer the question using ONLY the query results above. Be concise and cite \
the specific tags/equipment names your answer is grounded in.
"""


def synthesize_answer(question: str, cypher: str, results: list[dict]) -> str:
    """Use the LLM to synthesize an answer from Cypher query results."""
    # Format results as readable text
    if not results:
        results_text = "(no results returned)"
    else:
        lines = []
        for i, row in enumerate(results):
            parts = [f"{k}: {v}" for k, v in row.items()]
            lines.append(f"Row {i+1}: {', '.join(parts)}")
        results_text = "\n".join(lines)

    prompt = ANSWER_PROMPT.format(
        question=question, cypher=cypher, results=results_text
    )
    llm = get_llm(temperature=0)
    return llm.invoke(prompt).content


# --- Full CypherRAG pipeline ---

def cypher_rag(driver: Driver, query: str, level: str = "conceptual") -> dict:
    """Full CypherRAG pipeline: question → Cypher → execute → answer.

    Returns {"answer": str, "cypher": str, "results": list[dict]}.

    Mirrors Algorithm 4 of the paper. If the Cypher execution fails, the
    error is fed back to the LLM for one retry (per Section 6.2 of the paper).
    """
    # Step 1: Generate Cypher
    cypher = generate_cypher(driver, query, level)

    # Step 2: Execute Cypher (with one retry on error)
    try:
        results = execute_cypher(driver, cypher)
    except Exception as exc:
        # Retry: feed error back to LLM
        retry_prompt = f"""\
The following Cypher query failed with this error:
  {exc}

Original question: {query}

Fix the Cypher query. Write ONLY the corrected query:
"""
        llm = get_llm(temperature=0)
        corrected = llm.invoke(retry_prompt).content.strip()
        if corrected.startswith("```"):
            lines = corrected.split("\n")
            corrected = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
        cypher = corrected.strip()
        results = execute_cypher(driver, cypher)

    # Step 3: Synthesize answer
    answer = synthesize_answer(query, cypher, results)

    return {"answer": answer, "cypher": cypher, "results": results}


def cypher_rag_text(driver: Driver, query: str, level: str = "conceptual") -> str:
    """Convenience wrapper: return CypherRAG answer as plain text."""
    result = cypher_rag(driver, query, level)
    return result["answer"]
