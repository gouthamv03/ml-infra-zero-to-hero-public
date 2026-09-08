# Candidate Generators

The same list for every user isn't personalization. This step builds four candidate generators — each finding stories a specific user is likely to care about — before the ranker scores them.

## What's built

Four generators, each implementing the `CandidateGenerator` interface:

| Generator | How it finds candidates |
|---|---|
| Popularity | Top-N by upvotes — universal signal |
| Keyword | Stories whose title contains one of the user's interest words |
| Semantic | Cosine similarity between story embeddings and user interest embeddings |
| Exploration | Random sample from low-points long-tail stories |

Supporting code:
- `src/ranking_service/encoder.py` — in-memory sentence encoder using fastembed
- Story embeddings generated from the snapshot and queried via cosine similarity

## No Docker needed

Embeddings run in-memory against the 5K snapshot. No services required.

## Key concepts

- Candidate generators and encoders are separate layers — generators decide *what* to retrieve; the encoder decides *how* to represent meaning
- In-memory cosine similarity works fine at 5K stories; at millions you need a vector DB (the Storage step)
- Running all four and merging gives breadth (popularity, exploration) and depth (keyword, semantic)

## What's still missing

The ranker is still the HN decay formula — it never reads the user. Running all four generators and merging produces 500+ candidates, but popularity candidates dominate. A ranker that scores based on who the user is comes in the Ranker step. First, the Storage step replaces the in-memory generators with production-scale backends.
