import random
from abc import ABC, abstractmethod
from typing import List

from .encoder import SentenceEncoder
from .interface import Story, User


class CandidateGenerator(ABC):
    @abstractmethod
    def get_candidates(self, stories: List[Story], user: User, n: int = 500) -> List[Story]:
        """Return up to n candidate stories for the given user."""
        ...


class PopularityCandidateGenerator(CandidateGenerator):
    """Rank by raw points — fast, no personalisation, strong baseline."""

    def get_candidates(self, stories: List[Story], user: User, n: int = 500) -> List[Story]:
        return sorted(stories, key=lambda s: s.points or 0, reverse=True)[:n]


class KeywordCandidateGenerator(CandidateGenerator):
    """Return stories whose titles contain any of the user's interest keywords.

    Fast and precise for exact-match terms; misses synonyms and paraphrases.
    The Storage step replaces this with Elasticsearch BM25.
    """

    def get_candidates(self, stories: List[Story], user: User, n: int = 500) -> List[Story]:
        if not user.interests:
            return []
        keywords = [kw.lower() for kw in user.interests]
        return [
            s for s in stories
            if any(kw in (s.title or "").lower() for kw in keywords)
        ][:n]


class SemanticCandidateGenerator(CandidateGenerator):
    """Find stories semantically close to the user's interests.

    Each interest is embedded separately; the best match across all interests
    is taken per story (max-per-interest scoring). This gives each interest
    equal weight and avoids broad terms dominating specific ones.

    Uses SentenceEncoder in-memory (the Candidate Generators step). In the Storage step this is
    replaced by Qdrant ANN search — same interface, better scale.
    """

    def __init__(self, encoder: SentenceEncoder):
        self._encoder = encoder

    def get_candidates(self, stories: List[Story], user: User, n: int = 500) -> List[Story]:
        if not user.interests:
            return []
        results = self._encoder.most_similar(user.interests, top_k=n)
        return [story for story, _score in results]


class ConnectedCandidateGenerator(CandidateGenerator):
    """Author-affinity: surface stories by authors of the user's top semantic matches.

    Approximates graph traversal in memory for the Candidate Generators step. The Storage step replaces
    this with Neo4j: same traversal idea, but over a full author-story engagement
    graph built from historical click and comment data.
    """

    def __init__(self, encoder: "SentenceEncoder" = None, seed_top_k: int = 20):
        self._encoder = encoder
        self._seed_top_k = seed_top_k

    def get_candidates(self, stories: List[Story], user: User, n: int = 500) -> List[Story]:
        if self._encoder is None or not user.interests:
            return []
        top = self._encoder.most_similar(user.interests, top_k=self._seed_top_k)
        seed_authors = {s.author for s, _ in top if s.author}
        seed_ids = {s.id for s, _ in top}
        return [
            s for s in stories
            if s.author in seed_authors and s.id not in seed_ids
        ][:n]


class ExplorationCandidateGenerator(CandidateGenerator):
    """Inject under-exposed stories to combat filter-bubble effects.

    Picks randomly from the long tail (low-point, under-exposed stories).
    Pass exclude_ids to ensure exploration only surfaces content outside what
    keyword and semantic generators already return — true anti-filter-bubble
    behaviour rather than random noise.
    """

    def __init__(self, points_threshold: int = 5, seed: int = None):
        self._threshold = points_threshold
        self._rng = random.Random(seed)

    def get_candidates(
        self, stories: List[Story], user: User, n: int = 500,
        exclude_ids: set = None,
    ) -> List[Story]:
        exclude = exclude_ids or set()
        tail = [
            s for s in stories
            if (s.points or 0) <= self._threshold and s.id not in exclude
        ]
        return self._rng.sample(tail, min(n, len(tail)))
