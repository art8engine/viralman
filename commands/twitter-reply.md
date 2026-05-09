---
description: Find recent X / Twitter posts where it's natural to reply with "I built this — want to take a look?", push them to the dashboard for inspection, and (only on explicit confirmation) send personalized replies.
allowed-tools: Read, Bash(viralman:*), Bash(grep:*), Bash(tail:*), Bash(head:*), Bash(open:*)
argument-hint: "<project-url|description> [--query '...'] [--keywords k1,k2] [--lang en|ko] [--max-candidates N] [--min-engagement N] [--mode scrape|scrape-and-reply]"
---

# /twitter-reply — find replyable tweets, inspect in dashboard, then reply

The full flow is documented in `skills/twitter-reply/SKILL.md` (single source of truth). This file covers entry, argument parsing, and boundaries only.

```
/twitter-reply https://github.com/rlaope/Argus
/twitter-reply "JVM monitoring without an agent"
/twitter-reply https://github.com/foo/bar --query '"jvm monitoring"' --min-engagement 25
```

## Entry behavior

1. **Pre-flight** — `viralman save-creds --show-keys` to verify `TWITTER_OAUTH2_BEARER` (search + reply scope) and one LLM key (or Claude Code CLI). If missing, route to `/viralman-setup twitter` and stop.
2. **Step 1 — Project intent capture** — follow `skills/copy-prep/SKILL.md` §Project intent capture (URL parsing, keyword derivation, 2–3 line confirmation).
3. **Step 2 — Batch question (AskUserQuestion, exactly once)** — Q1 Mode (scrape-only / scrape+reply), Q2 Search query (auto / free-form), Q3 Engagement floor (0 / 5 / 25), Q4 Candidate count (10 / 20 / 50). Skip any question whose value was already supplied via flags.
4. **Step 3 — Scrape** — `viralman twitter-reply find ... --out /tmp/twitter_candidates.json`. Summarize: count + top 3 with handle + first 80 chars.
5. **Step 4 — Dashboard handoff** — point the user at `http://localhost:8765/twitter-reply` (boots dashboard if needed via `/dashboard`). For Scrape-only, stop here.
6. **Step 5 — Per-candidate reply** (Scrape+reply only) — compose, sniff, show, wait for "send" / "발송", then `viralman twitter-reply reply --tweet-id ... --body -`.

If `$ARGUMENTS` already includes `--query` / `--keywords` / `--lang` / `--max-candidates` / `--min-engagement` / `--mode`, drop the matching question(s) from the batch.

## Boundaries (summary — full set in SKILL.md)

- Never call `viralman twitter-reply reply` without an explicit per-candidate "send" / "발송" from the user.
- Never invent tweet IDs, usernames, or candidate text — only use what the v2 search response returned.
- Never pass `--include-retweets` unless asked; reply chains under retweets are usually suppressed.
- Reply rate limit (Basic tier): 50 / 15-min window. Never send more than 5 per batch without re-confirming.
- Refuse private-tweet scraping or rate-limit evasion. Search uses v2 recent-search (last 7 days only).
- Never read or print the contents of `~/.viralman/.env`.
