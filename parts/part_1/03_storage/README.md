# Storage

The candidate generators from the previous step run in-memory against a 5K snapshot. This step replaces each one with a production-grade storage backend.

## What's built

- `src/ranking_service/backends/` — four backends, each a drop-in replacement for the in-memory version:

| Backend | Replaces | Role |
|---|---|---|
| `PostgresStore` | — | Source of truth for stories and users; all other backends ingest from here |
| `ElasticsearchCandidateGenerator` | `KeywordCandidateGenerator` | BM25 inverted index |
| `QdrantCandidateGenerator` | `SemanticCandidateGenerator` | HNSW approximate nearest-neighbour search |
| `Neo4jCandidateGenerator` | `ConnectedCandidateGenerator` | Cypher graph traversal |

The generator interfaces don't change — `get_candidates(stories, user, n)` is identical.

## Setup

**Dependencies** (if not already done from the repo root):
```bash
./setup.sh
```

**Start storage services:**
```bash
docker compose -f infra/docker-compose.yml \
  --profile core \
  --profile storage-deep-dive \
  up -d
```

| Service | Port | Role |
|---|---|---|
| Postgres | 5432 | Source of truth — stories + users |
| Elasticsearch | 9200 | BM25 keyword search |
| Qdrant | 6333 | ANN vector search |
| Neo4j | 7474 / 7687 | Graph traversal |

**Verify (optional):**
```bash
PYTHONPATH=src python3 parts/part_1/03_storage/test_backends.py
```

Each backend is tested independently. If a service isn't running it prints `SKIP` rather than failing.

## Storage architecture

```
JSONL snapshot ──(one-time migration)──► Postgres  (source of truth)
                                             │
                                   ┌─────────┼──────────┐
                                   ▼         ▼          ▼
                             Elasticsearch  Qdrant   Neo4j
                             (BM25 index)  (ANN)    (graph)
```

Postgres is the write-ahead store. The other three are derived indexes — they can be wiped and rebuilt from Postgres at any time without data loss.

## Key concepts

- **Source of truth vs derived indexes**: Postgres owns the data; Elasticsearch/Qdrant/Neo4j are indexes built for specific access patterns
- **Each backend solves a specific retrieval problem**: inverted index for keyword, HNSW for vector similarity, graph for relationship traversal
- **Interfaces stay the same**: swapping an in-memory generator for a production backend requires no changes upstream

## What's still missing

Storage is set up, but the ranker is still the Simple Ranker step's HN decay formula — it doesn't read the user at all. The Ranker step adds a trained LightGBM model, a FastAPI serving layer, and a Redis cache.
