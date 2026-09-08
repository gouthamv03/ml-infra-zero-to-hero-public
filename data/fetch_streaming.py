"""
Stream new HN stories from the Firebase real-time API and push to Kafka.
Introduced in Part 4.

Usage:
    python3 data/fetch_streaming.py --kafka-broker localhost:9092 --topic hn-stories
"""
import argparse
import json
import urllib.request


HN_FIREBASE = "https://hacker-news.firebaseio.com/v0"


def get_new_story_ids(n: int = 100) -> list:
    url = f"{HN_FIREBASE}/newstories.json"
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.loads(resp.read())[:n]


def get_story(story_id: int) -> dict:
    url = f"{HN_FIREBASE}/item/{story_id}.json"
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.loads(resp.read()) or {}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--kafka-broker", default="localhost:9092")
    parser.add_argument("--topic", default="hn-stories")
    parser.add_argument("--n", type=int, default=100, help="Stories to stream per poll")
    args = parser.parse_args()

    # kafka-python is only installed from Part 4 onward
    try:
        from kafka import KafkaProducer  # type: ignore
    except ImportError:
        raise SystemExit("Install kafka-python: pip install kafka-python")

    producer = KafkaProducer(
        bootstrap_servers=args.kafka_broker,
        value_serializer=lambda v: json.dumps(v).encode(),
    )

    story_ids = get_new_story_ids(args.n)
    for sid in story_ids:
        story = get_story(sid)
        if story:
            producer.send(args.topic, story)
            print(f"Sent story {sid}: {story.get('title', '')[:60]}")

    producer.flush()
    print(f"Done. Sent {len(story_ids)} stories to {args.topic}")


if __name__ == "__main__":
    main()
