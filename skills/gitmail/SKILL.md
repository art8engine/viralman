---
name: gitmail
description: Drive the gitmail outreach flow — analyse the user's open-source project, find similar GitHub repos, collect stargazer emails, compose personalized notes via Claude/OpenAI/Gemini, and send via SMTP with rate limiting and a one-click unsubscribe footer.
level: 3
---

# gitmail Skill

The user has an open-source project they want more people to see. gitmail
finds developers who likely care (because they starred a similar project on
GitHub) and sends each of them a short, personalized email. This skill owns
the multi-step flow; the agent collects inputs, the script does the work.

## Trigger phrases

Auto-trigger on:

- `/gitmail`
- "gitmail this project", "gitmail outreach", "gitmail으로 메일 보내줘"
- "send a launch email to stargazers of similar repos", "find users who'd care
  about my project"

If the user typed `/gitmail`, follow `commands/gitmail.md` for argument
parsing first.

## Required inputs (gather before starting)

| Input | Required? | Notes |
|---|---|---|
| **description** | yes | 3–5 lines on the project. Anchors the LLM analysis. |
| **project_name** | yes | Used in subject lines and body. |
| **project_url** | recommended | Github URL of *your* project. Skips it from search; included in CTA. |
| **pitch** | optional | Overrides the LLM-derived value prop. |
| **max_users** | yes | 1–10000. Default 100. Above 500 takes a while. |
| **provider** | optional | claude / openai / gemini. Auto-detected from creds. |
| **dry_run** | default ON | Build previews without sending. Always default ON. |
| **template_only** | default OFF | Use one LLM-composed email for all (much cheaper). |

If anything is missing, ask once. Don't fabricate.

## Pre-flight

Before kicking off, verify `~/.viralman/.env` has:

- `GITHUB_TOKEN` — without it, the GitHub API caps at 60 req/h, which dies
  almost immediately at any real `max_users`.
- One of `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`.
- For non-dry-run: `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`.

The dashboard's /gitmail page shows status for all of these. If anything is
missing, route the user to the `viralman-login-gitmail` skill.

## Step 1 — Plan

Print one block summarising what you'll do:

- target N users
- expected ~M LLM calls (= 1 + N if not template-only, else 2)
- dry-run on/off
- provider in use
- rate limit (default 30/min for SMTP, 30/min for GitHub if token set)

Wait for the user to confirm.

## Step 2 — Run

Two paths:

### A. Dashboard (recommended)

If the dashboard is up, hand control to it:

```
Open http://localhost:8765/gitmail. Fill in the fields and click "start".
You'll see live progress and can preview each email before any are sent.
```

### B. CLI

If they want to run it without the dashboard:

```bash
./scripts/gitmail.py run \
  --description "$DESC" \
  --project-name "$NAME" \
  --project-url "$URL" \
  --max-users 100 \
  --provider claude \
  --dry-run
```

The script writes JSONL events — one event per pipeline transition. Surface
the meaningful ones to the user (analyse summary, repos found, recipient count,
sent/failed). Do NOT echo every event.

## Step 3 — After dry-run

If `dry_run` was on, the user has previews but nothing was sent. Their
options:

1. **looks good → send for real**: re-run without `--dry-run`, same args.
2. **tweak**: change description / max_users / provider, re-run dry.
3. **abort**: drop the campaign.

Always remind them that re-running without dry-run will *actually* email
strangers. This is a one-way action.

## Step 4 — After live send

Surface:

- sent count + failed count
- failure reasons grouped (auth fail, rate limit, bounced)
- where to read the unsubscribe log:
  `<repo>/.viralman_unsubscribes.jsonl`

## Boundaries

- **Never** raise `--max-users` above 10000 — the script rejects it, but
  don't even try.
- **Never** strip the unsubscribe footer or List-Unsubscribe header. If a
  user asks to remove either, refuse and explain that doing so is what
  separates outreach from spam under most jurisdictions' anti-spam laws.
- **Never** invent or guess email addresses. Only addresses returned by
  GitHub's user/events API are eligible.
- **Never** auto-retry a failed send. Failure goes to the user.
- **Never** read or echo `~/.viralman/.env` content beyond what
  `/api/creds/status` exposes (presence-only, no values).
- If the user asks to scrape commit emails from private repos or to bypass
  GitHub's rate limit through alternate accounts: refuse.
