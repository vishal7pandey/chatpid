#!/bin/bash
set -e

# Wait for Neo4j to be ready
echo "Waiting for Neo4j..."
until python -c "
from neo4j import GraphDatabase
import os
uri = os.environ.get('NEO4J_URI', 'bolt://neo4j:7687')
auth = ('neo4j', os.environ.get('NEO4J_PASSWORD', 'chatpid_dev_pw'))
try:
    d = GraphDatabase.driver(uri, auth=auth)
    d.verify_connectivity()
    d.close()
    exit(0)
except:
    exit(1)
" 2>/dev/null; do
  echo "  Neo4j not ready, retrying in 2s..."
  sleep 2
done
echo "Neo4j is ready!"

# Check if graph is already ingested (skip if so)
COUNT=$(python -c "
from neo4j import GraphDatabase
import os
uri = os.environ.get('NEO4J_URI', 'bolt://neo4j:7687')
auth = ('neo4j', os.environ.get('NEO4J_PASSWORD', 'chatpid_dev_pw'))
d = GraphDatabase.driver(uri, auth=auth)
with d.session() as s:
    r = s.run('MATCH (n) RETURN count(n) as c')
    print(r.single()['c'])
d.close()
" 2>/dev/null || echo "0")

if [ "$COUNT" = "0" ]; then
  echo "Graph is empty — running seed ingestion..."
  uv run python scripts/00_fetch_sample_dexpi.py || echo "Fetch skipped (may already exist)"
  uv run python scripts/01_ingest.py
  echo "Seed ingestion complete!"
else
  echo "Graph already has $COUNT nodes — skipping ingestion."
fi

# Start the API
echo "Starting ChatP&ID API on port 8000..."
exec uv run uvicorn chatpid.api:app --host 0.0.0.0 --port 8000
