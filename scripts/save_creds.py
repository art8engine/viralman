#!/usr/bin/env python3
"""Merge KEY=VALUE pairs into ~/.viralman/.env atomically with chmod 600.

Designed so secrets never enter the LLM context: callers pipe the secret
via stdin or via a `read -s` shell pattern.

Usage:
  # explicit non-secret value
  ./scripts/save_creds.py --set REDDIT_CLIENT_ID=xxx

  # secret from stdin (preferred)
  read -s -p "secret: " s && printf '%s' "$s" | \\
      ./scripts/save_creds.py --stdin REDDIT_CLIENT_SECRET

  # multiple --set in one call
  ./scripts/save_creds.py --set REDDIT_USERNAME=alice --set REDDIT_USER_AGENT='viralman/0.1.0 by alice'
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple


CREDS_DIR = Path.home() / ".viralman"
ENV_PATH = CREDS_DIR / ".env"


def _parse_existing(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    out: Dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, _, v = line.partition("=")
        v = v.strip()
        if v and v[0] == v[-1] and v[0] in ('"', "'"):
            v = v[1:-1]
        out[k.strip()] = v
    return out


def _atomic_write(path: Path, data: str) -> None:
    fd, tmp = tempfile.mkstemp(prefix=".env.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _serialize(d: Dict[str, str]) -> str:
    lines = ["# viralman credentials — do not commit"]
    for k in sorted(d):
        v = d[k]
        if v == "":
            continue
        lines.append(f'{k}="{v}"')
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description="Save credentials to ~/.viralman/.env")
    p.add_argument(
        "--set",
        action="append",
        default=[],
        help="KEY=VALUE pair. Repeatable. NOT for secrets — secrets enter the LLM context this way.",
    )
    p.add_argument(
        "--stdin",
        default=None,
        help="Read the value for the given KEY from stdin. Use this for secrets.",
    )
    p.add_argument(
        "--unset",
        action="append",
        default=[],
        help="KEY to remove. Repeatable.",
    )
    p.add_argument(
        "--show-keys",
        action="store_true",
        help="Print the keys currently stored (no values).",
    )
    args = p.parse_args()

    CREDS_DIR.mkdir(mode=0o700, exist_ok=True)
    try:
        os.chmod(CREDS_DIR, 0o700)
    except PermissionError:
        pass

    existing = _parse_existing(ENV_PATH)

    if args.show_keys:
        for k in sorted(existing):
            print(k)
        return 0

    updates: List[Tuple[str, str]] = []

    for pair in args.set:
        if "=" not in pair:
            print(f"ERROR: --set must be KEY=VALUE, got: {pair}", file=sys.stderr)
            return 2
        k, _, v = pair.partition("=")
        k = k.strip()
        if not k.replace("_", "").isalnum() or not k.isupper():
            print(f"ERROR: key must be UPPER_SNAKE_CASE, got: {k}", file=sys.stderr)
            return 2
        updates.append((k, v))

    if args.stdin:
        k = args.stdin.strip()
        if not k.replace("_", "").isalnum() or not k.isupper():
            print(f"ERROR: key must be UPPER_SNAKE_CASE, got: {k}", file=sys.stderr)
            return 2
        v = sys.stdin.read().rstrip("\n").rstrip("\r")
        if not v:
            print(f"ERROR: empty value for {k}", file=sys.stderr)
            return 2
        updates.append((k, v))

    for k in args.unset:
        existing.pop(k, None)

    for k, v in updates:
        existing[k] = v

    if not updates and not args.unset:
        print("ERROR: nothing to do — pass --set or --stdin or --unset", file=sys.stderr)
        return 2

    _atomic_write(ENV_PATH, _serialize(existing))

    saved_keys = [k for k, _ in updates]
    if saved_keys:
        print(f"saved: {', '.join(saved_keys)}")
    if args.unset:
        print(f"removed: {', '.join(args.unset)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
