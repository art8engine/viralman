---
name: gitmail
description: Drive the gitmail outreach flow that sends personalized cold emails to GitHub stargazers of similar repos. Batches the user's four upfront decisions (language / subject style / targeting strategy / recipient count) into a single AskUserQuestion call before any heavy work runs, finds similar repos and collects recipient emails, renders a fast single-LLM-call dry-run preview of the email body, and gates live SMTP send strictly behind an explicit user confirmation.
level: 3
---

# gitmail Skill

Goal: when the user types `/gitmail <project>`, Claude analyzes the project, asks four upfront decisions in one batch, renders a fast single-LLM-call body preview, and only sends for real after the user has explicitly said "send" / "발송해줘".

## Trigger phrases

Auto-trigger on:

- `/gitmail`
- "gitmail", "gitmail 해줘", "gitmail 보내줘", "gitmail outreach"
- "gitmail this project", "gitmail으로 메일 보내줘", "gitmail로 홍보해줘"

**Korean**: "이 프로젝트 홍보메일 보내줘", "GitHub 스타거에게 메일", "비슷한 레포 사용자한테 메일", "이거 메일로 알려줘", "asyncprofiler 별표한 사람한테 보내줘"

**English**: "email people who starred similar repos", "send a launch outreach to <repo> stargazers", "promote my project via cold email"

**Chinese**: "给类似仓库的 stargazer 发邮件", "推广我的项目 邮件"

**Japanese**: "似たリポジトリのスターガザーにメール", "プロジェクトを紹介するメール"

When the user enters via `/gitmail`, the argument parsing in `commands/gitmail.md` runs first.

## Pre-flight

Run `./scripts/save_creds.py --show-keys` and confirm (never print the values):

- `GITHUB_TOKEN` — without it, GitHub API caps at 60 req/h.
- one of `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GEMINI_API_KEY`, **or** detect Claude Code CLI via `which claude`.
- For real send only: `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`.

If anything is missing, route the user to `/viralman-setup gitmail` and stop. Never read or print `.env` values.

---

## Step 1 — Project analysis (Claude direct, before any gitmail.py call)

Extract a GitHub URL or free-text description from `$ARGUMENTS`.

- First token starts with `https://github.com/` → treat as URL. Do **not** call `gh repo view` or fetch the README (saves rate budget + responds faster).
- If a free-text description is also present, use it as the description.
- If both are missing, ask once and wait for the answer. Do not guess.

When a URL is given, derive a first-pass keyword from the owner/repo slug (e.g. `rlaope/Argus` → "Argus"). If the user provided extra description, prefer that.

The analysis output is short (2–3 lines), printed to the user before the batch question so they have context for their answer:

```
Project: Argus (https://github.com/rlaope/Argus)
What I understood: <one-line summary — based on user description + URL slug>
If this is right, please answer the questions below. If wrong, correct me
and I'll redo it.
```

---

## Step 2 — Batch question (AskUserQuestion, exactly once, before any gitmail.py call)

**Critical: do not run `gitmail.py recipients` or `send-from-recipients` until the batch question is answered.** Letting the user decide upfront is the core of this skill.

Use the `AskUserQuestion` tool to surface all four questions in one call (multiSelect=false on every one):

### Q1 — Language

| option | description |
|---|---|
| Korean (default) | Default. Korean developers as the audience. |
| English | English mail. For global outreach. |
| Chinese | Chinese mail. |
| Japanese | Japanese mail. |

The selected value becomes a prefix to `--tone` (e.g. English → `--tone "in English, ..."`). For Korean, the prefix is omitted.

### Q2 — Subject style (5-way choice, with previews)

| key | pattern | example (Argus, English) |
|---|---|---|
| `auto` | LLM picks freely. Subject varies per recipient. | (LLM-decided) |
| `headline` | "Hi, now you can easily &lt;benefit&gt; too." | Hi, now you can easily watch your JVM in production too. |
| `tag` | `[Label] product — one-line value` | [New Tool] Argus — JVM monitoring without the heavy agent. |
| `simple` | Under 30 chars, no marketing tone | Argus — JVM monitoring |
| `manual` (직접 입력하기) | User provides the exact subject AND body. Skips the LLM entirely — placeholders `{login}`, `{starred_repo}`, `{project_name}`, `{project_url}` substitute per recipient. | (waiting for your input) |

Pass each option's example text into the `preview` field of `AskUserQuestion` so the user can compare side-by-side. The `manual` option must be placed **last** so the LLM-driven choices stay grouped.

