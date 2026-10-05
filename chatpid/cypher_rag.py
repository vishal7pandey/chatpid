"""CypherRAG: LLM-translated Cypher queries for grounded retrieval (Algorithm 4, Section 3.3.4).

The LLM translates natural language → Cypher, Neo4j validates/executes it,
and the LLM generates an answer from the results. The graph schema is injected
into the Cypher-generation prompt so the LLM knows what labels/properties exist.

This module implements:
  - get_graph_schema(): introspects Neo4j for labels, relationship types,
    and property keys at a given level
  - generate_cypher_prompt(): builds the LLM prompt with schema + question
  - execute_cypher(): runs a Cypher query safely (read-only)
  - cypher_rag(): full pipeline with retry on syntax errors and 0-result
    fallback to ContextRAG (needs LLM for steps 1 and 4)

The LLM-dependent steps (Cypher generation, answer synthesis) are separated
so the graph introspection and execution can be tested independently.
"""

from __future__ import annotations

from neo4j import READ_ACCESS, Driver

from chatpid.context_rag import context_rag
from chatpid.llm import get_llm

# --- Read-only sessions ---


def _read_session(driver: Driver):
    """Open a session that the database itself restricts to reads (CPID-12).

    `_validate_read_only` below is only a regex blocklist on LLM-generated text; this is the real guard.
    Every session in this module goes through here.
    """
    return driver.session(default_access_mode=READ_ACCESS)


# --- Graph schema introspection ---


def get_graph_schema(driver: Driver, level: str = "conceptual") -> str:
    """Return a textual summary of node labels, relationship types, and
    property keys present at `level`, for injection into the Cypher prompt.

    Filters by the `level` property on nodes/relationships since all three
    abstraction levels coexist in the same Neo4j database.
    """
    with _read_session(driver) as session:
        # Node labels and their property keys
        node_result = session.run(
            """
            MATCH (n {level: $level})
            UNWIND labels(n) AS label
            WITH label, collect(DISTINCT keys(n)) AS allKeys
            UNWIND allKeys AS keyList
            UNWIND keyList AS key
            RETURN label, collect(DISTINCT key) AS properties
            ORDER BY label
        """,
            level=level,
        )

        nodes_schema = []
        for record in node_result:
            label = record["label"]
            if label == "Node":
                continue
            props = [
                p for p in record["properties"] if p not in ("level", "element_id")
            ]
            nodes_schema.append(
                f"  (:{label}) - properties: {', '.join(sorted(props))}"
            )

        # Relationship types and their property keys
        rel_result = session.run(
            """
            MATCH ()-[r {level: $level}]->()
            RETURN DISTINCT type(r) AS relType, keys(r) AS properties
            ORDER BY relType
        """,
            level=level,
        )

        rels_schema = []
        for record in rel_result:
            rel_type = record["relType"]
            props = [p for p in record["properties"] if p not in ("level",)]
            if props:
                rels_schema.append(
                    f"  -[:{rel_type}]-> (properties: {', '.join(sorted(props))})"
                )
            else:
                rels_schema.append(f"  -[:{rel_type}]->")

        # Sample node tags per label (helps the LLM write better queries)
        tag_result = session.run(
            """
            MATCH (n {level: $level})
            WHERE n.tag IS NOT NULL
            RETURN labels(n) AS labels, collect(DISTINCT n.tag)[..5] AS sampleTags
            ORDER BY labels
        """,
            level=level,
        )

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
{chr(10).join(nodes_schema) if nodes_schema else "  (none)"}

Relationship types:
{chr(10).join(rels_schema) if rels_schema else "  (none)"}

Sample node tags by label:
{chr(10).join(tags_info) if tags_info else "  (none)"}

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


def _get_label_list(driver: Driver, level: str = "conceptual") -> list[str]:
    """Return just the node label names at `level`, for retry hints."""
    with _read_session(driver) as session:
        result = session.run(
            """
            MATCH (n {level: $level})
            UNWIND labels(n) AS label
            WITH label
            WHERE label <> 'Node'
            RETURN DISTINCT label
            ORDER BY label
        """,
            level=level,
        )
        return [record["label"] for record in result]


