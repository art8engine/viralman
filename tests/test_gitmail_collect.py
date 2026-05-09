"""Integration regression tests for _run_collect_job in dashboard/api.py.

Run:
  .venv/bin/python -m pytest tests/test_gitmail_collect.py -v
"""

from __future__ import annotations

import sys
import threading
import time
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))                       # so the dashboard package is reachable
sys.path.insert(0, str(ROOT / "scripts" / "lib"))   # for libs that gitmail imports

# Force-load the modules whose attributes we patch by string path. Each `with
# patch("dashboard.api.X")` resolves `dashboard.api` via getattr, so the package
# must be in sys.modules. Importing dashboard.api also appends scripts/ to
# sys.path, which lets the next line import gitmail.
import dashboard.api  # noqa: E402,F401
import gitmail  # noqa: E402,F401

# ---------------------------------------------------------------------------
# Helpers to import the module under test with creds patched out
# ---------------------------------------------------------------------------

def _make_job(description="K8s autoscaler in Go", max_users=10, **extra):
    """Build a GitmailJob using the real class from dashboard.api."""
    import dashboard.api as api
    job_id = "test-job-001"
    args = {"description": description, "max_users": max_users, **extra}
    return api.GitmailJob(job_id, args)


def _event_kinds(job) -> list[str]:
    return [e.get("event") for e in job.events]


def _recipients_from_done(job) -> list[dict]:
    for ev in job.events:
        if ev.get("event") == "done":
            return ev.get("recipients", [])
    return []


# ---------------------------------------------------------------------------
# Patch targets — after the pipeline-unification refactor (ADR 0001), the
# dashboard delegates to gitmail.step_*, so we patch the underlying lib calls
# rather than the dashboard's old inline implementation.
# ---------------------------------------------------------------------------

_LLM_ANALYSE  = "llm_compose.analyse_project_llm"
_ANALYSE      = "dashboard.api.github_search.analyse_project"
_SEARCH       = "dashboard.api.github_search.search_similar_repos"
_STARGAZERS   = "dashboard.api.github_search.iter_stargazers"
_BULK_PROFILE = "dashboard.api.github_search.bulk_resolve_profile_data"
_EMAIL        = "dashboard.api.github_search.resolve_user_email"
_LOAD_CREDS   = "dashboard.api.load_creds"


def _profile_dict(emails: dict) -> dict:
    """Shape a {login: email-or-empty} dict into the GraphQL bulk return shape:
    {login: {"email": <email-or-None>, "name": None}}. Empty string → None."""
    return {login: {"email": (e or None), "name": None}
            for login, e in emails.items()}


# ---------------------------------------------------------------------------
# 1. Happy-path lifecycle events
# ---------------------------------------------------------------------------

class TestCollectEmitsLifecycleEvents(unittest.TestCase):

    def test_collect_emits_lifecycle_events(self):
        emails = {"alice": "alice@x.com", "bob": "bob@x.com"}

        with patch(_LOAD_CREDS, return_value={}), \
             patch(_LLM_ANALYSE, side_effect=RuntimeError("no LLM in test")), \
             patch(_ANALYSE, return_value={"keywords": ["k8s"], "topics": ["kubernetes"]}), \
             patch(_SEARCH, return_value=[{"full_name": "foo/bar", "stars": 500}]), \
             patch(_STARGAZERS, return_value=iter([
                 {"login": "alice", "html_url": "https://github.com/alice"},
                 {"login": "bob",   "html_url": "https://github.com/bob"},
             ])), \
             patch(_BULK_PROFILE, return_value=_profile_dict(emails)), \
             patch(_EMAIL, side_effect=lambda login, **kwargs: emails.get(login, "")):
            import dashboard.api as api
            job = _make_job(description="K8s autoscaler in Go", max_users=10)
            api._run_collect_job(job)

        kinds = _event_kinds(job)

        # Required lifecycle order
        for expected in ("analyse_start", "analyse_done", "search_start",
                         "search_done", "recipients_start", "recipients_done", "done"):
            self.assertIn(expected, kinds, f"missing event: {expected}")

        # At least 2 recipient events
        recipient_events = [e for e in job.events if e.get("event") == "recipient"]
        self.assertGreaterEqual(len(recipient_events), 2)

        # Final done event has 2 recipients with correct data
        recipients = _recipients_from_done(job)
        self.assertEqual(len(recipients), 2)
        logins = {r["login"] for r in recipients}
        self.assertEqual(logins, {"alice", "bob"})
        email_set = {r["email"] for r in recipients}
        self.assertEqual(email_set, {"alice@x.com", "bob@x.com"})


