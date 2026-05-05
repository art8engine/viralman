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
import github_search  # noqa: E402
import smtp_send  # noqa: E402
from unsubscribe import (  # noqa: E402
    record_unsubscribe as _record_unsubscribe_lib,
    record_token_email as _record_token_email_lib,
    load_unsubscribed_emails as _load_unsubscribed_emails_lib,
    unsubscribe_log_path as _unsubscribe_log_path_lib,
    token_email_map_path as _token_email_map_path_lib,
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
    """Record an unsubscribe in the in-memory map and persist via shared lib."""
    UNSUBSCRIBES[token] = time.time()
    _record_unsubscribe_lib(token)


def _unsubscribe_log_path() -> Path:
    """Deprecated wrapper — delegates to scripts.lib.unsubscribe."""
    return _unsubscribe_log_path_lib()


def _token_email_map_path() -> Path:
    """Deprecated wrapper — delegates to scripts.lib.unsubscribe."""
    return _token_email_map_path_lib()


def _record_token_email(token: str, email: str) -> None:
    """Deprecated wrapper — delegates to scripts.lib.unsubscribe."""
    _record_token_email_lib(token, email)


def _load_unsubscribed_emails() -> set[str]:
    """Resolve unsubscribed *emails* via the shared lib, plus any in-memory
    UNSUBSCRIBES tokens that already have an email mapping on disk."""
    base = _load_unsubscribed_emails_lib()
    if not UNSUBSCRIBES:
        return base
    # In-memory tokens (from a hot route) need a token→email lookup
    map_path = _token_email_map_path_lib()
    if not map_path.exists():
        return base
    try:
        token_to_email: Dict[str, str] = {}
        with map_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                tok = row.get("token")
                email = row.get("email")
                if tok and email:
                    token_to_email[tok] = email.lower()
        extra = {token_to_email[t] for t in UNSUBSCRIBES.keys()
                 if t in token_to_email}
        return base | extra
    except Exception:
        return base


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


def _llm_draft_or_fallback(creds, lc, channel, project, keywords, intent, provider,
                            hashtags=None):
    """Generate a draft via LLM; if creds missing, return a templated stub."""
    name = project.get("name") or "my-project"
    pitch = project.get("pitch") or project.get("desc", "")[:200]
    sniffer = None
    try:
        from sniffer_check import check as sniffer
    except ImportError:
        pass

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
    try:
        try:
            creds = load_creds()
        except CredsError:
            creds = {}
        token = creds.get("GITHUB_TOKEN")
        desc = job.args.get("description", "")
        job.append({"event": "analyse_start"})
        analysis = github_search.analyse_project(desc)
        job.append({"event": "analyse_done",
                     "keywords": analysis.get("keywords", []),
                     "topics": analysis.get("topics", [])})
        if not analysis.get("topics") and not analysis.get("keywords"):
            job.append({"event": "fatal",
                         "reason": "no usable keywords found in description"})
            return
        job.append({"event": "search_start"})
        own_repo = None
        url = job.args.get("project_url") or ""
        if "github.com/" in url:
            tail = url.split("github.com/", 1)[1].rstrip("/").split("/")
            if len(tail) >= 2:
                own_repo = f"{tail[0]}/{tail[1]}"
        repos = github_search.search_similar_repos(
            topics=analysis.get("topics", []),
            keywords=analysis.get("keywords", []),
            min_stars=int(job.args.get("min_stars") or 200),
            limit=int(job.args.get("repo_limit") or 15),
            token=token,
            exclude_full_names={own_repo} if own_repo else None,
        )
        job.append({"event": "search_done", "count": len(repos),
                     "repos": [{"full_name": r["full_name"], "stars": r["stars"]}
                                for r in repos]})
        if not repos:
            job.append({"event": "fatal", "reason": "no similar repos found"})
            return
        max_users = min(int(job.args.get("max_users") or 100), 10000)
        job.append({"event": "recipients_start", "target": max_users,
                     "repo_count": len(repos)})
        seen: set[str] = set()
        recipients: List[Dict[str, Any]] = []
        iters = [(r, github_search.iter_stargazers(r["full_name"],
                                                     max_users=max_users * 5,
                                                     token=token))
                  for r in repos]
        while iters and len(recipients) < max_users and job.status != "cancelled":
            next_iters = []
            for repo, it in iters:
                try:
                    user = next(it)
                except StopIteration:
                    continue
                login = user.get("login")
                if not login or login in seen:
                    next_iters.append((repo, it))
                    continue
                seen.add(login)
                if job.status == "cancelled":
                    break
                email = github_search.resolve_user_email(login, token=token)
                if email:
                    rec = {
                        "login": login,
                        "email": email,
                        "starred_repo": repo["full_name"],
                        "profile": user.get("html_url", f"https://github.com/{login}"),
                    }
                    recipients.append(rec)
                    job.append({"event": "recipient",
                                 "count": len(recipients),
                                 "target": max_users,
                                 **rec})
                    if len(recipients) >= max_users:
                        break
                next_iters.append((repo, it))
            iters = next_iters
        job.append({"event": "recipients_done", "count": len(recipients)})
        job.append({"event": "done", "recipients": recipients,
                     "analysis": analysis})
    except Exception as e:
        job.append({"event": "fatal", "reason": f"{type(e).__name__}: {e}"})


def _run_send_job(job: "GitmailJob") -> None:
    try:
        creds = load_creds()
        recipients = job.args.get("recipients") or []
        body_template = job.args.get("body") or ""
        subject = job.args.get("subject") or f"about {job.args.get('project_name', 'your project')}"
        dry_run = bool(job.args.get("dry_run", True))
        unsubscribe_base = job.args.get("_url_root") or "http://localhost:8765"

        unsubbed = _load_unsubscribed_emails()

        def fill(rec: Dict[str, str]) -> str:
            return (body_template
                    .replace("{{login}}", rec.get("login", ""))
                    .replace("{{starred_repo}}", rec.get("starred_repo", "")))

        if dry_run:
            job.append({"event": "send_dry_run_start", "count": len(recipients)})
            previews = []
            skipped = 0
            for r in recipients:
                if job.status == "cancelled":
                    break
                email = (r.get("email") or "").lower()
                if email and email in unsubbed:
                    skipped += 1
                    job.append({"event": "send_skip",
                                 "reason": "unsubscribed",
                                 "to": r.get("email", "")})
                    continue
                body = fill(r)
                preview = smtp_send.render_preview(
                    creds, to_addr=r["email"], subject=subject, body=body,
                    unsubscribe_base=unsubscribe_base,
                )
                tok = preview.get("unsubscribe_token")
                if tok:
                    _record_token_email(tok, r["email"])
                previews.append({**r, "subject": subject, "body": body,
                                  "preview_headers": preview["headers"]})
                job.append({"event": "send_preview", "to": r["email"],
                             "subject": subject})
            job.append({"event": "send_dry_run_done", "count": len(previews),
                         "skipped": skipped})
            job.append({"event": "done",
                         "send": {"sent": 0, "failed": 0, "skipped": skipped,
                                   "previews": previews}})
            return

        try:
            smtp, limiter = smtp_send.open_session(creds)
        except smtp_send.SmtpError as e:
            job.append({"event": "fatal", "reason": str(e)})
            return

        sent = 0
        failed = 0
        skipped = 0
        failures: List[Dict[str, str]] = []
        job.append({"event": "send_start", "count": len(recipients)})
        try:
            for r in recipients:
                if job.status == "cancelled":
                    break
                email = (r.get("email") or "").lower()
                if email and email in unsubbed:
                    skipped += 1
                    job.append({"event": "send_skip",
                                 "reason": "unsubscribed",
                                 "to": r.get("email", "")})
                    continue
                limiter.wait()
                body = fill(r)
                try:
                    result = smtp_send.send_one(
                        smtp, creds, to_addr=r["email"], subject=subject,
                        body=body, unsubscribe_base=unsubscribe_base,
                    )
                    sent += 1
                    tok = result.get("unsubscribe_token")
                    if tok:
                        _record_token_email(tok, r["email"])
                    job.append({"event": "send_ok", "to": r["email"],
                                 "login": r.get("login", ""),
                                 "message_id": result.get("message_id", ""),
                                 "sent": sent, "target": len(recipients)})
                except Exception as e:
                    failed += 1
                    failures.append({"login": r.get("login", ""),
                                      "email": r["email"], "error": str(e)})
                    job.append({"event": "send_fail", "to": r["email"],
                                 "error": str(e), "failed": failed})
        finally:
            try:
                smtp.quit()
            except Exception:
                pass
        job.append({"event": "send_done", "sent": sent, "failed": failed,
                     "skipped": skipped})
        job.append({"event": "done",
                     "send": {"sent": sent, "failed": failed,
                               "skipped": skipped, "failures": failures}})
    except Exception as e:
        job.append({"event": "fatal", "reason": f"{type(e).__name__}: {e}"})


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
