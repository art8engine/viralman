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
from typing import Dict, Iterator, List, Optional

GH_API = "https://api.github.com"
NOREPLY_RE = re.compile(r"@users\.noreply\.github\.com$", re.IGNORECASE)


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
) -> Optional[str]:
    """Best-effort. Returns None if no plausible email is found."""
    status, headers, data = _json(f"/users/{login}", token=token)
    _respect_rate_limit(headers)
    if status == 200 and isinstance(data, dict):
        email = data.get("email")
        if email and not NOREPLY_RE.search(email):
            return email
        name = data.get("name") or login
    else:
        name = login

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


def collect_recipients(
    repos: List[Dict[str, object]],
    *,
    max_users: int,
    token: Optional[str] = None,
    on_progress=None,
) -> List[Dict[str, str]]:
    """Walk the given repos round-robin, collect up to `max_users` (login, email)."""
    seen_logins: set[str] = set()
    out: List[Dict[str, str]] = []
    iterators = [iter_stargazers(r["full_name"], max_users=max_users * 5, token=token)
                 for r in repos]

    while iterators and len(out) < max_users:
        next_iters = []
        for it in iterators:
            try:
                user = next(it)
            except StopIteration:
                continue
            login = user["login"]
            if login in seen_logins:
                next_iters.append(it)
                continue
            seen_logins.add(login)
            email = resolve_user_email(login, token=token)
            if email:
                out.append({"login": login, "email": email,
                            "profile": user.get("html_url", "")})
                if on_progress:
                    on_progress({"event": "recipient",
                                 "count": len(out),
                                 "target": max_users,
                                 "login": login})
                if len(out) >= max_users:
                    break
            next_iters.append(it)
        iterators = next_iters
    return out


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
    return 2


if __name__ == "__main__":
    raise SystemExit(_main())
