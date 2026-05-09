"""Resolution + safety check for the URL prefix baked into recipient
unsubscribe links. Without this, real (non-dry-run) sends used to
silently emit `http://localhost:8765/u/<token>` to recipients who
cannot reach the user's machine.

Run:
  .venv/bin/python -m pytest tests/test_unsubscribe_base.py -v
"""

from __future__ import annotations

import argparse
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

import gitmail  # noqa: E402


def _ns(unsubscribe_base: str = "http://localhost:8765"):
    return argparse.Namespace(unsubscribe_base=unsubscribe_base)


class TestIsLocalhostBase(unittest.TestCase):

    def test_localhost_variants(self):
        for url in (
            "http://localhost:8765",
            "https://localhost",
            "http://127.0.0.1:8765",
            "https://127.0.0.1",
            "localhost:8765",
            "127.0.0.1:8765",
            "HTTP://LOCALHOST:8765",
        ):
            with self.subTest(url=url):
                self.assertTrue(gitmail._is_localhost_base(url))

    def test_real_domains(self):
        for url in (
            "https://viralman.example.com",
            "http://outreach.acme.io",
            "https://yeachan.dev",
            "http://my-server.local:8000",
        ):
            with self.subTest(url=url):
                self.assertFalse(gitmail._is_localhost_base(url))

    def test_empty(self):
        self.assertFalse(gitmail._is_localhost_base(""))
        self.assertFalse(gitmail._is_localhost_base(None or ""))


class TestResolveUnsubscribeBase(unittest.TestCase):

    def test_dry_run_passes_localhost_through(self):
        base, err = gitmail._resolve_unsubscribe_base(
            _ns(), creds={}, dry_run=True,
        )
        self.assertIsNone(err)
        self.assertEqual(base, "http://localhost:8765")

    def test_real_send_with_only_localhost_aborts(self):
        base, err = gitmail._resolve_unsubscribe_base(
            _ns(), creds={}, dry_run=False,
        )
        self.assertIsNone(base)
        self.assertIsNotNone(err)
        self.assertIn("localhost", err)
        self.assertIn("VIRALMAN_UNSUBSCRIBE_BASE", err)

    def test_creds_value_wins_over_localhost_default(self):
        base, err = gitmail._resolve_unsubscribe_base(
            _ns(),
            creds={"VIRALMAN_UNSUBSCRIBE_BASE": "https://outreach.example.com"},
            dry_run=False,
        )
        self.assertIsNone(err)
        self.assertEqual(base, "https://outreach.example.com")

    def test_explicit_cli_wins_over_creds(self):
        base, err = gitmail._resolve_unsubscribe_base(
            _ns(unsubscribe_base="https://override.example.com"),
            creds={"VIRALMAN_UNSUBSCRIBE_BASE": "https://saved.example.com"},
            dry_run=False,
        )
        self.assertIsNone(err)
        self.assertEqual(base, "https://override.example.com")

    def test_localhost_cli_falls_through_to_creds(self):
        base, err = gitmail._resolve_unsubscribe_base(
            _ns(unsubscribe_base="http://localhost:8765"),
            creds={"VIRALMAN_UNSUBSCRIBE_BASE": "https://saved.example.com"},
            dry_run=False,
        )
        self.assertIsNone(err)
        self.assertEqual(base, "https://saved.example.com")

    def test_localhost_creds_does_not_save_us_on_real_send(self):
        base, err = gitmail._resolve_unsubscribe_base(
            _ns(),
            creds={"VIRALMAN_UNSUBSCRIBE_BASE": "http://localhost:8765"},
            dry_run=False,
        )
        self.assertIsNone(base)
        self.assertIn("localhost", err)


if __name__ == "__main__":
    unittest.main()
