"""Integration tests for the dashboard API (Flask test client).

Run:
  python -m pytest tests/test_dashboard_api.py -v
"""

from __future__ import annotations

import sys
import threading
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "lib"))


# ---------------------------------------------------------------------------
# App fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def app():
    from dashboard.server import create_app
    import dashboard.api as _api

    application = create_app(secret_key="test")
    application.config["TESTING"] = True

    # Reset module-level mutable globals before each test
    _api.JOBS.clear()
    _api.UNSUBSCRIBES.clear()

    yield application

    # Cleanup after test
    _api.JOBS.clear()
    _api.UNSUBSCRIBES.clear()


@pytest.fixture()
def client(app):
    return app.test_client()


# ---------------------------------------------------------------------------
# 1. Index redirect
# ---------------------------------------------------------------------------


def test_index_redirects_to_twitter(client):
    resp = client.get("/")
    assert resp.status_code == 302
    assert "/twitter" in resp.headers["Location"]


# ---------------------------------------------------------------------------
# 2. Pages render 200 with data-i18n markers
# ---------------------------------------------------------------------------


def test_pages_render_200(client):
    pages = ["/twitter", "/reddit", "/gitmail", "/setup"]
    for page in pages:
        resp = client.get(page)
        assert resp.status_code == 200, f"{page} returned {resp.status_code}"
        html = resp.data.decode()
        assert "data-i18n" in html, f"{page} missing data-i18n marker"


# ---------------------------------------------------------------------------
# 3. Unsubscribe GET records token
# ---------------------------------------------------------------------------


def test_unsubscribe_get_records_token(client):
    import dashboard.api as _api

    resp = client.get("/u/abc123")
    assert resp.status_code == 200
    text = resp.data.decode()
    assert "unsubscribed" in text.lower()
    assert "abc123" in _api.UNSUBSCRIBES


# ---------------------------------------------------------------------------
# 4. Unsubscribe POST idempotent
# ---------------------------------------------------------------------------


def test_unsubscribe_post_idempotent(client):
    resp1 = client.post("/u/abc123")
    resp2 = client.post("/u/abc123")
    assert resp1.status_code == 200
    assert resp2.status_code == 200


# ---------------------------------------------------------------------------
# 5. Creds status shape
# ---------------------------------------------------------------------------


def test_creds_status_shape(client, monkeypatch):
    import dashboard.api as _api

    monkeypatch.setattr(_api, "load_creds", lambda: {})

    resp = client.get("/api/creds/status")
    assert resp.status_code == 200
    data = resp.get_json()

    required_keys = [
        "twitter", "reddit", "linkedin", "github",
        "smtp", "claude", "openai", "gemini", "claude_cli",
    ]
    for key in required_keys:
        assert key in data, f"missing key: {key}"
        assert "configured" in data[key], f"{key} missing 'configured'"
        assert isinstance(data[key]["configured"], bool), f"{key}.configured not bool"


# ---------------------------------------------------------------------------
# 6. Preview twitter empty body -> 400
# ---------------------------------------------------------------------------


def test_preview_twitter_empty_body_400(client):
    resp = client.post("/api/preview/twitter", json={})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["ok"] is False


# ---------------------------------------------------------------------------
# 7. Preview twitter returns compose_url and flags
# ---------------------------------------------------------------------------


