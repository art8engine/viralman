"""Recipient quality filter tests.

Two layers:
  1. RecipientFilter.evaluate — pure unit tests on the filter dataclass
  2. step_recipients integration — verifies the filter prunes candidates
     between the GraphQL bulk fetch and the email-resolution loop, and that
     the `recipients_filtered` event carries the breakdown.

Run:
  .venv/bin/python -m pytest tests/test_recipient_filter.py -v
"""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

import github_search  # noqa: E402
import gitmail  # noqa: E402

RecipientFilter = github_search.RecipientFilter


def _profile(**fields):
    base = {
        "email": "x@y.com", "name": "X", "bio": "hello",
        "is_hireable": False,
        "created_at": "2020-01-01T00:00:00Z",
        "followers": 50, "following": 30, "public_repos": 5,
    }
    base.update(fields)
    return base


class TestRecipientFilterEvaluate(unittest.TestCase):

    def test_inactive_filter_passes_anything(self):
        f = RecipientFilter()
        self.assertFalse(f.is_active())
        self.assertIsNone(f.evaluate(_profile(followers=0, public_repos=0)))

    def test_min_followers_rejects_low(self):
        f = RecipientFilter(min_followers=100)
        self.assertEqual(f.evaluate(_profile(followers=50)), "min_followers")
        self.assertIsNone(f.evaluate(_profile(followers=100)))

    def test_max_followers_rejects_high(self):
        f = RecipientFilter(max_followers=200)
        self.assertEqual(f.evaluate(_profile(followers=500)), "max_followers")
        self.assertIsNone(f.evaluate(_profile(followers=200)))

    def test_min_following_and_max_following(self):
        self.assertEqual(
            RecipientFilter(min_following=10).evaluate(_profile(following=5)),
            "min_following",
        )
        self.assertEqual(
            RecipientFilter(max_following=100).evaluate(_profile(following=5000)),
            "max_following",
        )

    def test_min_public_repos_rejects_ghost_accounts(self):
        f = RecipientFilter(min_public_repos=1)
        self.assertEqual(f.evaluate(_profile(public_repos=0)), "min_public_repos")
        self.assertIsNone(f.evaluate(_profile(public_repos=1)))

    def test_max_public_repos(self):
        f = RecipientFilter(max_public_repos=10)
        self.assertEqual(f.evaluate(_profile(public_repos=999)),
                         "max_public_repos")

    def test_min_account_age_rejects_new_accounts(self):
        recent = (datetime.now(timezone.utc) - timedelta(days=10)
                  ).isoformat().replace("+00:00", "Z")
        old = (datetime.now(timezone.utc) - timedelta(days=400)
               ).isoformat().replace("+00:00", "Z")
        f = RecipientFilter(min_account_age_days=90)
        self.assertEqual(f.evaluate(_profile(created_at=recent)),
                         "min_account_age_days")
        self.assertIsNone(f.evaluate(_profile(created_at=old)))

    def test_require_bio(self):
        f = RecipientFilter(require_bio=True)
        self.assertEqual(f.evaluate(_profile(bio=None)), "require_bio")
        self.assertEqual(f.evaluate(_profile(bio="   ")), "require_bio")
        self.assertIsNone(f.evaluate(_profile(bio="hi")))

    def test_missing_data_fails_active_bound(self):
        # When the user opts into a bound, missing data (None) is a reject.
        f = RecipientFilter(min_followers=10)
        self.assertEqual(f.evaluate(_profile(followers=None)), "min_followers")

    def test_first_failing_dimension_is_returned(self):
        # min_followers checked before min_public_repos; both fail here.
        f = RecipientFilter(min_followers=100, min_public_repos=10)
        self.assertEqual(
            f.evaluate(_profile(followers=5, public_repos=0)),
            "min_followers",
        )


# --------------------------------------------------------------------------- #
# step_recipients integration                                                 #
# --------------------------------------------------------------------------- #


class TestStepRecipientsAppliesFilter(unittest.TestCase):

    def test_filter_drops_low_followers_before_email_loop(self):
        repos = [{"full_name": "foo/bar"}]
        creds = {"GITHUB_TOKEN": "x"}

        events = []

        def sink(event, **fields):
            events.append({"event": event, **fields})

        # 4 candidates from stargazers; only alice/dan have enough followers.
        stargazers = [
            {"login": "alice", "html_url": "https://github.com/alice"},
            {"login": "bob",   "html_url": "https://github.com/bob"},
            {"login": "carol", "html_url": "https://github.com/carol"},
            {"login": "dan",   "html_url": "https://github.com/dan"},
        ]

        profiles = {
            "alice": _profile(email="alice@x.com", followers=500),
            "bob":   _profile(email="bob@x.com",   followers=10),
            "carol": _profile(email=None,          followers=50),
            "dan":   _profile(email="dan@x.com",   followers=999),
        }

        with patch.object(github_search, "iter_stargazers",
                            return_value=iter(stargazers)), \
             patch.object(github_search, "bulk_resolve_profile_data",
                            return_value=profiles), \
             patch.object(github_search, "resolve_user_email",
                            return_value=None):

            recipients = gitmail.step_recipients(
                creds, repos, max_users=10, sink=sink,
                recipient_filter=RecipientFilter(min_followers=100),
            )

        kept_logins = {r["login"] for r in recipients}
        self.assertEqual(kept_logins, {"alice", "dan"})

        # Each surviving recipient carries the new profile fields.
        for r in recipients:
            self.assertIn("followers", r)
            self.assertIn("public_repos", r)

        # The filter event records the breakdown.
        filt = next(e for e in events if e["event"] == "recipients_filtered")
        self.assertEqual(filt["before"], 4)
        self.assertEqual(filt["after"], 2)
        self.assertEqual(filt["dropped"], 2)
        self.assertEqual(filt["rejection_breakdown"], {"min_followers": 2})

    def test_inactive_filter_is_a_noop(self):
        repos = [{"full_name": "foo/bar"}]
        creds = {"GITHUB_TOKEN": "x"}
        events = []

        def sink(event, **fields):
            events.append({"event": event, **fields})

        with patch.object(github_search, "iter_stargazers",
                            return_value=iter([
                                {"login": "alice",
                                 "html_url": "https://github.com/alice"},
                            ])), \
             patch.object(github_search, "bulk_resolve_profile_data",
                            return_value={"alice": _profile(
                                email="alice@x.com", followers=0,
                                public_repos=0)}), \
             patch.object(github_search, "resolve_user_email",
                            return_value=None):

            recipients = gitmail.step_recipients(
                creds, repos, max_users=10, sink=sink,
                recipient_filter=RecipientFilter(),  # inactive
            )

        self.assertEqual(len(recipients), 1)
        self.assertFalse(any(e["event"] == "recipients_filtered"
                             for e in events))


if __name__ == "__main__":
    unittest.main()
