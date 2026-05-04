#!/usr/bin/env python3
"""Thin shim around the `viralman` command. Kept so the existing scripts/ layout
still works (and so users can do `./scripts/dashboard.py`)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from viralman_cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