def test_preview_twitter_returns_compose_url_and_flags(client):
    resp = client.post(
        "/api/preview/twitter",
        json={"body": "shipped my K8s autoscaler v1.0"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert "char_count" in data
    assert "compose_url" in data
    assert "twitter.com/intent/tweet" in data["compose_url"]
    assert isinstance(data["flags"], list)


# ---------------------------------------------------------------------------
# 8. Preview twitter thread split on "---"
# ---------------------------------------------------------------------------


def test_preview_twitter_thread_split(client):
    body = "First part of the thread\n---\nSecond part here"
    resp = client.post("/api/preview/twitter", json={"body": body})
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["thread_parts"]) == 2


# ---------------------------------------------------------------------------
# 9. Preview twitter over limit flag
# ---------------------------------------------------------------------------


def test_preview_twitter_over_limit_flag(client):
    body = "a" * 300
    resp = client.post("/api/preview/twitter", json={"body": body})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["over_limit"] is True


# ---------------------------------------------------------------------------
# 10. Preview reddit requires sub and title
# ---------------------------------------------------------------------------


def test_preview_reddit_requires_sub_and_title(client):
    # Missing subreddit
    resp = client.post("/api/preview/reddit", json={"title": "My Post"})
    assert resp.status_code == 400

    # Missing title
    resp = client.post("/api/preview/reddit", json={"subreddit": "python"})
    assert resp.status_code == 400

    # Both present -> 200
    resp = client.post(
        "/api/preview/reddit",
        json={"subreddit": "python", "title": "My Post"},
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 11. Preview reddit strips r/ prefix
# ---------------------------------------------------------------------------


def test_preview_reddit_strips_r_prefix(client):
    resp = client.post(
        "/api/preview/reddit",
        json={"subreddit": "r/python", "title": "Hello"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["subreddit"] == "python"


# ---------------------------------------------------------------------------
# 12. Gitmail collect validates description
# ---------------------------------------------------------------------------


def test_gitmail_collect_validates_description(client, monkeypatch):
    import dashboard.api as _api

    monkeypatch.setattr(_api, "_run_collect_job", lambda job: None)
    # Patch threading.Thread so .start() is a no-op
    monkeypatch.setattr(
        _api.threading, "Thread",
        lambda target, args, daemon: types.SimpleNamespace(start=lambda: None),
    )

    resp = client.post("/api/gitmail/collect", json={"description": ""})
    assert resp.status_code == 400
    assert resp.get_json()["ok"] is False


# ---------------------------------------------------------------------------
# 15. Gitmail send requires recipients and body
# ---------------------------------------------------------------------------


def test_gitmail_send_requires_recipients_and_body(client, monkeypatch):
    import dashboard.api as _api

    monkeypatch.setattr(_api, "_run_send_job", lambda job: None)
    monkeypatch.setattr(
        _api.threading, "Thread",
        lambda target, args, daemon: types.SimpleNamespace(start=lambda: None),
    )

    # Empty recipients -> 400
    resp = client.post(
        "/api/gitmail/send",
        json={"recipients": [], "body": "Hello {{login}}"},
    )
    assert resp.status_code == 400

    # Missing body -> 400
    resp = client.post(
        "/api/gitmail/send",
        json={"recipients": [{"email": "x@example.com", "login": "x"}], "body": ""},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# 16. Gitmail status unknown id -> 404
# ---------------------------------------------------------------------------


def test_gitmail_status_unknown_id_404(client):
    resp = client.get("/api/gitmail/status/zzz")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 17. Gitmail cancel unknown id -> 404
# ---------------------------------------------------------------------------


def test_gitmail_cancel_unknown_id_404(client):
    resp = client.post("/api/gitmail/cancel/zzz")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 18. Creds manual validates key format
# ---------------------------------------------------------------------------


def test_creds_manual_validates_key_format(client, monkeypatch):
    import dashboard.api as _api

    # lowercase key -> 400 (key must be UPPER_SNAKE_CASE)
    resp = client.post(
        "/api/creds/manual",
        json={"key": "lowercase", "value": "x", "secret": False},
    )
    assert resp.status_code == 400

    # FOO_BAR with mock subprocess.run returning rc=0 -> 200
    fake_result = types.SimpleNamespace(returncode=0, stdout="", stderr="")
    monkeypatch.setattr(_api.subprocess, "run", lambda *a, **kw: fake_result)

    resp = client.post(
        "/api/creds/manual",
        json={"key": "FOO_BAR", "value": "x", "secret": False},
    )
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True


# ---------------------------------------------------------------------------
# 19. Generate requires desc and channels
# ---------------------------------------------------------------------------


def test_generate_requires_desc_and_channels(client):
    # Missing project.desc -> 400
    resp = client.post(
        "/api/generate",
        json={"project": {}, "channels": ["twitter"]},
    )
    assert resp.status_code == 400
    assert resp.get_json()["ok"] is False

    # Channels empty -> 400
    resp = client.post(
        "/api/generate",
        json={"project": {"desc": "A cool tool"}, "channels": []},
    )
    assert resp.status_code == 400
    assert resp.get_json()["ok"] is False


# ---------------------------------------------------------------------------
# 20. Scrape reddit threads requires subs
# ---------------------------------------------------------------------------


def test_scrape_reddit_threads_requires_subs(client):
    resp = client.post(
        "/api/scrape/reddit-threads",
        json={"subreddits": [], "keywords": ["python"]},
    )
    assert resp.status_code == 400
    assert resp.get_json()["ok"] is False


if __name__ == "__main__":
    import pytest as _pytest
    raise SystemExit(_pytest.main([__file__, "-v"]))
