"""GitHub helpers for the gitmail flow.

Three responsibilities:
  1. analyse_project(text)   -> {"keywords": [...], "topics": [...]}
     Pure-text heuristic; the LLM-driven version lives in llm_compose.
  2. search_similar_repos()  -> list[{full_name, stars, topics, html_url}]
     Uses the GitHub Search API.
  3. iter_stargazers()       -> yields {login, html_url}
     Paginated; respects max_users.

Optional follow-up: resolve_user_email(login) tries (in order)
  - GET /users/<login>           public profile email
  - GET /users/<login>/events    look at PushEvent commits for author.email
                                 (skipping the noreply@github.com mask)

GITHUB_TOKEN is read from ~/.viralman/.env via creds.load(); a missing token
falls back to anonymous (60 req/h) which is enough for tiny runs only.
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Iterator, List, Optional

GH_API = "https://api.github.com"
NOREPLY_RE = re.compile(r"@users\.noreply\.github\.com$", re.IGNORECASE)


# --------------------------------------------------------------------------- #
# Profile data shape returned by bulk_resolve_profile_data                    #
# --------------------------------------------------------------------------- #


PROFILE_KEYS = (
    "email", "name", "bio", "is_hireable", "created_at",
    "followers", "following", "public_repos",
)

# The subset that recipient records carry into compose/send (everything except
# `is_hireable`, plus `email`/`name` which already live on the recipient).
PROFILE_EXTRAS_KEYS = ("followers", "following", "public_repos",
                       "created_at", "bio")


def _empty_profile() -> Dict[str, Optional[object]]:
    """Default shape used when GraphQL fails for a login."""
    return {k: None for k in PROFILE_KEYS}


# --------------------------------------------------------------------------- #
# Stdlib HTTP helper                                                          #
# --------------------------------------------------------------------------- #


def _request(
    path: str,
    *,
    token: Optional[str] = None,
    params: Optional[Dict[str, str]] = None,
    timeout: int = 30,
) -> tuple[int, Dict[str, str], bytes]:
    url = path if path.startswith("http") else f"{GH_API}{path}"
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "viralman-gitmail/0.2")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers or {}), e.read() or b""


def _json(path: str, **kw) -> tuple[int, Dict[str, str], object]:
    status, headers, body = _request(path, **kw)
    try:
        data = json.loads(body.decode("utf-8")) if body else None
    except json.JSONDecodeError:
        data = None
    return status, headers, data


def _respect_rate_limit(headers: Dict[str, str]) -> None:
    remaining = headers.get("x-ratelimit-remaining") or headers.get("X-RateLimit-Remaining")
    reset = headers.get("x-ratelimit-reset") or headers.get("X-RateLimit-Reset")
    if remaining and int(remaining) <= 1 and reset:
        wait = max(0, int(reset) - int(time.time()) + 2)
        if wait > 0:
            print(f"github: rate limit hit, sleeping {wait}s", file=sys.stderr)
            time.sleep(min(wait, 120))


# --------------------------------------------------------------------------- #
# Project analysis (cheap heuristic; llm_compose has a smarter version)       #
# --------------------------------------------------------------------------- #


_KEYWORD_HINTS = [
    # languages
    "python", "go", "golang", "rust", "typescript", "javascript", "java", "ruby",
    "elixir", "kotlin", "swift", "c++", "scala", "php",
    # infra / cloud
    "kubernetes", "k8s", "docker", "terraform", "aws", "gcp", "azure", "serverless",
    "lambda", "cloudflare", "edge",
    # data
    "postgres", "mysql", "redis", "kafka", "spark", "duckdb", "clickhouse",
    "snowflake", "elasticsearch",
    # ai / ml
    "llm", "openai", "anthropic", "claude", "gpt", "gemini", "rag", "embedding",
    "vector", "agent", "prompt", "fine-tune", "fine-tuning", "transformer",
    # web / app
    "react", "nextjs", "svelte", "vue", "tauri", "electron", "fastapi", "flask",
    "django", "rails", "express",
    # categories
    "cli", "tui", "scraper", "crawler", "parser", "compiler", "linter",
    "autoscaler", "observability", "monitoring", "logging", "tracing",
    "auth", "authn", "authz", "oauth", "rbac", "queue", "scheduler", "etl",
]


def analyse_project(text: str) -> Dict[str, List[str]]:
    """Cheap keyword extraction. Returns keywords + likely GitHub topics."""
    t = text.lower()
    found: List[str] = []
    for kw in _KEYWORD_HINTS:
        if re.search(rf"\b{re.escape(kw)}\b", t):
            if kw not in found:
                found.append(kw)
    # Topic-ify a few aliases
    topics: List[str] = []
    for kw in found:
        if kw == "k8s":
            topics.append("kubernetes")
        elif kw == "golang":
            topics.append("go")
        else:
            topics.append(kw.replace(" ", "-"))
    return {"keywords": found, "topics": list(dict.fromkeys(topics))}


# --------------------------------------------------------------------------- #
# Similar-repo discovery                                                      #
# --------------------------------------------------------------------------- #


def search_similar_repos(
    *,
    topics: List[str],
    keywords: List[str] | None = None,
    min_stars: int = 100,
    limit: int = 20,
    token: Optional[str] = None,
    exclude_full_names: Optional[set[str]] = None,
) -> List[Dict[str, object]]:
    """Return up to `limit` repos matching the given topics, sorted by stars desc."""
    if not topics and not keywords:
        return []

    parts: List[str] = []
    for t in topics[:5]:
        parts.append(f"topic:{t}")
    for kw in (keywords or [])[:3]:
        if " " in kw:
            parts.append(f'"{kw}"')
        else:
            parts.append(kw)
    parts.append(f"stars:>={min_stars}")
    q = " ".join(parts)

    out: List[Dict[str, object]] = []
    seen: set[str] = set(exclude_full_names or [])
    page = 1
    per_page = min(limit, 100)
    while len(out) < limit and page <= 10:
        status, headers, data = _json(
            "/search/repositories",
            token=token,
            params={
                "q": q,
                "sort": "stars",
                "order": "desc",
                "per_page": str(per_page),
                "page": str(page),
            },
        )
        if status != 200 or not isinstance(data, dict):
            break
        items = data.get("items") or []
        if not items:
            break
        for it in items:
            full = it.get("full_name")
            if not full or full in seen:
                continue
            seen.add(full)
            out.append({
                "full_name": full,
                "stars": it.get("stargazers_count", 0),
                "topics": it.get("topics", []),
                "html_url": it.get("html_url", ""),
                "description": it.get("description") or "",
            })
            if len(out) >= limit:
                break
        _respect_rate_limit(headers)
        page += 1
    return out


# --------------------------------------------------------------------------- #
# Stargazer iteration                                                         #
# --------------------------------------------------------------------------- #


def iter_stargazers(
    full_name: str,
    *,
    max_users: int = 1000,
    token: Optional[str] = None,
) -> Iterator[Dict[str, object]]:
    """Yield up to `max_users` users who starred `full_name`."""
    page = 1
    yielded = 0
    while yielded < max_users:
        per_page = min(100, max_users - yielded)
        status, headers, data = _json(
            f"/repos/{full_name}/stargazers",
            token=token,
            params={"per_page": str(per_page), "page": str(page)},
        )
        if status != 200 or not isinstance(data, list) or not data:
            break
        for u in data:
            login = u.get("login")
            if not login:
                continue
            yield {"login": login, "html_url": u.get("html_url", "")}
            yielded += 1
            if yielded >= max_users:
                break
        _respect_rate_limit(headers)
        if len(data) < per_page:
            break
        page += 1


# --------------------------------------------------------------------------- #
# Email resolution                                                            #
# --------------------------------------------------------------------------- #


def resolve_user_email(
    login: str,
    *,
    token: Optional[str] = None,
    use_events: bool = True,
    pre_fetched_name: Optional[str] = None,
) -> Optional[str]:
    """Best-effort. Returns None if no plausible email is found.

    `pre_fetched_name` skips the REST profile GET when the caller already
    knows the user's display name (e.g. from a prior GraphQL query that
    returned `null` email). Saves 1 REST request per fallback candidate.
    """
    if pre_fetched_name is None:
        status, headers, data = _json(f"/users/{login}", token=token)
        _respect_rate_limit(headers)
        if status == 200 and isinstance(data, dict):
            email = data.get("email")
            if email and not NOREPLY_RE.search(email):
                return email
            name = data.get("name") or login
        else:
            name = login
    else:
        name = pre_fetched_name or login

    if not use_events:
        return None

    status, headers, data = _json(
        f"/users/{login}/events/public",
        token=token,
        params={"per_page": "30"},
    )
    _respect_rate_limit(headers)
    if status != 200 or not isinstance(data, list):
        return None

    for ev in data:
        if ev.get("type") != "PushEvent":
            continue
        payload = ev.get("payload") or {}
        for commit in payload.get("commits") or []:
            author = commit.get("author") or {}
            email = author.get("email")
            author_name = author.get("name") or ""
            if not email or NOREPLY_RE.search(email):
                continue
            # A commit is the user's only if the author name roughly matches
            if name and author_name and (
                author_name.lower() == name.lower()
                or author_name.lower() == login.lower()
            ):
                return email
            if author_name.lower() == login.lower():
                return email
    return None


# --------------------------------------------------------------------------- #
# GraphQL bulk lookup                                                          #
# --------------------------------------------------------------------------- #


GRAPHQL_URL = f"{GH_API}/graphql"


def bulk_resolve_profile_data(
    logins: List[str],
    *,
    token: Optional[str] = None,
    batch_size: int = 100,
    timeout: int = 30,
) -> Dict[str, Dict[str, Optional[str]]]:
    """Fetch public profile {email, name} for many GitHub logins via GraphQL.

    GraphQL has a 5,000-point/hr budget that's separate from REST's 5,000-req/hr,
    and one batched query covers up to `batch_size` users at ~1 point each. So
    we can resolve thousands of profile records per hour without touching the
    REST budget that callers reserve for PushEvent fallback.

    Returns {login: {"email": str_or_None, "name": str_or_None}}. Email is None
    if either the user has no public email or it's a noreply mask. The `name`
    is included so PushEvent fallback callers can verify commit authorship
    without re-fetching the profile via REST.
    """
    out: Dict[str, Dict[str, Optional[object]]] = {}
    if not logins:
        return out

    for start in range(0, len(logins), batch_size):
        batch = logins[start:start + batch_size]
        # GraphQL aliases must match /[A-Za-z][A-Za-z_0-9]*/, so use index-based
        # aliases (logins can contain hyphens). JSON-escape the login string.
        parts = []
        for i, login in enumerate(batch):
            esc = json.dumps(login)
            parts.append(
                f"u{i}: user(login: {esc}) {{ "
                f"login email name bio isHireable createdAt "
                f"followers {{ totalCount }} "
                f"following {{ totalCount }} "
                f"repositories(privacy: PUBLIC, ownerAffiliations: OWNER) "
                f"{{ totalCount }} "
                f"}}"
            )
        query = "query { " + " ".join(parts) + " }"
        body = json.dumps({"query": query}).encode("utf-8")

        req = urllib.request.Request(
            GRAPHQL_URL,
            data=body,
            method="POST",
        )
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")
        req.add_header("User-Agent", "viralman-gitmail/0.2")
        if token:
            req.add_header("Authorization", f"Bearer {token}")

        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                headers = dict(r.headers)
                payload = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            print(f"graphql: HTTP {e.code} on batch {start}-{start+len(batch)}",
                  file=sys.stderr)
            for login in batch:
                out.setdefault(login, _empty_profile())
            continue
        except Exception as e:
            print(f"graphql: network error on batch {start}: {e}",
                  file=sys.stderr)
            for login in batch:
                out.setdefault(login, _empty_profile())
            continue

        _respect_rate_limit(headers)

        data = payload.get("data") or {}
        for i, login in enumerate(batch):
            user = data.get(f"u{i}")
            if not isinstance(user, dict):
                out[login] = _empty_profile()
                continue
            email = user.get("email")
            if email and NOREPLY_RE.search(email):
                email = None
            followers = (user.get("followers") or {}).get("totalCount")
            following = (user.get("following") or {}).get("totalCount")
            public_repos = (user.get("repositories") or {}).get("totalCount")
            out[login] = {
                "email": email,
                "name": user.get("name"),
                "bio": user.get("bio") or None,
                "is_hireable": bool(user.get("isHireable")),
                "created_at": user.get("createdAt"),
                "followers": followers,
                "following": following,
                "public_repos": public_repos,
            }
    return out


# --------------------------------------------------------------------------- #
# Recipient quality filter                                                    #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class RecipientFilter:
    """Bound checks applied to a profile dict from `bulk_resolve_profile_data`.

    None means "do not check this dimension". An active filter keeps a
    candidate iff every checked dimension passes; the first failing dimension
    is reported back as the rejection reason."""
    min_followers: Optional[int] = None
    max_followers: Optional[int] = None
    min_following: Optional[int] = None
    max_following: Optional[int] = None
    min_public_repos: Optional[int] = None
    max_public_repos: Optional[int] = None
    min_account_age_days: Optional[int] = None
    require_bio: bool = False

    _INT_FIELDS = ("min_followers", "max_followers",
                   "min_following", "max_following",
                   "min_public_repos", "max_public_repos",
                   "min_account_age_days")

    @classmethod
    def from_mapping(cls, source: object) -> "RecipientFilter":
        """Build a filter from anything that supports indexed/attr access:
        argparse.Namespace, dict, or any object with the matching attributes.
        Empty strings, empty lists, and unparseable values are treated as
        unset — that's what dashboard JSON payloads typically send."""
        def lookup(key: str):
            if isinstance(source, dict):
                return source.get(key)
            return getattr(source, key, None)

        def opt_int(key: str) -> Optional[int]:
            v = lookup(key)
            if v in (None, "", []):
                return None
            try:
                return int(v)
            except (TypeError, ValueError):
                return None

        kwargs = {f: opt_int(f) for f in cls._INT_FIELDS}
        kwargs["require_bio"] = bool(lookup("require_bio"))
        return cls(**kwargs)

    def is_active(self) -> bool:
        return any((
            self.min_followers is not None,
            self.max_followers is not None,
            self.min_following is not None,
            self.max_following is not None,
            self.min_public_repos is not None,
            self.max_public_repos is not None,
            self.min_account_age_days is not None,
            self.require_bio,
        ))

    def evaluate(self, profile: Dict[str, object]) -> Optional[str]:
        """Returns None if the profile passes, else the failing-dimension key.

        Missing data (None) is treated as failing any min/max bound — when the
        user opts into a filter, they're asking for verified profiles only."""
        followers = profile.get("followers")
        if self.min_followers is not None:
            if not isinstance(followers, int) or followers < self.min_followers:
                return "min_followers"
        if self.max_followers is not None:
            if not isinstance(followers, int) or followers > self.max_followers:
                return "max_followers"

        following = profile.get("following")
        if self.min_following is not None:
            if not isinstance(following, int) or following < self.min_following:
                return "min_following"
        if self.max_following is not None:
            if not isinstance(following, int) or following > self.max_following:
                return "max_following"

        public_repos = profile.get("public_repos")
        if self.min_public_repos is not None:
            if not isinstance(public_repos, int) or public_repos < self.min_public_repos:
                return "min_public_repos"
        if self.max_public_repos is not None:
            if not isinstance(public_repos, int) or public_repos > self.max_public_repos:
                return "max_public_repos"

        if self.min_account_age_days is not None:
            age = _account_age_days(profile.get("created_at"))
            if age is None or age < self.min_account_age_days:
                return "min_account_age_days"

        if self.require_bio:
            bio = profile.get("bio")
            if not (isinstance(bio, str) and bio.strip()):
                return "require_bio"

        return None


