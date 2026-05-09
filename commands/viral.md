---
description: Generate non-AI-feeling viral / promo posts for Reddit, X, and LinkedIn, then publish them under the user's accounts after explicit confirmation.
allowed-tools: Read, Write, Edit, Bash(viralman:*), Bash(open:*), Agent
argument-hint: "<intent> [--mode growth-story|casual-hype|show-and-tell|contrarian-take] [--only reddit,x,linkedin] [--lang en|ko] [--yes]"
---

# /viral — write & publish posts that don't read like AI

The user has invoked you with an intent like "이런 내용으로 바이럴해줘" or "write a promo post about X". Your job is to drive the full pipeline defined in `skills/viral/SKILL.md`. **Read that file first** — it is the authoritative flow. This file is just the entry point.

## Arguments

`$ARGUMENTS` will contain the user's free-text intent plus optional flags. Parse them:

- `--mode <name>` — pick one of `growth-story`, `casual-hype`, `show-and-tell`, `contrarian-take`. Default: `growth-story` for technical/educational content, `casual-hype` for "we shipped X" / wow-moments. If unsure, ask once.
- `--only <list>` — comma-separated subset of `reddit`, `x`, `linkedin`. Default: all three.
- `--lang <code>` — `en` (default) or `ko`. The user's intent may be in Korean; output language is English unless `--lang ko` is passed.
- `--yes` — skip per-platform confirmation. Default is always-confirm.
- `--subreddit <name>` — required if `reddit` is in `--only`. Never guess a subreddit; ask if not provided.

Anything that isn't a flag is the **intent** — the substance the post should be about.

## What you do

1. Load `skills/viral/SKILL.md` and follow it step-by-step.
2. Use the `viral-writer` agent for drafting and `ai-tell-sniffer` for the review-and-rewrite pass. Do not author + review in the same agent context — keep them separated.
3. Hand off publishing to `scripts/post_*.py`. Never call platform APIs directly from the agent context — the scripts are the only place credentials live.
4. Default to **draft + confirm** unless the user passed `--yes`. Even with `--yes`, refuse to post if the sniffer pass left unresolved flags.

## Boundaries

- **Never** read or echo the contents of `~/.viralman/.env`.
- **Never** invent a subreddit, a LinkedIn company page, or a Twitter handle the user didn't supply.
- If credentials are missing for a platform, drop that platform to draft-only mode and tell the user how to set it up — do not crash the run.
- If a draft fails the sniffer 3x, surface the flags to the user instead of silently posting a flagged draft.
