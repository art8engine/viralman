#!/usr/bin/env python3
"""gitmail — find developers who likely care about your open-source project,
then send each one a short, personalized email.

Pipeline:
  1. Analyse the project description (LLM)
  2. Search GitHub for similar repos by topic + keyword
  3. Walk those repos' stargazers, resolve their public email
  4. For each recipient, compose a short personalized email (LLM)
  5. SMTP-send with rate limiting and a one-click unsubscribe footer

Streaming: every step emits a JSONL event to stdout. The dashboard tails this
to render live progress.

Usage (CLI):
  ./scripts/gitmail.py run \
      --project-name viralman \
      --description "A K8s autoscaler in Go that cuts cost by 47%" \
      --project-url https://github.com/foo/viralman \
      --max-users 200 \
      --provider claude \
      [--dry-run] [--unsubscribe-base http://localhost:8765]

  ./scripts/gitmail.py analyse "..."          # quick analysis only
  ./scripts/gitmail.py recipients "..." --max-users 50    # collect only

Exit codes:
  0  success
  1  partial — some emails failed to send
  2  configuration error (missing creds / invalid args)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent / "lib"))

from creds import load as load_creds, CredsError  # noqa: E402
import github_search  # noqa: E402
import llm_compose  # noqa: E402
import smtp_send  # noqa: E402


# --------------------------------------------------------------------------- #
# Streaming event helper                                                      #
# --------------------------------------------------------------------------- #


def _emit(event: str, **fields: Any) -> None:
    record = {"ts": time.time(), "event": event, **fields}
    sys.stdout.write(json.dumps(record, ensure_ascii=False) + "\n")
    sys.stdout.flush()


# --------------------------------------------------------------------------- #
# Pipeline pieces                                                             #
# --------------------------------------------------------------------------- #


def _own_repo_full_name(url: str) -> Optional[str]:
    if not url:
        return None
    m = url.strip().rstrip("/")
    if "github.com/" not in m:
        return None
    tail = m.split("github.com/", 1)[1]
    parts = tail.split("/")
    if len(parts) < 2:
        return None
    return f"{parts[0]}/{parts[1]}"


def step_analyse(creds: Dict[str, str], description: str,
                  *, provider: Optional[str] = None) -> Dict[str, Any]:
    _emit("analyse_start")
    try:
        analysis = llm_compose.analyse_project_llm(creds, description, provider=provider)
        analysis["source"] = "llm"
    except Exception as e:
        _emit("analyse_fallback", reason=str(e))
        analysis = github_search.analyse_project(description)
        analysis["source"] = "heuristic"
        analysis.setdefault("summary", description[:200])
        analysis.setdefault("value_prop", "")
    _emit("analyse_done",
          summary=analysis.get("summary", ""),
          keywords=analysis.get("keywords", []),
          topics=analysis.get("topics", []),
          source=analysis.get("source"))
    return analysis


def step_search(
    creds: Dict[str, str],
    analysis: Dict[str, Any],
    *,
    min_stars: int,
    repo_limit: int,
    own_repo: Optional[str],
) -> List[Dict[str, Any]]:
    token = creds.get("GITHUB_TOKEN")
    _emit("search_start", topics=analysis.get("topics", []),
          keywords=analysis.get("keywords", []), min_stars=min_stars)
    repos = github_search.search_similar_repos(
        topics=analysis.get("topics", []) or [],
        keywords=analysis.get("keywords", []) or [],
        min_stars=min_stars,
        limit=repo_limit,
        token=token,
        exclude_full_names={own_repo} if own_repo else None,
    )
    _emit("search_done", count=len(repos),
          repos=[{"full_name": r["full_name"], "stars": r["stars"]}
                 for r in repos])
    return repos


def step_recipients(
    creds: Dict[str, str],
    repos: List[Dict[str, Any]],
    *,
    max_users: int,
) -> List[Dict[str, str]]:
    token = creds.get("GITHUB_TOKEN")
    _emit("recipients_start", target=max_users, repo_count=len(repos))

    last_log = [0.0]

    def _on_progress(p: Dict[str, Any]) -> None:
        # Don't spam the stream — cap to 1 event/sec.
        now = time.monotonic()
        if now - last_log[0] >= 1.0 or p["count"] >= p["target"]:
            last_log[0] = now
            _emit("recipients_progress", count=p["count"], target=p["target"])

    by_login: Dict[str, str] = {}
    out: List[Dict[str, str]] = []
    iters = [(r, github_search.iter_stargazers(r["full_name"],
                                                max_users=max_users * 5,
                                                token=token))
              for r in repos]
    while iters and len(out) < max_users:
        next_iters = []
        for repo, it in iters:
            try:
                user = next(it)
            except StopIteration:
                continue
            login = user["login"]
            if login in by_login:
                next_iters.append((repo, it))
                continue
            email = github_search.resolve_user_email(login, token=token)
            if email:
                by_login[login] = email
                out.append({
                    "login": login,
                    "email": email,
                    "starred_repo": repo["full_name"],
                    "profile": user.get("html_url", ""),
                })
                _on_progress({"count": len(out), "target": max_users,
                              "login": login})
                if len(out) >= max_users:
                    break
            else:
                by_login[login] = ""
            next_iters.append((repo, it))
        iters = next_iters

    _emit("recipients_done", count=len(out))
    return out


def step_compose(
    creds: Dict[str, str],
    recipients: List[Dict[str, str]],
    *,
    project_name: str,
    project_pitch: str,
    project_url: str,
    provider: Optional[str],
    template_only: bool = False,
) -> List[Dict[str, str]]:
    """Returns each recipient enriched with subject+body."""
    _emit("compose_start", count=len(recipients), template_only=template_only)
    out: List[Dict[str, str]] = []
    for i, r in enumerate(recipients):
        if template_only and i > 0:
            # Reuse the first composition; only swap @login and starred_repo
            base = out[0]
            body = base["body"].replace(
                f"@{recipients[0]['login']}", f"@{r['login']}"
            ).replace(recipients[0]["starred_repo"], r["starred_repo"])
            out.append({**r, "subject": base["subject"], "body": body})
            continue
        try:
            email = llm_compose.compose_email(
                creds,
                project_name=project_name,
                project_pitch=project_pitch,
                project_url=project_url,
                login=r["login"],
                starred_repo=r["starred_repo"],
                provider=provider,
            )
        except Exception as e:
            _emit("compose_error", login=r["login"], error=str(e))
            email = {
                "subject": f"Quick note about {project_name}",
                "body": (f"Hi @{r['login']},\n\n"
                          f"Saw you starred {r['starred_repo']}. I built "
                          f"{project_name} ({project_pitch}). "
                          f"Repo: {project_url}. "
                          f"Curious if it's useful — happy to hear what's "
                          f"missing."),
            }
        rec = {**r, "subject": email["subject"], "body": email["body"]}
        out.append(rec)
        _emit("compose_progress", count=i + 1, target=len(recipients))
    _emit("compose_done", count=len(out))
    return out


def step_send(
    creds: Dict[str, str],
    composed: List[Dict[str, str]],
    *,
    unsubscribe_base: str,
    dry_run: bool,
    reply_to: Optional[str] = None,
) -> Dict[str, Any]:
    if dry_run:
        _emit("send_dry_run_start", count=len(composed))
        previews = []
        for r in composed:
            preview = smtp_send.render_preview(
                creds,
                to_addr=r["email"],
                subject=r["subject"],
                body=r["body"],
                unsubscribe_base=unsubscribe_base,
                reply_to=reply_to,
            )
            previews.append({**r, "preview_headers": preview["headers"]})
            _emit("send_preview", to=r["email"], subject=r["subject"])
        _emit("send_dry_run_done", count=len(previews))
        return {"sent": 0, "failed": 0, "previews": previews,
                "previews_count": len(previews)}

    try:
        smtp, limiter = smtp_send.open_session(creds)
    except smtp_send.SmtpError as e:
        _emit("send_error", reason=str(e))
        raise

    sent = 0
    failed = 0
    failures: List[Dict[str, str]] = []
    _emit("send_start", count=len(composed))
    try:
        for r in composed:
            limiter.wait()
            try:
                result = smtp_send.send_one(
                    smtp, creds,
                    to_addr=r["email"],
                    subject=r["subject"],
                    body=r["body"],
                    unsubscribe_base=unsubscribe_base,
                    reply_to=reply_to,
                )
                sent += 1
                _emit("send_ok", to=r["email"], login=r["login"],
                      message_id=result["message_id"], sent=sent,
                      target=len(composed))
            except Exception as e:
                failed += 1
                failures.append({"login": r["login"], "email": r["email"],
                                  "error": str(e)})
                _emit("send_fail", to=r["email"], login=r["login"],
                      error=str(e), failed=failed)
    finally:
        try:
            smtp.quit()
        except Exception:
            pass
    _emit("send_done", sent=sent, failed=failed)
    return {"sent": sent, "failed": failed, "failures": failures}


# --------------------------------------------------------------------------- #
# Top-level run                                                               #
# --------------------------------------------------------------------------- #


def cmd_run(args: argparse.Namespace) -> int:
    try:
        creds = load_creds()
    except CredsError as e:
        _emit("fatal", reason=str(e))
        return 2

    own_repo = _own_repo_full_name(args.project_url or "")

    analysis = step_analyse(creds, args.description, provider=args.provider)

    pitch = args.pitch or analysis.get("value_prop") or analysis.get("summary") or args.description[:200]

    repos = step_search(
        creds, analysis,
        min_stars=args.min_stars,
        repo_limit=args.repo_limit,
        own_repo=own_repo,
    )
    if not repos:
        _emit("fatal", reason="no similar repos found")
        return 2

    recipients = step_recipients(
        creds, repos, max_users=min(args.max_users, 10000),
    )
    if not recipients:
        _emit("fatal", reason="no recipients with public emails found")
        return 2

    composed = step_compose(
        creds, recipients,
        project_name=args.project_name,
        project_pitch=pitch,
        project_url=args.project_url or "",
        provider=args.provider,
        template_only=args.template_only,
    )

    result = step_send(
        creds, composed,
        unsubscribe_base=args.unsubscribe_base,
        dry_run=args.dry_run,
        reply_to=args.reply_to,
    )

    summary = {
        "project_name": args.project_name,
        "analysis": analysis,
        "repo_count": len(repos),
        "recipient_count": len(recipients),
        "send": result,
    }
    _emit("done", **summary)
    return 0 if result.get("failed", 0) == 0 else 1


def cmd_analyse(args: argparse.Namespace) -> int:
    try:
        creds = load_creds()
    except CredsError as e:
        _emit("fatal", reason=str(e))
        return 2
    analysis = step_analyse(creds, args.description, provider=args.provider)
    print(json.dumps(analysis, indent=2, ensure_ascii=False))
    return 0


def cmd_recipients(args: argparse.Namespace) -> int:
    try:
        creds = load_creds()
    except CredsError as e:
        _emit("fatal", reason=str(e))
        return 2
    analysis = step_analyse(creds, args.description, provider=args.provider)
    repos = step_search(
        creds, analysis,
        min_stars=args.min_stars,
        repo_limit=args.repo_limit,
        own_repo=_own_repo_full_name(args.project_url or ""),
    )
    recipients = step_recipients(creds, repos,
                                  max_users=min(args.max_users, 10000))
    print(json.dumps(recipients, indent=2, ensure_ascii=False))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="gitmail — outreach to stargazers of similar repos")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--description", required=True,
                         help="Free-text description of YOUR project.")
        sp.add_argument("--project-name", default="my-project")
        sp.add_argument("--project-url", default="")
        sp.add_argument("--pitch", default="",
                         help="One-sentence pitch (overrides LLM-derived value prop).")
        sp.add_argument("--provider", choices=["claude", "openai", "gemini"], default=None)
        sp.add_argument("--min-stars", type=int, default=200)
        sp.add_argument("--repo-limit", type=int, default=15)
        sp.add_argument("--max-users", type=int, default=100)

    run = sub.add_parser("run", help="Full pipeline.")
    add_common(run)
    run.add_argument("--dry-run", action="store_true",
                      help="Render previews instead of actually sending.")
    run.add_argument("--unsubscribe-base", default="http://localhost:8765",
                      help="Base URL for unsubscribe links.")
    run.add_argument("--reply-to", default=None)
    run.add_argument("--template-only", action="store_true",
                      help="Compose ONE email, reuse for all (cheaper).")

    an = sub.add_parser("analyse", help="Run the project-analysis step only.")
    an.add_argument("description")
    an.add_argument("--provider", choices=["claude", "openai", "gemini"], default=None)

    rec = sub.add_parser("recipients", help="Stop after collecting recipients.")
    add_common(rec)

    args = p.parse_args()
    if args.cmd == "run":
        return cmd_run(args)
    if args.cmd == "analyse":
        ns = argparse.Namespace(description=args.description, provider=args.provider)
        return cmd_analyse(ns)
    if args.cmd == "recipients":
        return cmd_recipients(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
