"""Tests for scripts/twitter_reply.py.

Pure functions exercised directly. The two HTTP-touching subcommands are
covered with the urllib.request.urlopen patch + a fake creds.load.
"""

from __future__ import annotations

import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS / "lib"))

import twitter_reply as tr  # noqa: E402


class TestBuildQuery(unittest.TestCase):
    def test_keywords_only(self) -> None:
        q = tr._build_query(None, ["jvm monitoring", "async-profiler"],
                              None, exclude_retweets=True)
        # Keywords get OR-joined; bare ones get quoted, already-quoted left alone.
        self.assertIn('"jvm monitoring"', q)
        self.assertIn('"async-profiler"', q)
        self.assertIn(" OR ", q)
        self.assertIn("-is:retweet", q)

    def test_query_only(self) -> None:
        q = tr._build_query("jvm tooling", [], "en", exclude_retweets=True)
        self.assertTrue(q.startswith("(jvm tooling)"))
        self.assertIn("lang:en", q)
        self.assertIn("-is:retweet", q)

    def test_empty(self) -> None:
        q = tr._build_query(None, [], None, exclude_retweets=False)
        self.assertEqual(q, "")

    def test_already_quoted_kept_literal(self) -> None:
        q = tr._build_query(None, ['"low-overhead profiler"'],
                              None, exclude_retweets=True)
        # Should appear once, not double-quoted.
        self.assertEqual(q.count('"low-overhead profiler"'), 1)
        self.assertNotIn('""', q)


class TestCandidatePasses(unittest.TestCase):
    def test_total_below_floor_fails(self) -> None:
        self.assertFalse(tr._candidate_passes(
            {"like_count": 1, "retweet_count": 0, "reply_count": 0, "quote_count": 0}, 5))

    def test_total_meets_floor(self) -> None:
        self.assertTrue(tr._candidate_passes(
            {"like_count": 3, "retweet_count": 1, "reply_count": 0, "quote_count": 1}, 5))

    def test_zero_floor_always_passes(self) -> None:
        self.assertTrue(tr._candidate_passes({}, 0))


class TestShapeCandidate(unittest.TestCase):
    def test_shape_with_author(self) -> None:
        out = tr._shape_candidate(
            {
                "id": "111", "text": "hi", "created_at": "2026-05-01T00:00:00Z",
                "author_id": "u1",
                "public_metrics": {"like_count": 2, "retweet_count": 1,
                                     "reply_count": 0, "quote_count": 1},
            },
            {"u1": {"username": "alice", "name": "Alice",
                     "profile_image_url": "https://x.example/a.jpg"}},
        )
        self.assertEqual(out["id"], "111")
        self.assertEqual(out["author"]["username"], "alice")
        self.assertEqual(out["author"]["name"], "Alice")
        self.assertEqual(out["engagement"]["total"], 4)
        self.assertEqual(out["url"], "https://x.com/alice/status/111")

    def test_shape_missing_author(self) -> None:
        out = tr._shape_candidate(
            {"id": "222", "text": "x", "author_id": "missing"},
            {},
        )
        self.assertEqual(out["author"]["username"], "unknown")
        self.assertEqual(out["url"], "https://x.com/unknown/status/222")


