---
name: twitter-reply
description: Find tweets where it's natural to reply "I built this thing — want to take a look?", and either inspect the candidates in the dashboard or send a personalized reply. The skill drives a two-step flow — scrape first, then optionally reply — and pushes the candidate list to the dashboard's /twitter-reply page so the user can browse cards (body / author / link / engagement) before deciding which ones to engage.
level: 3
---

# twitter-reply Skill

Goal: when the user types `/twitter-reply <project>` or natural language like "이 프로젝트 트위터 답글로 홍보할 만한 거 찾아줘", search recent X / Twitter posts for ones where a reply mentioning the user's project would land naturally, push the candidates to the dashboard for inspection, and (only after explicit confirmation) post per-candidate replies.

## Trigger phrases

Auto-trigger on:

- `/twitter-reply`, `/x-reply`
- "트위터 답글로 홍보", "x에 답글로 홍보", "트위터 답글 마케팅", "답글로 알릴 만한 트윗 찾아줘"
- "find tweets to reply to", "reply marketing on X", "scrape tweets I can reply to with my project"

If the user says only "트위터에 올려줘" / "x에 올려줘" — that's the existing `viral` skill's posting flow, NOT this skill. This skill is specifically for **reply-marketing** (engaging on someone else's tweet).

## Pre-flight

**Script location guard (run this first).** The skill operates against `./scripts/save_creds.py` and `./scripts/twitter_reply.py` in the current working directory (the viralman repo). If those files are not present (e.g. invoked from another project), **do not** `ls`/`find`/probe `~/.claude/plugins/cache/viralman/**` — the permission layer reads any traversal of that path as credential discovery and will block. Instead call `AskUserQuestion` **once** with:

- "Switch to the viralman repo and rerun" — stop now; user will `cd` and reinvoke.
- "Cancel" — abort cleanly.

Pick the first option as the default. Only proceed past this gate when `test -f ./scripts/save_creds.py` succeeds.

Once the scripts are local, run `./scripts/save_creds.py --show-keys` and confirm:

- `TWITTER_OAUTH2_BEARER` — required for both search (`tweet.read`) and reply (`tweet.write`). The dashboard PKCE login covers both scopes.
- one of `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GEMINI_API_KEY`, or detect Claude Code CLI via `which claude` (used to compose per-candidate reply bodies).

If the bearer is missing, route the user to `/viralman-setup twitter` (PKCE login) and stop. Never read or print `.env` values.

---

## Step 1 — Project intent capture

Follow `skills/copy-prep/SKILL.md` §Project intent capture. The struct it produces (`url` / `name` / `description` / `keyword`) feeds the search query in Step 3.

---

## Step 2 — Batch question (AskUserQuestion, exactly once)

Surface all four upfront decisions in one call before any search runs:

### Q1 — Mode

| option | description |
|---|---|
| Scrape only (recommended) | Find candidates, push them to the dashboard `/twitter-reply` page, stop. Reply step is a separate decision. |
| Scrape + reply | Same scrape, but also compose per-candidate replies and walk the user through send confirmations one tweet at a time. |

### Q2 — Search query

| option | description |
|---|---|
| Auto from project | Use `keyword` + 2–3 high-signal nouns from the project description as the v2 search query. Default. |
| Free-form | The user types their own query string (v2 recent-search syntax allowed: `"jvm monitoring" -is:retweet lang:en`). |

### Q3 — Engagement floor

| option | description |
|---|---|
| 0 (raw recency) | No floor. Cheaper signal, more noise. |
| 5 (default) | Likes+retweets+replies+quotes ≥ 5. Filters out pure shouts-into-void. |
| 25 (high signal) | Tweets that already have traction. Reply gets more eyes but the topic may already be saturated. |

### Q4 — Candidate count

| option | description |
|---|---|
| 10 | Quick first pass. |
| 20 (default) | Standard inspection batch. |
| 50 | Deeper sweep. v2 recent-search caps any single call at 100 results. |

Follow `skills/copy-prep/SKILL.md` §Language picker if the reply needs a non-default language. The picked language maps to the v2 `lang:` operator on the search and to the reply composition prompt.

---

## Step 3 — Scrape (the find subcommand)

Run once after the batch question:

```bash
.venv/bin/python ./scripts/twitter_reply.py find \
  --query "$QUERY" \
  --keywords "$KEYWORDS" \
  --lang "$LANG" \
  --max-candidates "$MAX" \
  --min-engagement "$MIN_ENGAGEMENT" \
  --out /tmp/twitter_candidates.json \
  > /tmp/twitter_find.json 2>&1
```

The script emits a JSONL event stream and writes the final candidates array to `--out`. Print a 2–4 line summary back to the user (count + top 3 candidates with handle + first 80 chars).

---

## Step 4 — Hand off to the dashboard

After the scrape completes, tell the user:

> N candidates ready. Open the dashboard at **http://localhost:8765/twitter-reply** to inspect them as cards (body, author, link, engagement). The page reads `/tmp/twitter_candidates.json` directly — refresh to see updates if you re-run scrape.

If the dashboard isn't running, suggest one of:

- `./bin/viralman dashboard` (preferred), or
- the `/dashboard` skill, which boots the Flask server on `:8765`.

If the user picked **Scrape only** in Q1, stop here. The dashboard view is the deliverable.

---

## Step 5 — Reply (only when user picked "Scrape + reply" AND explicitly confirms each)

For each candidate the user wants to engage:

1. Compose a reply body via LLM (or via `viral-writer` agent for tone control). Pass: candidate's text, project name + URL, the language picked in Step 2. Output ≤ 280 chars, no marketing slop, references the candidate's content concretely (not "great post! check out my thing"), ends with the project URL.
2. Pipe through `ai-tell-sniffer` once. If flagged 3 times, surface the flags and ask the user instead of auto-posting.
3. Show the draft + candidate side by side, ask "send / edit / regen / skip". Body agreement ≠ send agreement — only send after the user explicitly says "send" / "발송".
4. On send:

```bash
echo "$REPLY_BODY" | .venv/bin/python ./scripts/twitter_reply.py reply \
  --tweet-id "$TWEET_ID" --body -
```

5. Record the outcome to `~/.viralman/posts.jsonl` with `{ts, platform: "x-reply", in_reply_to, url}`.

---

## Boundaries

- **Never** post a reply without an explicit per-candidate "send" / "발송" from the user. Body agreement ≠ send agreement.
- **Never** invent a tweet ID, a username, or a candidate's text — they all come from the v2 search response.
- **Never** scrape with `--include-retweets` unless the user asks for it explicitly. Replying to a retweet creates a low-quality reply chain and most platforms suppress it.
- **Never** auto-retry a failed reply. v2 returns 4xx for things like "you've already replied to this tweet" or "rate limited" — those need a human decision, not a retry loop.
- Search uses the v2 recent-search endpoint (last 7 days). For longer windows the user needs the Twitter "all archive" tier — out of scope for this skill.
- Reply rate limits: v2 user-context allows 50 replies / 15-min window for the standard Basic tier. The skill never sends more than 5 in a single batch without re-confirming.
- Refuse private-tweet scraping or any attempt to evade Twitter's rate-limit headers.
