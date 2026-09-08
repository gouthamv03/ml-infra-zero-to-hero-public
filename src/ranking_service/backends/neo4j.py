from typing import List

from neo4j import Driver

from ..candidates import CandidateGenerator
from ..encoder import SentenceEncoder
from ..interface import Story, User


def _node_to_story(node) -> Story:
    return Story(
        id=node["id"],
        title=node["title"],
        url=node.get("url"),
        points=node.get("points") or 0,
        author=node.get("author") or "",
        created_at=node.get("created_at") or "",
        num_comments=node.get("num_comments") or 0,
        is_ask_hn=node.get("is_ask_hn", False),
        is_show_hn=node.get("is_show_hn", False),
        is_front_page=node.get("is_front_page", False),
    )


class Neo4jCandidateGenerator(CandidateGenerator):
    """Author-affinity traversal via Neo4j.

    Graph schema:
        (:Author)-[:WROTE]->(:Story)

    Traversal (two hops):
        1. Find seed stories most similar to the user's interests (via encoder)
        2. Traverse [:WROTE] edges to find their authors
        3. Return all other stories those authors wrote

    This is the same logic as the Candidate Generators step's in-memory ConnectedCandidateGenerator,
    now expressed as a Cypher query over a persistent graph. At production scale
    the graph also encodes click/comment engagement edges — authors a user has
    interacted with rank higher than authors they've never seen.
    """

    def __init__(self, driver: Driver, encoder: SentenceEncoder, seed_top_k: int = 20):
        self._driver = driver
        self._encoder = encoder
        self._seed_top_k = seed_top_k

    @classmethod
    def ingest(cls, stories: List[Story], driver: Driver, batch_size: int = 500) -> None:
        with driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
            session.run("CREATE INDEX author_name IF NOT EXISTS FOR (a:Author) ON (a.name)")
            session.run("CREATE INDEX story_id    IF NOT EXISTS FOR (s:Story)  ON (s.id)")

            for i in range(0, len(stories), batch_size):
                batch = [
                    {
                        "id": s.id,
                        "title": s.title,
                        "url": s.url or "",
                        "points": s.points,
                        "author": s.author or "",
                        "created_at": s.created_at,
                        "num_comments": s.num_comments,
                        "is_ask_hn": s.is_ask_hn,
                        "is_show_hn": s.is_show_hn,
                        "is_front_page": s.is_front_page,
                    }
                    for s in stories[i : i + batch_size]
                ]
                session.run(
                    """
                    UNWIND $batch AS row
                    MERGE (a:Author {name: row.author})
                    MERGE (s:Story {id: row.id})
                      ON CREATE SET
                        s.title        = row.title,
                        s.url          = row.url,
                        s.points       = row.points,
                        s.author       = row.author,
                        s.created_at   = row.created_at,
                        s.num_comments = row.num_comments,
                        s.is_ask_hn    = row.is_ask_hn,
                        s.is_show_hn   = row.is_show_hn,
                        s.is_front_page = row.is_front_page
                    MERGE (a)-[:WROTE]->(s)
                    """,
                    batch=batch,
                )

        with driver.session() as session:
            r = session.run(
                "MATCH (a:Author)-[:WROTE]->(s:Story) "
                "RETURN count(DISTINCT a) AS authors, count(DISTINCT s) AS stories"
            ).single()
            print(
                f"Neo4j graph: {r['authors']} Author nodes, "
                f"{r['stories']} Story nodes, WROTE edges connecting them"
            )

    def get_candidates(
        self, stories: List[Story], user: User, n: int = 500
    ) -> List[Story]:
        if not user.interests:
            return []

        top = self._encoder.most_similar(user.interests, top_k=self._seed_top_k)
        seed_ids = [s.id for s, _ in top]

        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (seed:Story)<-[:WROTE]-(a:Author)-[:WROTE]->(other:Story)
                WHERE seed.id IN $seed_ids
                  AND NOT other.id IN $seed_ids
                RETURN DISTINCT other
                LIMIT $limit
                """,
                seed_ids=seed_ids,
                limit=n,
            )
            return [_node_to_story(record["other"]) for record in result]
