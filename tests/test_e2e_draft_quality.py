"""End-to-end regression tests for /api/generate draft quality.

Guards the headline product claim "doesn't feel AI" at the integration boundary.
Runs against the Flask test client with load_creds mocked to {} so the stub
path always executes (no LLM credentials needed).

Run:
  .venv/bin/python -m pytest tests/test_e2e_draft_quality.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

# ---------------------------------------------------------------------------
# App + client fixtures
# ---------------------------------------------------------------------------

SAMPLE_PROJECTS = [
    {"name": "k8sauto",    "desc": "Go-based K8s autoscaler",           "pitch": "cuts cloud cost 47%"},
    {"name": "crev",       "desc": "TypeScript code-review CLI",         "pitch": "review code faster"},
    {"name": "pyobs",      "desc": "Python observability library",       "pitch": "traces with zero config"},
    {"name": "rxdbg",      "desc": "Rust regex debugger",                "pitch": "explains your regex"},
    {"name": "nextadmin",  "desc": "Next.js admin dashboard generator",  "pitch": "generates admin UIs"},
]

BANNED_PHRASES = [
    "delve",
    "leverage",
    "let's dive in",
    "supercharge",
    "harness the power",
    "embark on a journey",
    "it's not just",
]

BEGGING_TOKENS = [
    "please support",
    "would be great if",
    "would mean a lot",
]

FILLER_HASHTAGS = {
    "#innovation", "#growth", "#tech", "#ai", "#tips",
}


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


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _generate(client, monkeypatch, project, channels):
    """POST /api/generate with stub path forced (load_creds returns {})."""
    import dashboard.api as _api
    monkeypatch.setattr(_api, "load_creds", lambda: {})

    resp = client.post(
        "/api/generate",
        json={"project": project, "channels": channels},
    )
    assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.data}"
    data = resp.get_json()
    assert data["ok"] is True
    return data


def _hard_flags(flags: list) -> list:
    """Return flags that are NOT 'no-anchor' (anchor is soft for stubs)."""
    return [f for f in flags if f.get("id") != "no-anchor"]


# ---------------------------------------------------------------------------
# 1. Twitter draft passes sniffer
# ---------------------------------------------------------------------------

def test_stub_twitter_draft_passes_sniffer(client, monkeypatch):
    project = {"name": "k8sauto", "desc": "A K8s autoscaler in Go that cuts cost by 47%", "pitch": "cuts cost 47%"}
    data = _generate(client, monkeypatch, project, ["twitter"])

    twitter = data["drafts"]["twitter"]
    body = twitter["body"]
    assert body, "twitter body must be non-empty"

    flags = twitter.get("flags", [])
    hard = _hard_flags(flags)
    assert hard == [], f"twitter stub has hard sniffer flags: {hard}"


# ---------------------------------------------------------------------------
# 2. Reddit draft passes sniffer + no hashtags
# ---------------------------------------------------------------------------

def test_stub_reddit_draft_passes_sniffer(client, monkeypatch):
    from sniffer_check import check as sniff_check

    project = {"name": "k8sauto", "desc": "A K8s autoscaler in Go that cuts cost by 47%", "pitch": "cuts cost 47%"}
    data = _generate(client, monkeypatch, project, ["reddit"])

    reddit = data["drafts"]["reddit"]
    title = reddit.get("title", "")
    body = reddit["body"]

    assert title, "reddit title must be non-empty"
    assert len(title) <= 300, f"reddit title too long: {len(title)} chars"
    assert body, "reddit body must be non-empty"

    flags = sniff_check(body, platform="reddit")
    hard = _hard_flags(flags)
    assert hard == [], f"reddit stub has hard sniffer flags: {hard}"

    # Critically: no hashtags on reddit
    hashtag_flags = [f for f in flags if f.get("id") == "hashtags-on-reddit"]
    assert hashtag_flags == [], f"reddit stub contains hashtags: {hashtag_flags}"


# ---------------------------------------------------------------------------
# 3. Gitmail draft uses template tokens + passes sniffer + word count
# ---------------------------------------------------------------------------

def test_stub_gitmail_draft_uses_template_tokens(client, monkeypatch):
    from sniffer_check import check as sniff_check

    project = {"name": "k8sauto", "desc": "A K8s autoscaler in Go that cuts cost by 47%", "pitch": "cuts cost 47%"}
    data = _generate(client, monkeypatch, project, ["gitmail"])

    gitmail = data["drafts"]["gitmail"]
    body = gitmail["body"]

    assert "{{login}}" in body, "gitmail stub must contain {{login}} template token"
    assert "{{starred_repo}}" in body, "gitmail stub must contain {{starred_repo}} template token"

    flags = sniff_check(body, platform="linkedin")
    hard = _hard_flags(flags)
    assert hard == [], f"gitmail stub has hard sniffer flags: {hard}"

    word_count = len(body.split())
    assert 50 <= word_count <= 300, f"gitmail body word count out of range: {word_count}"


# ---------------------------------------------------------------------------
# 4. No banned phrases across 5 projects + all 3 channels
# ---------------------------------------------------------------------------

def test_stub_drafts_no_banned_phrases(client, monkeypatch):
    issues = []
    for proj in SAMPLE_PROJECTS:
        data = _generate(client, monkeypatch, proj, ["twitter", "reddit", "gitmail"])
        for channel, draft in data["drafts"].items():
            body_lower = draft["body"].lower()
            for phrase in BANNED_PHRASES:
                if phrase in body_lower:
                    issues.append(f"{proj['name']}/{channel}: contains banned phrase '{phrase}'")

    assert issues == [], "Banned phrases found in stubs:\n" + "\n".join(issues)


# ---------------------------------------------------------------------------
# 5. Twitter stub body <= 280 chars
# ---------------------------------------------------------------------------

def test_stub_twitter_draft_within_280_chars(client, monkeypatch):
    over = []
    for proj in SAMPLE_PROJECTS:
        data = _generate(client, monkeypatch, proj, ["twitter"])
        body = data["drafts"]["twitter"]["body"]
        # For single-tweet stubs, the whole body must fit
        first_part = body.split("---")[0].strip()
        if len(first_part) > 280:
            over.append(f"{proj['name']}: {len(first_part)} chars")

    assert over == [], "Twitter stubs exceed 280 chars:\n" + "\n".join(over)


# ---------------------------------------------------------------------------
# 6. Reddit title <= 300 chars
# ---------------------------------------------------------------------------

def test_stub_reddit_title_within_300_chars(client, monkeypatch):
    over = []
    for proj in SAMPLE_PROJECTS:
        data = _generate(client, monkeypatch, proj, ["reddit"])
        title = data["drafts"]["reddit"].get("title", "")
        if len(title) > 300:
            over.append(f"{proj['name']}: {len(title)} chars")

    assert over == [], "Reddit titles exceed 300 chars:\n" + "\n".join(over)


# ---------------------------------------------------------------------------
# 7. Each draft body contains a number, the project name, or the pitch text
# ---------------------------------------------------------------------------

def test_stub_drafts_contain_anchor_or_pitch(client, monkeypatch):
    import re
    missing = []
    for proj in SAMPLE_PROJECTS:
        data = _generate(client, monkeypatch, proj, ["twitter", "reddit", "gitmail"])
        for channel, draft in data["drafts"].items():
            body = draft["body"]
            has_number = bool(re.search(r"\b\d+", body))
            has_name = proj["name"].lower() in body.lower()
            has_pitch = proj["pitch"].lower() in body.lower()
            if not (has_number or has_name or has_pitch):
                missing.append(f"{proj['name']}/{channel}: no anchor (number/name/pitch)")

    assert missing == [], "Stubs missing anchor:\n" + "\n".join(missing)


# ---------------------------------------------------------------------------
# 8. Gitmail body does not contain begging tokens
# ---------------------------------------------------------------------------

def test_stub_gitmail_low_pressure_cta(client, monkeypatch):
    found = []
    for proj in SAMPLE_PROJECTS:
        data = _generate(client, monkeypatch, proj, ["gitmail"])
        body = data["drafts"]["gitmail"]["body"].lower()
        for token in BEGGING_TOKENS:
            if token in body:
                found.append(f"{proj['name']}: contains begging token '{token}'")

    assert found == [], "Gitmail stubs contain begging language:\n" + "\n".join(found)


# ---------------------------------------------------------------------------
# 9. Suggested subreddits align with K8s keywords
# ---------------------------------------------------------------------------

def test_suggested_subreddits_align_with_keywords(client, monkeypatch):
    project = {"name": "k8sauto", "desc": "K8s autoscaler in Go", "pitch": "cuts cost 47%"}
    data = _generate(client, monkeypatch, project, ["reddit"])

    subs = [s.lower() for s in data.get("suggested_subreddits", [])]
    relevant = {"kubernetes", "devops", "golang", "sre"}
    intersection = relevant & set(subs)

    assert intersection, (
        f"No kubernetes-relevant subreddits suggested. Got: {subs}. "
        f"Expected intersection with {relevant}"
    )

    # Soft assertion: javascript should NOT appear for a K8s/Go project
    assert "javascript" not in subs, (
        f"'javascript' should not appear in subreddits for a K8s/Go project. Got: {subs}"
    )


# ---------------------------------------------------------------------------
# 10. Suggested hashtags do not include filler class
# ---------------------------------------------------------------------------

def test_suggested_hashtags_no_filler_class(client, monkeypatch):
    project = {"name": "k8sauto", "desc": "A K8s autoscaler in Go that cuts cost by 47%", "pitch": "cuts cost 47%"}
    data = _generate(client, monkeypatch, project, ["twitter"])

    hashtags = {h.lower() for h in data.get("suggested_hashtags", [])}
    overlap = FILLER_HASHTAGS & hashtags

    assert overlap == set(), (
        f"Filler hashtags found in suggestions: {overlap}. Full list: {hashtags}"
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import pytest as _pytest
    raise SystemExit(_pytest.main([__file__, "-v"]))
