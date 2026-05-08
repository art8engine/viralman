"""Regression tests for the new collect→send split in gitmail.py.

Covers:
  - send-from-recipients subcommand (file + stdin paths, dry-run previews,
    template-only reuse, missing-field skipping)
  - tone/emphasis arguments threaded through to llm_compose.compose_email
  - --keywords override on `recipients`
  - --seed-repos skips search on `recipients`

Run:
  .venv/bin/python -m pytest tests/test_gitmail_send_phase.py -v
"""

from __future__ import annotations

import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

import gitmail  # noqa: E402
import llm_compose  # noqa: E402


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #


def _capture_emits():
    """Capture all _emit() events from gitmail."""
    captured: list[dict] = []

    def fake_emit(event: str, **fields):
        captured.append({"event": event, **fields})

    return captured, patch.object(gitmail, "_emit", side_effect=fake_emit)


def _make_recipients(n: int) -> list[dict]:
    return [{
        "login": f"user{i}",
        "email": f"user{i}@example.com",
        "starred_repo": f"upstream/repo{i}",
        "profile": f"https://github.com/user{i}",
    } for i in range(n)]


def _build_send_args(
    *,
    recipients_file: str | None = None,
    recipients_stdin: str | None = None,
    project_name: str = "demo",
    description: str = "an open source thing",
    project_url: str = "https://github.com/me/demo",
    pitch: str = "",
    provider=None,
    tone=None,
    emphasis=None,
    dry_run: bool = True,
    template_only: bool = False,
    unsubscribe_base: str = "http://localhost:8765",
    reply_to=None,
):
    import argparse
    return argparse.Namespace(
        cmd="send-from-recipients",
        recipients_file=recipients_file,
        recipients_stdin=recipients_stdin,
        project_name=project_name,
        description=description,
        project_url=project_url,
        pitch=pitch,
        provider=provider,
        tone=tone,
        emphasis=emphasis,
        dry_run=dry_run,
        template_only=template_only,
        unsubscribe_base=unsubscribe_base,
        reply_to=reply_to,
    )


def _build_recipients_args(
    *,
    description: str = "",
    project_name: str = "demo",
    project_url: str = "",
    pitch: str = "",
    provider=None,
    min_stars: int = 200,
    repo_limit: int = 15,
    max_users: int = 5,
    keywords=None,
    topics=None,
    seed_repos=None,
):
    import argparse
    return argparse.Namespace(
        cmd="recipients",
        description=description,
        project_name=project_name,
        project_url=project_url,
        pitch=pitch,
        provider=provider,
        min_stars=min_stars,
        repo_limit=repo_limit,
        max_users=max_users,
        keywords=keywords,
        topics=topics,
        seed_repos=seed_repos,
    )


def _fake_compose_email(creds, **kwargs):
    """Pretend to be llm_compose.compose_email for capturing kwargs."""
    return {
        "subject": f"hello {kwargs.get('login', '')}",
        "body": (f"hi @{kwargs.get('login', '')}\n"
                  f"saw you starred {kwargs.get('starred_repo', '')}\n"
                  f"about {kwargs.get('project_name', '')}: "
                  f"{kwargs.get('project_pitch', '')}"),
    }


# --------------------------------------------------------------------------- #
# 1. send-from-recipients dry-run emits previews                              #
# --------------------------------------------------------------------------- #


class TestSendFromRecipientsDryRunEmitsPreviews(unittest.TestCase):
    def test_send_from_recipients_dry_run_emits_previews(self):
        recipients = _make_recipients(5)
        recipients_file = self.tmp_path()
        recipients_file.write_text(json.dumps(recipients), encoding="utf-8")

        captured, emit_patch = _capture_emits()
        with patch.object(gitmail, "load_creds", return_value={"SMTP_FROM": "me@x.com",
                                                                 "SMTP_USER": "me@x.com"}), \
             patch.object(llm_compose, "compose_email", side_effect=_fake_compose_email), \
             patch.object(gitmail.llm_compose, "compose_email",
                          side_effect=_fake_compose_email), \
             emit_patch:
            args = _build_send_args(recipients_file=str(recipients_file),
                                     dry_run=True)
            rc = gitmail.cmd_send_from_recipients(args)

        self.assertEqual(rc, 0)
        kinds = [e["event"] for e in captured]
        self.assertIn("send_dry_run_done", kinds)
        # 5 send_preview events emitted
        self.assertEqual(sum(1 for e in captured if e["event"] == "send_preview"), 5)
        # No send_ok / send_fail in dry-run
        self.assertNotIn("send_ok", kinds)
        self.assertNotIn("send_fail", kinds)
        # Final done has previews count of 5
        done = [e for e in captured if e["event"] == "done"][-1]
        self.assertEqual(done["send"]["previews_count"], 5)
        self.assertEqual(done["send"]["sent"], 0)
        self.assertEqual(done["send"]["failed"], 0)

    def tmp_path(self) -> Path:
        import tempfile
        f = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        f.close()
        path = Path(f.name)
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        return path


