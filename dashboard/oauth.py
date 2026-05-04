"""OAuth flows for Twitter, Reddit, and LinkedIn.

Each platform uses Authorization Code flow with redirect_uri = the dashboard's
own /oauth/<platform>/callback. All three require a one-time CLIENT_ID +
CLIENT_SECRET pair to be saved (registered in the platform's dev portal).

GET  /oauth/<platform>/start    -> redirect to provider
GET  /oauth/<platform>/callback -> exchange code, save tokens, render result

Twitter uses OAuth 2.0 PKCE; the resulting Bearer token can post user-context
tweets via the v2 Tweets endpoint. Note that the legacy post_twitter.py script
uses OAuth 1.0a — both work; we save tokens under TWITTER_OAUTH2_BEARER too so
a future v2 sender can pick it up.

Reddit OAuth requires a "web app"-type registration (separate from the script
app currently used). Saved as REDDIT_OAUTH_TOKEN; PRAW falls back to it via
the OAuthHelper interface.

LinkedIn matches what the existing post_linkedin.py expects:
LINKEDIN_ACCESS_TOKEN + LINKEDIN_PERSON_URN.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets as _secrets
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS / "lib"))

from creds import load as load_creds, CredsError  # noqa: E402

import subprocess  # noqa: E402


CALLBACK_PATH = "/oauth/{platform}/callback"


def _build_redirect(platform: str, request_root: str) -> str:
    return request_root.rstrip("/") + CALLBACK_PATH.format(platform=platform)


def _save_creds(updates: Dict[str, str]) -> None:
    """Save via save_creds.py so the file mode and atomic write are consistent."""
    for key, value in updates.items():
        cmd = [sys.executable, str(SCRIPTS / "save_creds.py"),
                "--stdin", key]
        subprocess.run(cmd, input=value, text=True, capture_output=True,
                        cwd=str(REPO_ROOT), timeout=10, check=False)


def _http_post_form(url: str, data: dict, headers: dict | None = None,
                     timeout: int = 30) -> dict:
    body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _http_get_json(url: str, headers: dict, timeout: int = 30) -> dict:
    req = urllib.request.Request(url)
    for k, v in headers.items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


# --------------------------------------------------------------------------- #
# Per-platform configuration                                                  #
# --------------------------------------------------------------------------- #


PLATFORMS = {
    "twitter": {
        "auth": "https://twitter.com/i/oauth2/authorize",
        "token": "https://api.twitter.com/2/oauth2/token",
        "scopes": ["tweet.read", "tweet.write", "users.read", "offline.access"],
        "client_id": "TWITTER_OAUTH2_CLIENT_ID",
        "client_secret": "TWITTER_OAUTH2_CLIENT_SECRET",
        "needs_pkce": True,
    },
    "reddit": {
        "auth": "https://www.reddit.com/api/v1/authorize",
        "token": "https://www.reddit.com/api/v1/access_token",
        "scopes": ["identity", "submit", "read"],
        "client_id": "REDDIT_OAUTH_CLIENT_ID",
        "client_secret": "REDDIT_OAUTH_CLIENT_SECRET",
        "needs_pkce": False,
        "duration": "permanent",
    },
    "linkedin": {
        "auth": "https://www.linkedin.com/oauth/v2/authorization",
        "token": "https://www.linkedin.com/oauth/v2/accessToken",
        "scopes": ["openid", "profile", "email", "w_member_social"],
        "client_id": "LINKEDIN_CLIENT_ID",
        "client_secret": "LINKEDIN_CLIENT_SECRET",
        "needs_pkce": False,
    },
}


# --------------------------------------------------------------------------- #
# Route registration                                                          #
# --------------------------------------------------------------------------- #


def register(app) -> None:
    from flask import (jsonify, redirect, render_template_string, request,
                        session, url_for)

    @app.get("/api/oauth/config")
    def oauth_config():
        try:
            creds = load_creds()
        except CredsError:
            creds = {}
        out = {}
        for plat, conf in PLATFORMS.items():
            out[plat] = {
                "client_id_set": bool(creds.get(conf["client_id"])),
                "client_secret_set": bool(creds.get(conf["client_secret"])),
                "redirect_uri": _build_redirect(plat, request.url_root),
                "scopes": conf["scopes"],
            }
        return jsonify(out)

    @app.get("/oauth/<platform>/start")
    def oauth_start(platform):
        conf = PLATFORMS.get(platform)
        if not conf:
            return jsonify({"ok": False, "error": "unknown platform"}), 404
        try:
            creds = load_creds()
        except CredsError as e:
            return jsonify({"ok": False, "error": str(e)}), 400

        client_id = creds.get(conf["client_id"])
        if not client_id:
            return (jsonify({
                "ok": False,
                "error": f"missing {conf['client_id']} in ~/.viralman/.env",
                "hint": (f"Register a developer app for {platform}, set "
                          f"redirect URI to "
                          f"{_build_redirect(platform, request.url_root)}, "
                          f"then save its client id and secret."),
            }), 400)

        state = _secrets.token_urlsafe(32)
        session[f"oauth_state_{platform}"] = state
        params = {
            "client_id": client_id,
            "redirect_uri": _build_redirect(platform, request.url_root),
            "response_type": "code",
            "scope": " ".join(conf["scopes"]),
            "state": state,
        }
        if conf.get("needs_pkce"):
            verifier = _secrets.token_urlsafe(64)
            session[f"pkce_verifier_{platform}"] = verifier
            challenge = base64.urlsafe_b64encode(
                hashlib.sha256(verifier.encode("ascii")).digest()
            ).rstrip(b"=").decode("ascii")
            params["code_challenge"] = challenge
            params["code_challenge_method"] = "S256"
        if conf.get("duration"):
            params["duration"] = conf["duration"]
        url = conf["auth"] + "?" + urllib.parse.urlencode(params)
        return redirect(url)

    @app.get("/oauth/<platform>/callback")
    def oauth_callback(platform):
        conf = PLATFORMS.get(platform)
        if not conf:
            return jsonify({"ok": False, "error": "unknown platform"}), 404
        if request.args.get("error"):
            return _render_result(platform, ok=False, error=request.args.get("error_description") or request.args.get("error"))

        code = request.args.get("code")
        state = request.args.get("state")
        expected = session.pop(f"oauth_state_{platform}", None)
        if not code or not state or state != expected:
            return _render_result(platform, ok=False,
                                   error="state mismatch — replay/forged callback rejected")

        try:
            creds = load_creds()
        except CredsError as e:
            return _render_result(platform, ok=False, error=str(e))

        client_id = creds.get(conf["client_id"])
        client_secret = creds.get(conf["client_secret"])
        if not client_id or not client_secret:
            return _render_result(platform, ok=False,
                                   error=f"missing {conf['client_id']}/{conf['client_secret']}")

        token_data = {
            "client_id": client_id,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": _build_redirect(platform, request.url_root),
        }
        headers: dict[str, str] = {}

        if conf.get("needs_pkce"):
            verifier = session.pop(f"pkce_verifier_{platform}", None)
            if not verifier:
                return _render_result(platform, ok=False, error="PKCE verifier lost")
            token_data["code_verifier"] = verifier
            # Twitter expects HTTP Basic auth even with PKCE for confidential clients.
            basic = base64.b64encode(
                f"{client_id}:{client_secret}".encode("ascii")
            ).decode("ascii")
            headers["Authorization"] = f"Basic {basic}"
        elif platform == "reddit":
            basic = base64.b64encode(
                f"{client_id}:{client_secret}".encode("ascii")
            ).decode("ascii")
            headers["Authorization"] = f"Basic {basic}"
            headers["User-Agent"] = creds.get("REDDIT_USER_AGENT") or "viralman/0.2 dashboard"
        else:
            token_data["client_secret"] = client_secret

        try:
            tok = _http_post_form(conf["token"], token_data, headers=headers)
        except Exception as e:
            return _render_result(platform, ok=False, error=f"token exchange failed: {e}")

        access = tok.get("access_token")
        refresh = tok.get("refresh_token")
        if not access:
            return _render_result(platform, ok=False,
                                   error=f"no access_token in response: {tok}")

        updates = _save_platform_tokens(platform, access, refresh, tok, creds)
        return _render_result(platform, ok=True, info=updates)


def _save_platform_tokens(platform: str, access: str, refresh: str | None,
                           token_response: dict, creds: dict) -> dict:
    """Persist the right env vars per platform."""
    if platform == "twitter":
        keys = {
            "TWITTER_OAUTH2_BEARER": access,
        }
        if refresh:
            keys["TWITTER_OAUTH2_REFRESH"] = refresh
        _save_creds(keys)
        return {"saved_keys": list(keys.keys()),
                 "expires_in": token_response.get("expires_in"),
                 "scope": token_response.get("scope")}

    if platform == "reddit":
        keys = {"REDDIT_OAUTH_TOKEN": access}
        if refresh:
            keys["REDDIT_OAUTH_REFRESH"] = refresh
        _save_creds(keys)
        # Try to fetch the username for convenience.
        try:
            info = _http_get_json(
                "https://oauth.reddit.com/api/v1/me",
                headers={
                    "Authorization": f"Bearer {access}",
                    "User-Agent": creds.get("REDDIT_USER_AGENT") or "viralman/0.2 dashboard",
                },
            )
            if info.get("name"):
                _save_creds({"REDDIT_USERNAME": info["name"]})
        except Exception:
            pass
        return {"saved_keys": list(keys.keys()),
                 "expires_in": token_response.get("expires_in")}

    if platform == "linkedin":
        keys = {"LINKEDIN_ACCESS_TOKEN": access}
        if refresh:
            keys["LINKEDIN_REFRESH_TOKEN"] = refresh
        _save_creds(keys)
        try:
            info = _http_get_json(
                "https://api.linkedin.com/v2/userinfo",
                headers={"Authorization": f"Bearer {access}"},
            )
            sub = info.get("sub")
            if sub:
                _save_creds({"LINKEDIN_PERSON_URN": f"urn:li:person:{sub}"})
                keys["LINKEDIN_PERSON_URN"] = "urn:li:person:" + sub
        except Exception:
            pass
        return {"saved_keys": list(keys.keys()),
                 "expires_in": token_response.get("expires_in")}

    return {}


def _render_result(platform: str, *, ok: bool, error: str | None = None,
                    info: dict | None = None):
    from flask import render_template_string
    body = """
