---
description: Open the local viralman dashboard — a single-page 4-step wizard (project → generate → targets → send) with unified top-right login and a language switcher.
allowed-tools: Bash(./bin/viralman:*), Bash(./scripts/dashboard.py:*), Bash(viralman:*), Bash(open:*)
argument-hint: "[--port 8765] [--no-browser] [--host 127.0.0.1]"
---

# /dashboard — open the viralman dashboard

This launches the local web dashboard at `http://localhost:8765`.

The page is a single 4-step wizard:

1. **Project** — name, URL, one-line pitch, description.
2. **Generate** — pick channels (X / Reddit / Gitmail), provider, voice mode, get drafts.
3. **Targets** — hashtags, subreddits, comment threads to reply to, gitmail recipient count.
4. **Send** — dry-run toggle, explicit confirm checkbox, live progress per channel.

Login lives in the header **Connect ▾** dropdown — OAuth for X / Reddit /
LinkedIn, manual tokens for Gitmail (SMTP + LLM). Language picker is to its
left (en / ko / zh / ja, persisted in localStorage).

## How to invoke

If the user has installed the package, `viralman` is on PATH:

```bash
viralman                    # default: http://localhost:8765, opens browser
viralman --port 9000
viralman --no-browser
```

Otherwise run from the repo root:

```bash
./bin/viralman              # same flags
./scripts/dashboard.py      # alternate entry
```

If Flask is missing, the entry script prints a short install hint — relay
that exactly. Do not pip-install on the user's behalf without consent.

## What you do when invoked

1. Parse `$ARGUMENTS` for `--port`, `--host`, `--no-browser`. Defaults are
   `port=8765`, `host=127.0.0.1`, browser auto-opens.
2. Start the server in the foreground so the user sees the request log.
3. Tell the user the URL and that Ctrl-C stops the server.
4. Do NOT post on the user's behalf from inside chat — the dashboard is
   the surface for that.

## Troubleshooting prompts

- "address already in use" → suggest `--port <next>` (e.g., 8766).
- "ModuleNotFoundError: flask" → `pip install --user flask`, or set up a venv
  per the install hint.
- OAuth login redirect goes nowhere → user hasn't registered an app's
  client_id/secret yet. Point them at the Connect dropdown's "tokens"
  modal, which lists the exact fields to fill in.
- Connect counter stuck at 0/4 → no creds saved yet; route to the
  `/viralman-login-*` skills or the "tokens" / "setup" buttons in the
  dropdown.
