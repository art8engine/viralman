"""Flask app for the viralman dashboard.

Three pages — twitter / reddit / gitmail — sharing a project block via
localStorage. Header switches between them. Connect dropdown unifies login.
"""

from __future__ import annotations

import os
import secrets as _secrets
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))

try:
    from flask import Flask, redirect, render_template
except ImportError as e:  # pragma: no cover
    raise SystemExit(
        "ERROR: dashboard requires Flask. Run: pip install flask\n"
        f"({e})"
    )

from . import api  # noqa: E402
from . import oauth  # noqa: E402


def create_app(*, secret_key: str | None = None) -> Flask:
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).parent / "templates"),
        static_folder=str(Path(__file__).parent / "static"),
    )
    app.config["SECRET_KEY"] = secret_key or os.environ.get("VIRALMAN_SECRET") or _secrets.token_hex(32)
    app.config["REPO_ROOT"] = str(REPO_ROOT)

    @app.route("/")
    def index():
        return redirect("/twitter")

    @app.route("/twitter")
    def page_twitter():
        return render_template("twitter.html", active="twitter")

    @app.route("/reddit")
    def page_reddit():
        return render_template("reddit.html", active="reddit")

    @app.route("/gitmail")
    def page_gitmail():
        return render_template("gitmail.html", active="gitmail")

    @app.route("/twitter-reply")
    def page_twitter_reply():
        return render_template("twitter_reply.html", active="twitter-reply")

    @app.route("/setup")
    def page_setup():
        return render_template("setup.html", active="setup")

    @app.route("/u/<token>", methods=["GET", "POST"])
    def unsubscribe(token):
        api.record_unsubscribe(token)
        return ("You're unsubscribed. No further emails from this campaign.\n",
                 200, {"Content-Type": "text/plain; charset=utf-8"})

    api.register(app)
    oauth.register(app)
    return app


def main() -> int:
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--debug", action="store_true")
    args = p.parse_args()
    app = create_app()
    app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
