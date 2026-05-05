"""Unsubscribe state — shared between the dashboard and the CLI script.

Persisted files:
- ``<repo>/.viralman_unsubscribes.jsonl`` — append-only log of every
  ``/u/<token>`` hit. Tokens only.
- ``<repo>/.viralman_unsub_tokens.jsonl`` — append-only token→email map
  written at send time so future campaigns can resolve a token back to
  the email they belong to.

Env overrides for tests:
- ``VIRALMAN_UNSUB_LOG``         → unsubscribe log path
- ``VIRALMAN_UNSUB_TOKEN_LOG``   → token-email map path
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Dict, Optional


# Resolve repo root from this file's location: scripts/lib/unsubscribe.py
_DEFAULT_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _resolve_repo_root(repo_root: Optional[Path]) -> Path:
    return repo_root if repo_root is not None else _DEFAULT_REPO_ROOT


def unsubscribe_log_path(repo_root: Optional[Path] = None) -> Path:
    """Path to the persisted token-only unsubscribe log."""
    override = os.environ.get("VIRALMAN_UNSUB_LOG")
    if override:
        return Path(override)
    return _resolve_repo_root(repo_root) / ".viralman_unsubscribes.jsonl"


def token_email_map_path(repo_root: Optional[Path] = None) -> Path:
    """Path to the token->email map (append-only jsonl)."""
    override = os.environ.get("VIRALMAN_UNSUB_TOKEN_LOG")
    if override:
        return Path(override)
    return _resolve_repo_root(repo_root) / ".viralman_unsub_tokens.jsonl"


def record_unsubscribe(token: str, repo_root: Optional[Path] = None) -> None:
    """Append a token row to the unsubscribe log."""
    if not token:
        return
    path = unsubscribe_log_path(repo_root)
    try:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.time(), "token": token}) + "\n")
    except Exception:
        pass


def record_token_email(token: str, email: str,
                        repo_root: Optional[Path] = None) -> None:
    """Append a {token, email} row to the token-email map for later lookup."""
    if not token or not email:
        return
    path = token_email_map_path(repo_root)
    try:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.time(), "token": token,
                                 "email": email}) + "\n")
    except Exception:
        pass


def load_unsubscribed_emails(repo_root: Optional[Path] = None) -> set[str]:
    """Resolve unsubscribed emails by joining the unsubscribe log with the
    token->email map.

    Missing files are treated as empty (backward-compat). Returns a
    lower-cased set of emails.
    """
    unsub_tokens: set[str] = set()
    unsub_log = unsubscribe_log_path(repo_root)
    if unsub_log.exists():
        try:
            with unsub_log.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    tok = row.get("token")
                    if tok:
                        unsub_tokens.add(tok)
        except Exception:
            pass

    if not unsub_tokens:
        return set()

    token_to_email: Dict[str, str] = {}
    map_path = token_email_map_path(repo_root)
    if map_path.exists():
        try:
            with map_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    tok = row.get("token")
                    email = row.get("email")
                    if tok and email:
                        token_to_email[tok] = email.lower()
        except Exception:
            pass

    return {token_to_email[t] for t in unsub_tokens if t in token_to_email}
