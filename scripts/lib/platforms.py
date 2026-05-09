"""Per-platform credentials registry — single source of truth for which
keys each platform needs and how to live-check them.

Why this exists: the same fact ("Twitter needs OAuth2 bearer OR OAuth1
4-key", "Reddit needs username + password + client id + secret", …) used
to live in four places: dashboard/api.py's CREDS_BY_PLATFORM dict,
scripts/check_creds.py's per-platform check_* functions, and each
scripts/post_*.py's require() call. Adding a new platform meant touching
all four; adding a new auth alternative (e.g. Twitter OAuth2 alongside
OAuth1) silently failed to propagate to the dashboard status.

A `PlatformSpec` is the deepened module:

- `required_groups` is a list of key groups (OR-of-AND). A platform is
  "configured" iff at least one group is fully present in creds. Most
  platforms have one group; Twitter has two (OAuth2 bearer, OAuth1
  4-key).
- `check_fn(creds) -> int` is the live identity check (prints
  '<platform> OK — <identity>' or 'ERROR: …' and returns 0 / 1 / 2 per
  the legacy check_creds.py exit-code contract). Optional — platforms
  without a real API just leave it None.

Public surface:

- `PLATFORMS` — registry by name.
- `is_configured(spec, creds)`, `present_keys(spec, creds)`,
  `missing_keys(spec, creds)` — three queries used by dashboard status,
  CLI guards, and `require_configured`.
- `require_configured(name, creds)` — the spec-aware replacement for
  the legacy `creds.require(creds, [list], name)` pattern.

Adding a new platform = one PLATFORMS entry. Adding an auth alternative
to an existing platform = one extra entry in `required_groups`.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional


@dataclass(frozen=True)
class PlatformSpec:
    name: str
    required_groups: List[List[str]]
    check_fn: Optional[Callable[[Dict[str, str]], int]] = None


# --------------------------------------------------------------------------- #
# Queries                                                                     #
# --------------------------------------------------------------------------- #


def is_configured(spec: PlatformSpec, creds: Dict[str, str]) -> bool:
    """True iff at least one required_group is fully present in creds."""
    if not spec.required_groups:
        return False
    return any(all(creds.get(k) for k in group)
               for group in spec.required_groups)


def present_keys(spec: PlatformSpec, creds: Dict[str, str]) -> List[str]:
    """All keys (from any group) that are present in creds, deduped, in
    declaration order."""
    seen: set = set()
    out: List[str] = []
    for group in spec.required_groups:
        for k in group:
            if k not in seen and creds.get(k):
                seen.add(k)
                out.append(k)
    return out


def missing_keys(spec: PlatformSpec, creds: Dict[str, str]) -> List[str]:
    """Keys missing from the closest-to-satisfied group. Empty when any group
    is fully present. When no key is present at all, returns the first group
    (the natural starter set)."""
    if is_configured(spec, creds):
        return []
    if not spec.required_groups:
        return []
    best_group = max(spec.required_groups,
                     key=lambda g: sum(1 for k in g if creds.get(k)))
    return [k for k in best_group if not creds.get(k)]


def require_configured(name: str, creds: Dict[str, str]) -> None:
    """Raise CredsError if `name` is not configured. Spec-aware replacement
    for the legacy `creds.require(creds, [list], name)` pattern."""
    spec = PLATFORMS[name]
    if not is_configured(spec, creds):
        # Imported lazily so this module can be loaded without scripts/lib on
        # sys.path (e.g. by tests that only need the queries).
        from creds import CredsError
        raise CredsError(
            f"{name}: missing creds {missing_keys(spec, creds)}. "
            f"Run scripts/setup.sh to configure."
        )


# --------------------------------------------------------------------------- #
# Live identity checks                                                        #
# --------------------------------------------------------------------------- #


def _check_reddit(creds: Dict[str, str]) -> int:
    try:
        import praw  # type: ignore
    except ImportError:
        print("ERROR: praw not installed. Run: pip install praw",
              file=sys.stderr)
        return 2

    user_agent = creds.get(
        "REDDIT_USER_AGENT", "viralman/0.1.0 by " + creds["REDDIT_USERNAME"])
    try:
        reddit = praw.Reddit(
            client_id=creds["REDDIT_CLIENT_ID"],
            client_secret=creds["REDDIT_CLIENT_SECRET"],
            username=creds["REDDIT_USERNAME"],
            password=creds["REDDIT_PASSWORD"],
            user_agent=user_agent,
        )
        me = reddit.user.me()
        if me is None:
            print("ERROR: reddit returned no user; creds likely wrong",
                  file=sys.stderr)
            return 1
        print(f"reddit OK — u/{me.name}")
        return 0
    except Exception as e:
        print(f"ERROR: reddit auth failed: {e}", file=sys.stderr)
        return 1


def _check_twitter(creds: Dict[str, str]) -> int:
    """Prefer the OAuth2 bearer when available — it's what the dashboard sets
    up via PKCE and what post_via_oauth2 / twitter_reply use. Fall back to
    OAuth1 (tweepy) only when no OAuth2 bearer is configured."""
    if creds.get("TWITTER_OAUTH2_BEARER"):
        try:
            import twitter_v2
        except ImportError as e:
            print(f"ERROR: twitter_v2 import failed: {e}", file=sys.stderr)
            return 2
        try:
            result = twitter_v2.request(creds, "GET", "/2/users/me")
        except twitter_v2.TwitterAuthError as e:
            print(f"ERROR: twitter oauth2 auth failed: {e}", file=sys.stderr)
            return 1
        except twitter_v2.TwitterApiError as e:
            print(f"ERROR: twitter oauth2 request failed: {e}",
                  file=sys.stderr)
            return 1
        user = result.get("data") or {}
        print(f"twitter OK — @{user.get('username', '?')} "
              f"(id={user.get('id', '?')})")
        return 0

    try:
        import tweepy  # type: ignore
    except ImportError:
        print("ERROR: tweepy not installed. Run: pip install tweepy",
              file=sys.stderr)
        return 2
    try:
        client = tweepy.Client(
            consumer_key=creds["TWITTER_API_KEY"],
            consumer_secret=creds["TWITTER_API_SECRET"],
            access_token=creds["TWITTER_ACCESS_TOKEN"],
            access_token_secret=creds["TWITTER_ACCESS_SECRET"],
        )
        resp = client.get_me(user_auth=True)
        if not resp or not resp.data:
            print("ERROR: twitter returned no user; creds likely wrong",
                  file=sys.stderr)
            return 1
        u = resp.data
        print(f"twitter OK — @{u.username} (id={u.id})")
        return 0
    except Exception as e:
        print(f"ERROR: twitter auth failed: {e}", file=sys.stderr)
        return 1


def _check_linkedin(creds: Dict[str, str]) -> int:
    try:
        import requests  # type: ignore
    except ImportError:
        print("ERROR: requests not installed. Run: pip install requests",
              file=sys.stderr)
        return 2
    headers = {
        "Authorization": f"Bearer {creds['LINKEDIN_ACCESS_TOKEN']}",
        "X-Restli-Protocol-Version": "2.0.0",
    }
    try:
        r = requests.get("https://api.linkedin.com/v2/userinfo",
                         headers=headers, timeout=15)
    except Exception as e:
        print(f"ERROR: linkedin request failed: {e}", file=sys.stderr)
        return 1
    if r.status_code != 200:
        print(f"ERROR: linkedin {r.status_code}: {r.text}", file=sys.stderr)
        return 1
    data = r.json()
    name = (data.get("name")
            or f"{data.get('given_name', '')} {data.get('family_name', '')}".strip())
    sub = data.get("sub", "")
    print(f"linkedin OK — {name} (sub={sub})")
    if not creds.get("LINKEDIN_PERSON_URN") and sub:
        print(f"hint: set LINKEDIN_PERSON_URN=urn:li:person:{sub}",
              file=sys.stderr)
    return 0


# --------------------------------------------------------------------------- #
# Registry                                                                    #
# --------------------------------------------------------------------------- #


PLATFORMS: Dict[str, PlatformSpec] = {
    "twitter": PlatformSpec(
        name="twitter",
        required_groups=[
            ["TWITTER_OAUTH2_BEARER"],
            ["TWITTER_API_KEY", "TWITTER_API_SECRET",
             "TWITTER_ACCESS_TOKEN", "TWITTER_ACCESS_SECRET"],
        ],
        check_fn=_check_twitter,
    ),
    "reddit": PlatformSpec(
        name="reddit",
        required_groups=[
            ["REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET",
             "REDDIT_USERNAME", "REDDIT_PASSWORD"],
        ],
        check_fn=_check_reddit,
    ),
    "linkedin": PlatformSpec(
        name="linkedin",
        required_groups=[
            ["LINKEDIN_ACCESS_TOKEN", "LINKEDIN_PERSON_URN"],
        ],
        check_fn=_check_linkedin,
    ),
    "github": PlatformSpec(
        name="github",
        required_groups=[["GITHUB_TOKEN"]],
    ),
    "smtp": PlatformSpec(
        name="smtp",
        required_groups=[["SMTP_HOST", "SMTP_USER",
                          "SMTP_PASSWORD", "SMTP_FROM"]],
    ),
    "claude": PlatformSpec(
        name="claude",
        required_groups=[["ANTHROPIC_API_KEY"]],
    ),
    "openai": PlatformSpec(
        name="openai",
        required_groups=[["OPENAI_API_KEY"]],
    ),
    "gemini": PlatformSpec(
        name="gemini",
        required_groups=[["GEMINI_API_KEY"]],
    ),
}
