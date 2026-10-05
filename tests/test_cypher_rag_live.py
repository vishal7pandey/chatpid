"""Live-Neo4j proof that CypherRAG's read path is enforced by the database (CPID-12). Opt-in.

Not run in CI or by default: it needs a running Neo4j. To run it locally:

    docker compose up -d neo4j                  # bolt://localhost:7687 (credentials as in docker-compose.yml)
    CHATPID_LIVE_NEO4J=1 uv run python -m pytest tests/test_cypher_rag_live.py -q

Connection settings come from the usual NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD environment variables
(see chatpid/config.py). The test creates nothing that survives: the write it attempts must be refused, and
it removes any `CPID12Probe` node if the database wrongly accepted one.
"""

from __future__ import annotations

import os

import pytest
from neo4j.exceptions import ClientError

from chatpid import cypher_rag
from chatpid.cypher_rag import execute_cypher
from chatpid.ingest import get_driver

pytestmark = pytest.mark.skipif(
    os.environ.get("CHATPID_LIVE_NEO4J") != "1",
    reason="needs a running Neo4j; set CHATPID_LIVE_NEO4J=1 (see the module docstring)",
)


@pytest.fixture
def driver():
    drv = get_driver()
    drv.verify_connectivity()
    yield drv
    with (
        drv.session() as session
    ):  # cleanup only if the database wrongly accepted the write
        session.run("MATCH (n:CPID12Probe) DELETE n")
    drv.close()


def _probe_count(drv) -> int:
    with drv.session() as session:
        return session.run("MATCH (n:CPID12Probe) RETURN count(n) AS c").single()["c"]


def test_a_read_query_works_through_the_read_transaction(driver):
    assert execute_cypher(driver, "RETURN 1 AS x") == [{"x": 1}]


def test_neo4j_itself_refuses_a_write_even_with_the_regex_layer_bypassed(
    driver, monkeypatch
):
    monkeypatch.setattr(cypher_rag, "_validate_read_only", lambda cypher: None)

    with pytest.raises(ClientError):
        execute_cypher(driver, "CREATE (n:CPID12Probe {id: 'cpid-12'})")

    assert _probe_count(driver) == 0
