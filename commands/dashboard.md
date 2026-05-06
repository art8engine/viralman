---
description: Open the local viralman dashboard — three pages (Twitter / Reddit / Gitmail) sharing one project state, with a free-text "what to write" prompt driving per-platform AI drafts, unified top-right login, and a language switcher.
allowed-tools: Bash(./bin/viralman:*), Bash(./scripts/dashboard.py:*), Bash(viralman:*), Bash(open:*), Bash(which:*), Bash(test:*), Bash(git rev-parse:*), Bash(ls:*), Bash(./.venv/bin/pip:*)
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

1. **Resolve the binary** — try in this order:
   a. `which viralman 2>/dev/null` — if it exists, use that.
   b. `test -x ~/.local/bin/viralman` — if so, use that.
   c. Find the repo root via `git rev-parse --show-toplevel` (must be a viralman repo — confirm by checking `.claude-plugin/marketplace.json` for `name: viralman`). If found and `<root>/.venv/bin/python` exists, use `<root>/.venv/bin/python <root>/bin/viralman`.
   d. Else: `~/.claude/plugins/cache/*/viralman/*/.venv/bin/python` — pick the latest.
   e. **Nothing found** — surface this:
      ```
      viralman is not installed yet. I can run `/viralman-setup` to bootstrap
      it — its Step 0 detects this and handles clone, venv, flask, and the
      shim before asking about credentials. Should I?
      ```
      If the user says yes, invoke `/viralman-setup` first (its Step 0 covers
      bootstrap), then come back to step 1.

2. **Pre-flight checks** (only after binary is found):
   - Do `<binary> --help 2>&1 | head -1` and look for `usage:` text. If that fails with `ModuleNotFoundError: No module named 'flask'`, run `<venv>/bin/pip install flask` automatically (no prompt — flask is already declared in pyproject.toml as a runtime dep, so we treat its absence as a recoverable bug).
   - If `--port` clashes (`OSError: [Errno 48] Address already in use`), suggest the user pass `--port 8766` or higher and stop. Don't auto-pick a free port — the user might already have something on 8765.

3. **Parse `$ARGUMENTS`** for `--port`, `--host`, `--no-browser`. Defaults: `port=8765`, `host=127.0.0.1`, browser auto-opens to `/twitter`.

4. **Start the server** in the foreground so the user sees the request log. Tell them:
   - The URL (`http://<host>:<port>/twitter`).
   - The three subpaths (`/twitter`, `/reddit`, `/gitmail`, plus `/setup`).
   - That Ctrl-C stops the server.

5. **Do NOT post on the user's behalf from inside chat** — the dashboard is the surface for that.

## Troubleshooting prompts (auto-recovery branches)

- `command not found: viralman` → step 1.e (offer `/viralman-setup` — its Step 0 bootstraps).
- `ModuleNotFoundError: flask` → run `<venv>/bin/pip install flask`, retry once.
- `address already in use` → tell the user `--port 8766`. Don't auto-pick.
- OAuth login goes nowhere → no `CLIENT_ID` / `CLIENT_SECRET` saved. Route them to `/viralman-setup` (recommended) or the dropdown's "tokens" modal.
- Connect counter stuck at 0/4 → no creds. Same: `/viralman-setup`.
- Generate returns a stub (not LLM-written) → no API key saved. `/viralman-setup` → category `gitmail` step 3 (LLM key) — or set up Claude Max via `which claude && claude --version` (skill auto-detects).
