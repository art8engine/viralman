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
  ./scripts/gitmail.py send-from-recipients \
      --recipients-file r.json --project-name X \
      --description "..." --project-url https://...

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
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent / "lib"))

from creds import load as load_creds, CredsError  # noqa: E402
import github_search  # noqa: E402
import llm_compose  # noqa: E402
import smtp_send  # noqa: E402
from unsubscribe import (  # noqa: E402
    load_unsubscribed_emails,
    record_token_email,
)


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


def _split_csv(value: Optional[str]) -> List[str]:
    """Comma-split a CLI string into a list, trimming empties."""
    if not value:
        return []
    return [p.strip() for p in value.split(",") if p.strip()]


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

    # Phase 1 — enumerate candidate stargazers across all repos (REST stargazers
    # endpoint, ~100 stargazers per request).
    #
    # Oversample 3x: GitHub's GraphQL budget is 5,000 points/hr, ~1 point per
    # user in a batched query. With 3x and max_users up to 1,500 we stay under
    # 4,500 points, leaving headroom for retries.
    target_candidates = max_users * 3
    seen: set[str] = set()
    candidates: List[tuple[str, str, str]] = []  # (login, html_url, source_repo)
    iters = [(r, github_search.iter_stargazers(r["full_name"],
                                                max_users=max_users * 5,
                                                token=token))
              for r in repos]
    while iters and len(candidates) < target_candidates:
        next_iters = []
        for repo, it in iters:
            try:
                user = next(it)
            except StopIteration:
                continue
            login = user["login"]
            if login not in seen:
                seen.add(login)
                candidates.append((login, user.get("html_url", ""),
                                    repo["full_name"]))
            next_iters.append((repo, it))
        iters = next_iters

    _emit("candidates_collected", count=len(candidates))

    cand_meta: Dict[str, tuple[str, str]] = {
        login: (html, repo_name) for login, html, repo_name in candidates
    }

    # Phase 2a — GraphQL bulk profile fetch. Uses the GraphQL budget bucket
    # (separate from REST), so it doesn't compete with PushEvent fallback below.
    profiles = github_search.bulk_resolve_profile_data(
        list(cand_meta.keys()), token=token, batch_size=100,
    )
    profile_hits = sum(1 for d in profiles.values() if d.get("email"))
    _emit("graphql_profiles_done",
          looked_up=len(profiles), email_found=profile_hits)

    out: List[Dict[str, str]] = []
    for login, data in profiles.items():
        if len(out) >= max_users:
            break
        email = data.get("email")
        if not email:
            continue
        html, repo_name = cand_meta[login]
        out.append({
            "login": login,
            "email": email,
            "starred_repo": repo_name,
            "profile": html,
        })
        _on_progress({"count": len(out), "target": max_users, "login": login})

    # Phase 2b — REST PushEvent mining for the remaining candidates. We pass
    # `pre_fetched_name` from GraphQL so resolve_user_email skips the redundant
    # /users/{login} GET and goes straight to /users/{login}/events/public —
    # halving REST cost per fallback candidate.
    if len(out) < max_users:
        fallback_logins = [login for login in cand_meta
                           if login not in {r["login"] for r in out}]

        def _events(login: str) -> tuple[str, Optional[str]]:
            name = (profiles.get(login) or {}).get("name")
            try:
                email = github_search.resolve_user_email(
                    login, token=token, use_events=True,
                    pre_fetched_name=name,
                )
            except Exception:
                email = None
            return (login, email)

        pool = ThreadPoolExecutor(max_workers=8)
        try:
            futures = [pool.submit(_events, login) for login in fallback_logins]
            for fut in as_completed(futures):
                login, email = fut.result()
                if not email:
                    continue
                html, repo_name = cand_meta[login]
                out.append({
                    "login": login,
                    "email": email,
                    "starred_repo": repo_name,
                    "profile": html,
                })
                _on_progress({"count": len(out), "target": max_users,
                              "login": login})
                if len(out) >= max_users:
                    break
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

    _emit("recipients_done", count=len(out))
    return out[:max_users]


