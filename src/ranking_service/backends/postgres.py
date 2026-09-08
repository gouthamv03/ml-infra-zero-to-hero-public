from typing import List, Optional

import psycopg2
from psycopg2.extras import execute_values, RealDictCursor

from ..interface import Story, User


class PostgresStore:
    """Source-of-truth store for stories and users.

    Postgres is the write-ahead store. Elasticsearch, Qdrant, and Neo4j are
    derived indexes — they ingest FROM Postgres and can be rebuilt at any time
    without losing data.

    Schema:
        stories — one row per HN story, mirrors the Story dataclass
        users   — one row per user, stores interests as a Postgres array

    Production note: in a live system, writes to the stories table would
    trigger async re-indexing jobs (Kafka → Flink → ES/Qdrant/Neo4j).
    Part 4 adds that streaming layer. For now ingestion is synchronous.
    """

    def __init__(self, conn):
        self._conn = conn

    @classmethod
    def connect(
        cls,
        host: str = "localhost",
        port: int = 5432,
        dbname: str = "mlinfra",
        user: str = "mlinfra",
        password: str = "mlinfra",
    ) -> "PostgresStore":
        conn = psycopg2.connect(
            host=host, port=port, dbname=dbname, user=user, password=password
        )
        return cls(conn)

    def setup_schema(self, drop_existing: bool = False) -> None:
        with self._conn.cursor() as cur:
            if drop_existing:
                cur.execute("DROP TABLE IF EXISTS stories CASCADE")
                cur.execute("DROP TABLE IF EXISTS users CASCADE")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS stories (
                    id            TEXT PRIMARY KEY,
                    title         TEXT NOT NULL,
                    url           TEXT,
                    points        INTEGER DEFAULT 0,
                    author        TEXT,
                    created_at    TEXT,
                    num_comments  INTEGER DEFAULT 0,
                    is_ask_hn     BOOLEAN DEFAULT FALSE,
                    is_show_hn    BOOLEAN DEFAULT FALSE,
                    is_front_page BOOLEAN DEFAULT FALSE
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id        TEXT PRIMARY KEY,
                    interests TEXT[]  DEFAULT '{}',
                    language  TEXT,
                    country   TEXT
                )
            """)
        self._conn.commit()

    def ingest_stories(self, stories: List[Story]) -> None:
        with self._conn.cursor() as cur:
            execute_values(
                cur,
                """
                INSERT INTO stories
                    (id, title, url, points, author, created_at,
                     num_comments, is_ask_hn, is_show_hn, is_front_page)
                VALUES %s
                ON CONFLICT (id) DO UPDATE SET
                    title         = EXCLUDED.title,
                    url           = EXCLUDED.url,
                    points        = EXCLUDED.points,
                    author        = EXCLUDED.author,
                    created_at    = EXCLUDED.created_at,
                    num_comments  = EXCLUDED.num_comments,
                    is_ask_hn     = EXCLUDED.is_ask_hn,
                    is_show_hn    = EXCLUDED.is_show_hn,
                    is_front_page = EXCLUDED.is_front_page
                """,
                [
                    (
                        s.id, s.title, s.url, s.points, s.author, s.created_at,
                        s.num_comments, s.is_ask_hn, s.is_show_hn, s.is_front_page,
                    )
                    for s in stories
                ],
            )
        self._conn.commit()
        print(f"Upserted {len(stories)} stories into Postgres")

    def ingest_users(self, users: List[User]) -> None:
        with self._conn.cursor() as cur:
            execute_values(
                cur,
                """
                INSERT INTO users (id, interests, language, country)
                VALUES %s
                ON CONFLICT (id) DO UPDATE SET
                    interests = EXCLUDED.interests,
                    language  = EXCLUDED.language,
                    country   = EXCLUDED.country
                """,
                [(u.id, u.interests, u.language, u.country) for u in users],
            )
        self._conn.commit()
        print(f"Upserted {len(users)} users into Postgres")

    def load_stories(self) -> List[Story]:
        with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM stories ORDER BY created_at DESC")
            rows = cur.fetchall()
        return [
            Story(
                id=r["id"], title=r["title"], url=r["url"],
                points=r["points"] or 0, author=r["author"] or "",
                created_at=r["created_at"] or "", num_comments=r["num_comments"] or 0,
                is_ask_hn=r["is_ask_hn"], is_show_hn=r["is_show_hn"],
                is_front_page=r["is_front_page"],
            )
            for r in rows
        ]

    def load_users(self) -> List[User]:
        with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM users ORDER BY id")
            rows = cur.fetchall()
        return [
            User(
                id=r["id"],
                interests=list(r["interests"] or []),
                language=r["language"],
                country=r["country"],
            )
            for r in rows
        ]

    def story_count(self) -> int:
        with self._conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM stories")
            return cur.fetchone()[0]

    def user_count(self) -> int:
        with self._conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM users")
            return cur.fetchone()[0]

    def close(self) -> None:
        self._conn.close()
