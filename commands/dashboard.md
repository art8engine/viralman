---
description: Open the local viralman dashboard — three pages (Twitter / Reddit / Gitmail) sharing one project state, with a free-text "what to write" prompt driving per-platform AI drafts, unified top-right login, and a language switcher.
allowed-tools: Bash(./bin/viralman:*), Bash(./scripts/dashboard.py:*), Bash(viralman:*), Bash(open:*)
argument-hint: "[--port 8765] [--no-browser] [--host 127.0.0.1]"
---

# /dashboard — open the viralman dashboard

This launches the local web dashboard at `http://localhost:8765` and opens
the Twitter page. Header switches between **Twitter / Reddit / Gitmail**.

Each page runs the same flow:

1. **Project block** — name, URL, one-line pitch, description (shared across
   pages via `localStorage`).
2. **What to write** — free-text textarea. The user describes angle, tone,
   what to emphasize. No mode dropdown.
3. **Generate** — calls `/api/generate`, returns a platform-tuned draft.
4. **Edit + targets** — Twitter: hashtags. Reddit: subreddits + thread scan.
   Gitmail: max users / min stars / template flag.
5. **Post / send** — Gitmail has an explicit "I confirm" checkbox; Twitter
   and Reddit confirm via OS-level dialog.

Login lives in the header **Connect ▾** dropdown — OAuth for X / Reddit /
LinkedIn, manual tokens for Gitmail (SMTP + LLM). Language picker is left
of Connect (en / ko / zh / ja, persisted in localStorage).

## How to invoke

If the user installed the package, `viralman` is on PATH:

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
   `port=8765`, `host=127.0.0.1`, browser auto-opens to `/twitter`.
2. Start the server in the foreground so the user sees the request log.
3. Tell the user the URL, the three subpaths, and that Ctrl-C stops the server.
4. Do NOT post on the user's behalf from inside chat — the dashboard is
   the surface for that.

## Troubleshooting prompts

- "address already in use" → suggest `--port <next>` (e.g., 8766).
- "ModuleNotFoundError: flask" → `pip install --user flask`, or set up a venv
  per the install hint.
- OAuth login goes nowhere → the user hasn't saved a `CLIENT_ID` /
  `CLIENT_SECRET` for that platform. Point them at the Connect dropdown's
  "tokens" modal, which lists the exact fields.
- Connect counter stuck at 0/4 → no creds saved yet; route to the
  `/viralman-login-*` skills or the dropdown's per-row buttons.
- Generate returns a stub (not an LLM-written draft) → no Anthropic / OpenAI /
  Gemini key saved. Save one via the Gitmail "setup" modal or
  `/viralman-login-gitmail`.
