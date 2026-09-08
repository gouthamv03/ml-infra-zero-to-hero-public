from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Story:
    id: str
    title: str
    url: Optional[str]
    points: int
    author: str
    created_at: str
    num_comments: int
    is_ask_hn: bool = False
    is_show_hn: bool = False
    is_front_page: bool = False


@dataclass
class User:
    id: str
    interests: List[str] = field(default_factory=list)
    language: Optional[str] = None
    country: Optional[str] = None


@dataclass
class Context:
    timestamp: str
    page: int = 1


class RankingService(ABC):
    @abstractmethod
    def rank(self, stories: List[Story], user: User, context: Context) -> List[Story]:
        """Return stories sorted by relevance for the given user and context."""
        ...
