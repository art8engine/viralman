"""Regression tests for targeting heuristics — subreddit suggestions, hashtag
shape from /api/generate, and compose_urls round-trip.

Covers P-TG (promotional targeting accuracy) items from the QA plan.

Run:
  .venv/bin/python -m pytest tests/test_targeting_heuristics.py -v
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

# ---------------------------------------------------------------------------
# Import _suggest_subreddits directly from dashboard.api
# ---------------------------------------------------------------------------

# Ensure the dashboard package is importable
sys.path.insert(0, str(ROOT))

from dashboard.api import _suggest_subreddits  # noqa: E402


# ===========================================================================
# 1. _suggest_subreddits unit tests
# ===========================================================================


def test_kubernetes_keyword_suggests_devops_subreddits():
    result = _suggest_subreddits(topics=[], keywords=["k8s", "kubernetes"])
    assert "kubernetes" in result, f"expected 'kubernetes' in {result}"
    assert "devops" in result, f"expected 'devops' in {result}"


def test_python_keyword_suggests_python_subreddits():
    result = _suggest_subreddits(topics=[], keywords=["python"])
    assert "Python" in result, f"expected 'Python' in {result}"
    assert "learnpython" in result, f"expected 'learnpython' in {result}"


def test_llm_keyword_suggests_local_llama():
    result = _suggest_subreddits(topics=[], keywords=["llm", "rag"])
    assert "LocalLLaMA" in result, f"expected 'LocalLLaMA' in {result}"


def test_unknown_keyword_falls_back_to_generic():
    result = _suggest_subreddits(topics=[], keywords=["quantum-foo"])
    assert result == ["programming", "opensource", "SideProject"], (
        f"expected generic fallbacks, got {result}"
    )


def test_dedup():
    # k8s and kubernetes both map to 'kubernetes' and 'devops'
    result = _suggest_subreddits(topics=[], keywords=["k8s", "kubernetes", "docker"])
    assert len(result) == len(set(result)), f"duplicate entries in {result}"


def test_caps_at_six():
    # Many aliases: python + golang + rust + kubernetes + llm + docker + react
    many_kws = ["python", "golang", "rust", "kubernetes", "llm", "docker", "react"]
    result = _suggest_subreddits(topics=[], keywords=many_kws)
    assert len(result) <= 6, f"expected <= 6 entries, got {len(result)}: {result}"


def test_empty_inputs():
    result = _suggest_subreddits(topics=[], keywords=[])
    assert result == ["programming", "opensource", "SideProject"], (
        f"expected generic fallbacks for empty inputs, got {result}"
    )


def test_alias_normalization_lowercase():
    # Keywords passed with mixed/upper case — should still resolve via .lower()
    result = _suggest_subreddits(topics=[], keywords=["Python", "GO", "Kubernetes"])
    assert "Python" in result or "learnpython" in result, (
        f"expected Python/learnpython in {result}"
    )
    assert "golang" in result, f"expected 'golang' in {result}"
    assert "kubernetes" in result, f"expected 'kubernetes' in {result}"


# ===========================================================================
# 2. /api/generate — suggested_hashtags and suggested_subreddits shape
# ===========================================================================


@pytest.fixture()
def app():
    from dashboard.server import create_app
    import dashboard.api as _api

    application = create_app(secret_key="test")
    application.config["TESTING"] = True

    _api.JOBS.clear()
    _api.UNSUBSCRIBES.clear()

    yield application

    _api.JOBS.clear()
    _api.UNSUBSCRIBES.clear()


@pytest.fixture()
def client(app):
    return app.test_client()


def test_generate_returns_hashtags_from_topics(client, monkeypatch):
    import dashboard.api as _api

    # No LLM keys — force stub path
    monkeypatch.setattr(_api, "load_creds", lambda: {})

    resp = client.post(
        "/api/generate",
        json={
            "project": {"desc": "A Go-based K8s autoscaler"},
            "channels": ["twitter"],
        },
    )
    assert resp.status_code == 200, f"unexpected status {resp.status_code}: {resp.data}"
    data = resp.get_json()
    assert data["ok"] is True

    hashtags = data.get("suggested_hashtags")
    assert isinstance(hashtags, list), f"suggested_hashtags not a list: {hashtags}"
    assert len(hashtags) <= 6, f"too many hashtags: {hashtags}"
    for tag in hashtags:
        assert tag.startswith("#"), f"hashtag missing '#' prefix: {tag!r}"


def test_generate_hashtags_no_filler_class(client, monkeypatch):
    """Hashtags are derived from project topics, never from a generic filler list.

    The generate endpoint builds suggested_hashtags as "#" + topic strings, so
    domain-neutral spam tags like #innovation/#growth/#tech must not appear for
    a domain-specific input.  No xfail needed — the current implementation
    already satisfies this constraint.
    """
    import dashboard.api as _api

    monkeypatch.setattr(_api, "load_creds", lambda: {})

    resp = client.post(
        "/api/generate",
        json={
            "project": {"desc": "A Go-based K8s autoscaler"},
            "channels": ["twitter"],
        },
    )
    assert resp.status_code == 200
    data = resp.get_json()
    hashtags = data.get("suggested_hashtags", [])

    filler = {"#innovation", "#growth", "#tech"}
    overlap = filler & set(hashtags)
    assert not overlap, (
        f"filler hashtags found in suggestions: {overlap}"
    )


def test_suggested_subreddits_in_generate_response(client, monkeypatch):
    import dashboard.api as _api

    monkeypatch.setattr(_api, "load_creds", lambda: {})

    resp = client.post(
        "/api/generate",
        json={
            "project": {"desc": "A Go-based K8s autoscaler"},
            "channels": ["twitter"],
        },
    )
    assert resp.status_code == 200
    data = resp.get_json()

    subs = data.get("suggested_subreddits")
    assert isinstance(subs, list), f"suggested_subreddits not a list: {subs}"
    assert len(subs) <= 6, f"too many subreddits: {subs}"
    assert len(subs) == len(set(subs)), f"duplicate subreddits: {subs}"


# ===========================================================================
# 3. compose_urls round-trip
# ===========================================================================

# Import compose_urls from scripts/lib (already on sys.path via ROOT insert above)
from compose_urls import twitter_intent, reddit_submit  # noqa: E402


def test_twitter_intent_url_encodes_body():
    body = "Hello World!\nWith newlines 🎉 and emoji"
    url = twitter_intent(body)
    assert url.startswith("https://twitter.com/intent/tweet"), (
        f"unexpected base URL: {url}"
    )
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    assert "text" in qs, f"'text' param missing in {url}"
    # urllib.parse.parse_qs decodes the value for us
    decoded = qs["text"][0]
    assert decoded == body, f"decoded body mismatch: {decoded!r} != {body!r}"


def test_reddit_submit_includes_subreddit_title_body():
    sub = "python"
    title = "My cool project"
    body = "Here is the description."
    url = reddit_submit(sub, title, body)

    assert f"/r/{sub}/submit" in url, f"expected /r/{sub}/submit in {url}"
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    assert qs.get("title", [None])[0] == title, (
        f"title param mismatch in {url}"
    )
    assert qs.get("text", [None])[0] == body, (
        f"body (text) param mismatch in {url}"
    )


def test_reddit_submit_strips_r_prefix():
    """reddit_submit('r/python', ...) produces /r/python/submit, not /r/r/python/submit."""
    url = reddit_submit("r/python", "Title", "Body")
    assert "/r/r/python" not in url, (
        f"double 'r/' prefix found in URL: {url}"
    )
    path = urlparse(url).path
    assert path.count("/r/") == 1, (
        f"expected exactly one '/r/' in path, got: {path!r}"
    )
    url2 = reddit_submit("/r/golang", "T", "B")
    assert "/r/golang/submit" in url2 and "/r/r/" not in url2
    url3 = reddit_submit("R/Rust", "T", "B")
    assert "/r/Rust/submit" in url3 and "/r/R/" not in url3


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
