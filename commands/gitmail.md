---
description: Send personalized cold emails to GitHub stargazers of similar repos. Asks four upfront questions in one batch (language / subject style / targeting / recipient count), collects recipients, generates a fast template-only dry-run preview of the email body, and only sends for real after the user explicitly confirms. Single source of truth lives in `skills/gitmail/SKILL.md`.
allowed-tools: Read, Bash(.venv/bin/python:*), Bash(./scripts/gitmail.py:*), Bash(./scripts/save_creds.py:*), Bash(./bin/viralman:*), Bash(grep:*), Bash(tail:*), Bash(head:*), Bash(wc:*)
argument-hint: "<project-url|description> [--tone '...'] [--emphasis '...'] [--seed-repos a/b,c/d] [--keywords k1,k2] [--max-users N] [--subject-style auto|headline|tag|simple]"
---

# /gitmail — personalized cold email to similar-repo stargazers

The full flow is documented in `skills/gitmail/SKILL.md` (single source of truth). This file covers entry point, argument parsing, and boundaries only.

```
/gitmail https://github.com/rlaope/Argus
/gitmail "Want to launch my JVM-monitoring SaaS"
/gitmail https://github.com/foo/bar --subject-style tag --max-users 100
```

## Entry behavior

1. **Pre-flight** — `./scripts/save_creds.py --show-keys` to verify `GITHUB_TOKEN` + one LLM key + (for real send) the SMTP cred set. If anything is missing, route to `/viralman-setup gitmail` and stop.
2. **Step 1 — Project analysis (Claude direct)** — when the first token of `$ARGUMENTS` is a GitHub URL, derive a first-pass keyword from the owner/repo slug and combine with any free-text the user provided. Do not fetch the README. Print the analysis as 2–3 lines so the user has context for the batch question.
3. **Step 2 — Batch question (AskUserQuestion, exactly once)** — surface all four questions in one call. Do **not** call `gitmail.py recipients` or `send-from-recipients` until the answers are in.
   - **Q1 Language**: Korean / English / Chinese / Japanese
   - **Q2 Subject style**: `auto` / `headline` / `tag` / `simple` (each option carries a preview string)
   - **Q3 Targeting strategy**: recommended seeds (Claude picks live) / keyword search / auto
   - **Q4 Recipients**: 100 / 500 / 1000 / 1500 (Other auto-added, 1–1500). Tell the user the two caps are separate:
     - **Collection cap = 1,500** — safe ceiling at 3x oversample on GitHub's GraphQL+REST dual 5,000/hr buckets.
     - **SMTP send cap (per day)** — *free @gmail.com 500*, *Workspace 2,000*. Even if 1500 is collected, free Gmail needs a 3-day split. step_send auto-aborts and splits the remainder into an `unprocessed` count.
4. **Step 3 — Collection** — run `.venv/bin/python ./scripts/gitmail.py recipients ...`. Slice the recipients array off the tail of the JSONL stream and save to `/tmp/gitmail_recipients_clean.json`. Print at most 8 in the preview.
5. **Step 4 — Fast dry-run preview** — `send-from-recipients --template-only --dry-run` makes one LLM call and reuses the body. (Cuts a 50-recipient dry-run from 13 min to ~16 sec.)
6. **Step 5 — Wait for explicit send confirmation** — only run without `--dry-run` (`--template-only` retained) after the user explicitly says "발송해줘" / "send" / "go". On feedback, change the relevant arg and rerun Step 4.

If `$ARGUMENTS` already includes `--subject-style` / `--tone` / `--emphasis` / `--seed-repos` / `--keywords` / `--max-users`, drop the matching question(s) from the batch and use the supplied value as-is.

## Boundaries (summary — full set in SKILL.md)

- Never call `send-from-recipients` without `--dry-run` until the user has explicitly said "발송해줘" / "send" / "go".
- Never strip the unsubscribe footer or the `List-Unsubscribe` header.
- `--max-users` is allowed only in 1–1500 (the safe GraphQL 5,000 pt/hr + REST 5,000 req/hr dual-bucket ceiling; above that, one bucket stalls on rate limit).
- SMTP send limit is separate. Free @gmail.com 500/24h, Workspace 2,000/24h. When the collected count exceeds the SMTP cap, step_send auto-aborts, emits a `send_aborted` event, and prints a Korean stderr line. The remainder lands in `unprocessed` — point the user at the rolling 24h reset and the retry-recipients file.
- For live progress, use `./scripts/gitmail_watch.py --auto` (or `--once` for a single statusLine print).
- Never read or print `~/.viralman/.env` (only `--show-keys` is safe).
- Never invent email addresses. Use only what the GitHub Users API / PushEvent endpoints return.
- No automatic retry on send failures.
- Refuse private-repo scraping or GitHub rate-limit evasion requests.
