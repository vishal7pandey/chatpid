"""Helper for docker-entrypoint.sh — exits 0 if Neo4j is reachable, 1 otherwise."""

import os
import sys

try:
    from neo4j import GraphDatabase

    uri = os.environ.get("NEO4J_URI", "bolt://neo4j:7687")
    auth = ("neo4j", os.environ.get("NEO4J_PASSWORD", "chatpid_dev_pw"))
    d = GraphDatabase.driver(uri, auth=auth)
    d.verify_connectivity()
    d.close()
    sys.exit(0)
except Exception:
    sys.exit(1)