# ---------------------------------------------------------------------------
# 2. De-duplication by login across multiple repo iterators
# ---------------------------------------------------------------------------

class TestCollectDedupByLogin(unittest.TestCase):

    def test_collect_dedup_by_login(self):
        emails = {"alice": "alice@x.com", "bob": "bob@x.com"}

        # iter_stargazers is called once per repo; return different iterables
        call_count = {"n": 0}
        def fake_stargazers(full_name, max_users=None, token=None):
            call_count["n"] += 1
            if full_name == "a/x":
                return iter([{"login": "alice", "html_url": "https://github.com/alice"}])
            # a/y: alice appears again (should be deduped), plus bob
            return iter([
                {"login": "alice", "html_url": "https://github.com/alice"},
                {"login": "bob",   "html_url": "https://github.com/bob"},
            ])

        with patch(_LOAD_CREDS, return_value={}), \
             patch(_LLM_ANALYSE, side_effect=RuntimeError("no LLM in test")), \
             patch(_ANALYSE, return_value={"keywords": ["k8s"], "topics": ["kubernetes"]}), \
             patch(_SEARCH, return_value=[
                 {"full_name": "a/x", "stars": 100},
                 {"full_name": "a/y", "stars": 100},
             ]), \
             patch(_STARGAZERS, side_effect=fake_stargazers), \
             patch(_BULK_PROFILE, return_value=_profile_dict(emails)), \
             patch(_EMAIL, side_effect=lambda login, **kwargs: emails.get(login, "")):
            import dashboard.api as api
            job = _make_job(max_users=10)
            api._run_collect_job(job)

        recipients = _recipients_from_done(job)
        logins = [r["login"] for r in recipients]

        # alice must appear EXACTLY once
        self.assertEqual(logins.count("alice"), 1)
        # bob must also appear
        self.assertIn("bob", logins)
        # total: exactly 2
        self.assertEqual(len(recipients), 2)


# ---------------------------------------------------------------------------
# 3. Skips users without an email
# ---------------------------------------------------------------------------

class TestCollectSkipsUsersWithoutEmail(unittest.TestCase):

    def test_collect_skips_users_without_email(self):
        emails = {"alice": "alice@x.com", "bob": "", "carol": "carol@x.com"}

        with patch(_LOAD_CREDS, return_value={}), \
             patch(_LLM_ANALYSE, side_effect=RuntimeError("no LLM in test")), \
             patch(_ANALYSE, return_value={"keywords": ["cli"], "topics": ["cli"]}), \
             patch(_SEARCH, return_value=[{"full_name": "x/y", "stars": 300}]), \
             patch(_STARGAZERS, return_value=iter([
                 {"login": "alice", "html_url": "https://github.com/alice"},
                 {"login": "bob",   "html_url": "https://github.com/bob"},
                 {"login": "carol", "html_url": "https://github.com/carol"},
             ])), \
             patch(_BULK_PROFILE, return_value=_profile_dict(emails)), \
             patch(_EMAIL, side_effect=lambda login, **kwargs: emails.get(login, "")):
            import dashboard.api as api
            job = _make_job(max_users=10)
            api._run_collect_job(job)

        recipients = _recipients_from_done(job)
        self.assertEqual(len(recipients), 2)

        logins = {r["login"] for r in recipients}
        self.assertEqual(logins, {"alice", "carol"})
        self.assertNotIn("bob", logins)

        # No "recipient" event for bob
        recipient_events = [e for e in job.events if e.get("event") == "recipient"]
        event_logins = {e.get("login") for e in recipient_events}
        self.assertNotIn("bob", event_logins)


# ---------------------------------------------------------------------------
# 4. Excludes the user's own repo via exclude_full_names kwarg
# ---------------------------------------------------------------------------

