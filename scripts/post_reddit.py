#!/usr/bin/env python3
"""Post to Reddit using PRAW. Reads body from stdin, prints permalink to stdout.

Usage:
  ./scripts/post_reddit.py --subreddit <sub> --title <title> --body -
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))

from creds import load as load_creds, read_body_from_stdin_or_arg, CredsError  # noqa: E402
from platforms import require_configured  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--subreddit", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--body", default="-")
    p.add_argument("--flair", default=None)
    args = p.parse_args()

    try:
        creds = load_creds()
        require_configured("reddit", creds)
        body = read_body_from_stdin_or_arg(args.body)
    except CredsError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    try:
        import praw  # type: ignore
    except ImportError:
        print("ERROR: praw not installed. Run: pip install praw", file=sys.stderr)
        return 2

    user_agent = creds.get("REDDIT_USER_AGENT",
                            "viralman/0.1.0 by " + creds["REDDIT_USERNAME"])

    reddit = praw.Reddit(
        client_id=creds["REDDIT_CLIENT_ID"],
        client_secret=creds["REDDIT_CLIENT_SECRET"],
        username=creds["REDDIT_USERNAME"],
        password=creds["REDDIT_PASSWORD"],
        user_agent=user_agent,
    )

    if len(args.title) > 300:
        print(f"ERROR: title is {len(args.title)} chars, Reddit cap is 300", file=sys.stderr)
        return 2

    try:
        submission = reddit.subreddit(args.subreddit).submit(
            title=args.title,
            selftext=body,
            flair_id=args.flair,
        )
    except Exception as e:
        print(f"ERROR: reddit submit failed: {e}", file=sys.stderr)
        return 1

    url = f"https://www.reddit.com{submission.permalink}"
    print(url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
