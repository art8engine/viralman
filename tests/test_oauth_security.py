"""OAuth security regression tests for the viralman dashboard.

Tests cover CSRF state token validation, PKCE verifier lifecycle, unknown-platform
rejection, provider error surfacing, and entropy of generated state tokens.

Run:
  .venv/bin/python -m pytest tests/test_oauth_security.py -v
"""

from __future__ import annotations

import sys
import urllib.parse
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "lib"))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def app():
    from dashboard.server import create_app

    application = create_app(secret_key="test")
    application.config["TESTING"] = True
    return application


@pytest.fixture()
def client(app):
    return app.test_client()


# ---------------------------------------------------------------------------
# Helper: parse Location query params
# ---------------------------------------------------------------------------


def _location_params(resp) -> dict:
    loc = resp.headers["Location"]
    parsed = urllib.parse.urlparse(loc)
    return dict(urllib.parse.parse_qsl(parsed.query))


# ---------------------------------------------------------------------------
# 1. Config endpoint returns all three platforms with required keys
# ---------------------------------------------------------------------------


def test_oauth_config_returns_three_platforms(client, monkeypatch):
    import dashboard.oauth as _oauth

    monkeypatch.setattr(_oauth, "load_creds", lambda: {})

    resp = client.get("/api/oauth/config")
    assert resp.status_code == 200

    data = resp.get_json()
    assert set(data.keys()) >= {"twitter", "reddit", "linkedin"}

    for platform in ("twitter", "reddit", "linkedin"):
        plat_data = data[platform]
        assert "redirect_uri" in plat_data, f"{platform} missing redirect_uri"
        assert "scopes" in plat_data, f"{platform} missing scopes"
        assert "client_id_set" in plat_data, f"{platform} missing client_id_set"
        assert "client_secret_set" in plat_data, f"{platform} missing client_secret_set"
        assert isinstance(plat_data["client_id_set"], bool)
        assert isinstance(plat_data["client_secret_set"], bool)


# ---------------------------------------------------------------------------
# 2. Unknown platform on /start -> 404
# ---------------------------------------------------------------------------


def test_oauth_start_unknown_platform_404(client):
    resp = client.get("/oauth/foo/start")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 3. Unknown platform on /callback -> 404
# ---------------------------------------------------------------------------


def test_oauth_callback_unknown_platform_404(client):
    resp = client.get("/oauth/foo/callback")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 4. Missing client_id redirects to /setup
# ---------------------------------------------------------------------------


def test_oauth_start_missing_client_id_redirects_to_setup(client, monkeypatch):
    import dashboard.oauth as _oauth

    monkeypatch.setattr(_oauth, "load_creds", lambda: {})

    resp = client.get("/oauth/twitter/start")
    assert resp.status_code == 302
    loc = resp.headers["Location"]
    assert "/setup" in loc
    assert "platform=twitter" in loc
    assert "missing=client_id" in loc


# ---------------------------------------------------------------------------
# 5. Valid creds -> redirect to provider with state + PKCE params
# ---------------------------------------------------------------------------


def test_oauth_start_with_creds_redirects_to_provider_with_state(client, monkeypatch):
    import dashboard.oauth as _oauth

    monkeypatch.setattr(
        _oauth,
        "load_creds",
        lambda: {"TWITTER_OAUTH2_CLIENT_ID": "abc", "TWITTER_OAUTH2_CLIENT_SECRET": "sec"},
    )

    resp = client.get("/oauth/twitter/start")
    assert resp.status_code == 302

    loc = resp.headers["Location"]
    # Must point to Twitter's auth endpoint
    assert "twitter.com" in loc or "x.com" in loc

    params = _location_params(resp)
    assert params.get("response_type") == "code"
    assert "state" in params and params["state"]
    assert "code_challenge" in params
    assert params.get("code_challenge_method") == "S256"

    state_in_url = params["state"]

    # Session must store the same state token
    with client.session_transaction() as sess:
        assert sess.get("oauth_state_twitter") == state_in_url


# ---------------------------------------------------------------------------
# 6. State mismatch -> rejected (replay/forged callback)
# ---------------------------------------------------------------------------


def test_oauth_callback_state_mismatch_rejected(client, monkeypatch):
    import dashboard.oauth as _oauth

    monkeypatch.setattr(_oauth, "load_creds", lambda: {})
    monkeypatch.setattr(_oauth, "_save_creds", lambda updates: None)

    with client.session_transaction() as sess:
        sess["oauth_state_twitter"] = "real-state"

    resp = client.get("/oauth/twitter/callback?code=abc&state=fake-state")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "state mismatch" in body


# ---------------------------------------------------------------------------
# 7. Missing code -> rejected
# ---------------------------------------------------------------------------


def test_oauth_callback_missing_code_rejected(client, monkeypatch):
    import dashboard.oauth as _oauth

    monkeypatch.setattr(_oauth, "load_creds", lambda: {})
    monkeypatch.setattr(_oauth, "_save_creds", lambda updates: None)

    with client.session_transaction() as sess:
        sess["oauth_state_twitter"] = "good-state"

    # state matches but no code param -> not code branch triggers
    resp = client.get("/oauth/twitter/callback?state=good-state")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "state mismatch" in body


# ---------------------------------------------------------------------------
# 8. Missing state param -> rejected
# ---------------------------------------------------------------------------


