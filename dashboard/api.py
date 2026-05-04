"""JSON endpoints for the dashboard.

Routes:
  POST /api/preview/twitter   {body}                         -> validation + URL
  POST /api/preview/reddit    {subreddit,title,body}         -> validation + URL
  POST /api/post/twitter      {body}                         -> live URL or compose URL
  POST /api/post/reddit       {subreddit,title,body,flair}   -> live URL
  GET  /api/creds/status                                     -> per-platform status
  POST /api/creds/manual      {key,value}                    -> non-secret save
  POST /api/creds/secret      {key,value}                    -> secret save (note: still
                                                                  goes via subprocess; the
                                                                  value is held only in
                                                                  this Python process)
  POST /api/gitmail/start     {project_name,description,...} -> {job_id}
  GET  /api/gitmail/status/<job_id>                          -> {status,events,summary}
  POST /api/gitmail/cancel/<job_id>                          -> {ok}
  GET  /api/gitmail/jobs                                     -> list

Note on secrets: a browser-typed secret IS visible to this process. We mitigate
by piping it straight into save_creds.py's stdin (so it never lands on the
command line) and by only saving when explicitly asked. The shell-based skills
remain the recommended path.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import urllib.parse
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"

sys.path.insert(0, str(SCRIPTS / "lib"))

from creds import load as load_creds, CredsError  # noqa: E402
from compose_urls import twitter_intent, reddit_submit  # noqa: E402
from sniffer_check import check as sniff_check  # noqa: E402


# --------------------------------------------------------------------------- #
# In-memory job tracker for gitmail                                           #
# --------------------------------------------------------------------------- #


class GitmailJob:
    def __init__(self, job_id: str, args: Dict[str, Any]):
        self.id = job_id
        self.args = args
        self.events: List[Dict[str, Any]] = []
        self.lock = threading.Lock()
        self.proc: Optional[subprocess.Popen] = None
        self.status = "pending"
        self.started_at = time.time()
        self.ended_at: Optional[float] = None
        self.summary: Dict[str, Any] = {}

    def append(self, event: Dict[str, Any]) -> None:
        with self.lock:
            self.events.append(event)
            kind = event.get("event")
            if kind == "done":
                self.status = "done"
                self.summary = event
                self.ended_at = time.time()
            elif kind == "fatal":
                self.status = "error"
                self.summary = event
                self.ended_at = time.time()

    def cancel(self) -> bool:
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
            except Exception:
                return False
            self.status = "cancelled"
            self.ended_at = time.time()
            return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        with self.lock:
            return {
                "id": self.id,
                "status": self.status,
                "args": {k: v for k, v in self.args.items()
                          if k not in ("description",)},
                "started_at": self.started_at,
                "ended_at": self.ended_at,
                "event_count": len(self.events),
                "events": list(self.events),
                "summary": self.summary,
            }


JOBS: Dict[str, GitmailJob] = {}
JOBS_LOCK = threading.Lock()
UNSUBSCRIBES: Dict[str, float] = {}


def record_unsubscribe(token: str) -> None:
    UNSUBSCRIBES[token] = time.time()
    log = REPO_ROOT / ".viralman_unsubscribes.jsonl"
    try:
        with log.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.time(), "token": token}) + "\n")
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# Subprocess helpers                                                          #
# --------------------------------------------------------------------------- #


def _run_post_script(script: str, args: List[str], stdin: str) -> Dict[str, Any]:
    cmd = [sys.executable, str(SCRIPTS / script)] + args
    try:
        proc = subprocess.run(
            cmd,
            input=stdin,
            text=True,
            capture_output=True,
            timeout=120,
            cwd=str(REPO_ROOT),
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout", "url": None}
    return {
        "ok": proc.returncode == 0,
        "exit_code": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
        "url": proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else None,
    }


def _save_cred(key: str, value: str, *, secret: bool) -> Dict[str, Any]:
    if not key.replace("_", "").isalnum() or not key.isupper():
        return {"ok": False, "error": "key must be UPPER_SNAKE_CASE"}
    cmd = [sys.executable, str(SCRIPTS / "save_creds.py")]
    if secret:
        cmd += ["--stdin", key]
        proc = subprocess.run(cmd, input=value, text=True, capture_output=True,
                               cwd=str(REPO_ROOT), timeout=10)
    else:
        cmd += ["--set", f"{key}={value}"]
        proc = subprocess.run(cmd, text=True, capture_output=True,
                               cwd=str(REPO_ROOT), timeout=10)
    return {"ok": proc.returncode == 0,
             "stdout": proc.stdout.strip(),
             "stderr": proc.stderr.strip()}


def _start_gitmail_job(job: GitmailJob) -> None:
    cmd = [
        sys.executable, str(SCRIPTS / "gitmail.py"), "run",
        "--description", job.args["description"],
        "--project-name", job.args.get("project_name") or "my-project",
        "--project-url", job.args.get("project_url") or "",
        "--max-users", str(int(job.args.get("max_users") or 100)),
        "--min-stars", str(int(job.args.get("min_stars") or 200)),
        "--repo-limit", str(int(job.args.get("repo_limit") or 15)),
        "--unsubscribe-base", job.args.get("unsubscribe_base") or "http://localhost:8765",
    ]
    if job.args.get("provider"):
        cmd += ["--provider", job.args["provider"]]
    if job.args.get("pitch"):
        cmd += ["--pitch", job.args["pitch"]]
    if job.args.get("reply_to"):
        cmd += ["--reply-to", job.args["reply_to"]]
    if job.args.get("template_only"):
        cmd += ["--template-only"]
    if job.args.get("dry_run"):
        cmd += ["--dry-run"]

    proc = subprocess.Popen(
        cmd,
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    job.proc = proc
    job.status = "running"

    def reader(pipe, kind: str) -> None:
        for line in pipe:
            line = line.rstrip("\n")
            if not line:
                continue
            if kind == "stdout":
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    event = {"event": "log", "msg": line}
            else:
                event = {"event": "stderr", "msg": line}
            job.append(event)
        pipe.close()

    threading.Thread(target=reader, args=(proc.stdout, "stdout"),
                      daemon=True).start()
    threading.Thread(target=reader, args=(proc.stderr, "stderr"),
                      daemon=True).start()

    def waiter() -> None:
        rc = proc.wait()
        if job.status not in ("done", "error", "cancelled"):
            job.status = "error" if rc else "done"
            job.ended_at = time.time()
            job.append({"event": "exit", "code": rc})

    threading.Thread(target=waiter, daemon=True).start()


# --------------------------------------------------------------------------- #
# Status detection                                                            #
# --------------------------------------------------------------------------- #


CREDS_BY_PLATFORM = {
    "twitter": ["TWITTER_API_KEY", "TWITTER_API_SECRET",
                 "TWITTER_ACCESS_TOKEN", "TWITTER_ACCESS_SECRET"],
    "reddit": ["REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET",
                "REDDIT_USERNAME", "REDDIT_PASSWORD"],
    "linkedin": ["LINKEDIN_ACCESS_TOKEN", "LINKEDIN_PERSON_URN"],
    "github": ["GITHUB_TOKEN"],
    "smtp": ["SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM"],
    "claude": ["ANTHROPIC_API_KEY"],
    "openai": ["OPENAI_API_KEY"],
    "gemini": ["GEMINI_API_KEY"],
}


def _creds_status() -> Dict[str, Dict[str, Any]]:
    try:
        creds = load_creds()
    except CredsError:
        creds = {}
    out: Dict[str, Dict[str, Any]] = {}
    for platform, keys in CREDS_BY_PLATFORM.items():
        present = [k for k in keys if creds.get(k)]
        out[platform] = {
            "configured": len(present) == len(keys),
            "present": present,
            "missing": [k for k in keys if not creds.get(k)],
        }
    handle = creds.get("TWITTER_HANDLE")
    if handle:
        out["twitter"]["handle"] = handle
    if creds.get("REDDIT_USERNAME"):
        out["reddit"]["username"] = creds["REDDIT_USERNAME"]
    if creds.get("SMTP_FROM"):
        out["smtp"]["from"] = creds["SMTP_FROM"]
    return out


# --------------------------------------------------------------------------- #
# Route registration                                                          #
# --------------------------------------------------------------------------- #


def register(app) -> None:
    from flask import jsonify, request

    # ----- creds -----

    @app.get("/api/creds/status")
    def creds_status():
        return jsonify(_creds_status())

    @app.post("/api/creds/manual")
    def creds_manual():
        data = request.get_json(silent=True) or {}
        key = (data.get("key") or "").strip()
        value = (data.get("value") or "").strip()
        secret = bool(data.get("secret"))
        if not key or not value:
            return jsonify({"ok": False, "error": "key and value required"}), 400
        result = _save_cred(key, value, secret=secret)
        if not result.get("ok"):
            return jsonify(result), 400
        return jsonify({"ok": True, "status": _creds_status()})

    # ----- twitter -----

    @app.post("/api/preview/twitter")
    def preview_twitter():
        data = request.get_json(silent=True) or {}
        body = (data.get("body") or "").strip()
        if not body:
            return jsonify({"ok": False, "error": "empty body"}), 400
        first = body.split("---")[0].strip()
        flags = sniff_check(first, platform="x")
        return jsonify({
            "ok": True,
            "char_count": len(first),
            "limit": 280,
            "over_limit": len(first) > 280,
            "compose_url": twitter_intent(first),
            "flags": flags,
            "thread_parts": [p.strip() for p in body.split("---") if p.strip()],
        })

    @app.post("/api/post/twitter")
    def post_twitter():
        data = request.get_json(silent=True) or {}
        body = (data.get("body") or "").strip()
        if not body:
            return jsonify({"ok": False, "error": "empty body"}), 400
        result = _run_post_script("post_twitter.py", ["--body", "-", "--no-open"], body)
        return jsonify(result)

    # ----- reddit -----

    @app.post("/api/preview/reddit")
    def preview_reddit():
        data = request.get_json(silent=True) or {}
        sub = (data.get("subreddit") or "").strip().lstrip("r/").lstrip("/")
        title = (data.get("title") or "").strip()
        body = (data.get("body") or "").strip()
        if not sub or not title:
            return jsonify({"ok": False, "error": "subreddit and title required"}), 400
        flags = sniff_check(body or title, platform="reddit")
        return jsonify({
            "ok": True,
            "subreddit": sub,
            "title_len": len(title),
            "title_over": len(title) > 300,
            "body_len": len(body),
            "compose_url": reddit_submit(sub, title, body),
            "flags": flags,
        })

    @app.post("/api/post/reddit")
    def post_reddit():
        data = request.get_json(silent=True) or {}
        sub = (data.get("subreddit") or "").strip().lstrip("r/").lstrip("/")
        title = (data.get("title") or "").strip()
        body = (data.get("body") or "").strip()
        flair = (data.get("flair") or "").strip() or None
        if not sub or not title:
            return jsonify({"ok": False, "error": "subreddit and title required"}), 400
        cli = ["--subreddit", sub, "--title", title, "--body", "-"]
        if flair:
            cli += ["--flair", flair]
        return jsonify(_run_post_script("post_reddit.py", cli, body))

    # ----- gitmail -----

    @app.post("/api/gitmail/start")
    def gitmail_start():
        data = request.get_json(silent=True) or {}
        if not (data.get("description") or "").strip():
            return jsonify({"ok": False, "error": "description required"}), 400
        max_users = int(data.get("max_users") or 100)
        if max_users < 1 or max_users > 10000:
            return jsonify({"ok": False, "error": "max_users must be 1..10000"}), 400
        job_id = uuid.uuid4().hex[:12]
        job = GitmailJob(job_id, {
            "description": data["description"],
            "project_name": data.get("project_name") or "my-project",
            "project_url": data.get("project_url") or "",
            "pitch": data.get("pitch") or "",
            "max_users": max_users,
            "min_stars": int(data.get("min_stars") or 200),
            "repo_limit": int(data.get("repo_limit") or 15),
            "provider": data.get("provider"),
            "dry_run": bool(data.get("dry_run", True)),
            "template_only": bool(data.get("template_only", False)),
            "unsubscribe_base": data.get("unsubscribe_base")
                or f"{request.url_root.rstrip('/')}",
            "reply_to": data.get("reply_to"),
        })
        with JOBS_LOCK:
            JOBS[job_id] = job
        _start_gitmail_job(job)
        return jsonify({"ok": True, "job_id": job_id})

    @app.get("/api/gitmail/status/<job_id>")
    def gitmail_status(job_id):
        with JOBS_LOCK:
            job = JOBS.get(job_id)
        if not job:
            return jsonify({"ok": False, "error": "no such job"}), 404
        since = int(request.args.get("since", "0"))
        snapshot = job.to_dict()
        snapshot["events"] = snapshot["events"][since:]
        snapshot["next_since"] = since + len(snapshot["events"])
        return jsonify(snapshot)

    @app.post("/api/gitmail/cancel/<job_id>")
    def gitmail_cancel(job_id):
        with JOBS_LOCK:
            job = JOBS.get(job_id)
        if not job:
            return jsonify({"ok": False, "error": "no such job"}), 404
        return jsonify({"ok": job.cancel()})

    @app.get("/api/gitmail/jobs")
    def gitmail_jobs():
        with JOBS_LOCK:
            return jsonify({
                "jobs": [{"id": j.id, "status": j.status,
                           "started_at": j.started_at,
                           "ended_at": j.ended_at}
                          for j in JOBS.values()]
            })
