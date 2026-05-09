"""Console-script entry for the `viralman` command.

Mirrors bin/viralman but lives as an importable module so pyproject.toml's
[project.scripts] can resolve it after pip install.

Two modes:
  - `viralman`                 → start the dashboard (legacy default).
  - `viralman <subcommand> …`  → dispatch to scripts/<subcommand>.py with the
    remaining argv. Lets users in any directory run gitmail / twitter-reply /
    save-creds / etc. without needing a clone of the repo on hand.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path


SUBCOMMAND_SCRIPTS = {
    "gitmail":        "gitmail.py",
    "twitter-reply":  "twitter_reply.py",
    "save-creds":     "save_creds.py",
    "check-creds":    "check_creds.py",
    "post-twitter":   "post_twitter.py",
    "post-reddit":    "post_reddit.py",
    "post-linkedin":  "post_linkedin.py",
    "gitmail-watch":  "gitmail_watch.py",
}


def _scripts_dir() -> Path:
    """Locate scripts/ regardless of install path. Either packaged alongside
    viralman_cli (after `pip install`) or sibling in a repo checkout."""
    candidate = Path(__file__).resolve().parent.parent / "scripts"
    if not (candidate / "gitmail.py").is_file():
        raise RuntimeError(
            f"viralman scripts/ not found at {candidate}. The package may "
            "have been installed without scripts/. Reinstall:\n"
            "  pip install --upgrade git+https://github.com/art8engine/viralman"
        )
    return candidate


def _dispatch_subcommand(name: str, rest_argv: list[str]) -> int:
    script = _scripts_dir() / SUBCOMMAND_SCRIPTS[name]
    return subprocess.run(
        [sys.executable, str(script), *rest_argv],
        check=False,
    ).returncode


def _ensure_repo_on_path() -> Path:
    here = Path(__file__).resolve().parent.parent
    if (here / "dashboard" / "server.py").exists():
        sys.path.insert(0, str(here))
    return here


def _install_hint() -> str:
    py = sys.executable or "python3"
    return (
        "viralman dashboard needs Flask. Install it with:\n"
        f"  {py} -m pip install --user flask\n"
        "or use a venv (.venv/bin/pip install flask)."
    )


def _open_browser_when_ready(url: str, *, delay: float = 1.0) -> None:
    def _go() -> None:
        time.sleep(delay)
        try:
            webbrowser.open(url, new=2)
        except Exception:
            pass
    threading.Thread(target=_go, daemon=True).start()


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    if raw and raw[0] in SUBCOMMAND_SCRIPTS:
        return _dispatch_subcommand(raw[0], raw[1:])

    p = argparse.ArgumentParser(
        prog="viralman",
        description=(
            "Start the viralman dashboard, or dispatch a subcommand "
            f"({', '.join(SUBCOMMAND_SCRIPTS)})."
        ),
    )
    p.add_argument("--host", default=os.environ.get("VIRALMAN_HOST", "127.0.0.1"))
    p.add_argument("--port", type=int,
                    default=int(os.environ.get("VIRALMAN_PORT", "8765")))
    p.add_argument("--no-browser", action="store_true")
    p.add_argument("--debug", action="store_true")
    args = p.parse_args(raw)

    _ensure_repo_on_path()

    try:
        from dashboard.server import create_app
    except (SystemExit, ImportError) as e:
        sys.stderr.write(_install_hint() + "\n")
        return 2

    app = create_app()
    host_for_url = "localhost" if args.host == "0.0.0.0" else args.host
    url = f"http://{host_for_url}:{args.port}"
    print(f"viralman dashboard → {url}")
    print(f"  twitter:  {url}/twitter")
    print(f"  reddit:   {url}/reddit")
    print(f"  gitmail:  {url}/gitmail")
    print("Ctrl-C to stop.")

    if not args.no_browser:
        _open_browser_when_ready(url)

    try:
        app.run(host=args.host, port=args.port, debug=args.debug,
                 threaded=True, use_reloader=False)
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"\nport {args.port} in use. Try: viralman --port {args.port + 1}",
                   file=sys.stderr)
            return 2
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
