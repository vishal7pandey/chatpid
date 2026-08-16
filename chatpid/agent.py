"""The ChatP&ID agent: a LangGraph ReAct agent over the GraphRAG tools.

Flattened from the old agent/{graph,prompts}.py. Mirrors Figure 3 of the paper
- a single reasoning node that decides whether a GraphRAG tool is needed, calls
it, inspects the result, and either answers or calls another tool, up to a
tool-call limit (here: LangGraph's recursion_limit, passed at invoke() time
rather than baked into the graph).

Tools wired in:
  - ContextRAG: condensed graph text (Section 3.3.1)
  - PathRAG: locate-and-trace path exploration (Section 3.3.3)
  - CypherRAG: LLM-translated Cypher queries (Section 3.3.4)

Not yet wired (needs semantic enrichment + embeddings):
  - VectorRAG: semantic similarity search (Section 3.3.2)

LLM provider is selected by the LLM_PROVIDER env var (groq|gemini).
"""

from __future__ import annotations

from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from neo4j import Driver

from chatpid.context_rag import context_rag
from chatpid.cypher_rag import cypher_rag_text
from chatpid.llm import get_llm
from chatpid.path_rag import path_rag_text

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
  - PathRAG: best for path/flow tracing questions ("trace the flow from X to
    Y", "how to isolate Z", "what's upstream of W"). Traces paths through
    the graph starting from relevant nodes.
  - CypherRAG: best for precise attribute lookups ("what is the design
    pressure of P4711") or listing components by type ("list all valves").
    Translates your question into a Cypher query for exact retrieval.

When you answer, be concise and cite the specific tags/equipment names your \
answer is grounded in.
"""


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
        return context_rag(driver, level=level, mode=mode)

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
        return path_rag_text(driver, query, level=level, max_depth=max_depth, max_breadth=max_breadth)

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
        return cypher_rag_text(driver, query, level=level)

    llm = get_llm(temperature=0)
    return create_react_agent(llm, tools=[ContextRAG, PathRAG, CypherRAG], prompt=SYSTEM_PROMPT)
