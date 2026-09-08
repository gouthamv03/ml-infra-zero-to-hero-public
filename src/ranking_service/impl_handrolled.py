from datetime import datetime, timezone
from typing import List

from .interface import Context, RankingService, Story, User


def _hn_score(story: Story, now: datetime = None) -> float:
    if now is None:
        now = datetime.now(timezone.utc)
    points = story.points or 1
    try:
        ts = datetime.fromisoformat(story.created_at.replace("Z", "+00:00"))
        age_hours = (now - ts).total_seconds() / 3600
    except Exception:
        age_hours = 24
    return (points - 1) / (age_hours + 2) ** 1.8


class HandrolledRankingService(RankingService):
    def rank(self, stories: List[Story], user: User, context: Context) -> List[Story]:
        now = datetime.fromisoformat(context.timestamp.replace("Z", "+00:00"))
        return sorted(stories, key=lambda s: _hn_score(s, now), reverse=True)