# --------------------------------------------------------------------------- #
# 2. send-from-recipients reads stdin                                          #
# --------------------------------------------------------------------------- #


class TestSendFromRecipientsStdin(unittest.TestCase):
    def test_send_from_recipients_stdin(self):
        recipients = _make_recipients(5)
        captured, emit_patch = _capture_emits()
        stdin_buffer = io.StringIO(json.dumps(recipients))

        with patch.object(gitmail, "load_creds", return_value={"SMTP_FROM": "me@x.com",
                                                                 "SMTP_USER": "me@x.com"}), \
             patch.object(gitmail.llm_compose, "compose_email",
                          side_effect=_fake_compose_email), \
             patch.object(gitmail.sys, "stdin", stdin_buffer), \
             emit_patch:
            args = _build_send_args(recipients_stdin="-", dry_run=True)
            rc = gitmail.cmd_send_from_recipients(args)

        self.assertEqual(rc, 0)
        previews = [e for e in captured if e["event"] == "send_preview"]
        self.assertEqual(len(previews), 5)


# --------------------------------------------------------------------------- #
# 3. tone passed to compose_email                                             #
# --------------------------------------------------------------------------- #


class TestTonePassedToComposeEmail(unittest.TestCase):
    def test_tone_passed_to_compose_email(self):
        recipients = _make_recipients(2)
        captured_kwargs: list[dict] = []

        def capturing_compose(creds, **kwargs):
            captured_kwargs.append(kwargs)
            return _fake_compose_email(creds, **kwargs)

        recipients_file = self._tmp(recipients)
        captured, emit_patch = _capture_emits()
        with patch.object(gitmail, "load_creds", return_value={"SMTP_FROM": "me@x.com",
                                                                 "SMTP_USER": "me@x.com"}), \
             patch.object(gitmail.llm_compose, "compose_email",
                          side_effect=capturing_compose), \
             emit_patch:
            args = _build_send_args(
                recipients_file=str(recipients_file),
                tone="casual hype",
                dry_run=True,
            )
            rc = gitmail.cmd_send_from_recipients(args)

        self.assertEqual(rc, 0)
        self.assertEqual(len(captured_kwargs), 2)
        for kw in captured_kwargs:
            self.assertEqual(kw.get("tone"), "casual hype")

    def _tmp(self, payload):
        import tempfile
        f = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        f.write(json.dumps(payload).encode("utf-8"))
        f.close()
        path = Path(f.name)
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        return path


# --------------------------------------------------------------------------- #
# 4. emphasis passed to compose_email                                         #
# --------------------------------------------------------------------------- #


class TestEmphasisPassedToComposeEmail(unittest.TestCase):
    def test_emphasis_passed_to_compose_email(self):
        recipients = _make_recipients(3)
        captured_kwargs: list[dict] = []

        def capturing_compose(creds, **kwargs):
            captured_kwargs.append(kwargs)
            return _fake_compose_email(creds, **kwargs)

        recipients_file = self._tmp(recipients)
        captured, emit_patch = _capture_emits()
        with patch.object(gitmail, "load_creds", return_value={"SMTP_FROM": "me@x.com",
                                                                 "SMTP_USER": "me@x.com"}), \
             patch.object(gitmail.llm_compose, "compose_email",
                          side_effect=capturing_compose), \
             emit_patch:
            args = _build_send_args(
                recipients_file=str(recipients_file),
                emphasis="47% cost cut, OSS, free",
                dry_run=True,
            )
            rc = gitmail.cmd_send_from_recipients(args)

        self.assertEqual(rc, 0)
        self.assertEqual(len(captured_kwargs), 3)
        for kw in captured_kwargs:
            self.assertEqual(kw.get("emphasis"), "47% cost cut, OSS, free")

    def _tmp(self, payload):
        import tempfile
        f = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        f.write(json.dumps(payload).encode("utf-8"))
        f.close()
        path = Path(f.name)
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        return path


