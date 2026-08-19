#!/bin/bash
set -e

# Wait for Neo4j to be ready
echo "Waiting for Neo4j..."
until uv run python /app/scripts/_wait_neo4j.py 2>/dev/null; do
  echo "  Neo4j not ready, retrying in 2s..."
  sleep 2
done
echo "Neo4j is ready!"

# Check if graph is already ingested (skip if so)
COUNT=$(uv run python /app/scripts/_count_nodes.py 2>/dev/null || echo "0")

if [ "$COUNT" = "0" ]; then
  echo "Graph is empty — running seed ingestion..."
  uv run python scripts/00_fetch_sample_dexpi.py || echo "Fetch skipped (may already exist)"
  uv run python scripts/01_ingest.py --levels complete,process,conceptual
  echo "Seed ingestion complete!"
else
  echo "Graph already has $COUNT nodes — skipping ingestion."
fi

# Start the API
echo "Starting ChatP&ID API on port 8000..."
exec uv run uvicorn chatpid.api:app --host 0.0.0.0 --port 8000
