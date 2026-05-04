---
name: dashboard
description: Start the local viralman dashboard — a single-page 4-step wizard (project → generate → targets → send) at http://localhost:8765, with unified top-right login and a language switcher (en / ko / zh / ja).
level: 2
---

# Dashboard skill

The dashboard is one page, four steps. It replaces the old per-platform tabs.
This skill exists so phrases like "open the dashboard", "viralman 띄워줘",
"run viralman" route to a deterministic flow.

## Trigger phrases

Auto-trigger on:

- `/dashboard`
- "open the dashboard", "start the dashboard", "viralman dashboard"
- "viralman 켜줘", "viralman 띄워줘", "대시보드 열어줘"
- bare `viralman` in chat that clearly means "start the app", not the project

If the user typed `/dashboard`, follow `commands/dashboard.md` for argument
parsing.

## What the page is

One URL (`/`), four sections gated step by step:

| # | Step | What |
|---|---|---|
| 1 | Project | name, GitHub URL, one-line pitch, description |
| 2 | Generate | pick channels (X / Reddit / Gitmail), pick LLM provider + voice mode, generate drafts |
| 3 | Targets | hashtags, subreddits, scrapeable comment threads, recipient count for gitmail |
| 4 | Send | dry-run toggle + explicit confirm checkbox + live progress per channel |

A few things to know:

- The header shows a **Connect 0/4 ▾** dropdown on the right. That's the
  single login surface. OAuth (X / Reddit / LinkedIn) and manual tokens
  (Gitmail SMTP+LLM) all live in there.
- A small **EN / 한 / 中 / 日** picker is to the left of Connect. Persists
  in `localStorage`. Auto-detects from `navigator.language` on first visit.
- Step 4 won't enable the Send button until the user checks the explicit
  "I confirm I want to send under my accounts" box.

## Step 1 — Start the server

```bash
viralman                            # if installed
./bin/viralman                      # from repo root
./scripts/dashboard.py              # equivalent
```

Default flags: `--host 127.0.0.1 --port 8765`, browser auto-opens. Pass
`--no-browser` if no auto-open is wanted.

If Flask is missing, the entry script prints a precise install hint — relay
it verbatim. Do NOT pip-install on the user's behalf without consent.

## Step 2 — Tell the user what's up

```
viralman dashboard → http://localhost:8765
  (single-page wizard, header switches language; "Connect ▾" is your login)
Ctrl-C to stop.
```

If the user is over SSH or has no browser, surface the URL and stop.

## Step 3 — Hands off

The user drives from the browser. Do not shadow-post on their behalf, and
do not call the post-API endpoints from inside chat — those are gated
behind the dashboard's explicit "send" button for a reason.

## Common issues

- **Port already in use**: `viralman --port 8766` (or whatever).
- **Connect dropdown shows 0/4**: the user hasn't saved any creds yet.
  Point them at `/viralman-login-{reddit,twitter,linkedin,gitmail}` skills,
  or have them use the per-row "tokens" / "setup" buttons in the dropdown.
- **OAuth login button does nothing**: the platform's `CLIENT_ID` /
  `CLIENT_SECRET` aren't saved yet. Each Connect dropdown row's "tokens"
  modal lists exactly what to register.
- **gitmail won't start**: missing creds. The skill `viralman-login-gitmail`
  walks the user through `GITHUB_TOKEN`, `SMTP_*`, and one LLM key.
- **Language picker doesn't change strings**: hard-refresh; an old
  service-worker-cached page can hold stale templates.

## Boundaries

- The skill never reads `~/.viralman/.env`. Only `save_creds.py` /
  `creds.py` / `post_*.py` / `gitmail.py` do.
- The skill never starts the server with `--debug` unless the user asked —
  the reloader can race with the OAuth state in `session`.
- The skill never bypasses dry-run defaults on the gitmail send.