# --------------------------------------------------------------------------- #
# 5. recipients --keywords overrides analyse output                            #
# --------------------------------------------------------------------------- #


class TestRecipientsKeywordsOverride(unittest.TestCase):
    def test_recipients_keywords_override(self):
        captured_search_kwargs: list[dict] = []

        def fake_search(*, topics, keywords=None, min_stars=200, limit=15,
                        token=None, exclude_full_names=None):
            captured_search_kwargs.append({
                "topics": list(topics or []),
                "keywords": list(keywords or []),
            })
            return [{"full_name": "a/x", "stars": 500, "topics": [],
                     "html_url": "", "description": ""}]

        emails = {"alice": "alice@x.com"}

        captured, emit_patch = _capture_emits()
        with patch.object(gitmail, "load_creds", return_value={}), \
             patch.object(gitmail.llm_compose, "analyse_project_llm",
                          return_value={"summary": "", "keywords": ["bogus-kw"],
                                          "topics": ["bogus-topic"], "value_prop": ""}), \
             patch.object(gitmail.github_search, "search_similar_repos",
                          side_effect=fake_search), \
             patch.object(gitmail.github_search, "iter_stargazers",
                          return_value=iter([{"login": "alice",
                                                "html_url": "https://github.com/alice"}])), \
             patch.object(gitmail.github_search, "resolve_user_email",
                          side_effect=lambda login, token=None, **kw: emails.get(login, "")), \
             patch("builtins.print"), \
             emit_patch:
            args = _build_recipients_args(
                description="anything",
                keywords="k1,k2",
                max_users=1,
            )
            rc = gitmail.cmd_recipients(args)

        self.assertEqual(rc, 0)
        self.assertEqual(len(captured_search_kwargs), 1)
        # Override took effect: bogus-kw is gone, k1,k2 present
        self.assertEqual(captured_search_kwargs[0]["keywords"], ["k1", "k2"])
        # topics untouched (no --topics override given)
        self.assertEqual(captured_search_kwargs[0]["topics"], ["bogus-topic"])


# --------------------------------------------------------------------------- #
# 6. --seed-repos skips search                                                 #
# --------------------------------------------------------------------------- #


class TestRecipientsSeedReposSkipsSearch(unittest.TestCase):
    def test_recipients_seed_repos_skips_search(self):
        search_calls: list[dict] = []
        stargazer_calls: list[str] = []

        def fake_search(**kwargs):
            search_calls.append(kwargs)
            return []

        def fake_stargazers(full_name, max_users=None, token=None):
            stargazer_calls.append(full_name)
            return iter([{"login": f"{full_name}-user",
                          "html_url": f"https://github.com/{full_name}-user"}])

        emails = {"owner1/repo1-user": "u1@x.com",
                  "owner2/repo2-user": "u2@x.com"}

        captured, emit_patch = _capture_emits()
        with patch.object(gitmail, "load_creds", return_value={}), \
             patch.object(gitmail.github_search, "search_similar_repos",
                          side_effect=fake_search), \
             patch.object(gitmail.github_search, "iter_stargazers",
                          side_effect=fake_stargazers), \
             patch.object(gitmail.github_search, "resolve_user_email",
                          side_effect=lambda login, token=None, **kw: emails.get(login, "")), \
             patch("builtins.print"), \
             emit_patch:
            args = _build_recipients_args(
                seed_repos="owner1/repo1,owner2/repo2",
                max_users=2,
            )
            rc = gitmail.cmd_recipients(args)

        self.assertEqual(rc, 0)
        # search NOT called
        self.assertEqual(search_calls, [])
        # stargazers called for both seed repos
        self.assertIn("owner1/repo1", stargazer_calls)
        self.assertIn("owner2/repo2", stargazer_calls)


# --------------------------------------------------------------------------- #
# 7. validates required fields                                                #
# --------------------------------------------------------------------------- #


