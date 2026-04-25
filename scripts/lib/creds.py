"""Credential loader for viralman post scripts.

All credentials live in ~/.viralman/.env, mode 600. This module is the
ONLY place that file is read. The agent context never sees it.
"""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path
from typing import Dict


CREDS_DIR = Path.home() / ".viralman"
ENV_PATH = CREDS_DIR / ".env"


class CredsError(Exception):
    pass


def _parse_env(text: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if val and val[0] == val[-1] and val[0] in ('"', "'"):
            val = val[1:-1]
        out[key] = val
    return out


def load() -> Dict[str, str]:
    if not ENV_PATH.exists():
        raise CredsError(
            f"No credentials at {ENV_PATH}. Run scripts/setup.sh to configure."
        )

    st = ENV_PATH.stat()
    mode = stat.S_IMODE(st.st_mode)
    if mode & 0o077:
        raise CredsError(
            f"{ENV_PATH} has mode {oct(mode)}; refusing to read. "
            f"Run: chmod 600 {ENV_PATH}"
        )

    text = ENV_PATH.read_text(encoding="utf-8")
    return _parse_env(text)


def require(creds: Dict[str, str], keys: list[str], platform: str) -> Dict[str, str]:
    missing = [k for k in keys if not creds.get(k)]
    if missing:
        raise CredsError(
            f"{platform}: missing credentials {missing}. "
            f"Run scripts/setup.sh to configure."
        )
    return {k: creds[k] for k in keys}


def read_body_from_stdin_or_arg(arg_value: str | None) -> str:
    if arg_value == "-" or arg_value is None:
        if sys.stdin.isatty():
            raise CredsError("expected post body on stdin (use --body -)")
        return sys.stdin.read()
    return arg_value
