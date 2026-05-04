"""Tests for the gitmail lib pieces that don't require network or creds.

Covers:
  - github_search.analyse_project (heuristic only)
  - llm_compose._extract_json (JSON extraction tolerance)
  - llm_compose._resolve_provider (cred → provider routing)
  - smtp_send.render_preview (envelope construction without network)
  - smtp_send.RateLimiter (timing behaviour)
"""

from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts" / "lib"))

import github_search  # noqa: E402
import llm_compose  # noqa: E402
import smtp_send  # noqa: E402


class TestProjectAnalyse(unittest.TestCase):
    def test_picks_up_known_keywords(self) -> None:
        out = github_search.analyse_project(
            "A Go-based K8s autoscaler that uses Kafka and Postgres"
        )
        self.assertIn("go", out["keywords"])
        self.assertIn("k8s", out["keywords"])
        self.assertIn("kafka", out["keywords"])
        self.assertIn("postgres", out["keywords"])
        self.assertIn("autoscaler", out["keywords"])
        # k8s is normalised to kubernetes for topic search
        self.assertIn("kubernetes", out["topics"])
        self.assertIn("go", out["topics"])

    def test_empty_input(self) -> None:
        out = github_search.analyse_project("")
        self.assertEqual(out["keywords"], [])
        self.assertEqual(out["topics"], [])

    def test_does_not_match_substrings(self) -> None:
        # 'pythonic' should not match the language 'python'
        out = github_search.analyse_project("a pythonic codebase")
        self.assertNotIn("python", out["keywords"])


class TestJSONExtract(unittest.TestCase):
    def test_plain_object(self) -> None:
        d = llm_compose._extract_json('{"a": 1, "b": [1,2]}')
        self.assertEqual(d, {"a": 1, "b": [1, 2]})

    def test_fenced_json(self) -> None:
        text = "Here is the result:\n```json\n{\"k\": \"v\"}\n```\nthanks"
        self.assertEqual(llm_compose._extract_json(text), {"k": "v"})

    def test_with_prose_around(self) -> None:
        text = "Sure!\n{\"name\": \"viralman\", \"keywords\": [\"a\",\"b\"]}\nLet me know."
        d = llm_compose._extract_json(text)
        self.assertEqual(d, {"name": "viralman", "keywords": ["a", "b"]})

    def test_nested(self) -> None:
        text = '{"outer": {"inner": [1, 2, {"deep": true}]}}'
        d = llm_compose._extract_json(text)
        self.assertEqual(d["outer"]["inner"][2]["deep"], True)

    def test_empty(self) -> None:
        self.assertEqual(llm_compose._extract_json(""), {})
        self.assertEqual(llm_compose._extract_json("no json here"), {})


class TestProviderRouting(unittest.TestCase):
    def test_explicit_claude(self) -> None:
        prov = llm_compose._resolve_provider({"ANTHROPIC_API_KEY": "x"}, "claude")
        self.assertEqual(prov, "claude")

    def test_anthropic_alias(self) -> None:
        prov = llm_compose._resolve_provider({"ANTHROPIC_API_KEY": "x"}, "anthropic")
        self.assertEqual(prov, "claude")

    def test_openai(self) -> None:
        prov = llm_compose._resolve_provider({"OPENAI_API_KEY": "x"}, "openai")
        self.assertEqual(prov, "openai")

    def test_gpt_alias(self) -> None:
        prov = llm_compose._resolve_provider({"OPENAI_API_KEY": "x"}, "gpt")
        self.assertEqual(prov, "openai")

    def test_auto_detect_first_present(self) -> None:
        creds = {"OPENAI_API_KEY": "x", "GEMINI_API_KEY": "y"}
        self.assertEqual(llm_compose._resolve_provider(creds), "openai")

    def test_auto_detect_claude_priority(self) -> None:
        creds = {
            "ANTHROPIC_API_KEY": "a",
            "OPENAI_API_KEY": "b",
            "GEMINI_API_KEY": "c",
        }
        self.assertEqual(llm_compose._resolve_provider(creds), "claude")

    def test_no_provider_raises(self) -> None:
        # Should raise only when neither API key nor `claude` CLI is available.
        from unittest.mock import patch
        with patch("shutil.which", return_value=None):
            with self.assertRaises(RuntimeError):
                llm_compose._resolve_provider({})

    def test_falls_back_to_claude_cli_when_present(self) -> None:
        from unittest.mock import patch
        with patch("shutil.which", return_value="/usr/local/bin/claude"):
            self.assertEqual(llm_compose._resolve_provider({}), "claude-cli")

    def test_explicit_claude_cli(self) -> None:
        self.assertEqual(llm_compose._resolve_provider({}, "claude-cli"), "claude-cli")
        self.assertEqual(llm_compose._resolve_provider({}, "claude-max"), "claude-cli")