class _SafeFormatDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def step_compose(
    creds: Dict[str, str],
    recipients: List[Dict[str, str]],
    *,
    project_name: str,
    project_pitch: str,
    project_url: str,
    provider: Optional[str],
    template_only: bool = False,
    tone: Optional[str] = None,
    emphasis: Optional[str] = None,
    subject_style: Optional[str] = None,
    prewritten_subject: Optional[str] = None,
    prewritten_body: Optional[str] = None,
) -> List[Dict[str, str]]:
    """Returns each recipient enriched with subject+body.

    If both prewritten_subject and prewritten_body are provided, skip the LLM
    entirely and per-recipient placeholder-substitute {login}, {starred_repo},
    {project_name}, {project_url}. This is the path for users who don't want
    to set an Anthropic/OpenAI API key.
    """
    if prewritten_subject is not None and prewritten_body is not None:
        _emit("compose_start", count=len(recipients), template_only=True,
              prewritten=True)
        out: List[Dict[str, str]] = []
        for i, r in enumerate(recipients):
            ctx = _SafeFormatDict(
                login=r["login"],
                starred_repo=r["starred_repo"],
                project_name=project_name,
                project_url=project_url,
            )
            subj = prewritten_subject.format_map(ctx)
            body = prewritten_body.format_map(ctx)
            out.append({**r, "subject": subj, "body": body})
            _emit("compose_progress", count=i + 1, target=len(recipients))
        _emit("compose_done", count=len(out))
        return out

    _emit("compose_start", count=len(recipients), template_only=template_only)
    out = []
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
                tone=tone,
                emphasis=emphasis,
                subject_style=subject_style,
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
    unsubbed = load_unsubscribed_emails()
    skipped = 0
    skips: List[Dict[str, str]] = []

    if dry_run:
        _emit("send_dry_run_start", count=len(composed))
        previews = []
        for r in composed:
            email = (r.get("email") or "").lower()
            if email and email in unsubbed:
                skipped += 1
                skips.append({"email": r["email"], "login": r.get("login", "")})
                _emit("send_skip", reason="unsubscribed", to=r["email"])
                continue
            preview = smtp_send.render_preview(
                creds,
                to_addr=r["email"],
                subject=r["subject"],
                body=r["body"],
                unsubscribe_base=unsubscribe_base,
                reply_to=reply_to,
            )
            tok = preview.get("unsubscribe_token")
            if tok:
                record_token_email(tok, r["email"])
            previews.append({**r, "preview_headers": preview["headers"]})
            _emit("send_preview", to=r["email"], subject=r["subject"])
        _emit("send_dry_run_done", count=len(previews), skipped=skipped)
        return {"sent": 0, "failed": 0, "skipped": skipped,
                "previews": previews, "previews_count": len(previews),
                "skips": skips}

    try:
        smtp, limiter = smtp_send.open_session(creds)
    except smtp_send.SmtpError as e:
        _emit("send_error", reason=str(e))
        raise

    sent = 0
    failed = 0
    unprocessed = 0
    failures: List[Dict[str, str]] = []
    # Provider-side errors that mean the session is dead or further attempts
    # will be rejected. When we see one, stop the loop instead of cascading
    # 'please run connect() first' into hundreds of false failures.
    abort_markers = (
        "connect() first",                   # smtplib on a closed session
        "Connection unexpectedly closed",    # mid-send disconnect
        "Daily user sending limit",          # Gmail global daily quota (5.4.5)
        "5.4.5",                              # Gmail rate-limit code (defensive)
    )
    _emit("send_start", count=len(composed))
    try:
        for i, r in enumerate(composed):
            email = (r.get("email") or "").lower()
            if email and email in unsubbed:
                skipped += 1
                skips.append({"email": r["email"], "login": r.get("login", "")})
                _emit("send_skip", reason="unsubscribed", to=r["email"])
                continue
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
                tok = result.get("unsubscribe_token")
                if tok:
                    record_token_email(tok, r["email"])
                _emit("send_ok", to=r["email"], login=r["login"],
                      message_id=result["message_id"], sent=sent,
                      target=len(composed))
            except Exception as e:
                msg = str(e)
                failed += 1
                failures.append({"login": r["login"], "email": r["email"],
                                  "error": msg})
                _emit("send_fail", to=r["email"], login=r["login"],
                      error=msg, failed=failed)
                if any(m in msg for m in abort_markers):
                    unprocessed = len(composed) - i - 1
                    _emit("send_aborted",
                          reason="smtp_unrecoverable",
                          processed=sent + failed,
                          total=len(composed),
                          unprocessed=unprocessed,
                          first_blocking_error=msg[:200])
                    break
    finally:
        try:
            smtp.quit()
        except Exception:
            pass
    _emit("send_done", sent=sent, failed=failed, skipped=skipped,
          unprocessed=unprocessed)
    return {"sent": sent, "failed": failed, "skipped": skipped,
            "unprocessed": unprocessed,
            "failures": failures, "skips": skips}


