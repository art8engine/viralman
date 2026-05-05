"""Regression test: CLI ``step_send`` honors the shared unsubscribe filter.

Bug: ``scripts/gitmail.py::step_send`` previously sent to every recipient,
ignoring the unsubscribe log written by the dashboard's ``/u/<token>`` route.
The fix shares the unsubscribe filter via ``scripts/lib/unsubscribe.py``.

Run:
  python -m pytest tests/test_unsubscribe_cli.py -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

import gitmail  # noqa: E402


def _make_composed(rows):
    """Build a composed list as step_send expects (login, email, starred_repo,
    profile, subject, body)."""
    return [{
        "login": r["login"],
        "email": r["email"],
        "starred_repo": r.get("starred_repo", "u/r"),
        "profile": r.get("profile", ""),
        "subject": r.get("subject", "hi"),
        "body": r.get("body", "test body"),
    } for r in rows]


def _capture_emits():
    captured: list[dict] = []

    def fake_emit(event: str, **fields):
        captured.append({"event": event, **fields})

    return captured, patch.object(gitmail, "_emit", side_effect=fake_emit)


@pytest.fixture()
def isolated_logs(tmp_path, monkeypatch):
    """Redirect both jsonl logs to tmp_path so the test never writes to repo."""
    unsub_log = tmp_path / "unsub.jsonl"
    token_map = tmp_path / "token_map.jsonl"
    monkeypatch.setenv("VIRALMAN_UNSUB_LOG", str(unsub_log))
    monkeypatch.setenv("VIRALMAN_UNSUB_TOKEN_LOG", str(token_map))
    return {"unsub_log": unsub_log, "token_map": token_map}


def _seed_unsub(unsub_log: Path, token: str) -> None:
    with unsub_log.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": 1.0, "token": token}) + "\n")


def _seed_token_map(token_map: Path, token: str, email: str) -> None:
    with token_map.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": 1.0, "token": token, "email": email}) + "\n")


# --------------------------------------------------------------------------- #
# Test 1 — dry-run filters unsubscribed; previews only the rest               #
# --------------------------------------------------------------------------- #


def test_cli_step_send_filters_unsubscribed_dry_run(isolated_logs):
    _seed_unsub(isolated_logs["unsub_log"], "tok-alice")
    _seed_token_map(isolated_logs["token_map"], "tok-alice", "alice@example.com")

    composed = _make_composed([
        {"login": "alice", "email": "alice@example.com"},
        {"login": "bob", "email": "bob@example.com"},
        {"login": "carol", "email": "carol@example.com"},
    ])

    fake_tokens = iter(["tok-bob", "tok-carol"])

    def fake_render_preview(creds, *, to_addr, subject, body,
                             unsubscribe_base, reply_to=None):
        return {
            "from": "test@x", "to": to_addr, "subject": subject,
            "headers": f"To: {to_addr}\nSubject: {subject}",
            "body": body, "raw": body,
            "unsubscribe_token": next(fake_tokens),
        }

    captured, emit_patch = _capture_emits()
    with patch.object(gitmail.smtp_send, "render_preview",
                       side_effect=fake_render_preview), \
         emit_patch:
        result = gitmail.step_send(
            {}, composed,
            unsubscribe_base="http://localhost:8765",
            dry_run=True,
        )

    skip_events = [e for e in captured if e["event"] == "send_skip"]
    preview_events = [e for e in captured if e["event"] == "send_preview"]
    assert len(skip_events) == 1
    assert skip_events[0]["reason"] == "unsubscribed"
    assert skip_events[0]["to"] == "alice@example.com"

    assert len(preview_events) == 2
    preview_emails = {e["to"] for e in preview_events}
    assert preview_emails == {"bob@example.com", "carol@example.com"}

    # Returned dict carries skipped count and the skip rows
    assert result["sent"] == 0
    assert result["failed"] == 0
    assert result["skipped"] == 1
    assert len(result["previews"]) == 2
    assert result["skips"][0]["email"] == "alice@example.com"


# --------------------------------------------------------------------------- #
# Test 2 — live send filters unsubscribed; send_one called only for rest      #
# --------------------------------------------------------------------------- #


def test_cli_step_send_filters_unsubscribed_live(isolated_logs):
    _seed_unsub(isolated_logs["unsub_log"], "tok-alice")
    _seed_token_map(isolated_logs["token_map"], "tok-alice", "alice@example.com")

    composed = _make_composed([
        {"login": "alice", "email": "alice@example.com"},
        {"login": "bob", "email": "bob@example.com"},
    ])

    fake_smtp = MagicMock()
    fake_limiter = MagicMock()
    send_one_calls: list[str] = []

    def fake_send_one(smtp, creds, *, to_addr, subject, body,
                       unsubscribe_base, reply_to=None):
        send_one_calls.append(to_addr)
        return {"to": to_addr, "subject": subject,
                "message_id": "<x@y>", "unsubscribe_token": "tok-new-bob"}

    creds = {"SMTP_FROM": "me@x", "SMTP_USER": "me", "SMTP_PASSWORD": "pw",
             "SMTP_HOST": "smtp.x"}

    captured, emit_patch = _capture_emits()
    with patch.object(gitmail.smtp_send, "open_session",
                       return_value=(fake_smtp, fake_limiter)), \
         patch.object(gitmail.smtp_send, "send_one",
                       side_effect=fake_send_one), \
         emit_patch:
        result = gitmail.step_send(
            creds, composed,
            unsubscribe_base="http://localhost:8765",
            dry_run=False,
        )

    # alice was skipped, bob was sent
    assert send_one_calls == ["bob@example.com"]
    skip_events = [e for e in captured if e["event"] == "send_skip"]
    assert len(skip_events) == 1
    assert skip_events[0]["to"] == "alice@example.com"

    # rate-limiter only used for the actually-sent recipient
    assert fake_limiter.wait.call_count == 1

    assert result["sent"] == 1
    assert result["failed"] == 0
    assert result["skipped"] == 1


# --------------------------------------------------------------------------- #
# Test 3 — live send records token→email map after each send_one              #
# --------------------------------------------------------------------------- #


def test_cli_records_token_email_after_send(isolated_logs):
    composed = _make_composed([
        {"login": "alice", "email": "alice@example.com"},
        {"login": "bob", "email": "bob@example.com"},
    ])

    fake_smtp = MagicMock()
    fake_limiter = MagicMock()
    tokens = iter(["tok-1", "tok-2"])

    def fake_send_one(smtp, creds, *, to_addr, subject, body,
                       unsubscribe_base, reply_to=None):
        return {"to": to_addr, "subject": subject,
                "message_id": "<m@x>", "unsubscribe_token": next(tokens)}

    creds = {"SMTP_FROM": "me@x", "SMTP_USER": "me", "SMTP_PASSWORD": "pw",
             "SMTP_HOST": "smtp.x"}

    _, emit_patch = _capture_emits()
    with patch.object(gitmail.smtp_send, "open_session",
                       return_value=(fake_smtp, fake_limiter)), \
         patch.object(gitmail.smtp_send, "send_one",
                       side_effect=fake_send_one), \
         emit_patch:
        gitmail.step_send(
            creds, composed,
            unsubscribe_base="http://localhost:8765",
            dry_run=False,
        )

    map_path = isolated_logs["token_map"]
    assert map_path.exists()
    rows = [json.loads(line) for line in
            map_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    # 2 sends → 2 mapping rows
    emails = {r["email"] for r in rows}
    assert emails == {"alice@example.com", "bob@example.com"}
    tokens_seen = {r["token"] for r in rows}
    assert tokens_seen == {"tok-1", "tok-2"}


# --------------------------------------------------------------------------- #
# Test 4 — case-insensitive email match                                        #
# --------------------------------------------------------------------------- #


def test_cli_case_insensitive_email_match(isolated_logs):
    # Stored token→email mapping uses mixed case; lower-casing should normalise
    _seed_unsub(isolated_logs["unsub_log"], "tok-mixed")
    _seed_token_map(isolated_logs["token_map"], "tok-mixed",
                     "Alice@Example.COM")

    composed = _make_composed([
        {"login": "alice", "email": "alice@example.com"},
    ])

    captured, emit_patch = _capture_emits()
    with patch.object(gitmail.smtp_send, "render_preview",
                       side_effect=lambda *a, **kw: {
                           "from": "x", "to": kw["to_addr"],
                           "subject": kw["subject"],
                           "headers": "", "body": "", "raw": "",
                           "unsubscribe_token": "tok-x",
                       }), \
         emit_patch:
        result = gitmail.step_send(
            {}, composed,
            unsubscribe_base="http://localhost:8765",
            dry_run=True,
        )

    skip_events = [e for e in captured if e["event"] == "send_skip"]
    preview_events = [e for e in captured if e["event"] == "send_preview"]
    assert len(skip_events) == 1
    assert len(preview_events) == 0
    assert result["skipped"] == 1
    assert result["sent"] == 0


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