**If the user picks `manual`**, do NOT proceed to Step 3 yet. Ask one follow-up prompt that requests:
1. the subject line (free text, may use the placeholders above),
2. the email body (free text; multi-line OK; may use the same placeholders).

Save the body to `/tmp/gitmail_user_body.txt`. In Step 4 / Step 5, replace `--template-only` with `--prewritten-subject "<subject>" --prewritten-body /tmp/gitmail_user_body.txt`. Keep `--dry-run` for Step 4 so the user still sees a literal preview before live send.

### Q3 — Targeting strategy

| option | behavior |
|---|---|
| Recommended seeds (Claude picks) | Claude proposes 3–5 domain-specific repos based on the Step 1 analysis. Highest accuracy. |
| Keyword search | The user types keywords directly. Maximum flexibility. |
| Auto (LLM extracts) | gitmail.py's `analyse` step decides on its own. Fast but average accuracy. |

For "Recommended seeds" — Claude shows the chosen seed repos explicitly (e.g. "for JVM monitoring I'll go with jvm-profiling-tools/async-profiler, glowroot/glowroot, pinpoint-apm/pinpoint, prometheus/jmx_exporter"). Honor any pushback from the user; otherwise proceed.

### Q4 — Recipient count (max-users)

| option | description |
|---|---|
| 100 (recommended for first try) | First send. Safe on free Gmail / Workspace / any SMTP. |
| 500 | **Exactly the free @gmail.com daily ceiling** (500 msg / 24h rolling). The largest single-batch send. |
| 1000 | Workspace recommended (within 2,000/24h). On free Gmail this needs a 2-day split. |
| 1500 | GitHub collection cap (GraphQL+REST dual bucket). Free Gmail = 3-day split, Workspace = single day. |
| Other | User-supplied (1–1500). Above 1500 will stall on GitHub rate limit. |

> **Two caps, separate concerns**:
> - **Collection cap = 1,500 / run** — GitHub API budgets (GraphQL 5,000 pt/hr + REST 5,000 req/hr).
> - **Send cap = SMTP policy** — free @gmail.com is **500 msg / rolling 24h**, Google Workspace is **2,000 msg / 24h** per user.
>
> Even after collecting 1,500, free Gmail can only deliver 500 in a day. When the SMTP daily limit is hit, `step_send` aborts cleanly, emits `send_aborted` plus a Korean stderr line, and counts the remainder as `unprocessed` (retry after the rolling 24h reset).

---

## Step 3 — Recipient collection (collect phase)

After all four answers are in, run once:

```bash
.venv/bin/python ./scripts/gitmail.py recipients \
  --description "$DESC" \
  --project-url "$URL" \
  --max-users $MAX \
  [--seed-repos "$SEEDS"]      # Q3=recommended seeds OR keywords
  [--keywords "$KW"]            # Q3=keywords only
  > /tmp/gitmail_recipients.json 2>&1
```

> stdout is a JSONL event stream followed by a final recipients array. Cut everything from the first line that begins with `^\[` and save as `recipients_clean.json` so the next step can read it directly.

When done, summarize **briefly** for the user (preview up to 8):

```
Collected N recipients.
1. @asyncuser — alice@example.com (async-profiler ★)
2. @graalfan — bob@example.com (graalvm ★)
... (up to 8)

Generate a body preview with this list? (yes / adjust count / cancel)
```

---

## Step 4 — Fast dry-run preview (template-only, 1 LLM call)

**Critical: combine `--template-only --dry-run` so only one LLM call composes the body, then it's reused for all N recipients in the preview.** Cuts a 50-recipient dry-run from 13 minutes down to ~16 seconds.

```bash
.venv/bin/python ./scripts/gitmail.py send-from-recipients \
  --recipients-file /tmp/gitmail_recipients_clean.json \
  --project-name "$NAME" \
  --description "$DESC" \
  --project-url "$URL" \
  --tone "$LANG_PREFIX$TONE" \
  --emphasis "$EMPHASIS" \
  --subject-style "$STYLE" \
  --template-only --dry-run \
  > /tmp/gitmail_dryrun.json 2>&1
```

**Manual path (Q2 = `manual` / 직접 입력하기)** — skip the LLM entirely:

```bash
.venv/bin/python ./scripts/gitmail.py send-from-recipients \
  --recipients-file /tmp/gitmail_recipients_clean.json \
  --project-name "$NAME" \
  --description "$DESC" \
  --project-url "$URL" \
  --prewritten-subject "$USER_SUBJECT" \
  --prewritten-body /tmp/gitmail_user_body.txt \
  --dry-run \
  > /tmp/gitmail_dryrun.json 2>&1
```

