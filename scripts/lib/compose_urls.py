"""Build platform compose-URL fallbacks for when API posting isn't configured."""

from __future__ import annotations

import urllib.parse


def twitter_intent(text: str) -> str:
    encoded = urllib.parse.quote(text, safe="")
    return f"https://twitter.com/intent/tweet?text={encoded}"


def reddit_submit(subreddit: str, title: str, body: str) -> str:
    params = {
        "title": title,
        "text": body,
    }
    qs = urllib.parse.urlencode(params)
    return f"https://www.reddit.com/r/{subreddit}/submit?{qs}"


def linkedin_share(text: str) -> str:
    encoded = urllib.parse.quote(text, safe="")
    return f"https://www.linkedin.com/feed/?shareActive=true&text={encoded}"
