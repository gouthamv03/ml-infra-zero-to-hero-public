#!/usr/bin/env bash
# Setup script for ML Infra: Zero to Hero
# Run once before starting any part's notebook.
#
# Usage:
#   chmod +x setup.sh
#   ./setup.sh

set -e

echo "=== ML Infra: Zero to Hero — setup ==="
echo ""

# ── Python dependencies ────────────────────────────────────────────────────────
echo "1. Installing Python dependencies..."
pip install -r requirements.txt
echo "   Done."
echo ""

# ── Docker services ────────────────────────────────────────────────────────────
echo "2. Docker services"
echo "   Part 1 first two steps (Simple Ranker, Candidate Generators): no Docker needed."
echo "   Storage step and beyond  : start storage services with:"
echo ""
echo "     docker compose -f infra/docker-compose.yml \\"
echo "       --profile core \\"
echo "       --profile storage-deep-dive \\"
echo "       up -d"
echo ""
echo "   Services started by the above command:"
echo "     postgres       localhost:5432  (source of truth — stories + users)"
echo "     elasticsearch  localhost:9200  (BM25 keyword search)"
echo "     qdrant         localhost:6333  (ANN vector search)"
echo "     neo4j          localhost:7687  (graph traversal)"
echo ""

# ── Verify Part 1 Storage step backends (optional, requires Docker services running) ─
if [[ "${1}" == "--test-storage" ]]; then
  echo "3. Running storage backend verification..."
  PYTHONPATH=src python3 parts/part_1/03_storage/test_backends.py
else
  echo "3. To verify storage backends after starting Docker:"
  echo "   PYTHONPATH=src python3 parts/part_1/03_storage/test_backends.py"
fi

echo ""
echo "=== Setup complete ==="