# --------------------------------------------------------------------------- #
# Recipients-collection helpers (shared by recipients + run)                  #
# --------------------------------------------------------------------------- #


def _collect_from_seed_repos(
    creds: Dict[str, str],
    seed_repos: List[str],
    *,
    max_users: int,
) -> List[Dict[str, str]]:
    """Skip search; treat the given repos as the seed list directly."""
    repos = [{"full_name": fn, "stars": 0} for fn in seed_repos]
    _emit("search_done", count=len(repos),
          repos=[{"full_name": r["full_name"], "stars": 0} for r in repos],
          source="seed_repos")
    return step_recipients(creds, repos, max_users=max_users)


def _resolve_targeting(
    creds: Dict[str, str],
    args: argparse.Namespace,
) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Run analyse + search with optional CLI overrides.

    Returns (analysis, repos).
    Honors --keywords/--topics overrides on top of analyse output.
    """
    description = getattr(args, "description", "") or ""
    if description.strip():
        analysis = step_analyse(creds, description, provider=args.provider)
    else:
        analysis = {"summary": "", "keywords": [], "topics": [],
                     "value_prop": "", "source": "override"}

    keywords_override = _split_csv(getattr(args, "keywords", None))
    topics_override = _split_csv(getattr(args, "topics", None))
    if keywords_override:
        analysis["keywords"] = keywords_override
    if topics_override:
        analysis["topics"] = topics_override

    repos = step_search(
        creds, analysis,
        min_stars=args.min_stars,
        repo_limit=args.repo_limit,
        own_repo=_own_repo_full_name(getattr(args, "project_url", "") or ""),
    )
    return analysis, repos


# --------------------------------------------------------------------------- #
# Top-level run                                                               #
# --------------------------------------------------------------------------- #


def cmd_run(args: argparse.Namespace) -> int:
    try:
        creds = load_creds()
    except CredsError as e:
        _emit("fatal", reason=str(e))
        return 2

    seed_repos = _split_csv(getattr(args, "seed_repos", None))
    max_users = min(args.max_users, 1500)

    if seed_repos:
        analysis: Dict[str, Any] = {"summary": "", "keywords": [],
                                      "topics": [], "value_prop": "",
                                      "source": "seed_repos"}
        if (args.description or "").strip():
            analysis = step_analyse(creds, args.description,
                                     provider=args.provider)
        recipients = _collect_from_seed_repos(creds, seed_repos,
                                                max_users=max_users)
        repos_count = len(seed_repos)
    else:
        analysis, repos = _resolve_targeting(creds, args)
        if not repos:
            _emit("fatal", reason="no similar repos found")
            return 2
        recipients = step_recipients(creds, repos, max_users=max_users)
        repos_count = len(repos)

    if not recipients:
        _emit("fatal", reason="no recipients with public emails found")
        return 2

    pitch = (args.pitch or analysis.get("value_prop")
             or analysis.get("summary") or (args.description or "")[:200])

    composed = step_compose(
        creds, recipients,
        project_name=args.project_name,
        project_pitch=pitch,
        project_url=args.project_url or "",
        provider=args.provider,
        template_only=args.template_only,
        tone=getattr(args, "tone", None),
        emphasis=getattr(args, "emphasis", None),
        subject_style=getattr(args, "subject_style", None),
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
        "repo_count": repos_count,
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

    seed_repos = _split_csv(getattr(args, "seed_repos", None))
    max_users = min(args.max_users, 1500)

    if seed_repos:
        recipients = _collect_from_seed_repos(creds, seed_repos,
                                                max_users=max_users)
    else:
        if not (args.description or "").strip():
            _emit("fatal",
                  reason="either --description or --seed-repos is required")
            return 2
        _, repos = _resolve_targeting(creds, args)
        if not repos:
            _emit("fatal", reason="no similar repos found")
            return 2
        recipients = step_recipients(creds, repos, max_users=max_users)

    print(json.dumps(recipients, indent=2, ensure_ascii=False))
    return 0


def _load_recipients_input(args: argparse.Namespace) -> List[Dict[str, str]]:
    """Load recipients JSON from --recipients-file or --recipients-stdin."""
    if getattr(args, "recipients_stdin", None):
        raw = sys.stdin.read()
    else:
        path = Path(args.recipients_file)
        raw = path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise SystemExit(f"recipients JSON parse error: {e}")
    if not isinstance(data, list):
        raise SystemExit("recipients JSON must be a list")
    return data


def cmd_send_from_recipients(args: argparse.Namespace) -> int:
    try:
        creds = load_creds()
    except CredsError as e:
        _emit("fatal", reason=str(e))
        return 2

    try:
        raw_recipients = _load_recipients_input(args)
    except SystemExit as e:
        _emit("fatal", reason=str(e))
        return 2

    recipients: List[Dict[str, str]] = []
    skipped: List[Dict[str, str]] = []
    for r in raw_recipients:
        if not isinstance(r, dict):
            continue
        login = (r.get("login") or "").strip()
        email = (r.get("email") or "").strip()
        starred_repo = (r.get("starred_repo") or "").strip()
        if not login or not email or not starred_repo:
            skipped.append({"login": login, "email": email,
                            "reason": "missing required field"})
            continue
        recipients.append({
            "login": login,
            "email": email,
            "starred_repo": starred_repo,
            "profile": r.get("profile", ""),
        })

    if skipped:
        _emit("recipients_skipped", count=len(skipped), entries=skipped)

    if not recipients:
        _emit("fatal", reason="no valid recipients in input")
        return 2

    _emit("recipients_loaded", count=len(recipients))

    pitch = args.pitch or (args.description or "")[:200]

    prewritten_subject = getattr(args, "prewritten_subject", None)
    prewritten_body_path = getattr(args, "prewritten_body", None)
    prewritten_body = None
    if prewritten_body_path:
        try:
            prewritten_body = Path(prewritten_body_path).read_text(encoding="utf-8")
        except OSError as e:
            _emit("fatal", reason=f"--prewritten-body read failed: {e}")
            return 2
    if (prewritten_subject is None) != (prewritten_body is None):
        _emit("fatal",
              reason="--prewritten-subject and --prewritten-body must be used together")
        return 2

    composed = step_compose(
        creds, recipients,
        project_name=args.project_name,
        project_pitch=pitch,
        project_url=args.project_url or "",
        provider=args.provider,
        template_only=args.template_only,
        tone=args.tone,
        emphasis=args.emphasis,
        subject_style=getattr(args, "subject_style", None),
        prewritten_subject=prewritten_subject,
        prewritten_body=prewritten_body,
    )

    result = step_send(
        creds, composed,
        unsubscribe_base=args.unsubscribe_base,
        dry_run=args.dry_run,
        reply_to=args.reply_to,
    )

    summary = {
        "project_name": args.project_name,
        "recipient_count": len(recipients),
        "send": result,
    }
    _emit("done", **summary)
    return 0 if result.get("failed", 0) == 0 else 1


def main() -> int:
    p = argparse.ArgumentParser(description="gitmail — outreach to stargazers of similar repos")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_targeting(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--keywords", default=None,
                         help="Comma-separated keywords. Overrides analyse output.")
        sp.add_argument("--topics", default=None,
                         help="Comma-separated topic slugs. Overrides analyse output.")
        sp.add_argument("--seed-repos", default=None,
                         help="Comma-separated owner/repo list. Skips search.")

    def add_compose_voice(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--tone", default=None,
                         help="Free-form tone hint (e.g. 'casual hype, short').")
        sp.add_argument("--emphasis", default=None,
                         help="Free-form emphasis points to lead with.")
        sp.add_argument("--subject-style",
                         choices=["auto", "headline", "tag", "simple"],
                         default="auto",
                         help="Subject pattern. auto=LLM picks; headline=greeting+benefit; "
                              "tag=[Label] product one-liner; simple=very short product intro.")

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
    add_targeting(run)
    add_compose_voice(run)
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
    # recipients allows --description OR --seed-repos. Don't make either required
    # at argparse level; cmd_recipients validates the combination.
    rec.add_argument("--description", default="",
                      help="Free-text description of YOUR project. Required unless "
                           "--seed-repos is given.")
    rec.add_argument("--project-name", default="my-project")
    rec.add_argument("--project-url", default="")
    rec.add_argument("--pitch", default="")
    rec.add_argument("--provider", choices=["claude", "openai", "gemini"], default=None)
    rec.add_argument("--min-stars", type=int, default=200)
    rec.add_argument("--repo-limit", type=int, default=15)
    rec.add_argument("--max-users", type=int, default=100)
    add_targeting(rec)

    sfr = sub.add_parser("send-from-recipients",
                          help="Compose+send for an already-collected recipients JSON.")
    sfr.add_argument("--recipients-file", default=None,
                      help="Path to recipients JSON. Use --recipients-stdin instead "
                           "to read from stdin.")
    sfr.add_argument("--recipients-stdin", action="store_true",
                      help="Read recipients JSON from stdin.")
    sfr.add_argument("--project-name", default="my-project")
    sfr.add_argument("--description", default="")
    sfr.add_argument("--project-url", default="")
    sfr.add_argument("--pitch", default="")
    sfr.add_argument("--provider", choices=["claude", "openai", "gemini"], default=None)
    add_compose_voice(sfr)
    sfr.add_argument("--dry-run", action="store_true")
    sfr.add_argument("--template-only", action="store_true")
    sfr.add_argument("--prewritten-subject", default=None,
                      help="Skip LLM compose: use this exact subject for every "
                           "recipient. Supports {login}, {starred_repo}, "
                           "{project_name}, {project_url} placeholders. "
                           "Requires --prewritten-body.")
    sfr.add_argument("--prewritten-body", default=None,
                      help="Skip LLM compose: path to a UTF-8 file whose "
                           "contents are used as the body for every recipient. "
                           "Same placeholders as --prewritten-subject.")
    sfr.add_argument("--unsubscribe-base", default="http://localhost:8765")
    sfr.add_argument("--reply-to", default=None)

    args = p.parse_args()
    if args.cmd == "run":
        return cmd_run(args)
    if args.cmd == "analyse":
        return cmd_analyse(args)
    if args.cmd == "recipients":
        return cmd_recipients(args)
    if args.cmd == "send-from-recipients":
        if not args.recipients_file and not args.recipients_stdin:
            _emit("fatal",
                  reason="either --recipients-file or --recipients-stdin is required")
            return 2
        return cmd_send_from_recipients(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