class TestFindCommand(unittest.TestCase):
    def setUp(self) -> None:
        self.fake_response = {
            "data": [
                {
                    "id": "100", "text": "Looking for a JVM profiler",
                    "author_id": "u1", "created_at": "2026-05-01T00:00:00Z",
                    "public_metrics": {"like_count": 10, "retweet_count": 2,
                                         "reply_count": 1, "quote_count": 0},
                },
                {
                    "id": "101", "text": "low-noise tweet",
                    "author_id": "u2", "created_at": "2026-05-01T01:00:00Z",
                    "public_metrics": {"like_count": 0, "retweet_count": 0,
                                         "reply_count": 0, "quote_count": 0},
                },
            ],
            "includes": {
                "users": [
                    {"id": "u1", "username": "alice", "name": "Alice",
                     "profile_image_url": ""},
                    {"id": "u2", "username": "bob", "name": "Bob",
                     "profile_image_url": ""},
                ],
            },
        }

    def _run_find(self, *, min_engagement: int, max_candidates: int = 20):
        # urlopen returns a context manager whose .read() yields the JSON bytes.
        fake_cm = mock.MagicMock()
        fake_cm.__enter__.return_value.read.return_value = json.dumps(
            self.fake_response).encode()
        fake_cm.__exit__.return_value = False

        args = mock.MagicMock(
            query="jvm", keywords=None, lang=None,
            max_candidates=max_candidates, min_engagement=min_engagement,
            include_retweets=False, out=None,
        )
        with mock.patch.object(tr.urllib.request, "urlopen", return_value=fake_cm), \
             mock.patch.object(tr, "load_creds",
                                 return_value={"TWITTER_OAUTH2_BEARER": "T"}), \
             mock.patch.object(sys, "stdout", new_callable=io.StringIO) as fake_out:
            rc = tr.cmd_find(args)
        return rc, fake_out.getvalue()

    def test_find_filters_by_engagement(self) -> None:
        rc, output = self._run_find(min_engagement=5)
        self.assertEqual(rc, 0)
        # Last block of output is the JSON candidate dump (after JSONL events).
        # Split off the last `]\n` block.
        json_start = output.rfind("[")
        candidates = json.loads(output[json_start:])
        # Only the first tweet (engagement total 13) should pass.
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["id"], "100")

    def test_find_zero_floor_keeps_all(self) -> None:
        rc, output = self._run_find(min_engagement=0)
        self.assertEqual(rc, 0)
        candidates = json.loads(output[output.rfind("["):])
        self.assertEqual(len(candidates), 2)

    def test_find_writes_out_file(self) -> None:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            out_path = f.name
        try:
            fake_cm = mock.MagicMock()
            fake_cm.__enter__.return_value.read.return_value = json.dumps(
                self.fake_response).encode()
            fake_cm.__exit__.return_value = False
            args = mock.MagicMock(
                query="jvm", keywords=None, lang=None,
                max_candidates=20, min_engagement=0,
                include_retweets=False, out=out_path,
            )
            with mock.patch.object(tr.urllib.request, "urlopen", return_value=fake_cm), \
                 mock.patch.object(tr, "load_creds",
                                     return_value={"TWITTER_OAUTH2_BEARER": "T"}), \
                 mock.patch.object(sys, "stdout", new_callable=io.StringIO):
                rc = tr.cmd_find(args)
            self.assertEqual(rc, 0)
            payload = json.loads(Path(out_path).read_text(encoding="utf-8"))
            self.assertEqual(len(payload["candidates"]), 2)
            self.assertIn("query", payload)
        finally:
            Path(out_path).unlink(missing_ok=True)

    def test_find_no_bearer_fails(self) -> None:
        args = mock.MagicMock(
            query="jvm", keywords=None, lang=None,
            max_candidates=20, min_engagement=0,
            include_retweets=False, out=None,
        )
        with mock.patch.object(tr, "load_creds", return_value={}), \
             mock.patch.object(sys, "stdout", new_callable=io.StringIO) as fake_out:
            rc = tr.cmd_find(args)
        self.assertEqual(rc, 2)
        self.assertIn("TWITTER_OAUTH2_BEARER missing", fake_out.getvalue())


class TestReplyCommand(unittest.TestCase):
    def test_dry_run_no_network(self) -> None:
        args = mock.MagicMock(
            tweet_id="900", body="hey @alice — built this thing", dry_run=True,
        )
        with mock.patch.object(tr, "load_creds",
                                 return_value={"TWITTER_OAUTH2_BEARER": "T"}), \
             mock.patch.object(sys, "stdout", new_callable=io.StringIO) as fake_out:
            rc = tr.cmd_reply(args)
        self.assertEqual(rc, 0)
        self.assertIn("reply_dry_run", fake_out.getvalue())

    def test_body_too_long_fails(self) -> None:
        args = mock.MagicMock(
            tweet_id="900", body="x" * 281, dry_run=True,
        )
        with mock.patch.object(tr, "load_creds",
                                 return_value={"TWITTER_OAUTH2_BEARER": "T"}), \
             mock.patch.object(sys, "stdout", new_callable=io.StringIO) as fake_out:
            rc = tr.cmd_reply(args)
        self.assertEqual(rc, 2)
        self.assertIn("X cap is 280", fake_out.getvalue())

    def test_live_post_calls_v2(self) -> None:
        fake_cm = mock.MagicMock()
        fake_cm.__enter__.return_value.read.return_value = json.dumps(
            {"data": {"id": "999"}}).encode()
        fake_cm.__exit__.return_value = False

        args = mock.MagicMock(
            tweet_id="900", body="thanks for sharing — built this lately",
            dry_run=False,
        )
        with mock.patch.object(tr.urllib.request, "urlopen",
                                 return_value=fake_cm) as urlopen, \
             mock.patch.object(tr, "load_creds",
                                 return_value={"TWITTER_OAUTH2_BEARER": "T",
                                                 "TWITTER_HANDLE": "me"}), \
             mock.patch.object(sys, "stdout", new_callable=io.StringIO) as fake_out:
            rc = tr.cmd_reply(args)
        self.assertEqual(rc, 0)
        # Verify the request payload included in_reply_to_tweet_id.
        called_req = urlopen.call_args.args[0]
        body = json.loads(called_req.data.decode())
        self.assertEqual(body["reply"]["in_reply_to_tweet_id"], "900")
        self.assertEqual(body["text"], args.body)
        # And the printed URL uses the configured handle.
        out = fake_out.getvalue()
        self.assertIn("https://x.com/me/status/999", out)


if __name__ == "__main__":
    unittest.main()
