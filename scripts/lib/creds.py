"""Credential loader for viralman post scripts.

All credentials live in ~/.viralman/.env, mode 600. This module is the
ONLY place that file is read or written. The agent context never sees it.
"""

from __future__ import annotations

import os
import stat
import sys
import tempfile
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


def save_many(updates: Dict[str, str], unset: list[str] | None = None) -> None:
    """Atomically merge updates into ~/.viralman/.env (mode 600).

    Preserves existing keys not present in `updates`. Empty-string values are
    dropped from the file. Optional `unset` removes keys before applying
    updates. Single Python-level path used by save_creds.py CLI, dashboard
    OAuth callbacks, and post_twitter.py token rotation.
    """
    CREDS_DIR.mkdir(mode=0o700, exist_ok=True)
    try:
        os.chmod(CREDS_DIR, 0o700)
    except PermissionError:
        pass

    existing: Dict[str, str] = {}
    if ENV_PATH.exists():
        existing = _parse_env(ENV_PATH.read_text(encoding="utf-8"))

    for k in (unset or []):
        existing.pop(k, None)
    existing.update(updates)

    _atomic_write(ENV_PATH, _serialize(existing))


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
