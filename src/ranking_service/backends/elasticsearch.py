from typing import List, Optional

from elasticsearch import Elasticsearch, helpers

from ..candidates import CandidateGenerator
from ..interface import Story, User


def _hit_to_story(hit: dict) -> Story:
    src = hit["_source"]
    return Story(
        id=src["id"],
        title=src["title"],
        url=src.get("url"),
        points=src.get("points") or 0,
        author=src.get("author") or "",
        created_at=src.get("created_at") or "",
        num_comments=src.get("num_comments") or 0,
        is_ask_hn=src.get("is_ask_hn", False),
        is_show_hn=src.get("is_show_hn", False),
        is_front_page=src.get("is_front_page", False),
    )


class ElasticsearchCandidateGenerator(CandidateGenerator):
    """BM25 keyword retrieval via Elasticsearch.

    Replaces KeywordCandidateGenerator's exact substring match with a proper
    inverted index + TF-IDF/BM25 scoring. Benefits over substring match:
    - Partial word matches (stemming)
    - Rare words score higher than common ones (IDF weighting)
    - Scales to millions of documents without linear scan

    the Ranker step adds query-time boosting and field weights on top of this.
    """

    INDEX = "hn_stories"

    def __init__(self, client: Elasticsearch, index: str = INDEX):
        self._client = client
        self._index = index

    @classmethod
    def ingest(
        cls,
        stories: List[Story],
        client: Elasticsearch,
        index: str = INDEX,
        recreate: bool = False,
    ) -> None:
        if recreate and client.indices.exists(index=index):
            client.indices.delete(index=index)

        if not client.indices.exists(index=index):
            client.indices.create(
                index=index,
                body={
                    "mappings": {
                        "properties": {
                            "id":           {"type": "keyword"},
                            "title":        {"type": "text", "analyzer": "english"},
                            "url":          {"type": "keyword"},
                            "points":       {"type": "integer"},
                            "author":       {"type": "keyword"},
                            "created_at":   {"type": "keyword"},
                            "num_comments": {"type": "integer"},
                            "is_ask_hn":    {"type": "boolean"},
                            "is_show_hn":   {"type": "boolean"},
                            "is_front_page":{"type": "boolean"},
                        }
                    }
                },
            )

        def _actions():
            for s in stories:
                yield {
                    "_index": index,
                    "_id": s.id,
                    "_source": {
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
                }

        success, errors = helpers.bulk(client, _actions(), raise_on_error=False)
        client.indices.refresh(index=index)
        if errors:
            raise RuntimeError(f"ES bulk ingest had {len(errors)} errors: {errors[:3]}")
        print(f"Indexed {success} stories into '{index}'")

    def get_candidates(
        self, stories: List[Story], user: User, n: int = 500
    ) -> List[Story]:
        if not user.interests:
            return []

        # One `match` clause per interest — BM25 scores across all, returns union
        response = self._client.search(
            index=self._index,
            body={
                "query": {
                    "bool": {
                        "should": [
                            {"match": {"title": {"query": interest, "boost": 1.0}}}
                            for interest in user.interests
                        ],
                        "minimum_should_match": 1,
                    }
                },
                "size": n,
            },
        )
        return [_hit_to_story(h) for h in response["hits"]["hits"]]
