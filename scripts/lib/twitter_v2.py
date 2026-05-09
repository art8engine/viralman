"""Twitter v2 API client with auto-refreshing OAuth2 user-context bearer.

Why this module: post_twitter.py and twitter_reply.py both have to (a) make
v2 calls with a `TWITTER_OAUTH2_BEARER`, (b) refresh on 401 using the stored
refresh token + client credentials, (c) persist the rotated bearer/refresh
back into ~/.viralman/.env. They previously kept two near-identical copies of
this dance — including duplicate exception classes named the same. This
module is the single seam.

Public surface:

  request(creds, method, path_or_url, *, json=None) -> dict
      Generic HTTP. Adds the bearer, refreshes once on 401, persists rotated
      tokens, then retries.

  post_tweet(creds, *, text, in_reply_to_tweet_id=None) -> tweet_id (str)
      Convenience wrapper used by both the thread-posting path in
      post_twitter.py and the reply path in twitter_reply.py.

  TwitterAuthError    — 401 even after refresh (or refresh impossible).
  TwitterApiError     — any other v2/network failure.

Design notes:

- creds is a plain dict (the project's universal cred shape). On refresh we
  mutate it in place AND call save_many() so future calls see the rotation.
- search query construction stays in twitter_reply.py since it's caller-
  specific (lang/retweet/keyword OR-ing). This module only owns auth + HTTP.
- The OAuth1 (tweepy) path is unrelated and stays in post_twitter.py.
"""

from __future__ import annotations

import base64
import json as _json
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

from creds import save_many


API_ROOT = "https://api.twitter.com"
V2_TWEETS_URL = f"{API_ROOT}/2/tweets"
V2_TOKEN_URL = f"{API_ROOT}/2/oauth2/token"


class TwitterAuthError(Exception):
    """Bearer is missing/expired and refresh did not produce a working token."""


class TwitterApiError(Exception):
    """Non-401 API or network failure from a v2 endpoint."""


def _resolve_url(path_or_url: str) -> str:
    if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
        return path_or_url
    if not path_or_url.startswith("/"):
        path_or_url = "/" + path_or_url
    return f"{API_ROOT}{path_or_url}"


def _send(method: str, url: str, bearer: str,
          *, json: Optional[Dict[str, Any]] = None,
          timeout: int = 15) -> Dict[str, Any]:
    """Single HTTP attempt. Raises TwitterAuthError on 401, TwitterApiError on
    everything else; returns the parsed JSON body on 2xx."""
    headers = {"Authorization": f"Bearer {bearer}"}
    data: Optional[bytes] = None
    if json is not None:
        data = _json.dumps(json).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return _json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = (e.read() or b"").decode(errors="replace")[:300]
        if e.code == 401:
            raise TwitterAuthError(f"401 {body}") from e
        raise TwitterApiError(f"{e.code} {body}") from e
    except Exception as e:
        raise TwitterApiError(f"network: {e}") from e


def _refresh_token(creds: Dict[str, str]) -> Optional[str]:
    """Refresh the bearer using the stored refresh token + client credentials.

    On success: mutates `creds` in place, persists via save_many, returns the
    new bearer. On any failure (missing refresh creds, refresh HTTP error,
    response without access_token): returns None and logs to stderr."""
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
            tok = _json.loads(resp.read())
    except urllib.error.HTTPError as e:
        err_body = (e.read() or b"").decode(errors="replace")[:200]
        print(f"WARN: oauth2 refresh failed: {e.code} {err_body}",
              file=sys.stderr)
        return None
    except Exception as e:
        print(f"WARN: oauth2 refresh network failure: {e}", file=sys.stderr)
        return None

    new_bearer = tok.get("access_token")
    new_refresh = tok.get("refresh_token")
    if not new_bearer:
        return None

    to_save: Dict[str, str] = {"TWITTER_OAUTH2_BEARER": new_bearer}
    if new_refresh and new_refresh != rt:
        to_save["TWITTER_OAUTH2_REFRESH"] = new_refresh
    try:
        save_many(to_save)
    except Exception as e:
        print(f"WARN: persisting rotated tokens failed: {e}", file=sys.stderr)

    creds.update(to_save)
    return new_bearer


def request(creds: Dict[str, str], method: str, path_or_url: str,
            *, json: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Make a v2 call with the user-context bearer in `creds`. On 401, refresh
    once and retry. Returns the parsed JSON response."""
    bearer = creds.get("TWITTER_OAUTH2_BEARER")
    if not bearer:
        raise TwitterAuthError("TWITTER_OAUTH2_BEARER missing — log in via the dashboard first")

    url = _resolve_url(path_or_url)
    try:
        return _send(method, url, bearer, json=json)
    except TwitterAuthError:
        new_bearer = _refresh_token(creds)
        if not new_bearer:
            raise TwitterAuthError("oauth2 401 and refresh failed")
        return _send(method, url, new_bearer, json=json)


def post_tweet(creds: Dict[str, str], *, text: str,
               in_reply_to_tweet_id: Optional[str] = None) -> str:
    """POST /2/tweets and return the new tweet id. Raises TwitterAuthError or
    TwitterApiError on failure."""
    payload: Dict[str, Any] = {"text": text}
    if in_reply_to_tweet_id:
        payload["reply"] = {"in_reply_to_tweet_id": in_reply_to_tweet_id}
    result = request(creds, "POST", "/2/tweets", json=payload)
    tid = (result.get("data") or {}).get("id")
    if not tid:
        raise TwitterApiError(f"no id in response: {result}")
    return str(tid)
