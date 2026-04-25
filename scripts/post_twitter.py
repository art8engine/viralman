#!/usr/bin/env python3
"""Post to X (Twitter). If TWITTER_BEARER + access tokens are set, post via API.
Otherwise build a `https://twitter.com/intent/tweet?text=...` URL, open it in
the browser, and print it to stdout for the user to one-click send.

Usage:
  ./scripts/post_twitter.py --body -
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))

from creds import load as load_creds, read_body_from_stdin_or_arg, CredsError  # noqa: E402
from compose_urls import twitter_intent  # noqa: E402


def post_via_api(creds: dict, body: str) -> str | None:
    needed = ["TWITTER_API_KEY", "TWITTER_API_SECRET", "TWITTER_ACCESS_TOKEN", "TWITTER_ACCESS_SECRET"]
    if not all(creds.get(k) for k in needed):
        return None

    try:
        import tweepy  # type: ignore
    except ImportError:
        print("WARN: tweepy not installed; falling back to compose URL", file=sys.stderr)
        return None

    client = tweepy.Client(
        consumer_key=creds["TWITTER_API_KEY"],
        consumer_secret=creds["TWITTER_API_SECRET"],
        access_token=creds["TWITTER_ACCESS_TOKEN"],
        access_token_secret=creds["TWITTER_ACCESS_SECRET"],
    )

    parts = [p.strip() for p in body.split("---") if p.strip()]
    if not parts:
        return None

    parent_id = None
    last_id = None
    for tweet in parts:
        resp = client.create_tweet(text=tweet, in_reply_to_tweet_id=parent_id)
        last_id = resp.data["id"]
        if parent_id is None:
            parent_id = last_id
        else:
            parent_id = last_id

    handle = creds.get("TWITTER_HANDLE", "i")
    return f"https://twitter.com/{handle}/status/{parent_id}"


def post_via_compose(body: str) -> str:
    parts = [p.strip() for p in body.split("---") if p.strip()]
    first = parts[0] if parts else body
    url = twitter_intent(first)
    try:
        subprocess.run(["open", url], check=False)
    except FileNotFoundError:
        pass
    return url


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--body", default="-")
    p.add_argument("--no-open", action="store_true", help="don't open the compose URL in a browser")
    args = p.parse_args()

    try:
        body = read_body_from_stdin_or_arg(args.body)
    except CredsError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    try:
        creds = load_creds()
    except CredsError:
        creds = {}

    if len(body.split("---")[0]) > 280:
        print(
            f"ERROR: first tweet is {len(body.split('---')[0])} chars, X cap is 280",
            file=sys.stderr,
        )
        return 2

    api_url = post_via_api(creds, body)
    if api_url:
        print(api_url)
        return 0

    url = post_via_compose(body) if not args.no_open else twitter_intent(body.split("---")[0])
    print(f"DRAFT {url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
