"""The ChatP&ID agent: a LangGraph ReAct agent over the GraphRAG tools.

Flattened from the old agent/{graph,prompts}.py. Mirrors Figure 3 of the paper
- a single reasoning node that decides whether a GraphRAG tool is needed, calls
it, inspects the result, and either answers or calls another tool, up to a
tool-call limit (here: LangGraph's recursion_limit, passed at invoke() time
rather than baked into the graph).

Tools wired in:
  - ContextRAG: condensed graph text (Section 3.3.1)
  - VectorRAG: semantic similarity search (Section 3.3.2)
  - PathRAG: locate-and-trace path exploration (Section 3.3.3)
  - CypherRAG: LLM-translated Cypher queries (Section 3.3.4)

LLM provider is selected by the LLM_PROVIDER env var (openai|groq|gemini).
"""

from __future__ import annotations

from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from neo4j import Driver

from chatpid.context_rag import context_rag
from chatpid.cypher_rag import cypher_rag_text
from chatpid.llm import get_llm
from chatpid.path_rag import path_rag_text
from chatpid.vector_rag import vector_rag_text

SYSTEM_PROMPT = """\
You are ChatP&ID, an assistant that answers questions about a Piping and \
Instrumentation Diagram (P&ID) by querying a knowledge graph - never from \
memory or guesswork.

You have GraphRAG tools available to retrieve grounded information from the \
graph. Decide whether you need a tool before answering, pick the one best \
suited to the question, and inspect its result before deciding whether you \
have enough to answer or need to call another tool. Prefer the smallest \
number of tool calls that gets you a correct, well-grounded answer.

Tool selection guide:
  - ContextRAG: best for broad/summarization questions or when you need the
    general shape of the process. Returns the full graph as text.
  - VectorRAG: best for finding specific components by semantic similarity
    ("which equipment controls temperature", "find all pumps"). Returns the
    top-k most relevant nodes with their semantic descriptions.
  - PathRAG: best for path/flow tracing questions ("trace the flow from X to
    Y", "how to isolate Z", "what's upstream of W"). Traces paths through
    the graph starting from relevant nodes.
  - CypherRAG: best for precise attribute lookups ("what is the design
    pressure of P4711") or listing components by type ("list all valves").
    Translates your question into a Cypher query for exact retrieval.

When you answer, be concise and cite the specific tags/equipment names your \
answer is grounded in.
"""


def _safe_tool(name: str, fn):
    """Wrap a tool function so exceptions return an error string instead of propagating.

    LangGraph's @tool decorator does NOT catch exceptions from the tool body —
    an unhandled exception crashes the entire agent.invoke() call.  This wrapper
    ensures the agent always gets a message back and can decide to retry with a
    different tool or answer from what it has.
    """
    import functools

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            return f"[{name} error] {type(exc).__name__}: {exc!s:.300}"

    return wrapper


def build_agent(driver: Driver):
    """Build the ChatP&ID LangGraph ReAct agent bound to a live Neo4j driver."""
    @tool
    def ContextRAG(level: str = "conceptual", mode: str = "graph") -> str:
        """Retrieve a condensed, noise-filtered graph context for the P&ID.

        Use for broad/summarization questions or when you need the general
        shape of the process, rather than one specific value.

        Args:
            level: "complete" | "process" | "conceptual" (conceptual is the
                best default - richest signal for the lowest token cost).
            mode: "graph" includes node/edge attributes (tags, design specs);
                "topology" is connectivity only, for a lightweight overview.
        """
        return _safe_tool("ContextRAG", lambda: context_rag(driver, level=level, mode=mode))()

    @tool
    def PathRAG(query: str, level: str = "conceptual", max_depth: int = 3, max_breadth: int = 2) -> str:
        """Trace paths through the P&ID graph to answer flow/path questions.

        Use for questions like "trace the flow path from X to Y", "how to
        isolate tank Z", "what's upstream of W". Finds relevant starting
        nodes and traverses the graph along the most relevant paths.

        Args:
            query: the natural language question to trace.
            level: graph abstraction level (default: conceptual).
            max_depth: max hops per path (default: 3).
            max_breadth: max parallel starting paths (default: 2).
        """
        return _safe_tool("PathRAG", lambda: path_rag_text(driver, query, level=level, max_depth=max_depth, max_breadth=max_breadth))()

    @tool
    def CypherRAG(query: str, level: str = "conceptual") -> str:
        """Translate a question into a Cypher query and execute it on the graph.

        Use for precise attribute lookups ("what is the design pressure of
        P4711") or listing components by type ("list all valves"). The Cypher
        query is generated from the graph schema and executed safely (read-only).

        Args:
            query: the natural language question.
            level: graph abstraction level (default: conceptual).
        """
        return _safe_tool("CypherRAG", lambda: cypher_rag_text(driver, query, level=level))()

    @tool
    def VectorRAG(query: str, index: str = "global_semantic_index", top_k: int = 5, level: str = "conceptual") -> str:
        """Find nodes by semantic similarity to the query.

        Use for finding relevant components when you don't know the exact tag
        ("which equipment controls temperature", "find all pumps"). Returns
        the top-k most relevant nodes with their semantic descriptions.

        Args:
            query: natural language search query.
            index: "global_semantic_index" (whole-flowsheet role) or
                "local_semantic_index" (immediate neighborhood role).
            top_k: number of results (default: 5).
            level: graph abstraction level (default: conceptual).
        """
        return _safe_tool("VectorRAG", lambda: vector_rag_text(driver, query, index=index, top_k=top_k, level=level))()

    llm = get_llm(temperature=0)
    return create_react_agent(llm, tools=[ContextRAG, VectorRAG, PathRAG, CypherRAG], prompt=SYSTEM_PROMPT)
