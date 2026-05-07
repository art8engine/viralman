"""Regression tests for compose_email JSON-parse fallback.

P0-7: When the LLM emits prose instead of JSON, the previous implementation
silently used the entire raw text as the email body — including any preamble
like "Sure, here's the email:" — and shipped that. The fix retries once with
a stricter "JSON ONLY" reminder, and raises a RuntimeError if the second
attempt also fails. step_compose() in gitmail.py catches that and falls back
to a templated stub instead of corrupted prose.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

import llm_compose  # noqa: E402


def _kwargs():
    return dict(
        project_name="demo",
        project_pitch="cuts cost 47%",
        project_url="https://github.com/me/demo",
        login="alice",
        starred_repo="up/stream",
    )


class TestComposeEmailRetriesOnNonJson(unittest.TestCase):
    """First call returns prose; second call returns valid JSON. Must succeed."""

    def test_retries_once_on_non_json(self):
        calls: list[str] = []

        def fake_call_llm(creds, *, system, user, provider=None,
                          model=None, max_tokens=1500):
            calls.append(user)
            if len(calls) == 1:
                return "Sure! Here's the email:\nNo JSON though."
            # Second attempt — JSON.
            return '{"subject": "hi", "body": "real body"}'

        with patch.object(llm_compose, "call_llm", side_effect=fake_call_llm):
            out = llm_compose.compose_email({}, **_kwargs())

        self.assertEqual(len(calls), 2, "should retry exactly once")
        self.assertEqual(out["subject"], "hi")
        self.assertEqual(out["body"], "real body")
        # The retry's user prompt MUST contain the strict-JSON reminder.
        self.assertIn("ONLY the JSON object", calls[1])


class TestComposeEmailRaisesAfterTwoFailures(unittest.TestCase):
    """Both calls return prose. compose_email must raise — not dump prose as body."""

    def test_raises_after_two_non_json_attempts(self):
        prose = "I cannot output JSON. Here is some text instead."

        def fake_call_llm(creds, *, system, user, provider=None,
                          model=None, max_tokens=1500):
            return prose

        with patch.object(llm_compose, "call_llm", side_effect=fake_call_llm):
            with self.assertRaises(RuntimeError) as ctx:
                llm_compose.compose_email({}, **_kwargs())

        self.assertIn("parseable JSON", str(ctx.exception))


class TestComposeEmailNoBodyFieldRaises(unittest.TestCase):
    """Even if JSON parses, an empty body field must raise — never ship empty."""

    def test_raises_when_body_field_missing(self):
        def fake_call_llm(creds, *, system, user, provider=None,
                          model=None, max_tokens=1500):
            return '{"subject": "hi"}'  # no body

        with patch.object(llm_compose, "call_llm", side_effect=fake_call_llm):
            # The retry path also returns no body, so we expect RuntimeError.
            with self.assertRaises(RuntimeError):
                llm_compose.compose_email({}, **_kwargs())


class TestComposeEmailDoesNotDumpProseAsBody(unittest.TestCase):
    """The exact regression: prose like 'Sure! Here is your email: ...' must
    NEVER end up as the email body."""

    def test_prose_preamble_never_becomes_body(self):
        prose_with_preamble = (
            "Sure! Here's the email I drafted for you:\n\n"
            "Subject: Some subject\n"
            "Body: Hello there..."
        )

        def fake_call_llm(creds, *, system, user, provider=None,
                          model=None, max_tokens=1500):
            return prose_with_preamble

        with patch.object(llm_compose, "call_llm", side_effect=fake_call_llm):
            with self.assertRaises(RuntimeError):
                llm_compose.compose_email({}, **_kwargs())


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
