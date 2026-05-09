#!/usr/bin/env python3
"""twitter_reply — find tweets worth replying to, then optionally reply.

Two subcommands:
  find    Search Twitter for tweets matching keywords/query, return candidates.
  reply   Post a reply to a specific tweet ID.

Auth: reuses TWITTER_OAUTH2_BEARER (user context, tweet.read + tweet.write
scopes). On 401 for `find`, attempts to refresh once via the same flow as
post_twitter.py and retries. No legacy OAuth 1.0a fallback for search — v2
recent search requires a v2 bearer.

Streaming: emits JSONL events to stdout so dashboards/agents can render
progress; the final candidates list is also written to a JSON file given
via --out so consumers don't need to parse JSONL.

Usage:
  ./scripts/twitter_reply.py find \
      --query "JVM monitoring without agent" \
      --max-candidates 20 --min-engagement 5 \
      --out /tmp/twitter_candidates.json

  ./scripts/twitter_reply.py reply \
      --tweet-id 1234567890 --body -
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent / "lib"))

from creds import load as load_creds, read_body_from_stdin_or_arg, CredsError  # noqa: E402
import twitter_v2  # noqa: E402

V2_SEARCH_URL = "https://api.twitter.com/2/tweets/search/recent"


def _emit(event: str, **fields: Any) -> None:
    record = {"ts": time.time(), "event": event, **fields}
    sys.stdout.write(json.dumps(record, ensure_ascii=False) + "\n")
    sys.stdout.flush()


# --------------------------------------------------------------------------- #
# find subcommand                                                             #
# --------------------------------------------------------------------------- #


def _build_query(query: Optional[str], keywords: List[str], lang: Optional[str],
                  exclude_retweets: bool) -> str:
    """Build a v2 recent-search query string.

    Keywords are joined OR-style (already-quoted phrases stay literal). The
    caller's free-text query, if given, is wrapped in parens and AND-ed with
    the keyword block. lang and -is:retweet are appended as v2 operators."""
    parts: List[str] = []
    if query and query.strip():
        parts.append(f"({query.strip()})")
    if keywords:
        kw_block = " OR ".join(
            kw if (kw.startswith('"') and kw.endswith('"')) else f'"{kw}"'
            for kw in keywords
        )
        parts.append(f"({kw_block})")
    base = " ".join(parts) if parts else ""
    if exclude_retweets:
        base = f"{base} -is:retweet" if base else "-is:retweet"
    if lang:
        base = f"{base} lang:{lang}"
    return base.strip()


def _candidate_passes(metrics: Dict[str, int], min_engagement: int) -> bool:
    """A tweet 'engages' if likes+retweets+replies+quotes >= min_engagement."""
    total = (metrics.get("like_count", 0)
             + metrics.get("retweet_count", 0)
             + metrics.get("reply_count", 0)
             + metrics.get("quote_count", 0))
    return total >= min_engagement


def _shape_candidate(tweet: Dict[str, Any],
                       authors: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    metrics = tweet.get("public_metrics") or {}
    author = authors.get(tweet.get("author_id") or "") or {}
    handle = author.get("username") or "unknown"
    return {
        "id": tweet.get("id"),
        "text": tweet.get("text", ""),
        "created_at": tweet.get("created_at", ""),
        "author": {
            "id": tweet.get("author_id"),
            "username": handle,
            "name": author.get("name", ""),
            "profile_image_url": author.get("profile_image_url", ""),
        },
        "engagement": {
            "likes": metrics.get("like_count", 0),
            "retweets": metrics.get("retweet_count", 0),
            "replies": metrics.get("reply_count", 0),
            "quotes": metrics.get("quote_count", 0),
            "total": (metrics.get("like_count", 0)
                       + metrics.get("retweet_count", 0)
                       + metrics.get("reply_count", 0)
                       + metrics.get("quote_count", 0)),
        },
        "url": f"https://x.com/{handle}/status/{tweet.get('id')}",
    }


def cmd_find(args: argparse.Namespace) -> int:
    keywords = [k.strip() for k in (args.keywords or "").split(",") if k.strip()]
    query = _build_query(args.query, keywords,
                          args.lang, exclude_retweets=not args.include_retweets)
    if not query:
        _emit("fatal", reason="--query and/or --keywords required")
        return 2

    _emit("find_start", query=query, max_candidates=args.max_candidates,
          min_engagement=args.min_engagement)

    try:
        creds = load_creds()
    except CredsError as e:
        _emit("fatal", reason=str(e))
        return 2

    params = urllib.parse.urlencode({
        "query": query,
        "max_results": min(max(args.max_candidates, 10), 100),
        "tweet.fields": "public_metrics,created_at,author_id,lang",
        "expansions": "author_id",
        "user.fields": "username,name,profile_image_url",
    })
    url = f"{V2_SEARCH_URL}?{params}"

    try:
        data = twitter_v2.request(creds, "GET", url)
    except twitter_v2.TwitterAuthError as e:
        _emit("fatal", reason=str(e))
        return 2
    except twitter_v2.TwitterApiError as e:
        _emit("fatal", reason=f"v2 search failed: {e}")
        return 2

    tweets = data.get("data") or []
    users_by_id = {u["id"]: u for u in (data.get("includes") or {}).get("users", [])}

    candidates: List[Dict[str, Any]] = []
    for t in tweets:
        metrics = t.get("public_metrics") or {}
        if not _candidate_passes(metrics, args.min_engagement):
            continue
        candidates.append(_shape_candidate(t, users_by_id))
        if len(candidates) >= args.max_candidates:
            break

    candidates.sort(key=lambda c: -c["engagement"]["total"])
    _emit("find_done", count=len(candidates))

    if args.out:
        Path(args.out).write_text(
            json.dumps({"query": query, "candidates": candidates},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        _emit("write_done", path=args.out, count=len(candidates))

    print(json.dumps(candidates, ensure_ascii=False, indent=2))
    return 0


# --------------------------------------------------------------------------- #
# reply subcommand                                                            #
# --------------------------------------------------------------------------- #


def cmd_reply(args: argparse.Namespace) -> int:
    try:
        body = read_body_from_stdin_or_arg(args.body)
    except CredsError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    body = body.strip()
    if not body:
        _emit("fatal", reason="empty body")
        return 2
    if len(body) > 280:
        _emit("fatal", reason=f"body is {len(body)} chars, X cap is 280")
        return 2

    try:
        creds = load_creds()
    except CredsError as e:
        _emit("fatal", reason=str(e))
        return 2

    if args.dry_run:
        _emit("reply_dry_run",
              in_reply_to=args.tweet_id, body=body, length=len(body))
        return 0

    _emit("reply_start", in_reply_to=args.tweet_id, length=len(body))

    try:
        new_id = twitter_v2.post_tweet(creds, text=body,
                                         in_reply_to_tweet_id=args.tweet_id)
    except twitter_v2.TwitterAuthError as e:
        _emit("fatal", reason=str(e))
        return 2
    except twitter_v2.TwitterApiError as e:
        _emit("fatal", reason=f"reply failed: {e}")
        return 2

    handle = creds.get("TWITTER_HANDLE", "i")
    url = f"https://x.com/{handle}/status/{new_id}"
    _emit("reply_done", id=new_id, url=url)
    print(url)
    return 0


# --------------------------------------------------------------------------- #
# argparse                                                                    #
# --------------------------------------------------------------------------- #


def main() -> int:
    p = argparse.ArgumentParser(description="twitter_reply — find + reply on X")
    sub = p.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("find", help="Search recent tweets for replyable candidates.")
    f.add_argument("--query", default=None, help="Free-text query string (passed to v2 recent search).")
    f.add_argument("--keywords", default=None,
                    help="Comma-separated keywords. Joined OR-style; quoted phrases stay literal.")
    f.add_argument("--lang", default=None, help="ISO-639-1 lang filter (e.g. 'en', 'ko').")
    f.add_argument("--max-candidates", type=int, default=20, dest="max_candidates")
    f.add_argument("--min-engagement", type=int, default=0, dest="min_engagement",
                    help="Drop tweets below this likes+retweets+replies+quotes total.")
    f.add_argument("--include-retweets", action="store_true", dest="include_retweets",
                    help="By default retweets are excluded; pass this to keep them.")
    f.add_argument("--out", default=None,
                    help="Write candidates JSON to this path (in addition to stdout).")

    r = sub.add_parser("reply", help="Post a reply to a tweet ID.")
    r.add_argument("--tweet-id", required=True, dest="tweet_id")
    r.add_argument("--body", default="-", help="Reply body. '-' reads from stdin.")
    r.add_argument("--dry-run", action="store_true", dest="dry_run")

    args = p.parse_args()
    if args.cmd == "find":
        return cmd_find(args)
    if args.cmd == "reply":
        return cmd_reply(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
