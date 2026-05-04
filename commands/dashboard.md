---
description: Open the local viralman dashboard (twitter / reddit / gitmail) in the browser.
allowed-tools: Bash(./bin/viralman:*), Bash(./scripts/dashboard.py:*), Bash(viralman:*), Bash(open:*)
argument-hint: "[--port 8765] [--no-browser] [--host 127.0.0.1]"
---

# /dashboard — open the viralman dashboard

This launches the local web dashboard at http://localhost:8765 with three
pages:

- **/twitter** — preview + post a tweet or thread under your X account
- **/reddit**  — preview + post under your reddit account (subreddit, title, flair)
- **/gitmail** — drive the gitmail outreach pipeline (find similar repos →
  collect stargazer emails → compose → send), with live progress + per-recipient
  preview

Login per platform is OAuth-first with a manual-tokens fallback.

## How to invoke

If the user has installed the package, the literal command `viralman` already
exists on their PATH:

```bash
viralman                    # default: http://localhost:8765, opens browser
viralman --port 9000
viralman --no-browser
```

Otherwise, run from the repo root:

```bash
./bin/viralman              # same flags
./scripts/dashboard.py      # alternate entry, identical behavior
```

If the user has not installed Flask yet, the entry script prints a short
install hint — relay that exactly. Do NOT try to pip-install for them inside
the agent context unless they explicitly ask.

## What you do when invoked

1. Parse `$ARGUMENTS` for `--port`, `--host`, `--no-browser`. Defaults are
   `port=8765`, `host=127.0.0.1`, browser auto-opens.
2. Start the server in the foreground so the user sees the request log.
3. Tell the user what URL to visit, and that Ctrl-C stops the server.
4. Do NOT post on the user's behalf from inside the chat — the dashboard is
   the surface for that. The agent's job is to start the server, not act as
   the user.

## Troubleshooting prompts

- "address already in use" → suggest `--port <next>` (e.g., 8766).
- "ModuleNotFoundError: flask" → `pip install --user flask`, or set up a venv
  per the install hint.
- OAuth login redirect goes nowhere → the user hasn't registered an app for
  that platform yet. Point them at the platform's login pane in the dashboard;
  it shows the exact redirect URI to register.
