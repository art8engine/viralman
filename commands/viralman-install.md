---
description: (Internal helper — `/viralman-setup` is the recommended entry point and invokes this on cache miss.) Bootstrap viralman: find or clone the repo, create .venv, install flask + viralman, drop a `viralman` shim on PATH, verify. Idempotent.
allowed-tools: Read, Bash(git clone:*), Bash(git pull:*), Bash(git rev-parse:*), Bash(python3:*), Bash(./scripts/save_creds.py:*), Bash(test:*), Bash(mkdir:*), Bash(chmod:*), Bash(which:*), Bash(ls:*), Bash(cat:*), Bash(cd:*)
argument-hint: "[--path /custom/install/path] [--no-shim] [--reinstall]"
---

# /viralman-install — bootstrap viralman so the agent can run everything

This command makes everything else (`/dashboard`, `/gitmail`, `/viralman-setup`, …) "just work".
It is idempotent — running it twice is safe and only fixes what's actually missing.

## Arguments

- `--path /custom/path` — install location. Default heuristic:
  1. If we're already inside a viralman git repo (`.claude-plugin/marketplace.json` exists at the repo root and the package name matches), use that.
  2. Else if `~/.claude/plugins/cache/*/viralman/*/` exists, use the latest version directory there (Claude Code plugin path).
  3. Else clone into `$HOME/viralman` (creating that directory if needed).
- `--no-shim` — skip the `~/.local/bin/viralman` shim. PATH stays clean; user calls `<path>/.venv/bin/viralman` explicitly.
- `--reinstall` — wipe and recreate `.venv` even if it already exists.

## Step 1 — detect or clone the repo

Resolve `REPO` using this priority order:

1. Run `git rev-parse --show-toplevel 2>/dev/null` from CWD. If it returns a path **and** that path contains `.claude-plugin/marketplace.json` with `name: viralman`, set `REPO=<that path>`.
2. Else check `ls ~/.claude/plugins/cache/*/viralman/` (glob). If one or more version directories exist, pick the one with the highest version string: `REPO=~/.claude/plugins/cache/<owner>/viralman/<latest>`.
3. Else use `--path` value if provided; otherwise use `~/viralman`.
   - If that path doesn't exist: `git clone https://github.com/art8engine/viralman <path>`. If `git clone` fails (network, auth), surface the error verbatim and stop.
   - If the path exists and is a git repo: `git pull --ff-only` to update. If this fails, continue with what's there (best-effort).

Print: `REPO resolved to: <absolute path>`.

## Step 2 — create or verify the venv

```bash
python3 --version
```

Confirm the output is Python 3.10 or higher. If not, surface:
> Python 3.10+ required. Found: <version>. Install a newer Python and re-run.
Then stop.

- If `.venv/bin/python` doesn't exist inside `$REPO` **or** `--reinstall` was given:
  ```bash
  python3 -m venv "$REPO/.venv"
  ```
- Otherwise skip venv creation and print: `venv already exists — skipping (use --reinstall to recreate)`.

## Step 3 — install dependencies

```bash
"$REPO/.venv/bin/pip" install --upgrade pip --quiet
"$REPO/.venv/bin/pip" install flask
```

If the Python version is **less than 3.14**:
```bash
"$REPO/.venv/bin/pip" install -e "$REPO"
```

If the Python version is **3.14 or higher**: skip the editable install and print:
> Python 3.14 detected — skipping editable install (setuptools .pth execution is disabled on 3.14). The shim in the next step handles dispatch directly.

Never install packages globally. Every `pip` call must target `$REPO/.venv/bin/pip`.

## Step 4 — install the shim (unless `--no-shim`)

1. Ensure `~/.local/bin` exists:
   ```bash
   mkdir -p ~/.local/bin
   ```
2. Write `~/.local/bin/viralman` with this exact content (replace `<REPO>` with the absolute path):
   ```bash
   #!/usr/bin/env bash
   exec "<REPO>/.venv/bin/python" "<REPO>/bin/viralman" "$@"
   ```
3. Make it executable:
   ```bash
   chmod +x ~/.local/bin/viralman
   ```
4. Check whether `~/.local/bin` is on `$PATH`:
   ```bash
   echo "$PATH" | tr ':' '\n' | grep -qx "$HOME/.local/bin"
   ```
   If it is **not** on PATH, print exactly this (do not modify any rc file):
   > `~/.local/bin` is not on your PATH. Add this line to your shell rc (`~/.zshrc`, `~/.bashrc`, etc.):
   > ```
   > export PATH="$HOME/.local/bin:$PATH"
   > ```
   > Then run `source ~/.zshrc` (or restart your terminal) for the shim to work in new shells.

## Step 5 — verify

Start the dashboard in the background and probe it:

```bash
~/.local/bin/viralman --no-browser --port 8765 &
VIRALMAN_PID=$!
sleep 2
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8765/twitter)
kill $VIRALMAN_PID 2>/dev/null
wait $VIRALMAN_PID 2>/dev/null
```

- If `HTTP_STATUS` is `200`: print success summary:
  > viralman bootstrap OK — REPO=`<path>`, python=`<version>`, flask=`<flask version from pip show flask>`
- If not `200`: surface the actual curl error/response body and stop:
  > Dashboard did not respond (HTTP <status>). Check the error above. Re-run after fixing the issue.
  Kill the background process before exiting.

## Step 6 — next step suggestions

- Run `./scripts/save_creds.py --show-keys` (from `$REPO`). If it returns no keys or the file `~/.viralman/.env` does not exist:
  > No credentials found — run `/viralman-setup` to configure your first channel.
- If keys exist:
  > viralman is ready. Try `/gitmail` to send a launch email, or `/dashboard` to open the web UI.

## Boundaries

- **Never** clone outside `$HOME` without an explicit `--path`.
- **Never** use `sudo`. If an operation requires elevated privileges, fail loudly:
  > This step requires permissions viralman should not need. Do not run with sudo — check directory ownership instead.
- **Never** modify shell rc files (`~/.zshrc`, `~/.bashrc`, etc.). Only print the line the user should add.
- **Never** install packages outside the venv.
- If `git clone` fails, surface the error verbatim and stop. Do not attempt a fallback download.
- If the verify step fails to reach the dashboard, kill the background process and show the actual error output before stopping.
