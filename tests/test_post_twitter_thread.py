"""Regression tests for scripts/post_twitter.py thread handling.

P0-2: A multi-tweet thread (parts split by `---`) must return a permalink that
points at the ROOT tweet, not the last reply. The earlier implementation kept
overwriting `parent_id` with `last_id` on every iteration, so the URL ended up
pointing at the final reply — which renders as a single reply page on x.com,
not the thread root.
"""

from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "lib"))


def _stub_tweepy(client):
    """Return a fake `tweepy` module exposing a Client class that returns ours."""
    mod = types.ModuleType("tweepy")
    mod.Client = lambda **kwargs: client  # type: ignore[attr-defined]
    return mod


class TestThreadPermalinkPointsToRoot(unittest.TestCase):
    """3-tweet thread → returned URL must contain the FIRST tweet id."""

    def test_three_part_thread_returns_root_permalink(self):
        # tweepy stub: each create_tweet returns a fresh sequential id.
        ids = iter(["111", "222", "333"])

        def fake_create_tweet(*, text, in_reply_to_tweet_id=None):
            tid = next(ids)
            return types.SimpleNamespace(data={"id": tid})

        fake_client = MagicMock()
        fake_client.create_tweet.side_effect = fake_create_tweet
        sys.modules["tweepy"] = _stub_tweepy(fake_client)

        import importlib
        if "post_twitter" in sys.modules:
            del sys.modules["post_twitter"]
        post_twitter = importlib.import_module("post_twitter")

        creds = {
            "TWITTER_API_KEY": "k", "TWITTER_API_SECRET": "s",
            "TWITTER_ACCESS_TOKEN": "t", "TWITTER_ACCESS_SECRET": "ts",
            "TWITTER_HANDLE": "alice",
        }
        body = "first part\n---\nsecond part\n---\nthird part"
        url = post_twitter.post_via_api(creds, body)

        self.assertIsNotNone(url)
        # The URL must point at the root tweet (id=111), NOT the last reply.
        self.assertIn("/status/111", url, f"permalink should point at root, got {url}")
        self.assertNotIn("/status/333", url, "permalink must not point at last reply")

        # Sanity: the second and third create_tweet calls used in_reply_to=
        # the previously-emitted id (chain stays connected).
        kwargs = [call.kwargs for call in fake_client.create_tweet.call_args_list]
        self.assertEqual(kwargs[0]["in_reply_to_tweet_id"], None)
        self.assertEqual(kwargs[1]["in_reply_to_tweet_id"], "111")
        self.assertEqual(kwargs[2]["in_reply_to_tweet_id"], "222")

    def test_single_tweet_returns_its_own_id(self):
        fake_client = MagicMock()
        fake_client.create_tweet.return_value = types.SimpleNamespace(data={"id": "777"})
        sys.modules["tweepy"] = _stub_tweepy(fake_client)

        import importlib
        if "post_twitter" in sys.modules:
            del sys.modules["post_twitter"]
        post_twitter = importlib.import_module("post_twitter")

        creds = {
            "TWITTER_API_KEY": "k", "TWITTER_API_SECRET": "s",
            "TWITTER_ACCESS_TOKEN": "t", "TWITTER_ACCESS_SECRET": "ts",
            "TWITTER_HANDLE": "bob",
        }
        url = post_twitter.post_via_api(creds, "just one tweet")
        self.assertIn("/status/777", url)


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
