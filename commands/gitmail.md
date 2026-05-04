---
description: Run the gitmail outreach pipeline — analyse a project, find similar GitHub repos, collect stargazer emails, compose personalized notes, and send via SMTP.
allowed-tools: Read, Bash(./scripts/gitmail.py:*), Bash(./bin/viralman:*), Bash(open:*)
argument-hint: "<project-description> [--project-name name] [--project-url url] [--max-users N] [--provider claude|openai|gemini] [--dry-run] [--template-only]"
---

# /gitmail — outreach to people who likely care about your project

The user gives you a description of *their* open-source project. Your job is
to drive the gitmail flow, which:

1. Analyses the project's tech and topic.
2. Searches GitHub for similar repos by topic + keyword.
3. Walks the stargazers of those repos and resolves their public email.
4. Writes a short, personalized email to each (mentioning the repo they
   starred, so it doesn't read as blast spam).
5. Sends via SMTP with a one-click unsubscribe footer + List-Unsubscribe
   header, rate-limited to 30/min by default.

The user can do all this from the dashboard's `/gitmail` page (recommended),
but the slash command is here for one-shot CLI runs.

## Required inputs (gather before starting)

- **project description** (3–5 lines on what your project is and who it's for)
- **project name** (used in subject lines and body)
- **project URL** (optional but recommended — used to skip your own repo and
  to include in the CTA)
- **max users** (1..10000; default 100). Anything above ~500 will take a
  while because of GitHub rate limits.
- **provider** (claude / openai / gemini). Inferred from whichever API key is
  saved if not given.

If any of those are missing, ask once. Do NOT guess the project URL.

## Pre-flight

Before starting:

- **Confirm dry-run** unless the user explicitly typed `--no-dry-run`. Default
  is dry-run — it builds full previews without hitting SMTP. Sending real
  email to thousands of strangers is a one-way action; never do it without
  the user's eyes on the output.
- Confirm `~/.viralman/.env` has at least: `GITHUB_TOKEN`, an LLM API key,
  and (for non-dry-run) `SMTP_HOST` + `SMTP_USER` + `SMTP_PASSWORD` +
  `SMTP_FROM`. If any is missing, point them at `/viralman-login-gitmail`.

## How to run

```bash
./scripts/gitmail.py run \
  --description "$DESC" \
  --project-name "$NAME" \
  --project-url "$URL" \
  --max-users 100 \
  --provider claude \
  --dry-run
```

The script streams JSONL events to stdout — one per pipeline step. Surface
each step's outcome (analyse / search / recipients / compose / send) in your
reply, but do not paste raw JSON into the user-facing answer.

## After it finishes

- Summarise: number of similar repos found, recipient count, sent vs. failed.
- If dry-run, point the user to the dashboard's /gitmail page where they
  can read each preview, then re-run without `--dry-run`.
- If not dry-run, the script's final `done` event includes a `failures`
  list — surface failed addresses + reasons concisely.

## Boundaries

- **Never** disable the unsubscribe footer or List-Unsubscribe header.
- **Never** raise the per-minute rate limit silently. If the user wants
  faster sending, have them set `SMTP_RATE_PER_MIN` themselves.
- **Never** read or echo `~/.viralman/.env`.
- Refuse to run if `max_users > 10000` — that's the hard cap baked into the
  script, exposed via the dashboard slider.
- The agent never invents an email address. The script only sends to
  addresses returned by the GitHub Users API or public PushEvent commits.
