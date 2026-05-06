---
name: dashboard
description: Start the local viralman dashboard at http://localhost:8765 — three pages (Twitter / Reddit / Gitmail) with header tab switching, a free-text "what to write" prompt that drives AI generation per platform, unified top-right login, and a language switcher.
level: 2
---

# Dashboard skill

The dashboard is **three separate pages** sharing one project state. Each
page runs the same flow: enter project info → say what to write → AI
generates a platform-tuned draft → tweak targets → send.

This skill exists so phrases like "open the dashboard", "viralman 띄워줘",
"run viralman" route to a deterministic flow.

## Trigger phrases

Auto-trigger on:

- `/dashboard`
- "open the dashboard", "start the dashboard", "viralman dashboard"
- "viralman 켜줘", "viralman 띄워줘", "대시보드 열어줘"
- bare `viralman` in chat that clearly means "start the app", not the project

**한국어**:
- "대시보드 띄워줘", "대시보드 켜줘", "대시보드 실행"
- "viralman 웹 UI 열어줘", "viralman 화면 띄워줘"
- "로컬 서버 켜줘", "viralman 서버 실행"

**English**:
- "open the dashboard", "launch viralman dashboard", "fire up the dashboard"
- "start the viralman web UI", "give me the viralman page"
- "boot viralman locally"

**中文**:
- "打开 viralman 面板", "启动 viralman 仪表盘"

**日本語**:
- "viralman の ダッシュボード を 開いて", "ダッシュボード を 起動"

If the user typed `/dashboard`, follow `commands/dashboard.md` for argument
parsing.

## What the pages are

| URL | Platform | What you can do |
|---|---|---|
| `/twitter` | X (Twitter) | tweet body + char count + sniffer flags + hashtag chips, post via API or compose-URL fallback |
| `/reddit` | Reddit | title + body, subreddit chips, scan recent threads to comment on, post via PRAW |
| `/gitmail` | Email outreach | email template (uses `{{login}}` and `{{starred_repo}}`), recipient slider, live progress + per-recipient preview |

Every page has the same top blocks:

1. **project** — name, GitHub URL, one-line pitch, multi-line description.
   Persists in `localStorage` so it carries across page tabs.
2. **what to write** — a free-text textarea where the user describes the
   angle, tone, what to emphasize. Replaces the old "mode" dropdown — the
   LLM gets the user's intent verbatim.
3. **provider** — auto / claude / openai / gemini.
4. **generate** — calls `/api/generate`, returns a platform-specific draft.

Header (shared across all 3 pages):

- Tabs on the left: **Twitter | Reddit | Gitmail** (active tab highlighted).
- Language picker mid-right: **EN / 한 / 中 / 日**, persists in `localStorage`,
  auto-detects `navigator.language` on first visit.
- **Connect 0/4 ▾** dropdown on the right — the single login surface.
  OAuth (X / Reddit / LinkedIn) plus manual tokens (Gitmail SMTP + LLM key)
  all live there.

## Step 0 — environment check (auto-recovery before anything else)

Before launching, verify viralman is installed and importable. Sequence:

1. Resolve the `viralman` binary using the priority order in `commands/dashboard.md` step 1.
2. If nothing is found, do NOT attempt to clone or pip-install yourself — invoke `/viralman-setup` instead. Its Step 0 detects the missing environment and runs the bootstrap (clone, venv, flask, shim) before asking about credentials. Idempotent.
3. After bootstrap (or if already present), confirm the binary's `--help` works without a `ModuleNotFoundError`. If flask is missing, run `<venv>/bin/pip install flask` and retry once. After that retry fails, surface the error.

Why two skills:
- `/dashboard` is "make the UI run for me, now". It must not become a heavy installer.
- `/viralman-setup` is the single entry point for "get viralman working" — its Step 0 owns clone, venv, and shim; later steps cover credentials.
- The dashboard skill *invokes* the setup skill on cache miss. The user shouldn't need to know the difference.

## Step 1 — Start the server

```bash
viralman                            # if installed
./bin/viralman                      # from repo root
./scripts/dashboard.py              # equivalent
```

Default flags: `--host 127.0.0.1 --port 8765`, browser auto-opens to
`/twitter`. Pass `--no-browser` if no auto-open is wanted.

If Flask is missing, the entry script prints a precise install hint — relay
it verbatim. Do NOT pip-install on the user's behalf without consent.

## Step 2 — Tell the user what's up

```
viralman dashboard → http://localhost:8765
  twitter:  http://localhost:8765/twitter
  reddit:   http://localhost:8765/reddit
  gitmail:  http://localhost:8765/gitmail
Ctrl-C to stop.
```

Say the language switcher and Connect dropdown are both top-right.

## Step 3 — Hands off

The user drives from the browser. Don't shadow-post on their behalf, and
don't call the post-API endpoints from inside chat — those are gated
behind the dashboard's explicit "post" / "send" buttons for a reason.

## Common issues

- **Port already in use**: `viralman --port 8766` (or whatever).
- **Connect counter stuck at 0/4**: no creds saved yet. Point the user at
  the per-row "tokens" / "setup" buttons in the dropdown, or at the
  `/viralman-login-{reddit,twitter,linkedin,gitmail}` skills.
- **OAuth login button does nothing**: the platform's `CLIENT_ID` /
  `CLIENT_SECRET` aren't saved. Each Connect dropdown row's "tokens" modal
  lists exactly what to register.
- **Generate fails with "No LLM provider configured"**: no Anthropic /
  OpenAI / Gemini key saved yet. Route to `/viralman-login-gitmail`, or have
  the user save one via the Gitmail row in the Connect dropdown.
- **gitmail won't actually send**: SMTP creds not configured. Same modal
  covers SMTP fields.
- **Project disappears between page tabs**: `localStorage` was cleared, or a
  different browser/profile is in use. Just retype.

## Boundaries

- The skill never reads `~/.viralman/.env`. Only `save_creds.py` /
  `creds.py` / `post_*.py` / `gitmail.py` do.
- The skill never starts the server with `--debug` unless the user asked —
  the reloader can race with the OAuth state in `session`.
- The skill never bypasses the "I confirm" checkbox on the Gitmail page.
