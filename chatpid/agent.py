"""The ChatP&ID agent: a LangGraph ReAct agent over the GraphRAG tools.

Flattened from the old agent/{graph,prompts}.py. Mirrors Figure 3 of the paper
- a single reasoning node that decides whether a GraphRAG tool is needed, calls
it, inspects the result, and either answers or calls another tool, up to a
tool-call limit (here: LangGraph's recursion_limit, passed at invoke() time
rather than baked into the graph).

Only ContextRAG is wired in for now (the only fully implemented tool).
Uncomment the others in tools=[...] below as you implement them.

LLM provider is selected by the LLM_PROVIDER env var (groq|gemini).
"""

from __future__ import annotations

from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from neo4j import Driver

from chatpid.context_rag import context_rag
from chatpid.llm import get_llm

# from chatpid.tools_todo import vector_rag, path_rag, cypher_rag

SYSTEM_PROMPT = """\
You are ChatP&ID, an assistant that answers questions about a Piping and \
Instrumentation Diagram (P&ID) by querying a knowledge graph - never from \
memory or guesswork.

You have GraphRAG tools available to retrieve grounded information from the \
graph. Decide whether you need a tool before answering, pick the one best \
suited to the question, and inspect its result before deciding whether you \
have enough to answer or need to call another tool. Prefer the smallest \
number of tool calls that gets you a correct, well-grounded answer.

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

    llm = get_llm(temperature=0)
    return create_react_agent(llm, tools=[ContextRAG], prompt=SYSTEM_PROMPT)
