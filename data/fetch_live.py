"""
Fetch recent stories from the HN Algolia API and write to stdout as JSONL.

Usage:
    python3 data/fetch_live.py --n 5000 > data/hn_stories_snapshot.jsonl
    python3 data/fetch_live.py --n 100  # quick test
"""
import argparse
import json
import sys
import time
import urllib.request


HN_API = "https://hn.algolia.com/api/v1/search_by_date"
FIELDS = ("title", "url", "points", "author", "created_at", "num_comments")

# Algolia caps pagination at 1000 results per query (page * hitsPerPage <= 1000).
# To pull more, we window by created_at_i: fetch the newest 1000, note the oldest
# timestamp in that batch, then ask for everything older and repeat.
MAX_PER_WINDOW = 1000


def fetch_page(page: int, before_ts: int = None, hits_per_page: int = 200) -> dict:
    url = f"{HN_API}?tags=story&hitsPerPage={hits_per_page}&page={page}"
    if before_ts is not None:
        url += f"&numericFilters=created_at_i<{before_ts}"
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.loads(resp.read())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=5000, help="Number of stories to fetch")
    args = parser.parse_args()

    fetched = 0
    before_ts = None
    seen_ids = set()

    while fetched < args.n:
        window_fetched = 0
        page = 0
        oldest_ts = None

        while fetched < args.n and window_fetched < MAX_PER_WINDOW:
            data = fetch_page(page, before_ts=before_ts)
            hits = data.get("hits", [])
            if not hits:
                break
            for hit in hits:
                if fetched >= args.n:
                    break
                story_id = hit.get("objectID")
                if story_id in seen_ids:
                    continue
                seen_ids.add(story_id)
                story = {k: hit.get(k) for k in FIELDS}
                story["id"] = story_id
                tags = hit.get("_tags") or []
                story["is_ask_hn"] = "ask_hn" in tags
                story["is_show_hn"] = "show_hn" in tags
                story["is_front_page"] = "front_page" in tags
                print(json.dumps(story))
                fetched += 1
                window_fetched += 1
                oldest_ts = hit.get("created_at_i")
            page += 1
            time.sleep(0.1)

        if oldest_ts is None:
            break
        before_ts = oldest_ts

    print(f"Fetched {fetched} stories", file=sys.stderr)


if __name__ == "__main__":
    main()
