---
# The ChatPID charter, a proposal for the owner. It is approved only through decision record D-002
# (`factory decide D-002 --accept`, run by the owner); until then `factory doctor` says "no approved charter".
# The benchmark bar in C2 (0.7) is the agent's proposal, grounded in the Aug 2026 single-agent run (14 of 19 correct or
# partially correct = 0.74); the number is the owner's to change.
purpose: "ChatP&ID answers questions about piping and instrumentation diagrams by loading DEXPI P&ID XML into Neo4j and retrieving with GraphRAG. It is a learning and research project that reproduces and extends the approach of the ChatP&ID paper, for its owner."
mode: active
decision: D-002
done:
  - id: C1
    text: "DEXPI P&ID files ingest into Neo4j end to end on the three reference drawings"
    check: {jira: CPID-45}
  - id: C2
    text: "The paper's 19-question benchmark is reproduced and at least 70 percent of its answers are correct or partially correct, recorded in a committed summary file"
    check: {metric: {file: docs/eval/benchmark-latest.json, key: correct_or_partial_fraction, min: 0.7}}
  - id: C3
    text: "The licence of the DEXPI e.V. reference files used in data/dexpi_real is resolved and written down"
    check: {jira: CPID-27}
  - id: C4
    text: "CI runs the frontend build and tests on every pull request"
    check: {jira: CPID-38}
  - id: C5
    text: "No scanner finding of critical or high severity is open, the last one being the SonarCloud S2083 alert"
    check: {jira: CPID-41}
non_goals:
  - "Multi-document scoping of the RAG tools (CPID-11)"
  - "Anything beyond the 19-question benchmark scope: no new benchmarks, scaling studies, model comparisons or agent redesign"
  - "Turning images into DEXPI (CPID-19)"
  - "Production hosting, user accounts or a multi-tenant service"
parked:
  - {item: "Epic: improvements from the laptop-2 snapshot, which only holds multi-document scoping", jira: CPID-10}
  - {item: "Multi-document scoping: pass document_id through all four RAG tools", jira: CPID-11}
  - {item: "Tidy the RAG modules and settle PathRAG's temporary VectorRAG", jira: CPID-17}
  - {item: "Fix drift: LLM_PROVIDER default and the missing /ingest client in api.ts", jira: CPID-18}
  - {item: "Idea: image to DEXPI to graph with ade's P&ID extraction", jira: CPID-19}
  - {item: "Bound the POST /ingest request body (no upload size limit, no auth); a hardening item the owner may want to promote to a done criterion", jira: CPID-22}
  - {item: "Live-Neo4j CypherRAG read-only test and a read-only Neo4j user", jira: CPID-26}
---
# The ChatPID charter

ChatPID is finished as a research prototype when the five criteria above are all met: the graph can be loaded from the
reference drawings (C1), the paper's benchmark has a recorded score at or above the bar (C2), the reference data may
legally be in the repository (C3), CI covers the whole product (C4) and no serious scanner finding is open (C5).
The parked list is what the owner has deliberately not asked for; each item stays parked until the owner amends this
charter. The benchmark bar in C2 is a proposal from the Aug 2026 single-agent run and is the owner's to change.

## Maintenance mode

When every done criterion is met the project enters maintenance mode (`mode: maintenance`, approved through a new
charter decision). In maintenance mode only security and dependency updates are made, through the findings and
dependency loops (`factory-findings`, `factory-dependencies`). Any other change needs a charter amendment: a new
charter decision the owner accepts. `factory feature start` warns, but does not block, so the owner can proceed
deliberately.
