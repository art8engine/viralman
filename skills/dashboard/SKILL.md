---
name: dashboard
description: Start the local viralman dashboard (Flask app at http://localhost:8765 with three pages — twitter, reddit, gitmail) and open it in the user's browser. The dashboard owns OAuth login, post previews, and the gitmail pipeline.
level: 2
---

# Dashboard skill

The dashboard is the user's primary surface. It exposes everything viralman
can do without making them remember CLI flags. This skill exists so phrases
like "open the dashboard", "viralman 띄워줘", "run viralman" route to a
deterministic flow.

## Trigger phrases

Auto-trigger on:

- `/dashboard`
- "open the dashboard", "start the dashboard", "viralman dashboard"
- "viralman 켜줘", "viralman 띄워줘", "대시보드 열어줘"
- bare `viralman` in chat that clearly means "start the app", not the project

If the user typed `/dashboard`, follow `commands/dashboard.md` for argument
parsing.

## What it does

The dashboard runs a tiny Flask app at `http://localhost:8765` (default
port). Three pages, one shared dark header:

| Page | Purpose |
|---|---|
| `/twitter` | compose, preview (sniffer flags + char count + compose URL fallback), post |
| `/reddit`  | compose, subreddit + title + flair + body, preview, post |
| `/gitmail` | start outreach jobs with live progress + per-recipient preview |

Login is OAuth-first per platform with a manual-tokens fallback. The OAuth
flow ends at `/oauth/<platform>/callback` and saves tokens to
`~/.viralman/.env` via `save_creds.py`.

## Step 1 — Start the server

Run in the foreground:

```bash
viralman                            # if installed
./bin/viralman                      # from repo root
./scripts/dashboard.py              # equivalent
```

Default flags: `--host 127.0.0.1 --port 8765` and a browser tab is auto-opened.
Pass `--no-browser` if the user wants no auto-open.

If Flask is missing, the entry script prints a precise install hint — relay
it verbatim. Do NOT pip-install on the user's behalf without consent.

## Step 2 — Tell the user what's up

After starting:

```
viralman dashboard → http://localhost:8765
  twitter:  http://localhost:8765/twitter
  reddit:   http://localhost:8765/reddit
  gitmail:  http://localhost:8765/gitmail
Ctrl-C to stop.
```

A browser tab should open automatically. If the user is over SSH or has no
browser, surface the URLs and stop.

## Step 3 — Hands off

Once the dashboard is up, the agent's job is done. The user drives from the
browser. Do NOT shadow-post on their behalf, and do NOT call the post-API
endpoints from inside the chat — those are gated behind the dashboard's
explicit "post" buttons for a reason.

## Common issues

- **port already in use**: `viralman --port 8766` (or whatever).
- **OAuth login button does nothing**: the user hasn't registered the app's
  client_id + secret. Each platform's login pane shows the exact redirect URI
  to use (`http://localhost:8765/oauth/<platform>/callback`). Point them at
  the dev portal:
  - twitter:  https://developer.twitter.com/en/portal/dashboard
  - reddit:   https://www.reddit.com/prefs/apps   (must be "web app" type)
  - linkedin: https://www.linkedin.com/developers/apps
- **gitmail won't start**: missing creds. The skill `viralman-login-gitmail`
  walks the user through `GITHUB_TOKEN`, `SMTP_*`, and an LLM key.

## Boundaries

- The skill never reads `~/.viralman/.env`. Only `save_creds.py` /
  `creds.py` / `post_*.py` / `gitmail.py` do.
- The skill never starts the server with `--debug` unless the user asked —
  the reloader can race with the OAuth state in `session`.
- The skill never bypasses dry-run defaults on the gitmail page.
