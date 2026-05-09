#!/usr/bin/env python3
"""Verify credentials by hitting a read-only endpoint on the platform.

The actual per-platform check logic lives in `scripts/lib/platforms.py` so
the dashboard's status endpoint, the post_*.py guards, and this script all
agree on what each platform needs (see ADR 0003). This file just dispatches.

Usage:
  ./scripts/check_creds.py --platform reddit
  ./scripts/check_creds.py --platform twitter
  ./scripts/check_creds.py --platform linkedin

Exit codes (mirrored from the per-platform check_fn):
  0 — creds work, identity printed
  1 — creds present but API rejected them
  2 — creds missing or library not installed
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))

from creds import load as load_creds, CredsError  # noqa: E402
from platforms import PLATFORMS, is_configured, missing_keys  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--platform", required=True,
        choices=sorted(name for name, spec in PLATFORMS.items()
                       if spec.check_fn is not None),
    )
    args = p.parse_args()

    try:
        creds = load_creds()
    except CredsError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    spec = PLATFORMS[args.platform]
    if not is_configured(spec, creds):
        print(f"ERROR: {args.platform}: missing creds "
              f"{missing_keys(spec, creds)}",
              file=sys.stderr)
        return 2
    return spec.check_fn(creds)


if __name__ == "__main__":
    raise SystemExit(main())
