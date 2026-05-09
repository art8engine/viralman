"""JSON endpoints for the dashboard.

Routes:
  POST /api/preview/twitter         {body}                       -> validation + URL
  POST /api/preview/reddit          {subreddit,title,body}       -> validation + URL
  POST /api/post/twitter            {body}                       -> live URL or compose URL
  POST /api/post/reddit             {subreddit,title,body,flair} -> live URL
  GET  /api/creds/status                                         -> per-platform status
  POST /api/creds/manual            {key,value}                  -> save (non-secret or secret)
  POST /api/gitmail/collect         {description,...}            -> {job_id}    (recipients only)
  POST /api/gitmail/send            {recipients,body,...}        -> {job_id}    (compose+send)
  GET  /api/gitmail/status/<job_id>                              -> {status,events,summary}
  POST /api/gitmail/cancel/<job_id>                              -> {ok}
  POST /api/generate                {project,channels,...}       -> drafts per channel
  POST /api/scrape/reddit-threads   {subreddits,keywords}        -> top threads

Note on secrets: a browser-typed secret IS visible to this process. We mitigate
by piping it straight into save_creds.py's stdin (so it never lands on the
command line) and by only saving when explicitly asked. The shell-based skills
remain the recommended path.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"

sys.path.insert(0, str(SCRIPTS / "lib"))
# Append (not insert) so scripts/dashboard.py does NOT shadow the dashboard
# package — `from gitmail import step_*` only needs scripts/ to be reachable.
sys.path.append(str(SCRIPTS))

from creds import load as load_creds, CredsError  # noqa: E402
from compose_urls import twitter_intent, reddit_submit  # noqa: E402
from sniffer_check import check as sniff_check  # noqa: E402
# These two are re-exported for tests that monkey-patch via `api.<name>`
# (test_unsubscribe_filter.py mocks `api.smtp_send.render_preview`, and
# test_gitmail_collect.py patches `dashboard.api.github_search.*`). The
# pipeline itself now goes through gitmail.step_*, not these directly.
import github_search  # noqa: E402,F401
import smtp_send  # noqa: E402,F401
from unsubscribe import (  # noqa: E402
    record_unsubscribe as _record_unsubscribe_lib,
)


# --------------------------------------------------------------------------- #
# In-memory job tracker for gitmail                                           #
# --------------------------------------------------------------------------- #


class GitmailJob:
    def __init__(self, job_id: str, args: Dict[str, Any]):
        self.id = job_id
        self.args = args
        self.events: List[Dict[str, Any]] = []
        self.lock = threading.Lock()
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
        """Cooperative cancel — collect/send loops check job.status each turn."""
        if self.status in ("done", "error", "cancelled"):
            return False
        self.status = "cancelled"
        self.ended_at = time.time()
        return True

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
    """Persist via the shared lib and keep an in-memory record so the route's
    test suite can verify that this process saw the unsubscribe. The send
    pipeline itself reads from disk via lib's load_unsubscribed_emails — see
    ADR 0001 — so this dict is no longer load-bearing for the send path."""
    UNSUBSCRIBES[token] = time.time()
    _record_unsubscribe_lib(token)


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


# --------------------------------------------------------------------------- #
# Status detection                                                            #
# --------------------------------------------------------------------------- #


def _llm_draft_or_fallback(creds, lc, channel, project, keywords, intent, provider,
                            hashtags=None):
    """Generate a draft via LLM; if creds missing, return a templated stub."""
    name = project.get("name") or "my-project"
    pitch = project.get("pitch") or project.get("desc", "")[:200]
    sniffer = sniff_check

    use_llm = any(creds.get(k) for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY"))
    if use_llm:
        try:
            system = (
                f"Write a {channel} post for a developer announcing their own project. "
                "No marketing slop. No 'let's dive in', 'leverage', 'supercharge', 'unlock'. "
                "Concrete, anchored in numbers/names where possible. End with a low-key CTA."
            )
            user_prompt = (
                f"Project: {name}\n"
                f"Pitch: {pitch}\n"
                f"Keywords: {', '.join(keywords[:8])}\n"
            )
            if intent:
                user_prompt += f"What the user wants to convey: {intent}\n"
            user_prompt += "\n"
            if channel == "twitter":
                user_prompt += (
                    f"Output ONLY the tweet body (<=280 chars). For a thread, separate parts "
                    f"with `---` on its own line. Add 0–2 hashtags from {hashtags or []}."
                )
                raw = lc.call_llm(creds, system=system, user=user_prompt,
                                   provider=provider, max_tokens=600)
                return _wrap_draft(channel, body=raw, sniffer=sniffer)
            if channel == "reddit":
                user_prompt += (
                    "Output JSON ONLY: {\"title\": \"<=300 chars, no clickbait\", "
                    "\"body\": \"markdown body, 200-600 words\"}"
                )
                raw = lc.call_llm(creds, system=system, user=user_prompt,
                                   provider=provider, max_tokens=900)
                d = lc._extract_json(raw) or {}
                return _wrap_draft(channel, title=d.get("title", name),
                                   body=d.get("body", raw), sniffer=sniffer)
            if channel == "gitmail":
                user_prompt += (
                    "Output ONLY the email body (90-160 words) as a TEMPLATE. "
                    "Use `{{login}}` for the recipient handle and `{{starred_repo}}` for the repo "
                    "they starred. End with a low-pressure CTA — repo link or one-question reply."
                )
                raw = lc.call_llm(creds, system=system, user=user_prompt,
                                   provider=provider, max_tokens=700)
                return _wrap_draft(channel, body=raw, sniffer=sniffer)
        except Exception as e:
            return _stub_draft(channel, name, pitch, keywords, sniffer,
                                error=str(e))
    return _stub_draft(channel, name, pitch, keywords, sniffer)


def _wrap_draft(channel, body="", title="", sniffer=None):
    flags = []
    if sniffer and body:
        try:
            platform_map = {"twitter": "x", "reddit": "reddit", "gitmail": "linkedin"}
            flags = sniffer(body, platform=platform_map.get(channel, "linkedin"))
        except Exception:
            flags = []
    out = {"body": (body or "").strip(), "flags": flags}
    if title:
        out["title"] = title.strip()
    return out


def _stub_draft(channel, name, pitch, keywords, sniffer, error=None):
    kw = ", ".join(keywords[:5]) or "open source"
    if channel == "twitter":
        body = (f"shipped {name}: {pitch[:140]}\n\n"
                 f"if you work with {kw}, would love your read.")
    elif channel == "reddit":
        body = (f"# {name}\n\n"
                 f"{pitch}\n\n"
                 f"keywords: {kw}\n\n"
                 f"happy to take feedback — what's the first thing that'd stop you from using this?")
        return _wrap_draft(channel, title=name, body=body, sniffer=sniffer)
    else:  # gitmail
        body = (f"Hi {{{{login}}}},\n\n"
                 f"Noticed you starred {{{{starred_repo}}}}. Thought this might be relevant.\n\n"
                 f"I built {name}: {pitch}. It's open source and I'm still in early feedback mode, "
                 f"so rough edges are expected. The main use case is {kw}.\n\n"
                 f"If you get a chance to look, I'd like to know what's missing or broken "
                 f"for your workflow. A one-line reply is plenty.\n\n"
                 f"Repo: https://github.com/your-handle/{name}\n\n"
                 f"- {name}")
    out = _wrap_draft(channel, body=body, sniffer=sniffer)
    if error:
        out["llm_error"] = error
    return out


def _suggest_subreddits(topics, keywords):
    """Heuristic subreddit suggestions based on keywords."""
    candidates = []
    aliases = {
        "go": ["golang"], "golang": ["golang"],
        "python": ["Python", "learnpython"],
        "rust": ["rust"],
        "javascript": ["javascript"], "typescript": ["typescript"],
        "kubernetes": ["kubernetes", "devops"],
        "k8s": ["kubernetes", "devops"],
        "docker": ["docker", "devops"],
        "react": ["reactjs"],
        "nextjs": ["nextjs"],
        "ai": ["MachineLearning", "LocalLLaMA"],
        "llm": ["LocalLLaMA", "MachineLearning"],
        "rag": ["LocalLLaMA"],
        "cli": ["commandline"],
        "tui": ["commandline"],
        "scraper": ["webscraping"],
        "observability": ["devops", "sre"],
        "monitoring": ["devops", "sre"],
    }
    seen = set()
    for kw in (topics or []) + (keywords or []):
        for s in aliases.get(kw.lower(), []):
            if s not in seen:
                seen.add(s)
                candidates.append(s)
    if not candidates:
        candidates = ["programming", "opensource", "SideProject"]
    return candidates[:6]


def _fetch_reddit_threads(subs, keywords, per_sub=5):
    """Hit Reddit's public JSON listing — no auth required for read-only."""
    import urllib.parse
    import urllib.request
    query = " OR ".join(f'"{k}"' if " " in k else k for k in (keywords or [])) or ""
    out = []
    for sub in subs:
        sub = sub.strip().lstrip("r/").lstrip("/")
        if not sub:
            continue
        if query:
            url = (f"https://www.reddit.com/r/{sub}/search.json?"
                    f"q={urllib.parse.quote(query)}&restrict_sr=on&sort=new&limit={per_sub}")
        else:
            url = f"https://www.reddit.com/r/{sub}/new.json?limit={per_sub}"
        req = urllib.request.Request(
            url, headers={"User-Agent": "viralman-dashboard/0.2"}
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                body = r.read()
            data = json.loads(body)
        except Exception:
            continue
        for child in (data.get("data") or {}).get("children") or []:
            d = child.get("data") or {}
            out.append({
                "subreddit": d.get("subreddit") or sub,
                "title": d.get("title") or "",
                "url": "https://www.reddit.com" + (d.get("permalink") or ""),
                "score": d.get("score", 0),
                "comments": d.get("num_comments", 0),
                "created": d.get("created_utc", 0),
            })
    out.sort(key=lambda t: -t.get("score", 0))
    return out[:15]


# ─── In-process gitmail collect / send (no subprocess) ───

def _run_collect_job(job: "GitmailJob") -> None:
    """Drive the collect phase of the Outreach Pipeline by calling step_* with
    a job-bound sink and cancel check. Behaviour matches the CLI's
    `gitmail recipients` exactly — same GraphQL bulk profile lookup and the
    same Gmail/abort guards apply (see ADR 0001)."""

    def job_sink(event: str, **fields: Any) -> None:
        job.append({"event": event, **fields})

    def cancelled() -> bool:
        return job.status == "cancelled"

    try:
        try:
            creds = load_creds()
        except CredsError:
            creds = {}

        from gitmail import (step_analyse, step_search, step_recipients,
                              _own_repo_full_name)

        analysis = step_analyse(creds, job.args.get("description", ""),
                                 sink=job_sink)
        if not analysis.get("topics") and not analysis.get("keywords"):
            job_sink("fatal", reason="no usable keywords found in description")
            return
        if cancelled():
            return

        repos = step_search(
            creds, analysis,
            min_stars=int(job.args.get("min_stars") or 200),
            repo_limit=int(job.args.get("repo_limit") or 15),
            own_repo=_own_repo_full_name(job.args.get("project_url") or ""),
            sink=job_sink,
        )
        if not repos:
            job_sink("fatal", reason="no similar repos found")
            return

        max_users = min(int(job.args.get("max_users") or 100), 1500)
        recipients = step_recipients(
            creds, repos, max_users=max_users,
            sink=job_sink, cancel_check=cancelled,
        )
        job_sink("done", recipients=recipients, analysis=analysis)
    except Exception as e:
        job.append({"event": "fatal", "reason": f"{type(e).__name__}: {e}"})


def _run_send_job(job: "GitmailJob") -> None:
    """Drive compose+send for a recipient list the user already collected.

    Both compose and send are step_* calls — same Gmail quota guard, same
    abort marker handling, same unsubscribe-token recording as the CLI.
    The dashboard form's body/subject are treated as Prewritten Templates
    (see CONTEXT.md): step_compose's prewritten path substitutes
    {{login}}/{{starred_repo}}/{{project_name}}/{{project_url}}.
    """

    def job_sink(event: str, **fields: Any) -> None:
        job.append({"event": event, **fields})

    def cancelled() -> bool:
        return job.status == "cancelled"

    try:
        creds = load_creds()
        recipients = job.args.get("recipients") or []
        project_name = job.args.get("project_name", "")
        project_url = job.args.get("project_url", "")
        body_template = job.args.get("body") or ""
        subject_template = (job.args.get("subject")
                             or f"about {project_name or 'your project'}")
        dry_run = bool(job.args.get("dry_run", True))
        unsubscribe_base = job.args.get("_url_root") or "http://localhost:8765"

        # Normalise recipient shape — step_compose expects a starred_repo on
        # every row, so backfill empty strings rather than KeyError downstream.
        clean_recipients: List[Dict[str, str]] = []
        for r in recipients:
            if not isinstance(r, dict) or not r.get("email"):
                continue
            clean_recipients.append({
                "login": r.get("login", "") or "",
                "email": r["email"],
                "starred_repo": r.get("starred_repo", "") or "",
                "profile": r.get("profile", "") or "",
            })

        from gitmail import step_compose, step_send

        composed = step_compose(
            creds, clean_recipients,
            project_name=project_name,
            project_pitch="",
            project_url=project_url,
            provider=None,
            prewritten_subject=subject_template,
            prewritten_body=body_template,
            sink=job_sink, cancel_check=cancelled,
        )

        result = step_send(
            creds, composed,
            unsubscribe_base=unsubscribe_base,
            dry_run=dry_run,
            sink=job_sink, cancel_check=cancelled,
        )
        job_sink("done", send=result)
    except Exception as e:
        job.append({"event": "fatal", "reason": f"{type(e).__name__}: {e}"})


def _creds_status() -> Dict[str, Dict[str, Any]]:
    """Per-platform configuration status, sourced from the platforms registry
    so the dashboard, check_creds.py, and post_*.py all agree on what's
    needed."""
    from platforms import PLATFORMS, is_configured, present_keys, missing_keys

    try:
        creds = load_creds()
    except CredsError:
        creds = {}
    out: Dict[str, Dict[str, Any]] = {}
    for name, spec in PLATFORMS.items():
        out[name] = {
            "configured": is_configured(spec, creds),
            "present": present_keys(spec, creds),
            "missing": missing_keys(spec, creds),
        }

    # Identity hints — surfaced in the connect dropdown when set.
    handle = creds.get("TWITTER_HANDLE")
    if handle:
        out["twitter"]["handle"] = handle
    if creds.get("REDDIT_USERNAME"):
        out["reddit"]["username"] = creds["REDDIT_USERNAME"]
    if creds.get("SMTP_FROM"):
        out["smtp"]["from"] = creds["SMTP_FROM"]

    # Claude CLI (Claude Max plan) — no key, just check the binary
    import shutil as _sh
    binary = _sh.which("claude")
    cli_info: Dict[str, Any] = {"available": bool(binary)}
    if binary:
        cli_info["path"] = binary
        try:
            import subprocess as _sp
            ver = _sp.run([binary, "--version"], capture_output=True, text=True, timeout=5)
            if ver.returncode == 0:
                cli_info["version"] = ver.stdout.strip().split()[0]
        except Exception:
            pass
    cli_info["configured"] = cli_info["available"]
    out["claude_cli"] = cli_info
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

    # ----- gitmail status / cancel (shared by collect + send jobs) -----

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

    # ----- generate (LLM-driven drafts for selected channels) -----

    @app.post("/api/generate")
    def generate():
        data = request.get_json(silent=True) or {}
        project = data.get("project") or {}
        channels = [c for c in (data.get("channels") or []) if c in ("twitter", "reddit", "gitmail")]
        if not project.get("desc"):
            return jsonify({"ok": False, "error": "project.desc required"}), 400
        if not channels:
            return jsonify({"ok": False, "error": "no channels selected"}), 400

        try:
            from creds import load as load_creds, CredsError
            import github_search as gs
            import llm_compose as lc
        except ImportError as e:
            return jsonify({"ok": False, "error": f"import failed: {e}"}), 500

        try:
            creds = load_creds()
        except CredsError:
            creds = {}

        analysis = gs.analyse_project(project["desc"])
        keywords = analysis.get("keywords", [])
        topics = analysis.get("topics", [])
        suggested_hashtags = ["#" + (t.replace("-", "") or t) for t in topics[:6]]
        suggested_subreddits = _suggest_subreddits(topics, keywords)

        provider = data.get("provider")
        intent = (data.get("intent") or "").strip()
        drafts: dict[str, dict] = {}

        if "twitter" in channels:
            drafts["twitter"] = _llm_draft_or_fallback(
                creds, lc, "twitter", project, keywords, intent, provider, hashtags=suggested_hashtags[:2],
            )
        if "reddit" in channels:
            drafts["reddit"] = _llm_draft_or_fallback(
                creds, lc, "reddit", project, keywords, intent, provider,
            )
        if "gitmail" in channels:
            drafts["gitmail"] = _llm_draft_or_fallback(
                creds, lc, "gitmail", project, keywords, intent, provider,
            )

        return jsonify({
            "ok": True,
            "drafts": drafts,
            "keywords": keywords,
            "topics": topics,
            "suggested_hashtags": suggested_hashtags,
            "suggested_subreddits": suggested_subreddits,
        })

    # ----- reddit thread scraping (read-only, no auth needed) -----

    # ----- gitmail collect (recipients only, no send) -----

    @app.post("/api/gitmail/collect")
    def gitmail_collect():
        data = request.get_json(silent=True) or {}
        if not (data.get("description") or "").strip():
            return jsonify({"ok": False, "error": "description required"}), 400
        max_users = int(data.get("max_users") or 100)
        if max_users < 1 or max_users > 10000:
            return jsonify({"ok": False, "error": "max_users must be 1..10000"}), 400
        job_id = uuid.uuid4().hex[:12]
        job = GitmailJob(job_id, {**data, "_kind": "collect"})
        with JOBS_LOCK:
            JOBS[job_id] = job
        threading.Thread(target=_run_collect_job, args=(job,), daemon=True).start()
        return jsonify({"ok": True, "job_id": job_id})

    # ----- gitmail send (selected recipients only) -----

    @app.post("/api/gitmail/send")
    def gitmail_send():
        data = request.get_json(silent=True) or {}
        recipients = data.get("recipients") or []
        if not recipients:
            return jsonify({"ok": False, "error": "no recipients selected"}), 400
        if not (data.get("body") or "").strip():
            return jsonify({"ok": False, "error": "email body required"}), 400
        job_id = uuid.uuid4().hex[:12]
        url_root = request.url_root.rstrip("/") or "http://localhost:8765"
        job = GitmailJob(job_id, {**data, "_kind": "send", "_url_root": url_root})
        with JOBS_LOCK:
            JOBS[job_id] = job
        threading.Thread(target=_run_send_job, args=(job,), daemon=True).start()
        return jsonify({"ok": True, "job_id": job_id})

    @app.post("/api/scrape/reddit-threads")
    def scrape_reddit_threads():
        data = request.get_json(silent=True) or {}
        subs = data.get("subreddits") or []
        keywords = data.get("keywords") or []
        if not subs:
            return jsonify({"ok": False, "error": "subreddits required"}), 400

        threads = _fetch_reddit_threads(subs[:5], keywords[:3], per_sub=5)
        return jsonify({"ok": True, "threads": threads})

    # ----- twitter reply (scrape candidates + post per-tweet replies) -----

    TWITTER_CANDIDATES_PATH = Path("/tmp/twitter_candidates.json")

    @app.get("/api/twitter-reply/cache")
    def twitter_reply_cache():
        if not TWITTER_CANDIDATES_PATH.exists():
            return jsonify({"ok": True, "candidates": [], "query": ""})
        try:
            payload = json.loads(TWITTER_CANDIDATES_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            return jsonify({"ok": False, "error": f"cache parse error: {e}"}), 500
        return jsonify({"ok": True,
                         "candidates": payload.get("candidates", []),
                         "query": payload.get("query", "")})

    @app.post("/api/twitter-reply/scrape")
    def twitter_reply_scrape():
        data = request.get_json(silent=True) or {}
        query = (data.get("query") or "").strip()
        keywords = (data.get("keywords") or "").strip()
        if not query and not keywords:
            return jsonify({"ok": False, "error": "query or keywords required"}), 400

        cli = ["find", "--out", str(TWITTER_CANDIDATES_PATH),
                "--max-candidates", str(int(data.get("max_candidates") or 20)),
                "--min-engagement", str(int(data.get("min_engagement") or 0))]
        if query:
            cli += ["--query", query]
        if keywords:
            cli += ["--keywords", keywords]
        if data.get("lang"):
            cli += ["--lang", str(data["lang"])]
        if data.get("include_retweets"):
            cli += ["--include-retweets"]

        cmd = [sys.executable, str(SCRIPTS / "twitter_reply.py")] + cli
        try:
            proc = subprocess.run(cmd, text=True, capture_output=True, timeout=30,
                                    cwd=str(REPO_ROOT))
        except subprocess.TimeoutExpired:
            return jsonify({"ok": False, "error": "scrape timeout"}), 504

        if proc.returncode != 0:
            err = proc.stderr.strip() or proc.stdout.strip() or "scrape failed"
            return jsonify({"ok": False, "error": err[:300]}), 502

        if not TWITTER_CANDIDATES_PATH.exists():
            return jsonify({"ok": False, "error": "no output file written"}), 502
        try:
            payload = json.loads(TWITTER_CANDIDATES_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            return jsonify({"ok": False, "error": f"output parse error: {e}"}), 502
        return jsonify({"ok": True,
                         "candidates": payload.get("candidates", []),
                         "query": payload.get("query", "")})

    @app.post("/api/twitter-reply/reply")
    def twitter_reply_post():
        data = request.get_json(silent=True) or {}
        tweet_id = (data.get("tweet_id") or "").strip()
        body = (data.get("body") or "").strip()
        if not tweet_id or not body:
            return jsonify({"ok": False, "error": "tweet_id and body required"}), 400
        if len(body) > 280:
            return jsonify({"ok": False, "error": f"{len(body)} chars > 280"}), 400

        result = _run_post_script(
            "twitter_reply.py",
            ["reply", "--tweet-id", tweet_id, "--body", "-"],
            body,
        )
        if not result.get("ok"):
            return jsonify({"ok": False,
                             "error": result.get("stderr") or result.get("stdout") or "reply failed"}), 502
        return jsonify({"ok": True, "url": result.get("url")})
