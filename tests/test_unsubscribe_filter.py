"""Regression test: unsubscribed recipients are not re-emailed.

Bug: ``_run_send_job`` previously sent to every recipient in the supplied
list, ignoring the per-token unsubscribe log written by ``record_unsubscribe``.
The fix joins the unsubscribe log with a token->email map (persisted at send
time) and skips any recipient whose lower-cased email appears in that set.

Run:
  python -m pytest tests/test_unsubscribe_filter.py -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "lib"))


@pytest.fixture()
def isolated_logs(tmp_path, monkeypatch):
    """Redirect both jsonl logs to tmp_path and reset in-memory state."""
    unsub_log = tmp_path / "unsub.jsonl"
    token_map = tmp_path / "token_map.jsonl"
    monkeypatch.setenv("VIRALMAN_UNSUB_LOG", str(unsub_log))
    monkeypatch.setenv("VIRALMAN_UNSUB_TOKEN_LOG", str(token_map))

    import dashboard.api as api  # noqa: E402

    api.UNSUBSCRIBES.clear()
    api.JOBS.clear()
    yield {"unsub_log": unsub_log, "token_map": token_map, "api": api}
    api.UNSUBSCRIBES.clear()
    api.JOBS.clear()


def _seed_unsub(unsub_log: Path, token: str) -> None:
    unsub_log.write_text(
        json.dumps({"ts": 1.0, "token": token}) + "\n",
        encoding="utf-8",
    )


def _seed_token_map(token_map: Path, token: str, email: str) -> None:
    token_map.write_text(
        json.dumps({"ts": 1.0, "token": token, "email": email}) + "\n",
        encoding="utf-8",
    )


def test_unsubscribed_email_is_skipped_in_dry_run(isolated_logs, monkeypatch):
    api = isolated_logs["api"]
    unsub_log = isolated_logs["unsub_log"]
    token_map = isolated_logs["token_map"]

    # alice unsubscribed via token "tok-alice" earlier
    _seed_unsub(unsub_log, "tok-alice")
    _seed_token_map(token_map, "tok-alice", "alice@example.com")

    # No-op creds loader (avoids touching ~/.viralman/.env)
    monkeypatch.setattr(api, "load_creds", lambda: {})

    # Deterministic preview that returns a fresh token per call
    fake_tokens = iter(["tok-new-1", "tok-new-2", "tok-new-3"])

    def fake_render_preview(creds, *, to_addr, subject, body,
                             unsubscribe_base, reply_to=None):
        return {
            "from": "test@example.com",
            "to": to_addr,
            "subject": subject,
            "headers": f"To: {to_addr}\nSubject: {subject}",
            "body": body,
            "raw": body,
            "unsubscribe_token": next(fake_tokens),
        }

    monkeypatch.setattr(api.smtp_send, "render_preview", fake_render_preview)

    job = api.GitmailJob("test-job", {
        "recipients": [
            {"login": "alice", "email": "alice@example.com",
             "starred_repo": "foo/bar"},
            {"login": "bob", "email": "bob@example.com",
             "starred_repo": "foo/bar"},
        ],
        "body": "Hi {{login}}, thanks for starring {{starred_repo}}.",
        "subject": "hello",
        "dry_run": True,
        "_url_root": "http://localhost:8765",
        "_kind": "send",
    })

    api._run_send_job(job)

    events = job.events
    skip_events = [e for e in events if e.get("event") == "send_skip"]
    preview_events = [e for e in events if e.get("event") == "send_preview"]
    done_events = [e for e in events if e.get("event") == "done"]

    # alice was skipped, bob got a preview
    assert len(skip_events) == 1
    assert skip_events[0]["reason"] == "unsubscribed"
    assert skip_events[0]["to"] == "alice@example.com"

    assert len(preview_events) == 1
    assert preview_events[0]["to"] == "bob@example.com"

    # final done summary carries skipped=1
    assert len(done_events) == 1
    summary = done_events[0]["send"]
    assert summary["skipped"] == 1
    assert summary["sent"] == 0
    assert summary["failed"] == 0
    assert len(summary["previews"]) == 1
    assert summary["previews"][0]["email"] == "bob@example.com"

    # bob's token was persisted to the token-email map for future lookups
    map_lines = [json.loads(line) for line in
                  token_map.read_text(encoding="utf-8").splitlines() if line.strip()]
    bob_rows = [r for r in map_lines if r.get("email") == "bob@example.com"]
    assert bob_rows, "bob's token-email mapping should have been persisted"


def test_case_insensitive_email_match(isolated_logs, monkeypatch):
    """Mixed-case incoming email should still match the lower-cased unsub set."""
    api = isolated_logs["api"]
    _seed_unsub(isolated_logs["unsub_log"], "tok-alice")
    _seed_token_map(isolated_logs["token_map"], "tok-alice",
                     "alice@example.com")

    monkeypatch.setattr(api, "load_creds", lambda: {})
    monkeypatch.setattr(api.smtp_send, "render_preview",
                         lambda *a, **kw: {
                             "from": "x", "to": kw["to_addr"],
                             "subject": kw["subject"],
                             "headers": "", "body": kw["body"], "raw": "",
                             "unsubscribe_token": "tok-x",
                         })

    job = api.GitmailJob("t2", {
        "recipients": [
            {"login": "alice", "email": "Alice@Example.COM",
             "starred_repo": "foo/bar"},
        ],
        "body": "hi",
        "subject": "s",
        "dry_run": True,
        "_url_root": "http://localhost:8765",
    })
    api._run_send_job(job)

    skip = [e for e in job.events if e.get("event") == "send_skip"]
    preview = [e for e in job.events if e.get("event") == "send_preview"]
    assert len(skip) == 1
    assert len(preview) == 0


def test_no_unsub_files_treats_as_empty(isolated_logs, monkeypatch):
    """Missing jsonl files should not crash; everyone gets through."""
    api = isolated_logs["api"]
    # Files do not exist (we never created them in the fixture)
    assert not isolated_logs["unsub_log"].exists()
    assert not isolated_logs["token_map"].exists()

    monkeypatch.setattr(api, "load_creds", lambda: {})
    monkeypatch.setattr(api.smtp_send, "render_preview",
                         lambda *a, **kw: {
                             "from": "x", "to": kw["to_addr"],
                             "subject": kw["subject"],
                             "headers": "", "body": kw["body"], "raw": "",
                             "unsubscribe_token": "tok-fresh",
                         })

    job = api.GitmailJob("t3", {
        "recipients": [{"login": "carol", "email": "carol@example.com",
                         "starred_repo": "foo/bar"}],
        "body": "hi",
        "subject": "s",
        "dry_run": True,
        "_url_root": "http://localhost:8765",
    })
    api._run_send_job(job)

    skip = [e for e in job.events if e.get("event") == "send_skip"]
    preview = [e for e in job.events if e.get("event") == "send_preview"]
    assert len(skip) == 0
    assert len(preview) == 1


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