class TestSendFromRecipientsValidatesRequiredFields(unittest.TestCase):
    def test_send_from_recipients_validates_required_fields(self):
        # Mix of valid + missing-email row
        recipients = [
            {"login": "alice", "email": "alice@x.com",
             "starred_repo": "u/x", "profile": ""},
            {"login": "bob", "starred_repo": "u/y"},  # missing email
            {"login": "carol", "email": "carol@x.com",
             "starred_repo": "u/z"},
        ]

        recipients_file = self._tmp(recipients)
        captured, emit_patch = _capture_emits()
        with patch.object(gitmail, "load_creds", return_value={"SMTP_FROM": "me@x.com",
                                                                 "SMTP_USER": "me@x.com"}), \
             patch.object(gitmail.llm_compose, "compose_email",
                          side_effect=_fake_compose_email), \
             emit_patch:
            args = _build_send_args(recipients_file=str(recipients_file),
                                     dry_run=True)
            rc = gitmail.cmd_send_from_recipients(args)

        self.assertEqual(rc, 0)
        # bob skipped, alice + carol kept
        loaded = [e for e in captured if e["event"] == "recipients_loaded"]
        self.assertEqual(loaded[0]["count"], 2)
        skipped = [e for e in captured if e["event"] == "recipients_skipped"]
        self.assertEqual(len(skipped), 1)
        self.assertEqual(skipped[0]["count"], 1)
        # Two preview events
        previews = [e for e in captured if e["event"] == "send_preview"]
        self.assertEqual(len(previews), 2)
        sent_to = {p["to"] for p in previews}
        self.assertEqual(sent_to, {"alice@x.com", "carol@x.com"})

    def _tmp(self, payload):
        import tempfile
        f = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        f.write(json.dumps(payload).encode("utf-8"))
        f.close()
        path = Path(f.name)
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        return path


# --------------------------------------------------------------------------- #
# 8. --template-only reuses first compose                                     #
# --------------------------------------------------------------------------- #


class TestTemplateOnlyReusesFirstCompose(unittest.TestCase):
    def test_template_only_reuses_first_compose(self):
        recipients = _make_recipients(4)
        compose_call_count = {"n": 0}

        def counting_compose(creds, **kwargs):
            compose_call_count["n"] += 1
            return _fake_compose_email(creds, **kwargs)

        recipients_file = self._tmp(recipients)
        captured, emit_patch = _capture_emits()
        with patch.object(gitmail, "load_creds", return_value={"SMTP_FROM": "me@x.com",
                                                                 "SMTP_USER": "me@x.com"}), \
             patch.object(gitmail.llm_compose, "compose_email",
                          side_effect=counting_compose), \
             emit_patch:
            args = _build_send_args(recipients_file=str(recipients_file),
                                     dry_run=True, template_only=True)
            rc = gitmail.cmd_send_from_recipients(args)

        self.assertEqual(rc, 0)
        # compose_email called exactly once
        self.assertEqual(compose_call_count["n"], 1)
        # All 4 still get a preview
        previews = [e for e in captured if e["event"] == "send_preview"]
        self.assertEqual(len(previews), 4)

    def _tmp(self, payload):
        import tempfile
        f = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        f.write(json.dumps(payload).encode("utf-8"))
        f.close()
        path = Path(f.name)
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        return path


# --------------------------------------------------------------------------- #
# 9. compose_email itself accepts tone/emphasis (signature regression)         #
# --------------------------------------------------------------------------- #


class TestComposeEmailSignatureAcceptsToneEmphasis(unittest.TestCase):
    def test_signature(self):
        captured_kwargs: dict = {}

        def fake_call_llm(creds, *, system, user, provider=None,
                          model=None, max_tokens=1500):
            captured_kwargs["system"] = system
            captured_kwargs["user"] = user
            return '{"subject": "ok", "body": "hi"}'

        with patch.object(llm_compose, "call_llm", side_effect=fake_call_llm):
            out = llm_compose.compose_email(
                {},
                project_name="x", project_pitch="y", project_url="",
                login="a", starred_repo="b/c",
                tone="friendly dev",
                emphasis="ship-fast, OSS",
            )
        self.assertEqual(out["subject"], "ok")
        # tone + emphasis must end up reflected in the system prompt
        self.assertIn("friendly dev", captured_kwargs["system"])
        self.assertIn("ship-fast, OSS", captured_kwargs["system"])

    def test_signature_backcompat_no_kwargs(self):
        """Calling without tone/emphasis must keep working (dashboard path)."""
        def fake_call_llm(creds, *, system, user, provider=None,
                          model=None, max_tokens=1500):
            return '{"subject": "ok", "body": "hi"}'

        with patch.object(llm_compose, "call_llm", side_effect=fake_call_llm):
            out = llm_compose.compose_email(
                {},
                project_name="x", project_pitch="y", project_url="",
                login="a", starred_repo="b/c",
            )
        self.assertEqual(out["subject"], "ok")


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