<!doctype html>
<html><head><meta charset="utf-8"><title>{{ platform }} OAuth — viralman</title>
<style>
  body { background:#0a0a0a; color:#e8e8e8; font-family:system-ui, sans-serif;
         padding:48px; max-width:640px; margin:0 auto; }
  h1   { color: {{ '#7be88c' if ok else '#ff6b6b' }}; }
  pre  { background:#141414; padding:16px; border-radius:8px;
         border:1px solid #222; white-space:pre-wrap; word-break:break-all; }
  a    { color:#69b3ff; }
</style></head>
<body>
  <h1>{{ platform | capitalize }} — {{ 'connected' if ok else 'failed' }}</h1>
  {% if ok %}
    <p>Tokens saved to <code>~/.viralman/.env</code>. You can close this tab.</p>
    <pre>{{ info | tojson(indent=2) }}</pre>
  {% else %}
    <p>{{ error }}</p>
    <p>You can <a href="/oauth/{{ platform }}/start">retry</a> or go back to
       the <a href="/{{ platform if platform != 'gitmail' else 'gitmail' }}">dashboard</a>.</p>
  {% endif %}
  <p style="margin-top:48px"><a href="/">← back to dashboard</a></p>
</body></html>
"""
    return render_template_string(body, platform=platform, ok=ok, error=error,
                                    info=info or {})