Pull the first body from the `compose_done` event and show it:

```
[Preview] First mail
TO: <first recipient email>
SUBJECT: <subject>
---
<body>
---

Reply with one of:
  • "발송해줘" / "send" / "go" → send for real to all 50 (template_only fast path)
  • feedback (e.g. "make it shorter", "change the tone", "more direct subject") → regenerate
  • "cancel" → stop
```

Showing the body counts as composition agreement, NOT send agreement. **Body agreement ≠ send agreement (본문 합의 ≠ 발송 합의)** — until the user explicitly says "발송해줘" / "send" / "go", do not call the real-send command.

---

## Step 5 — Real send (only after explicit user OK)

Run only when the user has explicitly signaled intent to send:

```bash
.venv/bin/python ./scripts/gitmail.py send-from-recipients \
  --recipients-file /tmp/gitmail_recipients_clean.json \
  --project-name "$NAME" \
  --description "$DESC" \
  --project-url "$URL" \
  --tone "$LANG_PREFIX$TONE" \
  --emphasis "$EMPHASIS" \
  --subject-style "$STYLE" \
  --template-only \
  > /tmp/gitmail_send.json 2>&1
```

Keep `--template-only` — the body is the one the user already approved, so regenerating costs nothing useful. Calling the LLM 50 more times is wasted budget and time.

**Manual path (Q2 = `manual` / 직접 입력하기)** — same as Step 4 minus `--dry-run`, no LLM call:

```bash
.venv/bin/python ./scripts/gitmail.py send-from-recipients \
  --recipients-file /tmp/gitmail_recipients_clean.json \
  --project-name "$NAME" \
  --description "$DESC" \
  --project-url "$URL" \
  --prewritten-subject "$USER_SUBJECT" \
  --prewritten-body /tmp/gitmail_user_body.txt \
  > /tmp/gitmail_send.json 2>&1
```

When done, summarize:

```
Send complete.
  Sent: N
  Failed: M (grouped by reason: 4xx / 5xx / unsubscribed / invalid-address)
  Unsubscribe log: .viralman_unsubscribes.jsonl
```

No automatic retry on failures. Pass the failure reason through to the user verbatim.

---

## Feedback loop (when the user requests a tweak in Step 4)

If the user says things like "shorter", "different subject", "change the tone":

1. Map the feedback to the right argument:
   - "shorter" / "less technical" → strengthen `--emphasis` or `--tone`
   - "different subject" → flip `--subject-style` (or accept a free-form headline)
   - "in Korean" / "in English" → change the language prefix in `--tone`
2. Re-run **Step 4 only** (template-only dry-run) with the new args. Do NOT re-run Step 3 (collection).
3. Show the new body and wait for the user's OK again.

Only return to Step 3 if the user signals they want to recollect (e.g. "use different seeds", "more recipients").

---

## Boundaries

- **Never** call `send-from-recipients` without `--dry-run` until the user has explicitly said "발송해줘" / "send" / "go". Body agreement ≠ send agreement (본문 합의 ≠ 발송 합의).
- **Never** strip the unsubscribe footer or the `List-Unsubscribe` header.
- **Never** pass `--max-users` greater than 1500 (the safe GraphQL 5,000 pt/hr + REST 5,000 req/hr ceiling at 3x oversample). For larger campaigns, advise the user to split runs across a secondary GitHub account token.
- When the collected count exceeds the **SMTP daily limit**, surface it: free @gmail.com 500/24h, Workspace 2,000/24h. `step_send` will auto-abort and split the remainder into `unprocessed` — tell the user when the rolling 24h window resets and how to use the retry-recipients file.
- For live progress during a send, run `./scripts/gitmail_watch.py --auto` in a separate terminal/tab (auto-picks the newest /tmp/gitmail_send_*.json). Single-line carriage-return display; `--once` prints once and exits, suitable for a Claude Code statusLine command.
- **Never** read or print the contents of `~/.viralman/.env`.
- **Never** invent or guess email addresses. Use only what the GitHub Users API / PushEvent endpoints return.
- **Never** auto-retry a failed send.
- Don't tweak per-minute rate limits without permission. Tell the user to set `SMTP_RATE_PER_MIN` themselves if they want a faster send.
- Refuse private-repo commit-email scraping or GitHub rate-limit evasion requests.
