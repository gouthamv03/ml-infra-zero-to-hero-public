# Infrastructure

This directory contains the single `docker-compose.yml` that grows across all parts.

You will never need to read the source code of these systems. They are tools. The lessons are in `src/`.

All commands below should be run from the **repo root**.

---

## Profiles

| Profile | Services | First used |
|---|---|---|
| `core` | Postgres, Redis, Qdrant | Part 1 / Storage step |
| `storage-deep-dive` | Elasticsearch, Neo4j | Part 1 / Storage step |
| `streaming` | Kafka, Flink | Part 5 |
| `app` | Our built services | Part 2+ |

---

## Start / stop / restart

**Part 1 / Storage step (storage):**
```bash
docker compose -f infra/docker-compose.yml \
  --profile core --profile storage-deep-dive up -d
```

**Part 5+ (add streaming):**
```bash
docker compose -f infra/docker-compose.yml \
  --profile core --profile storage-deep-dive --profile streaming up -d
```

**Stop all services (containers stay, data preserved):**
```bash
docker compose -f infra/docker-compose.yml down
```

**Stop and wipe all data volumes (full reset):**
```bash
docker compose -f infra/docker-compose.yml down -v
```

**Restart a single service:**
```bash
docker compose -f infra/docker-compose.yml restart elasticsearch
```

**Check what's running:**
```bash
docker compose -f infra/docker-compose.yml ps
```

---

## Troubleshooting

**Service won't start — port already in use**
```bash
# Find what's using the port (e.g. 9200 for Elasticsearch)
lsof -i :9200
# Kill it, or change the host port in docker-compose.yml
```

**Elasticsearch exits immediately**
```bash
# Check logs
docker compose -f infra/docker-compose.yml logs elasticsearch
# Common cause: not enough virtual memory
sudo sysctl -w vm.max_map_count=262144
```

**Neo4j auth error**
Credentials are `neo4j / mlinfra123`. If you've previously run Neo4j with different
credentials, wipe its volume and restart:
```bash
docker compose -f infra/docker-compose.yml down -v neo4j
docker compose -f infra/docker-compose.yml --profile storage-deep-dive up -d neo4j
```

**Postgres connection refused**
```bash
docker compose -f infra/docker-compose.yml logs postgres
# If healthy but refusing connections, wait ~5s after start for it to be ready
```

**Out of disk space**
```bash
# Remove stopped containers and dangling images
docker system prune
# Nuclear option — removes ALL unused volumes (affects other projects too)
docker system prune --volumes
```

**Start fresh (wipe everything and re-ingest)**
```bash
docker compose -f infra/docker-compose.yml down -v
docker compose -f infra/docker-compose.yml \
  --profile core --profile storage-deep-dive up -d
# Then re-run the ingestion cells in the notebook
```

---

## Resource notes

| Profile combo | Approx. RAM |
|---|---|
| core + storage-deep-dive | ~3–4 GB |
| core + storage-deep-dive + streaming | ~6–8 GB |

On an 8 GB machine, avoid running the streaming profile locally — use GitHub Codespaces instead.
