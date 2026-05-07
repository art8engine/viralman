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
import sys
from pathlib import Path
from typing import Dict

sys.path.insert(0, str(Path(__file__).parent / "lib"))

from creds import ENV_PATH, _parse_env, save_many  # noqa: E402


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

    if args.show_keys:
        if ENV_PATH.exists():
            for k in sorted(_parse_env(ENV_PATH.read_text(encoding="utf-8"))):
                print(k)
        return 0

    updates: Dict[str, str] = {}

    for pair in args.set:
        if "=" not in pair:
            print(f"ERROR: --set must be KEY=VALUE, got: {pair}", file=sys.stderr)
            return 2
        k, _, v = pair.partition("=")
        k = k.strip()
        if not k.replace("_", "").isalnum() or not k.isupper():
            print(f"ERROR: key must be UPPER_SNAKE_CASE, got: {k}", file=sys.stderr)
            return 2
        updates[k] = v

    if args.stdin:
        k = args.stdin.strip()
        if not k.replace("_", "").isalnum() or not k.isupper():
            print(f"ERROR: key must be UPPER_SNAKE_CASE, got: {k}", file=sys.stderr)
            return 2
        v = sys.stdin.read().rstrip("\n").rstrip("\r")
        if not v:
            print(f"ERROR: empty value for {k}", file=sys.stderr)
            return 2
        updates[k] = v

    if not updates and not args.unset:
        print("ERROR: nothing to do — pass --set or --stdin or --unset", file=sys.stderr)
        return 2

    save_many(updates, unset=args.unset)

    if updates:
        print(f"saved: {', '.join(updates.keys())}")
    if args.unset:
        print(f"removed: {', '.join(args.unset)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
