"""Helper for docker-entrypoint.sh — prints node count, or '0' on error."""
import os
import sys

try:
    from neo4j import GraphDatabase
    uri = os.environ.get("NEO4J_URI", "bolt://neo4j:7687")
    auth = ("neo4j", os.environ.get("NEO4J_PASSWORD", "chatpid_dev_pw"))
    d = GraphDatabase.driver(uri, auth=auth)
    with d.session() as s:
        r = s.run("MATCH (n) RETURN count(n) as c")
        print(r.single()["c"])
    d.close()
except Exception:
    print("0")
