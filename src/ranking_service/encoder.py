from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
from fastembed import TextEmbedding
from sklearn.metrics.pairwise import cosine_similarity

from .interface import Story


class SentenceEncoder:
    """Dense sentence embeddings for story retrieval.

    Uses fastembed (ONNX, no PyTorch) with BAAI/bge-small-en-v1.5.
    Embeddings are cached to disk — first fit takes ~30s, subsequent
    fits load in under a second.

    Retrieval uses per-interest max scoring: each interest is embedded
    separately and the highest similarity across all interests is taken
    per story. This prevents broad terms (e.g. 'AI') from dominating
    specific ones (e.g. 'transformers').

    In the Storage step this is replaced by Qdrant-backed ANN search.
    The fit / most_similar interface stays the same.
    """

    MODEL = "BAAI/bge-small-en-v1.5"

    def __init__(self, cache_path: Optional[Path] = None):
        self._model = TextEmbedding(self.MODEL)
        self._cache_path = cache_path
        self._matrix: Optional[np.ndarray] = None
        self._stories: List[Story] = []

    def fit(self, stories: List[Story]) -> "SentenceEncoder":
        self._stories = stories
        if self._cache_path is not None and self._cache_path.exists():
            matrix = np.load(self._cache_path)
            if matrix.shape[0] == len(stories):
                self._matrix = matrix
                print(f"Loaded cached embeddings ({self._cache_path.name})")
                return self
            print(f"Cache row count {matrix.shape[0]} != {len(stories)} stories — re-embedding")
        print(f"Embedding {len(stories)} titles with {self.MODEL} (~30s on first run)...")
        titles = [s.title or "" for s in stories]
        self._matrix = np.array(list(self._model.embed(titles)))
        if self._cache_path is not None:
            np.save(self._cache_path, self._matrix)
            print(f"Cached to {self._cache_path.name}")
        return self

    @property
    def n_stories(self) -> int:
        return len(self._stories)

    @property
    def n_dims(self) -> int:
        return self._matrix.shape[1] if self._matrix is not None else 0

    def most_similar(self, interests: List[str], top_k: int = 500) -> List[Tuple[Story, float]]:
        """Score each interest against the corpus separately, return top_k by max score."""
        interest_vecs = np.array(list(self._model.embed(interests)))  # (n_interests, 384)
        sims = cosine_similarity(interest_vecs, self._matrix)          # (n_interests, n_stories)
        max_sims = sims.max(axis=0)                                    # (n_stories,)
        top_idx = np.argsort(max_sims)[::-1][:top_k]
        return [(self._stories[i], float(max_sims[i])) for i in top_idx]