def test_oauth_callback_missing_state_rejected(client, monkeypatch):
    import dashboard.oauth as _oauth

    monkeypatch.setattr(_oauth, "load_creds", lambda: {})
    monkeypatch.setattr(_oauth, "_save_creds", lambda updates: None)

    with client.session_transaction() as sess:
        sess["oauth_state_twitter"] = "good-state"

    # code present but state param absent
    resp = client.get("/oauth/twitter/callback?code=abc")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "state mismatch" in body


# ---------------------------------------------------------------------------
# 9. State token consumed on first use (replay prevention)
# ---------------------------------------------------------------------------


def test_oauth_callback_state_consumed_on_use(client, monkeypatch):
    import dashboard.oauth as _oauth

    # Patch load_creds to return creds so callback can get past the state check
    # but fail at token exchange (network) — we only care about state lifecycle
    monkeypatch.setattr(
        _oauth,
        "load_creds",
        lambda: {
            "TWITTER_OAUTH2_CLIENT_ID": "abc",
            "TWITTER_OAUTH2_CLIENT_SECRET": "sec",
        },
    )
    monkeypatch.setattr(_oauth, "_save_creds", lambda updates: None)

    def _fail_token_exchange(url, data, headers=None, timeout=30):
        raise RuntimeError("simulated network failure")

    monkeypatch.setattr(_oauth, "_http_post_form", _fail_token_exchange)

    # Seed state + pkce_verifier (needed for Twitter PKCE branch)
    with client.session_transaction() as sess:
        sess["oauth_state_twitter"] = "good"
        sess["pkce_verifier_twitter"] = "verifier-xyz"

    # First request with correct state — token exchange fails harmlessly
    resp1 = client.get("/oauth/twitter/callback?code=abc&state=good")
    assert resp1.status_code == 200
    body1 = resp1.data.decode()
    # Should NOT be a state-mismatch; should be a token-exchange error
    assert "state mismatch" not in body1
    assert "token exchange failed" in body1 or "failed" in body1

    # State must be popped — second request with same state must be rejected
    resp2 = client.get("/oauth/twitter/callback?code=abc&state=good")
    assert resp2.status_code == 200
    body2 = resp2.data.decode()
    assert "state mismatch" in body2


# ---------------------------------------------------------------------------
# 10. Provider error param surfaces in response
# ---------------------------------------------------------------------------


def test_oauth_callback_provider_error_param_surfaces(client, monkeypatch):
    import dashboard.oauth as _oauth

    monkeypatch.setattr(_oauth, "load_creds", lambda: {})

    resp = client.get(
        "/oauth/twitter/callback"
        "?error=access_denied&error_description=user+cancelled"
    )
    assert resp.status_code == 200
    body = resp.data.decode()
    # Either the description or the error code must appear
    assert "user cancelled" in body or "access_denied" in body


# ---------------------------------------------------------------------------
# 11. PKCE verifier popped regardless of token exchange outcome
# ---------------------------------------------------------------------------


def test_oauth_callback_pkce_verifier_consumed(client, monkeypatch):
    """The PKCE verifier must be popped from the session after the callback
    (line 209 in oauth.py does session.pop inside the needs_pkce branch).

    If verifier is NOT present, the code returns early with 'PKCE verifier lost'
    BEFORE calling the token endpoint, so the verifier is still consumed (popped)
    because session.pop returns None on absence — effectively a no-op pop.

    We test the normal path: verifier IS present, token exchange raises — verifier
    must be gone from the session.
    """
    import dashboard.oauth as _oauth

    monkeypatch.setattr(
        _oauth,
        "load_creds",
        lambda: {
            "TWITTER_OAUTH2_CLIENT_ID": "abc",
            "TWITTER_OAUTH2_CLIENT_SECRET": "sec",
        },
    )
    monkeypatch.setattr(_oauth, "_save_creds", lambda updates: None)

    def _fail_token_exchange(url, data, headers=None, timeout=30):
        raise RuntimeError("network failure")

    monkeypatch.setattr(_oauth, "_http_post_form", _fail_token_exchange)

    with client.session_transaction() as sess:
        sess["oauth_state_twitter"] = "s1"
        sess["pkce_verifier_twitter"] = "verifier-abc"

    resp = client.get("/oauth/twitter/callback?code=xyz&state=s1")
    assert resp.status_code == 200

    # Check the actual code path:
    # oauth.py line 209: verifier = session.pop(f"pkce_verifier_{platform}", None)
    # This happens BEFORE _http_post_form, so verifier IS consumed even on failure.
    with client.session_transaction() as sess:
        assert "pkce_verifier_twitter" not in sess, (
            "PKCE verifier was NOT consumed after callback — "
            "potential verifier reuse vulnerability"
        )


# ---------------------------------------------------------------------------
# 12. State token has high entropy (>= 32 chars)
# ---------------------------------------------------------------------------


def test_oauth_state_token_is_high_entropy(client, monkeypatch):
    import dashboard.oauth as _oauth

    monkeypatch.setattr(
        _oauth,
        "load_creds",
        lambda: {
            "REDDIT_OAUTH_CLIENT_ID": "rid",
            "REDDIT_OAUTH_CLIENT_SECRET": "rsec",
        },
    )

    resp = client.get("/oauth/reddit/start")
    assert resp.status_code == 302

    params = _location_params(resp)
    state = params.get("state", "")
    assert len(state) >= 32, (
        f"State token too short ({len(state)} chars) — insufficient entropy for CSRF protection"
    )


# ---------------------------------------------------------------------------
# Entry point for direct execution
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    import pytest as _pytest

    raise SystemExit(_pytest.main([__file__, "-v"]))