def _account_age_days(created_at: Optional[object]) -> Optional[int]:
    if not isinstance(created_at, str) or not created_at:
        return None
    s = created_at.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - dt
    return max(0, delta.days)


# --------------------------------------------------------------------------- #
# Smoke-test CLI                                                              #
# --------------------------------------------------------------------------- #


def _main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="GitHub helpers smoke test.")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("analyse")
    a.add_argument("text")
    s = sub.add_parser("search")
    s.add_argument("--topic", action="append", default=[])
    s.add_argument("--keyword", action="append", default=[])
    s.add_argument("--limit", type=int, default=5)
    sub.add_parser("ratelimit")
    bg = sub.add_parser("bulkemail",
                         help="GraphQL smoke: bulk-resolve emails for given logins")
    bg.add_argument("logins", nargs="+", help="GitHub logins")
    args = p.parse_args()

    sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
    try:
        from creds import load as load_creds
        token = (load_creds() or {}).get("GITHUB_TOKEN")
    except Exception:
        token = None

    if args.cmd == "analyse":
        print(json.dumps(analyse_project(args.text), indent=2))
        return 0
    if args.cmd == "search":
        repos = search_similar_repos(
            topics=args.topic,
            keywords=args.keyword,
            limit=args.limit,
            token=token,
        )
        print(json.dumps(repos, indent=2))
        return 0
    if args.cmd == "ratelimit":
        status, _, data = _json("/rate_limit", token=token)
        print(json.dumps({"status": status, "rate_limit": data}, indent=2))
        return 0
    if args.cmd == "bulkemail":
        result = bulk_resolve_profile_data(args.logins, token=token)
        print(json.dumps({k: v["email"] for k, v in result.items()}, indent=2))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(_main())
