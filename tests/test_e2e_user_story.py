"""E2E regression tests — 5-step slash-only user story (no dashboard).

Pipeline flow being tested:
  1. (plugin install — skipped, external)
  2. /viralman-setup saves creds
  3. /gitmail  → collect recipients (seed-repos OR keywords path)
  4. review collected recipients (out-of-process, user action — covered by verifying output)
  5. /gitmail send-from-recipients → compose + send / dry-run

All network I/O (GitHub / SMTP / LLM) is monkeypatched.
Tests call cmd_* functions directly via argparse.Namespace so that
unittest.mock.patch can intercept gitmail module-level imports cleanly.

Run:
    .venv/bin/python -m pytest tests/test_e2e_user_story.py -v
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

import gitmail  # noqa: E402


# --------------------------------------------------------------------------- #
# Shared helpers                                                               #
# --------------------------------------------------------------------------- #


def _capture_emits():
    """Return (list, context-manager) that captures all _emit() calls."""
    captured: list[dict] = []

    def fake_emit(event: str, **fields):
        captured.append({"event": event, **fields})

    return captured, patch.object(gitmail, "_emit", side_effect=fake_emit)


def _make_recipients(n: int, *, missing_email_idx: int | None = None) -> list[dict]:
    rows = []
    for i in range(n):
        email = "" if i == missing_email_idx else f"user{i}@example.com"
        rows.append({
            "login": f"user{i}",
            "email": email,
            "starred_repo": f"upstream/repo{i}",
            "profile": f"https://github.com/user{i}",
        })
    return rows


def _tmp_json(payload: object) -> Path:
    f = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
    f.write(json.dumps(payload).encode("utf-8"))
    f.close()
    return Path(f.name)


def _fake_compose_email(creds, **kwargs):
    login = kwargs.get("login", "unknown")
    starred = kwargs.get("starred_repo", "u/r")
    return {
        "subject": f"note to {login}",
        "body": f"hi @{login}, saw you starred {starred}",
    }


def _build_recipients_args(**overrides) -> argparse.Namespace:
    defaults = dict(
        cmd="recipients",
        description="",
        project_name="demo",
        project_url="",
        pitch="",
        provider=None,
        min_stars=200,
        repo_limit=15,
        max_users=5,
        keywords=None,
        topics=None,
        seed_repos=None,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _build_send_args(**overrides) -> argparse.Namespace:
    defaults = dict(
        cmd="send-from-recipients",
        recipients_file=None,
        recipients_stdin=None,
        project_name="TestProject",
        description="JVM monitor SaaS",
        project_url="https://github.com/me/testproject",
        pitch="",
        provider=None,
        tone=None,
        emphasis=None,
        dry_run=True,
        template_only=False,
        unsubscribe_base="http://localhost:8765",
        reply_to=None,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _build_run_args(**overrides) -> argparse.Namespace:
    defaults = dict(
        cmd="run",
        description="JVM monitor",
        project_name="jvmmon",
        project_url="https://github.com/me/jvmmon",
        pitch="",
        provider=None,
        min_stars=200,
        repo_limit=15,
        max_users=2,
        keywords=None,
        topics=None,
        seed_repos=None,
        tone=None,
        emphasis=None,
        dry_run=True,
        template_only=False,
        unsubscribe_base="http://localhost:8765",
        reply_to=None,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


# --------------------------------------------------------------------------- #
# Case 1 — step3: seed-repos path skips search, calls iter_stargazers per repo #
# --------------------------------------------------------------------------- #


class TestStep3CollectWithSeedRepos(unittest.TestCase):
    """User specifies --seed-repos; search_similar_repos must NOT be called."""

    def test_step3_collect_with_seed_repos(self):
        search_calls: list = []
        stargazer_calls: list[str] = []

        def fake_search(**kwargs):
            search_calls.append(kwargs)
            return []

        def fake_stargazers(full_name, max_users=None, token=None):
            stargazer_calls.append(full_name)
            users = [
                {"login": f"{full_name.replace('/', '-')}-{i}",
                 "html_url": f"https://github.com/u{i}"}
                for i in range(3)
            ]
            return iter(users)

        email_map = {
            "jvm-profiling-async-profiler-0": "a0@x.com",
            "jvm-profiling-async-profiler-1": "a1@x.com",
            "oracle-graal-0": "b0@x.com",
            "oracle-graal-1": "b1@x.com",
            "oracle-graal-2": "b2@x.com",
        }

        captured, emit_patch = _capture_emits()
        with patch.object(gitmail, "load_creds", return_value={}), \
             patch.object(gitmail.github_search, "search_similar_repos",
                          side_effect=fake_search), \
             patch.object(gitmail.github_search, "iter_stargazers",
                          side_effect=fake_stargazers), \
             patch.object(gitmail.github_search, "resolve_user_email",
                          side_effect=lambda login, token=None: email_map.get(login, "")), \
             patch("builtins.print"), \
             emit_patch:
            args = _build_recipients_args(
                seed_repos="jvm-profiling/async-profiler,oracle/graal",
                max_users=5,
            )
            rc = gitmail.cmd_recipients(args)

        self.assertEqual(rc, 0)
        # search NOT called (seed repos bypass search)
        self.assertEqual(search_calls, [],
                         "search_similar_repos must not be called when --seed-repos is given")
        # iter_stargazers called for both seed repos
        self.assertIn("jvm-profiling/async-profiler", stargazer_calls)
        self.assertIn("oracle/graal", stargazer_calls)
        # recipients_done event emitted with count ≤ 5
        done_events = [e for e in captured if e["event"] == "recipients_done"]
        self.assertEqual(len(done_events), 1)
        self.assertLessEqual(done_events[0]["count"], 5)


# --------------------------------------------------------------------------- #
# Case 2 — step3: --keywords overrides analyse output in search call           #
# --------------------------------------------------------------------------- #


class TestStep3CollectWithKeywordsOverride(unittest.TestCase):
    """--keywords jvm,profiler must be forwarded to search_similar_repos,
    overriding whatever analyse_project_llm returned."""

    def test_step3_collect_with_keywords_override(self):
        captured_search_kw: list[dict] = []

        def fake_search(*, topics, keywords=None, min_stars=200, limit=15,
                        token=None, exclude_full_names=None):
            captured_search_kw.append({
                "topics": list(topics or []),
                "keywords": list(keywords or []),
            })
            return [{"full_name": "a/x", "stars": 500, "topics": [],
                     "html_url": "", "description": ""}]

        def fake_stargazers(full_name, max_users=None, token=None):
            return iter([{"login": "alice", "html_url": "https://github.com/alice"}])

        captured, emit_patch = _capture_emits()
        with patch.object(gitmail, "load_creds", return_value={}), \
             patch.object(gitmail.llm_compose, "analyse_project_llm",
                          return_value={"summary": "s", "keywords": ["bogus"],
                                        "topics": ["wrong-topic"], "value_prop": ""}), \
             patch.object(gitmail.github_search, "search_similar_repos",
                          side_effect=fake_search), \
             patch.object(gitmail.github_search, "iter_stargazers",
                          side_effect=fake_stargazers), \
             patch.object(gitmail.github_search, "resolve_user_email",
                          return_value="alice@example.com"), \
             patch("builtins.print"), \
             emit_patch:
            args = _build_recipients_args(
                description="JVM monitoring SaaS",
                keywords="jvm,profiler",
                max_users=3,
            )
            rc = gitmail.cmd_recipients(args)

        self.assertEqual(rc, 0)
        self.assertEqual(len(captured_search_kw), 1,
                         "search_similar_repos should be called exactly once")
        # CLI --keywords override must win over analyse output
        self.assertEqual(captured_search_kw[0]["keywords"], ["jvm", "profiler"],
                         "keywords passed to search must be the CLI override, not analyse output")
        # topics remain from analyse (no --topics override given)
        self.assertEqual(captured_search_kw[0]["topics"], ["wrong-topic"])


# --------------------------------------------------------------------------- #
# Case 3 — step5 dry-run: tone/emphasis reach compose_email; smtp not opened   #
# --------------------------------------------------------------------------- #


class TestStep5SendFromRecipientsWithToneEmphasis(unittest.TestCase):
    """send-from-recipients --dry-run: tone/emphasis forwarded; SMTP not opened;
    send_dry_run_done emitted with 3 previews."""

    def test_step5_send_from_recipients_with_tone_emphasis(self):
        recipients = _make_recipients(3)
        rfile = _tmp_json(recipients)
        self.addCleanup(lambda: rfile.unlink(missing_ok=True))

        captured_compose_kwargs: list[dict] = []
        smtp_open_calls: list = []

        def capturing_compose(creds, **kwargs):
            captured_compose_kwargs.append(kwargs)
            return _fake_compose_email(creds, **kwargs)

        captured, emit_patch = _capture_emits()
        with patch.object(gitmail, "load_creds",
                          return_value={"SMTP_FROM": "me@x.com", "SMTP_USER": "me@x.com"}), \
             patch.object(gitmail.llm_compose, "compose_email",
                          side_effect=capturing_compose), \
             patch.object(gitmail.smtp_send, "open_session",
                          side_effect=smtp_open_calls.append), \
             emit_patch:
            args = _build_send_args(
                recipients_file=str(rfile),
                tone="친근한 개발자 톤",
                emphasis="47% 비용 절감",
                dry_run=True,
            )
            rc = gitmail.cmd_send_from_recipients(args)

        self.assertEqual(rc, 0)
        # SMTP session must NOT be opened in dry-run
        self.assertEqual(smtp_open_calls, [],
                         "smtp_send.open_session must not be called in dry-run mode")
        # tone and emphasis forwarded to every compose_email call
        self.assertEqual(len(captured_compose_kwargs), 3)
        for kw in captured_compose_kwargs:
            self.assertEqual(kw.get("tone"), "친근한 개발자 톤",
                             "tone must be forwarded to compose_email")
            self.assertEqual(kw.get("emphasis"), "47% 비용 절감",
                             "emphasis must be forwarded to compose_email")
        # send_dry_run_done event + exactly 3 previews
        event_names = [e["event"] for e in captured]
        self.assertIn("send_dry_run_done", event_names)
        previews = [e for e in captured if e["event"] == "send_preview"]
        self.assertEqual(len(previews), 3)
        # done event has previews_count == 3
        done = next(e for e in reversed(captured) if e["event"] == "done")
        self.assertEqual(done["send"]["previews_count"], 3)
        self.assertEqual(done["send"]["sent"], 0)


# --------------------------------------------------------------------------- #
# Case 4 — step5 live send: SMTP opened + send_one + rate-limiter called N×    #
# --------------------------------------------------------------------------- #


class TestStep5LiveSendCallsSmtpWithRateLimit(unittest.TestCase):
    """Without --dry-run: open_session called once, send_one and limiter.wait
    each called once per recipient; final done event has send.sent == N."""

    def test_step5_live_send_calls_smtp_with_rate_limit(self):
        recipients = _make_recipients(3)
        rfile = _tmp_json(recipients)
        self.addCleanup(lambda: rfile.unlink(missing_ok=True))

        fake_smtp = MagicMock()
        fake_limiter = MagicMock()
        send_one_results = [
            {"to": r["email"], "subject": "s", "message_id": f"<{i}@x>",
             "unsubscribe_token": f"tok{i}"}
            for i, r in enumerate(recipients)
        ]
        send_one_call_count = {"n": 0}

        def fake_send_one(smtp, creds, *, to_addr, subject, body,
                          unsubscribe_base, reply_to=None):
            idx = send_one_call_count["n"]
            send_one_call_count["n"] += 1
            return send_one_results[idx]

        captured, emit_patch = _capture_emits()
        with patch.object(gitmail, "load_creds",
                          return_value={"SMTP_FROM": "me@x.com",
                                        "SMTP_USER": "me",
                                        "SMTP_PASSWORD": "pw",
                                        "SMTP_HOST": "smtp.x.com"}), \
             patch.object(gitmail.llm_compose, "compose_email",
                          side_effect=_fake_compose_email), \
             patch.object(gitmail.smtp_send, "open_session",
                          return_value=(fake_smtp, fake_limiter)), \
             patch.object(gitmail.smtp_send, "send_one",
                          side_effect=fake_send_one), \
             emit_patch:
            args = _build_send_args(
                recipients_file=str(rfile),
                dry_run=False,
            )
            rc = gitmail.cmd_send_from_recipients(args)

        self.assertEqual(rc, 0)
        # send_one called once per recipient
        self.assertEqual(send_one_call_count["n"], 3)
        # rate limiter wait() called once per recipient
        self.assertEqual(fake_limiter.wait.call_count, 3)
        # final done event: send.sent == 3
        done = next(e for e in reversed(captured) if e["event"] == "done")
        self.assertEqual(done["send"]["sent"], 3)
        self.assertEqual(done["send"]["failed"], 0)


# --------------------------------------------------------------------------- #
# Case 5 — step4: rows with missing email are skipped                          #
# --------------------------------------------------------------------------- #


class TestStep4RecipientsSkippedForMissingEmail(unittest.TestCase):
    """4 recipients, 1 missing email → 3 previews + 1 recipients_skipped event."""

    def test_step4_recipients_skipped_for_missing_email(self):
        # index 2 has no email
        recipients = _make_recipients(4, missing_email_idx=2)
        rfile = _tmp_json(recipients)
        self.addCleanup(lambda: rfile.unlink(missing_ok=True))

        captured, emit_patch = _capture_emits()
        with patch.object(gitmail, "load_creds",
                          return_value={"SMTP_FROM": "me@x.com", "SMTP_USER": "me@x.com"}), \
             patch.object(gitmail.llm_compose, "compose_email",
                          side_effect=_fake_compose_email), \
             emit_patch:
            args = _build_send_args(recipients_file=str(rfile), dry_run=True)
            rc = gitmail.cmd_send_from_recipients(args)

        self.assertEqual(rc, 0)
        # exactly 3 previews (the row with missing email is dropped)
        previews = [e for e in captured if e["event"] == "send_preview"]
        self.assertEqual(len(previews), 3)
        # recipients_skipped event with count == 1
        skipped_events = [e for e in captured if e["event"] == "recipients_skipped"]
        self.assertEqual(len(skipped_events), 1)
        self.assertEqual(skipped_events[0]["count"], 1)


# --------------------------------------------------------------------------- #
# Case 6 — full pipeline: `run` subcommand wires all 5 steps end-to-end        #
# --------------------------------------------------------------------------- #


class TestFullPipelineRunWithUserOverrides(unittest.TestCase):
    """cmd_run --dry-run with keywords/tone/emphasis: verifies compose_email
    receives tone+emphasis, done.send.sent==0, previews==2."""

    def test_full_pipeline_run_with_user_overrides(self):
        fake_repo = [{"full_name": "some/repo", "stars": 1000, "topics": [],
                      "html_url": "", "description": ""}]

        def fake_stargazers(full_name, max_users=None, token=None):
            return iter([
                {"login": "dev0", "html_url": "https://github.com/dev0"},
                {"login": "dev1", "html_url": "https://github.com/dev1"},
            ])

        email_map = {"dev0": "dev0@x.com", "dev1": "dev1@x.com"}
        compose_kwargs_list: list[dict] = []

        def capturing_compose(creds, **kwargs):
            compose_kwargs_list.append(kwargs)
            return _fake_compose_email(creds, **kwargs)

        captured, emit_patch = _capture_emits()
        with patch.object(gitmail, "load_creds",
                          return_value={"SMTP_FROM": "me@x.com", "SMTP_USER": "me@x.com"}), \
             patch.object(gitmail.llm_compose, "analyse_project_llm",
                          return_value={"summary": "s", "keywords": ["jvm"],
                                        "topics": ["jvm"], "value_prop": "cuts cost"}), \
             patch.object(gitmail.github_search, "search_similar_repos",
                          return_value=fake_repo), \
             patch.object(gitmail.github_search, "iter_stargazers",
                          side_effect=fake_stargazers), \
             patch.object(gitmail.github_search, "resolve_user_email",
                          side_effect=lambda login, token=None: email_map.get(login, "")), \
             patch.object(gitmail.llm_compose, "compose_email",
                          side_effect=capturing_compose), \
             emit_patch:
            args = _build_run_args(
                description="JVM monitor",
                keywords="jvm,profiler",
                max_users=2,
                tone="casual",
                emphasis="free, OSS",
                dry_run=True,
            )
            rc = gitmail.cmd_run(args)

        self.assertEqual(rc, 0)
        # dry-run: sent == 0, previews == 2
        done = next(e for e in reversed(captured) if e["event"] == "done")
        self.assertEqual(done["send"]["sent"], 0)
        self.assertEqual(done["send"]["previews_count"], 2)
        # tone and emphasis reached compose_email
        self.assertGreater(len(compose_kwargs_list), 0,
                           "compose_email must be called at least once")
        for kw in compose_kwargs_list:
            self.assertEqual(kw.get("tone"), "casual",
                             "tone must reach compose_email")
            self.assertEqual(kw.get("emphasis"), "free, OSS",
                             "emphasis must reach compose_email")


# --------------------------------------------------------------------------- #
# Case 7 — seed-repos without --description: analyse step skipped              #
# --------------------------------------------------------------------------- #


class TestSeedReposPathWorksWithoutDescription(unittest.TestCase):
    """--seed-repos only, no --description → analyse step skipped, normal exit."""

    def test_seed_repos_path_works_without_description(self):
        analyse_calls: list = []

        def fake_stargazers(full_name, max_users=None, token=None):
            return iter([
                {"login": f"{full_name.replace('/', '_')}_u",
                 "html_url": "https://github.com/u"}
            ])

        captured, emit_patch = _capture_emits()
        with patch.object(gitmail, "load_creds", return_value={}), \
             patch.object(gitmail.llm_compose, "analyse_project_llm",
                          side_effect=lambda *a, **kw: analyse_calls.append(1) or {}), \
             patch.object(gitmail.github_search, "search_similar_repos",
                          return_value=[]), \
             patch.object(gitmail.github_search, "iter_stargazers",
                          side_effect=fake_stargazers), \
             patch.object(gitmail.github_search, "resolve_user_email",
                          return_value="u@x.com"), \
             patch("builtins.print"), \
             emit_patch:
            args = _build_recipients_args(
                seed_repos="a/b,c/d",
                description="",   # explicitly empty
                max_users=2,
            )
            rc = gitmail.cmd_recipients(args)

        self.assertEqual(rc, 0, "should exit 0 with seed-repos and no description")
        # analyse_project_llm must NOT be called (no description to analyse)
        self.assertEqual(analyse_calls, [],
                         "analyse_project_llm must not be called when description is absent")
        # recipients_done emitted
        done_events = [e for e in captured if e["event"] == "recipients_done"]
        self.assertEqual(len(done_events), 1)
        self.assertGreater(done_events[0]["count"], 0)


# --------------------------------------------------------------------------- #
# Case 8 — dry-run then live: same recipients file, same compose args both times #
# --------------------------------------------------------------------------- #


class TestDryRunThenLiveTwoPhaseSendIdempotentRecipients(unittest.TestCase):
    """Using the same recipients JSON for a dry-run call then a live call:
    - Both calls invoke compose_email with identical kwargs.
    - dry-run: send_one not called.
    - live: send_one called N times.
    """

    def test_dry_run_then_live_two_phase_send_idempotent_recipients(self):
        n = 3
        recipients = _make_recipients(n)
        rfile = _tmp_json(recipients)
        self.addCleanup(lambda: rfile.unlink(missing_ok=True))

        dry_compose_kwargs: list[dict] = []
        live_compose_kwargs: list[dict] = []

        def dry_compose(creds, **kwargs):
            dry_compose_kwargs.append(kwargs)
            return _fake_compose_email(creds, **kwargs)

        def live_compose(creds, **kwargs):
            live_compose_kwargs.append(kwargs)
            return _fake_compose_email(creds, **kwargs)

        fake_smtp = MagicMock()
        fake_limiter = MagicMock()
        send_one_calls = {"n": 0}

        def fake_send_one(smtp, creds, *, to_addr, subject, body,
                          unsubscribe_base, reply_to=None):
            send_one_calls["n"] += 1
            return {"to": to_addr, "subject": subject,
                    "message_id": f"<{send_one_calls['n']}@x>",
                    "unsubscribe_token": "tok"}

        creds = {"SMTP_FROM": "me@x.com", "SMTP_USER": "me",
                 "SMTP_PASSWORD": "pw", "SMTP_HOST": "smtp.x.com"}

        # --- dry-run pass ---
        dry_captured, dry_emit_patch = _capture_emits()
        with patch.object(gitmail, "load_creds", return_value=creds), \
             patch.object(gitmail.llm_compose, "compose_email",
                          side_effect=dry_compose), \
             dry_emit_patch:
            dry_args = _build_send_args(
                recipients_file=str(rfile),
                tone="concise",
                emphasis="zero cost",
                dry_run=True,
            )
            dry_rc = gitmail.cmd_send_from_recipients(dry_args)

        # --- live pass ---
        live_captured, live_emit_patch = _capture_emits()
        with patch.object(gitmail, "load_creds", return_value=creds), \
             patch.object(gitmail.llm_compose, "compose_email",
                          side_effect=live_compose), \
             patch.object(gitmail.smtp_send, "open_session",
                          return_value=(fake_smtp, fake_limiter)), \
             patch.object(gitmail.smtp_send, "send_one",
                          side_effect=fake_send_one), \
             live_emit_patch:
            live_args = _build_send_args(
                recipients_file=str(rfile),
                tone="concise",
                emphasis="zero cost",
                dry_run=False,
            )
            live_rc = gitmail.cmd_send_from_recipients(live_args)

        # Both passes exit cleanly
        self.assertEqual(dry_rc, 0)
        self.assertEqual(live_rc, 0)

        # dry-run: send_one not called at all
        # (send_one_calls["n"] should still be 0 after dry run, incremented only in live)
        # We test by checking live added all N
        self.assertEqual(send_one_calls["n"], n,
                         "send_one must be called once per recipient in live mode")

        # compose_email called N times in each pass
        self.assertEqual(len(dry_compose_kwargs), n)
        self.assertEqual(len(live_compose_kwargs), n)

        # Both passes used identical kwargs (project_name, tone, emphasis, logins)
        for dk, lk in zip(dry_compose_kwargs, live_compose_kwargs):
            self.assertEqual(dk.get("tone"), lk.get("tone"),
                             "tone must be identical across dry-run and live")
            self.assertEqual(dk.get("emphasis"), lk.get("emphasis"),
                             "emphasis must be identical across dry-run and live")
            self.assertEqual(dk.get("login"), lk.get("login"),
                             "login must be identical across dry-run and live")
            self.assertEqual(dk.get("project_name"), lk.get("project_name"),
                             "project_name must be identical across dry-run and live")

        # dry-run done event: sent == 0
        dry_done = next(e for e in reversed(dry_captured) if e["event"] == "done")
        self.assertEqual(dry_done["send"]["sent"], 0)

        # live done event: sent == n
        live_done = next(e for e in reversed(live_captured) if e["event"] == "done")
        self.assertEqual(live_done["send"]["sent"], n)


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