def _strip_code_fences(text: str) -> str:
    """Strip markdown code fences from LLM output."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
    return text.strip()


def generate_cypher(driver: Driver, question: str, level: str = "conceptual") -> str:
    """Use the LLM to translate a natural language question into a Cypher query."""
    schema = get_graph_schema(driver, level)
    prompt = CYPHER_GENERATION_PROMPT.format(
        schema=schema, question=question, level=level
    )
    llm = get_llm(temperature=0)
    response = llm.invoke(prompt)
    return _strip_code_fences(response.content)


# --- Cypher execution ---

import re

# Cypher write-clause patterns — matched against the full query with
# whitespace normalization, case-insensitive, and word-boundary aware.
# This replaces the old naive `kw in cypher_upper.split()` check which
# missed SET, FOREACH, LOAD CSV, +=, and was trivially bypassable via
# whitespace/case tricks.
_WRITE_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bSET\b",
        r"\bCREATE\b",
        r"\bDELETE\b",
        r"\bDETACH\s+DELETE\b",
        r"\bMERGE\b",
        r"\bDROP\b",
        r"\bREMOVE\b",
        r"\bFOREACH\b",
        r"\bLOAD\s+CSV\b",
        r"\+=",
        r"\bCALL\s+DB\b",
        r"\bCALL\s+db\.index\b",
        r"\bCALL\s+dbms\b",
        r"\bCALL\s+apoc\b",
        r"\bSHORTESTPATH\b",
    ]
]


def _validate_read_only(cypher: str) -> None:
    """Raise ValueError if the Cypher query contains write operations.

    Uses regex patterns with word boundaries instead of naive token splitting
    to catch SET, FOREACH, LOAD CSV, +=, CALL DB.*, and other write clauses
    regardless of whitespace or case tricks.
    """
    # Normalize: collapse multiple spaces/newlines to single space
    normalized = re.sub(r"\s+", " ", cypher).strip()
    for pattern in _WRITE_PATTERNS:
        if pattern.search(normalized):
            raise ValueError(
                f"Write operation not allowed in CypherRAG: matched pattern {pattern.pattern!r}"
            )


def execute_cypher(driver: Driver, cypher: str) -> list[dict]:
    """Execute a Cypher query and return results as a list of dicts.

    Two layers keep this read-only: the regex guard (`_validate_read_only`, raises ValueError) and, behind
    it, a read-access session with a managed read transaction, which the database enforces (raises a
    Neo4j ClientError for any write that got past the regex).
    """
    _validate_read_only(cypher)

    def _run(tx) -> list[dict]:
        # Rows must be consumed inside the transaction function
        return [dict(record) for record in tx.run(cypher)]

    # Layer 1: a READ_ACCESS session + execute_read, so the database rejects writes the regex missed.
    with _read_session(driver) as session:
        return session.execute_read(_run)


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


def synthesize_answer(
    question: str, cypher: str, results: list[dict], context: str = ""
) -> str:
    """Use the LLM to synthesize an answer from Cypher query results.

    If `context` is provided (ContextRAG fallback), it's included so the LLM
    can answer from the graph text instead of the empty Cypher results.
    """
    # Format results as readable text
    if not results:
        results_text = "(no results returned)"
    else:
        lines = []
        for i, row in enumerate(results):
            parts = [f"{k}: {v}" for k, v in row.items()]
            lines.append(f"Row {i + 1}: {', '.join(parts)}")
        results_text = "\n".join(lines)

    prompt = ANSWER_PROMPT.format(
        question=question, cypher=cypher, results=results_text
    )
    if context:
        prompt += f"\n\nGraph context (ContextRAG fallback):\n{context}\n\nAnswer using the graph context above."
    llm = get_llm(temperature=0)
    return llm.invoke(prompt).content


# --- Full CypherRAG pipeline ---


def _retry_with_schema(
    driver: Driver, query: str, level: str, error_or_reason: str
) -> str:
    """Regenerate Cypher with explicit label list injected as a hint."""
    labels = _get_label_list(driver, level)
    schema = get_graph_schema(driver, level)
    retry_prompt = f"""\
The previous Cypher query {error_or_reason}.

Graph schema (level: {level}):
{schema}

IMPORTANT: The exact node labels in this graph are: {", ".join(labels)}
Do NOT use generic labels like "Valve" or "Equipment" — use the exact labels above.

Original question: {query}

Write a corrected read-only Cypher query. Use MATCH/RETURN only.
Write ONLY the Cypher query (no explanation, no markdown fences):
"""
    llm = get_llm(temperature=0)
    return _strip_code_fences(llm.invoke(retry_prompt).content)


def cypher_rag(driver: Driver, query: str, level: str = "conceptual") -> dict:
    """Full CypherRAG pipeline: question → Cypher → execute → answer.

    Returns {"answer": str, "cypher": str, "results": list[dict], "fallback": bool}.

    Mirrors Algorithm 4 of the paper, with two robustness improvements:
      1. On Cypher syntax/execution error: retry once with schema + error hint
      2. On 0 results: retry once with explicit label list, then fall back
         to ContextRAG if the retry also returns 0 results
    """
    # Step 1: Generate Cypher
    cypher = generate_cypher(driver, query, level)

    # Step 2: Execute Cypher (with retry on syntax error)
    try:
        results = execute_cypher(driver, cypher)
    except Exception as exc:
        # Retry on syntax error: feed error + schema back to LLM
        try:
            cypher = _retry_with_schema(
                driver, query, level, f"failed with error: {exc}"
            )
            results = execute_cypher(driver, cypher)
        except Exception:
            # Both attempts failed — fall back to ContextRAG
            ctx = context_rag(driver, level=level, mode="graph")
            answer = synthesize_answer(
                query, "(CypherRAG failed — using ContextRAG fallback)", [], context=ctx
            )
            return {
                "answer": answer,
                "cypher": cypher,
                "results": [],
                "fallback": True,
                "context_rag": ctx,
            }

    # Step 3: If 0 results, retry once with explicit label hints
    if not results:
        try:
            cypher = _retry_with_schema(
                driver,
                query,
                level,
                "returned 0 results — the label names were likely wrong",
            )
            results = execute_cypher(driver, cypher)
        except Exception:
            results = []

    # Step 4: If still 0 results after retry, fall back to ContextRAG
    if not results:
        ctx = context_rag(driver, level=level, mode="graph")
        answer = synthesize_answer(
            query,
            "(CypherRAG returned no results — using ContextRAG fallback)",
            [],
            context=ctx,
        )
        return {
            "answer": answer,
            "cypher": cypher,
            "results": [],
            "fallback": True,
            "context_rag": ctx,
        }

    # Step 5: Synthesize answer from results
    answer = synthesize_answer(query, cypher, results)

    return {"answer": answer, "cypher": cypher, "results": results, "fallback": False}


def cypher_rag_text(driver: Driver, query: str, level: str = "conceptual") -> str:
    """Convenience wrapper: return CypherRAG answer as plain text.

    If CypherRAG fell back to ContextRAG, the context is prepended so the
    agent has the graph text to reason over.
    """
    result = cypher_rag(driver, query, level)
    if result.get("fallback") and result.get("context_rag"):
        return f"{result['answer']}\n\n--- ContextRAG fallback context ---\n{result['context_rag']}"
    return result["answer"]
