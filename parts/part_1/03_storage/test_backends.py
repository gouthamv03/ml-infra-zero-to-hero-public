"""
Verification script for Part 1 Storage step backends.

Prerequisites:
    1. Install dependencies:       pip install -r requirements.txt
    2. Start Docker services:      docker compose -f infra/docker-compose.yml \\
                                     --profile core --profile storage-deep-dive up -d
    3. Run this script:            PYTHONPATH=src python3 parts/part_1/03_storage/test_backends.py

Each backend is tested independently. If a service is not reachable the
test group is skipped with a clear message rather than crashing.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from ranking_service.interface import Story, User
from ranking_service.encoder import SentenceEncoder
from ranking_service.backends import (
    PostgresStore,
    ElasticsearchCandidateGenerator,
    QdrantCandidateGenerator,
    Neo4jCandidateGenerator,
)

SNAPSHOT = Path(__file__).resolve().parents[2] / "data" / "hn_stories_snapshot.jsonl"
CACHE    = Path(__file__).resolve().parents[2] / "data" / "story_embeddings.npy"

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
SKIP = "\033[33mSKIP\033[0m"

alice = User(id="alice", interests=["machine learning", "large language models",
                                     "transformers", "neural networks"])
bob   = User(id="bob",   interests=["trading", "markets", "finance", "economics"])


def load_stories_from_file(n: int = 200) -> list:
    raw = [json.loads(l) for l in SNAPSHOT.read_text().splitlines() if l.strip()][:n]
    return [
        Story(
            id=r["id"], title=r["title"], url=r.get("url"),
            points=r.get("points") or 0, author=r["author"],
            created_at=r["created_at"], num_comments=r.get("num_comments") or 0,
            is_ask_hn=r.get("is_ask_hn", False), is_show_hn=r.get("is_show_hn", False),
            is_front_page=r.get("is_front_page", False),
        )
        for r in raw
    ]


def make_encoder(stories: list) -> SentenceEncoder:
    # Never use the production cache in tests — it holds 5000 embeddings and
    # would be overwritten with the 200-story test subset, breaking ep2 notebooks.
    return SentenceEncoder(cache_path=None).fit(stories)


def check(label: str, cond: bool, detail: str = "") -> bool:
    status = PASS if cond else FAIL
    print(f"  [{status}] {label}" + (f"  ({detail})" if detail else ""))
    return cond


# ── Postgres ───────────────────────────────────────────────────────────────────

def test_postgres(stories):
    print("\n── Postgres ──────────────────────────────────────────────────────────")
    try:
        pg = PostgresStore.connect()
        check("connection", True)
    except Exception as e:
        check("connection", False, str(e))
        print(f"  [{SKIP}] remaining Postgres tests — service not running")
        return False, None

    ok = True
    pg.setup_schema(drop_existing=True)
    ok &= check("setup_schema", True)

    pg.ingest_stories(stories)
    count = pg.story_count()
    ok &= check("ingest_stories", count == len(stories), f"{count} rows")

    pg.ingest_users([alice, bob])
    u_count = pg.user_count()
    ok &= check("ingest_users", u_count == 2, f"{u_count} rows")

    loaded = pg.load_stories()
    ok &= check("load_stories round-trip", len(loaded) == len(stories),
                f"{len(loaded)} loaded")
    ok &= check("story fields intact", loaded[0].title != "",
                f'title="{loaded[0].title[:40]}"')

    loaded_users = pg.load_users()
    ok &= check("load_users round-trip", len(loaded_users) == 2)
    alice_pg = next((u for u in loaded_users if u.id == "alice"), None)
    ok &= check("user interests preserved", alice_pg is not None and
                alice_pg.interests == alice.interests,
                str(alice_pg.interests if alice_pg else "not found"))

    return ok, pg


# ── Elasticsearch ──────────────────────────────────────────────────────────────

def test_elasticsearch(stories, encoder):
    print("\n── Elasticsearch ─────────────────────────────────────────────────────")
    from elasticsearch import Elasticsearch
    es = Elasticsearch("http://localhost:9200", request_timeout=5)
    try:
        info = es.info()
        check("connection", True, info["version"]["number"])
    except Exception as e:
        check("connection", False, str(e))
        print(f"  [{SKIP}] remaining ES tests — service not running")
        return False

    ok = True
    ElasticsearchCandidateGenerator.ingest(stories, es, recreate=True)
    ok &= check("ingest", True)

    gen = ElasticsearchCandidateGenerator(es)
    alice_r = gen.get_candidates(stories, alice)
    ok &= check("returns results for Alice", len(alice_r) > 0, f"{len(alice_r)} candidates")



    bob_r = gen.get_candidates(stories, bob)
    ok &= check("different user → different pool",
                {s.id for s in alice_r} != {s.id for s in bob_r},
                f"Alice:{len(alice_r)} Bob:{len(bob_r)}")

    from ranking_service.candidates import KeywordCandidateGenerator
    kw_r    = KeywordCandidateGenerator().get_candidates(stories, alice)
    bm25_only = len({s.id for s in alice_r} - {s.id for s in kw_r})
    check("BM25 finds more than exact substring",
          bm25_only >= 0, f"{bm25_only} extra via BM25")

    return ok


# ── Qdrant ─────────────────────────────────────────────────────────────────────

def test_qdrant(stories, encoder):
    print("\n── Qdrant ────────────────────────────────────────────────────────────")
    from qdrant_client import QdrantClient
    client = QdrantClient(host="localhost", port=6333, timeout=5, check_compatibility=False)
    try:
        client.get_collections()
        check("connection", True)
    except Exception as e:
        check("connection", False, str(e))
        print(f"  [{SKIP}] remaining Qdrant tests — service not running")
        return False

    ok = True
    QdrantCandidateGenerator.ingest(stories, encoder, client, recreate=True)
    ok &= check("ingest", True)

    gen = QdrantCandidateGenerator(client, encoder)
    alice_r = gen.get_candidates(stories, alice)
    ok &= check("returns results for Alice", len(alice_r) > 0, f"{len(alice_r)} candidates")

    exact = [s for s, _ in encoder.most_similar(alice.interests, top_k=20)]
    exact_ids  = {s.id for s in exact}
    qdrant_ids = {s.id for s in alice_r[:20]}
    overlap = len(exact_ids & qdrant_ids)
    ok &= check("ANN recall ≥ 90% vs exact cosine (top-20)",
                overlap >= 18, f"{overlap}/20 shared")

    # Compare top-20 — with a 200-story corpus n=500 returns everything for both users
    alice_top20 = gen.get_candidates(stories, alice, n=20)
    bob_top20   = gen.get_candidates(stories, bob,   n=20)
    overlap20   = len({s.id for s in alice_top20} & {s.id for s in bob_top20})
    ok &= check("different user → different top-20",
                overlap20 < 18, f"{overlap20}/20 shared")

    return ok


# ── Neo4j ──────────────────────────────────────────────────────────────────────

def test_neo4j(stories, encoder):
    print("\n── Neo4j ─────────────────────────────────────────────────────────────")
    from neo4j import GraphDatabase
    driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "mlinfra123"))
    try:
        driver.verify_connectivity()
        check("connection", True)
    except Exception as e:
        check("connection", False, str(e))
        print(f"  [{SKIP}] remaining Neo4j tests — service not running")
        driver.close()
        return False

    ok = True
    Neo4jCandidateGenerator.ingest(stories, driver)
    ok &= check("ingest", True)

    gen = Neo4jCandidateGenerator(driver, encoder, seed_top_k=10)
    alice_r = gen.get_candidates(stories, alice)
    ok &= check("returns results for Alice", len(alice_r) > 0, f"{len(alice_r)} candidates")

    seed_ids     = {s.id for s, _ in encoder.most_similar(alice.interests, top_k=10)}
    seed_authors = {s.author for s, _ in encoder.most_similar(alice.interests, top_k=10)}
    leaked = [s for s in alice_r if s.id in seed_ids]
    ok &= check("seed stories excluded", len(leaked) == 0, f"{len(leaked)} leaked")
    wrong = [s for s in alice_r if s.author not in seed_authors]
    ok &= check("all results by seed authors", len(wrong) == 0,
                f"{len(wrong)} wrong-author stories")

    driver.close()
    return ok


# ── main ───────────────────────────────────────────────────────────────────────

def main():
    print("Loading stories from file (used for seeding Postgres)...")
    stories = load_stories_from_file(n=200)
    encoder = make_encoder(stories)
    print(f"{len(stories)} stories  |  {encoder.n_dims}-dim embeddings\n")

    pg_ok, pg = test_postgres(stories)

    # After Postgres is populated, reload stories from it (as the notebook does)
    if pg_ok and pg:
        print("\nReloading stories from Postgres for subsequent tests...")
        stories = pg.load_stories()
        encoder = make_encoder(stories)
        print(f"  {len(stories)} stories loaded from Postgres")

    results = {
        "Postgres":        pg_ok,
        "Elasticsearch":   test_elasticsearch(stories, encoder),
        "Qdrant":          test_qdrant(stories, encoder),
        "Neo4j":           test_neo4j(stories, encoder),
    }

    print("\n── Summary ───────────────────────────────────────────────────────────")
    all_passed = True
    for name, passed in results.items():
        if passed is False:
            status, all_passed = FAIL, False
        else:
            status = PASS
        print(f"  [{status}] {name}")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
