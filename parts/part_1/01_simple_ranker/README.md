# Simple Ranker

How do you rank news stories with no ML at all?

This step builds three non-ML ranking ideas and measures each one against Hacker News's own front-page selections as ground truth.

## What's built

- Three ranking approaches in `src/ranking_service/impl_handrolled.py`:
  1. Rank by upvotes (popularity)
  2. Rank by upvotes within a cohort (user interest group)
  3. HN-style decay formula: `(points - 1) / (age_hours + 2) ^ 1.8`
- `data/fetch_live.py` — pulls ~5K HN stories from the Algolia API
- `data/hn_stories_snapshot.jsonl` — committed snapshot for reproducibility

## No Docker needed

This step runs entirely from the committed JSONL snapshot. No services required.

## Key concepts

- The HN formula's `(P-1)` removes the submitter's automatic upvote
- Dividing by age ensures fresh stories compete with established ones
- Front-page match (63% for the decay formula vs 17% for raw points) is a concrete way to measure ranking quality without a labelled dataset

## What's still missing

Every user gets the same list. The formula reads `points` and `age` — the `user` argument exists but is never used. The Candidate Generators step fixes the first half of that.