class TestSmtpRender(unittest.TestCase):
    creds = {"SMTP_FROM": "me@example.com",
              "SMTP_USER": "me@example.com",
              "SMTP_FROM_NAME": "Sender"}

    def test_render_preview_has_required_headers(self) -> None:
        out = smtp_send.render_preview(
            self.creds,
            to_addr="alice@example.com",
            subject="hi",
            body="hello there",
            unsubscribe_base="https://viralman.local",
        )
        self.assertEqual(out["to"], "alice@example.com")
        self.assertEqual(out["subject"], "hi")
        self.assertIn("From: Sender <me@example.com>", out["headers"])
        self.assertIn("List-Unsubscribe:", out["headers"])
        self.assertIn("List-Unsubscribe-Post: List-Unsubscribe=One-Click",
                       out["headers"])
        self.assertIn("Message-ID:", out["headers"])
        self.assertIn(out["unsubscribe_token"], out["headers"])
        self.assertIn("Reply with 'unsubscribe'", out["body"])
        self.assertIn("hello there", out["body"])

    def test_unsubscribe_url_uses_token(self) -> None:
        url = smtp_send.build_unsubscribe_url("https://x.test/", "abc123")
        self.assertEqual(url, "https://x.test/u/abc123")

    def test_unsubscribe_url_strips_trailing_slash(self) -> None:
        a = smtp_send.build_unsubscribe_url("https://x.test/", "tok")
        b = smtp_send.build_unsubscribe_url("https://x.test", "tok")
        self.assertEqual(a, b)


class TestRateLimiter(unittest.TestCase):
    def test_does_not_block_below_limit(self) -> None:
        rl = smtp_send.RateLimiter(per_minute=10)
        t0 = time.monotonic()
        for _ in range(5):
            rl.wait()
        self.assertLess(time.monotonic() - t0, 0.1)

    def test_floor_to_one(self) -> None:
        rl = smtp_send.RateLimiter(per_minute=0)
        # Constructor floors to 1, so two calls should block once.
        rl.wait()
        # We don't actually wait the full minute in the test — just verify the
        # internal state is reasonable.
        self.assertEqual(rl.per_minute, 1)
        self.assertEqual(len(rl._times), 1)


class TestGitmailUrlParse(unittest.TestCase):
    def test_extracts_owner_repo(self) -> None:
        from gitmail import _own_repo_full_name
        self.assertEqual(_own_repo_full_name("https://github.com/foo/bar"), "foo/bar")
        self.assertEqual(_own_repo_full_name("https://github.com/foo/bar/"), "foo/bar")
        self.assertEqual(_own_repo_full_name("https://github.com/foo/bar/issues/1"), "foo/bar")

    def test_returns_none_for_non_github(self) -> None:
        from gitmail import _own_repo_full_name
        self.assertIsNone(_own_repo_full_name("https://example.com/foo/bar"))
        self.assertIsNone(_own_repo_full_name(""))


# Make scripts/gitmail.py importable for the URL-parse test
sys.path.insert(0, str(HERE.parent / "scripts"))


if __name__ == "__main__":
    unittest.main()
