#!/usr/bin/env python3
"""Post to X (Twitter).

Auth preference (first match wins):
  1. OAuth 2.0 Bearer (TWITTER_OAUTH2_BEARER) — set by the dashboard PKCE flow.
     On 401 we refresh via TWITTER_OAUTH2_REFRESH + CLIENT_ID/SECRET and persist
     the rotated pair, then retry once.
  2. OAuth 1.0a 4-key (TWITTER_API_KEY/SECRET + TWITTER_ACCESS_TOKEN/SECRET) —
     legacy path for users who already configured it. No refresh.
  3. Compose URL (`https://twitter.com/intent/tweet?text=...`) — no creds
     needed; opens browser for the user to one-click send.

Usage:
  ./scripts/post_twitter.py --body -
"""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))

from creds import load as load_creds, read_body_from_stdin_or_arg, CredsError  # noqa: E402
from compose_urls import twitter_intent  # noqa: E402


V2_TWEETS_URL = "https://api.twitter.com/2/tweets"
V2_TOKEN_URL = "https://api.twitter.com/2/oauth2/token"


class _OAuth2Unauthorized(Exception):
    pass


class _V2PostError(Exception):
    pass


def _v2_post_tweet(bearer: str, payload: dict) -> str:
    req = urllib.request.Request(
        V2_TWEETS_URL,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {bearer}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise _OAuth2Unauthorized() from e
        raise _V2PostError(f"{e.code} {e.read().decode(errors='replace')[:200]}") from e

    tid = (data.get("data") or {}).get("id")
    if not tid:
        raise _V2PostError(f"no id in response: {data}")
    return tid


def _refresh_oauth2(creds: dict) -> str | None:
    """Refresh TWITTER_OAUTH2_BEARER using the refresh token. Persists rotated
    tokens via save_creds.py --stdin (keeps secrets out of argv). Returns the
    new bearer on success, None otherwise."""
    rt = creds.get("TWITTER_OAUTH2_REFRESH")
    cid = creds.get("TWITTER_OAUTH2_CLIENT_ID")
    csec = creds.get("TWITTER_OAUTH2_CLIENT_SECRET")
    if not rt or not cid or not csec:
        return None

    body = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": rt,
        "client_id": cid,
    }).encode()
    basic = base64.b64encode(f"{cid}:{csec}".encode()).decode()
    req = urllib.request.Request(
        V2_TOKEN_URL,
        data=body,
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            tok = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(
            f"WARN: oauth2 refresh failed: {e.code} {e.read().decode(errors='replace')[:200]}",
            file=sys.stderr,
        )
        return None
    except Exception as e:
        print(f"WARN: oauth2 refresh network failure: {e}", file=sys.stderr)
        return None

    new_bearer = tok.get("access_token")
    new_refresh = tok.get("refresh_token")
    if not new_bearer:
        return None

    saver = Path(__file__).parent / "save_creds.py"
    subprocess.run(
        [sys.executable, str(saver), "--stdin", "TWITTER_OAUTH2_BEARER"],
        input=new_bearer, text=True, check=False, timeout=10,
    )
    if new_refresh:
        subprocess.run(
            [sys.executable, str(saver), "--stdin", "TWITTER_OAUTH2_REFRESH"],
            input=new_refresh, text=True, check=False, timeout=10,
        )

    return new_bearer


def post_via_oauth2(creds: dict, body: str) -> str | None:
    bearer = creds.get("TWITTER_OAUTH2_BEARER")
    if not bearer:
        return None

    parts = [p.strip() for p in body.split("---") if p.strip()]
    if not parts:
        return None

    handle = creds.get("TWITTER_HANDLE", "i")
    parent_id: str | None = None
    root_id: str | None = None
    refreshed = False

    for tweet in parts:
        payload: dict = {"text": tweet}
        if parent_id:
            payload["reply"] = {"in_reply_to_tweet_id": parent_id}

        try:
            tid = _v2_post_tweet(bearer, payload)
        except _OAuth2Unauthorized:
            if refreshed:
                print("WARN: oauth2 still 401 after refresh", file=sys.stderr)
                return None
            new_bearer = _refresh_oauth2(creds)
            if not new_bearer:
                return None
            bearer = new_bearer
            refreshed = True
            try:
                tid = _v2_post_tweet(bearer, payload)
            except (_OAuth2Unauthorized, _V2PostError) as e:
                print(f"WARN: oauth2 post failed after refresh: {e}", file=sys.stderr)
                return None
        except _V2PostError as e:
            print(f"WARN: oauth2 post failed: {e}", file=sys.stderr)
            return None

        if root_id is None:
            root_id = tid
        parent_id = tid

    return f"https://twitter.com/{handle}/status/{root_id}"


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
    root_id = None
    for tweet in parts:
        resp = client.create_tweet(text=tweet, in_reply_to_tweet_id=parent_id)
        tid = resp.data["id"]
        if root_id is None:
            root_id = tid
        parent_id = tid

    handle = creds.get("TWITTER_HANDLE", "i")
    return f"https://twitter.com/{handle}/status/{root_id}"


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

    api_url = post_via_oauth2(creds, body) or post_via_api(creds, body)
    if api_url:
        print(api_url)
        return 0

    url = post_via_compose(body) if not args.no_open else twitter_intent(body.split("---")[0])
    print(f"DRAFT {url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
