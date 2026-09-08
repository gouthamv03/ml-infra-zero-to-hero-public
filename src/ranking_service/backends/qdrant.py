from typing import List, Optional
import uuid

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    VectorParams,
)

from ..candidates import CandidateGenerator
from ..encoder import SentenceEncoder
from ..interface import Story, User


def _payload_to_story(payload: dict) -> Story:
    return Story(
        id=payload["id"],
        title=payload["title"],
        url=payload.get("url"),
        points=payload.get("points") or 0,
        author=payload.get("author") or "",
        created_at=payload.get("created_at") or "",
        num_comments=payload.get("num_comments") or 0,
        is_ask_hn=payload.get("is_ask_hn", False),
        is_show_hn=payload.get("is_show_hn", False),
        is_front_page=payload.get("is_front_page", False),
    )


def _story_id_to_int(story_id: str) -> int:
    """Qdrant requires integer or UUID point IDs; hash the string id."""
    return uuid.uuid5(uuid.NAMESPACE_DNS, story_id).int >> 64


class QdrantCandidateGenerator(CandidateGenerator):
    """ANN vector search via Qdrant.

    Replaces SemanticCandidateGenerator's linear cosine scan with an
    HNSW approximate nearest-neighbour index. The trade-off: a tiny recall
    loss (~1-2%) for orders-of-magnitude faster queries at scale.

    Uses the same fastembed BAAI/bge-small-en-v1.5 vectors as the Candidate Generators step —
    the encoder is unchanged, only the search backend changes.

    Preserves max-per-interest scoring: one query per interest, results merged
    by taking the highest score per story across all interests.
    """

    COLLECTION = "hn_stories"

    def __init__(
        self,
        client: QdrantClient,
        encoder: SentenceEncoder,
        collection: str = COLLECTION,
    ):
        self._client = client
        self._encoder = encoder
        self._collection = collection

    @classmethod
    def ingest(
        cls,
        stories: List[Story],
        encoder: SentenceEncoder,
        client: QdrantClient,
        collection: str = COLLECTION,
        recreate: bool = False,
    ) -> None:
        existing = [c.name for c in client.get_collections().collections]

        if recreate and collection in existing:
            client.delete_collection(collection)
            existing = []

        if collection not in existing:
            client.create_collection(
                collection_name=collection,
                vectors_config=VectorParams(
                    size=encoder.n_dims,
                    distance=Distance.COSINE,
                ),
            )

        if encoder._matrix is None:
            raise RuntimeError("Encoder has not been fit — call encoder.fit(stories) first.")

        batch_size = 256
        total = 0
        for i in range(0, len(stories), batch_size):
            batch_stories = stories[i : i + batch_size]
            batch_vecs = encoder._matrix[i : i + batch_size]
            points = [
                PointStruct(
                    id=_story_id_to_int(s.id),
                    vector=batch_vecs[j].tolist(),
                    payload={
                        "id": s.id,
                        "title": s.title,
                        "url": s.url,
                        "points": s.points,
                        "author": s.author,
                        "created_at": s.created_at,
                        "num_comments": s.num_comments,
                        "is_ask_hn": s.is_ask_hn,
                        "is_show_hn": s.is_show_hn,
                        "is_front_page": s.is_front_page,
                    },
                )
                for j, s in enumerate(batch_stories)
            ]
            client.upsert(collection_name=collection, points=points)
            total += len(points)

        print(f"Uploaded {total} vectors to Qdrant collection '{collection}'")

    def get_candidates(
        self, stories: List[Story], user: User, n: int = 500
    ) -> List[Story]:
        if not user.interests:
            return []

        interest_vecs = list(self._encoder._model.embed(user.interests))

        # Max-per-interest: query per interest, keep highest score per story
        best: dict[str, tuple[float, dict]] = {}
        for vec in interest_vecs:
            response = self._client.query_points(
                collection_name=self._collection,
                query=vec.tolist(),
                limit=n,
                with_payload=True,
            )
            for hit in response.points:
                sid = hit.payload["id"]
                if sid not in best or hit.score > best[sid][0]:
                    best[sid] = (hit.score, hit.payload)

        sorted_results = sorted(best.values(), key=lambda x: -x[0])[:n]
        return [_payload_to_story(payload) for _, payload in sorted_results]