class TestCollectExcludesOwnRepo(unittest.TestCase):

    def test_collect_excludes_own_repo(self):
        captured = {}

        def fake_search(*, topics, keywords=None, min_stars=200, limit=15,
                        token=None, exclude_full_names=None):
            captured["exclude_full_names"] = exclude_full_names
            return []  # no repos → fatal, but we only care about the kwarg

        with patch(_LOAD_CREDS, return_value={}), \
             patch(_LLM_ANALYSE, side_effect=RuntimeError("no LLM in test")), \
             patch(_ANALYSE, return_value={"keywords": ["cli"], "topics": ["cli"]}), \
             patch(_SEARCH, side_effect=fake_search):
            import dashboard.api as api
            job = _make_job(
                description="My CLI tool",
                max_users=10,
                project_url="https://github.com/me/my-tool",
            )
            api._run_collect_job(job)

        self.assertIsNotNone(captured.get("exclude_full_names"),
                             "exclude_full_names was not passed to search_similar_repos")
        self.assertIn("me/my-tool", captured["exclude_full_names"])


# ---------------------------------------------------------------------------
# 5. Respects cooperative cancellation mid-iteration
# ---------------------------------------------------------------------------

class TestCollectRespectsCancellation(unittest.TestCase):

    def test_collect_respects_cancel(self):
        import dashboard.api as api

        job = _make_job(max_users=100)
        call_counter = {"n": 0}

        def fake_stargazers(full_name, max_users=None, token=None):
            """Yields logins; on the 2nd next() call, sets job.status='cancelled'."""
            for i in range(100):
                call_counter["n"] += 1
                if call_counter["n"] == 2:
                    job.status = "cancelled"
                yield {"login": f"user{i}", "html_url": f"https://github.com/user{i}"}

        emails = {f"user{i}": f"user{i}@x.com" for i in range(100)}

        with patch(_LOAD_CREDS, return_value={}), \
             patch(_LLM_ANALYSE, side_effect=RuntimeError("no LLM in test")), \
             patch(_ANALYSE, return_value={"keywords": ["k8s"], "topics": ["kubernetes"]}), \
             patch(_SEARCH, return_value=[{"full_name": "big/repo", "stars": 9999}]), \
             patch(_STARGAZERS, side_effect=fake_stargazers), \
             patch(_BULK_PROFILE, return_value={}), \
             patch(_EMAIL, side_effect=lambda login, **kwargs: emails.get(login, "")):
            api._run_collect_job(job)

        recipients = _recipients_from_done(job)
        # The loop stopped early — far fewer than 100 recipients collected
        self.assertLessEqual(len(recipients), 2)


# ---------------------------------------------------------------------------
# 6. Fatal when analyse_project returns no keywords
# ---------------------------------------------------------------------------

class TestCollectFatalWhenNoKeywords(unittest.TestCase):

    def test_collect_fatal_when_no_keywords(self):
        with patch(_LOAD_CREDS, return_value={}), \
             patch(_LLM_ANALYSE, side_effect=RuntimeError("no LLM in test")), \
             patch(_ANALYSE, return_value={"keywords": [], "topics": []}):
            import dashboard.api as api
            job = _make_job()
            api._run_collect_job(job)

        kinds = _event_kinds(job)
        self.assertIn("fatal", kinds)
        self.assertNotIn("done", kinds)

        fatal_events = [e for e in job.events if e.get("event") == "fatal"]
        self.assertTrue(any(
            "no usable keywords" in (e.get("reason") or "")
            for e in fatal_events
        ))

        # No recipients produced
        self.assertEqual(_recipients_from_done(job), [])


# ---------------------------------------------------------------------------
# 7. Fatal when search_similar_repos returns no repos
# ---------------------------------------------------------------------------

class TestCollectFatalWhenNoRepos(unittest.TestCase):

    def test_collect_fatal_when_no_repos(self):
        with patch(_LOAD_CREDS, return_value={}), \
             patch(_LLM_ANALYSE, side_effect=RuntimeError("no LLM in test")), \
             patch(_ANALYSE, return_value={"keywords": ["cli"], "topics": ["cli"]}), \
             patch(_SEARCH, return_value=[]):
            import dashboard.api as api
            job = _make_job()
            api._run_collect_job(job)

        kinds = _event_kinds(job)
        self.assertIn("fatal", kinds)
        self.assertNotIn("done", kinds)

        fatal_events = [e for e in job.events if e.get("event") == "fatal"]
        self.assertTrue(any(
            "no similar repos" in (e.get("reason") or "")
            for e in fatal_events
        ))

        self.assertEqual(_recipients_from_done(job), [])


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
