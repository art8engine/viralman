#!/usr/bin/env python3
"""Verify credentials by hitting a read-only endpoint on the platform.

Usage:
  ./scripts/check_creds.py --platform reddit
  ./scripts/check_creds.py --platform twitter
  ./scripts/check_creds.py --platform linkedin

Exit codes:
  0 — creds work, identity printed
  1 — creds present but API rejected them
  2 — creds missing or library not installed
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))

from creds import load as load_creds, require, CredsError  # noqa: E402


def check_reddit() -> int:
    try:
        creds = load_creds()
        c = require(
            creds,
            ["REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USERNAME", "REDDIT_PASSWORD"],
            "reddit",
        )
    except CredsError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    try:
        import praw  # type: ignore
    except ImportError:
        print("ERROR: praw not installed. Run: pip install praw", file=sys.stderr)
        return 2

    user_agent = creds.get("REDDIT_USER_AGENT", "viralman/0.1.0 by " + c["REDDIT_USERNAME"])
    try:
        reddit = praw.Reddit(
            client_id=c["REDDIT_CLIENT_ID"],
            client_secret=c["REDDIT_CLIENT_SECRET"],
            username=c["REDDIT_USERNAME"],
            password=c["REDDIT_PASSWORD"],
            user_agent=user_agent,
        )
        me = reddit.user.me()
        if me is None:
            print("ERROR: reddit returned no user; creds likely wrong", file=sys.stderr)
            return 1
        print(f"reddit OK — u/{me.name}")
        return 0
    except Exception as e:
        print(f"ERROR: reddit auth failed: {e}", file=sys.stderr)
        return 1


def check_twitter() -> int:
    try:
        creds = load_creds()
        c = require(
            creds,
            ["TWITTER_API_KEY", "TWITTER_API_SECRET", "TWITTER_ACCESS_TOKEN", "TWITTER_ACCESS_SECRET"],
            "twitter",
        )
    except CredsError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    try:
        import tweepy  # type: ignore
    except ImportError:
        print("ERROR: tweepy not installed. Run: pip install tweepy", file=sys.stderr)
        return 2

    try:
        client = tweepy.Client(
            consumer_key=c["TWITTER_API_KEY"],
            consumer_secret=c["TWITTER_API_SECRET"],
            access_token=c["TWITTER_ACCESS_TOKEN"],
            access_token_secret=c["TWITTER_ACCESS_SECRET"],
        )
        resp = client.get_me(user_auth=True)
        if not resp or not resp.data:
            print("ERROR: twitter returned no user; creds likely wrong", file=sys.stderr)
            return 1
        u = resp.data
        print(f"twitter OK — @{u.username} (id={u.id})")
        return 0
    except Exception as e:
        print(f"ERROR: twitter auth failed: {e}", file=sys.stderr)
        return 1


def check_linkedin() -> int:
    try:
        creds = load_creds()
        c = require(creds, ["LINKEDIN_ACCESS_TOKEN"], "linkedin")
    except CredsError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    try:
        import requests  # type: ignore
    except ImportError:
        print("ERROR: requests not installed. Run: pip install requests", file=sys.stderr)
        return 2

    headers = {
        "Authorization": f"Bearer {c['LINKEDIN_ACCESS_TOKEN']}",
        "X-Restli-Protocol-Version": "2.0.0",
    }
    try:
        r = requests.get("https://api.linkedin.com/v2/userinfo", headers=headers, timeout=15)
    except Exception as e:
        print(f"ERROR: linkedin request failed: {e}", file=sys.stderr)
        return 1

    if r.status_code != 200:
        print(f"ERROR: linkedin {r.status_code}: {r.text}", file=sys.stderr)
        return 1

    data = r.json()
    name = data.get("name") or f"{data.get('given_name','')} {data.get('family_name','')}".strip()
    sub = data.get("sub", "")
    print(f"linkedin OK — {name} (sub={sub})")
    if not creds.get("LINKEDIN_PERSON_URN") and sub:
        print(f"hint: set LINKEDIN_PERSON_URN=urn:li:person:{sub}", file=sys.stderr)
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--platform", required=True, choices=["reddit", "twitter", "linkedin"])
    args = p.parse_args()

    if args.platform == "reddit":
        return check_reddit()
    if args.platform == "twitter":
        return check_twitter()
    if args.platform == "linkedin":
        return check_linkedin()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
