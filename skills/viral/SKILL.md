---
name: viral
description: Drive the end-to-end flow that turns a one-line intent into platform-tuned, non-AI-feeling posts and publishes them to the user's Reddit / X / LinkedIn after explicit confirmation.
level: 3
---

# Viral Skill

This skill is the spine of the viralman plugin. The `/viral` slash command and any natural-language trigger ("바이럴해줘", "make a promo post for…") route here. The skill owns the multi-step flow; the agents do the writing and review; the scripts do the posting.

## Trigger phrases

Auto-trigger when the user's message contains any of:

- `바이럴해줘`, `바이럴 해줘`, `홍보글 작성해줘`, `홍보 글 써줘`
- `make this go viral`, `write a promo post`, `write a launch post`, `post this to reddit/twitter/linkedin`

**한국어**:
- "이거 트위터에 올려줘 AI 같지 않게", "Reddit 글 써줘 자연스럽게"
- "X 스레드 만들어줘", "LinkedIn 공지 써줘"
- "내가 한 거 자랑해줘"
- "이번 출시 글 써줘"

**English**:
- "write a launch post for X / Reddit / LinkedIn"
- "tweet about this", "thread about this"
- "draft a Reddit post for r/<sub>"
- "make a non-AI-feeling promo post"

**中文**:
- "写一条不像 AI 的 推文", "写一篇 reddit 帖子"

**日本語**:
- "AI っぽくない 投稿 を 書いて", "ローンチ 投稿 を 作って"

If the user typed `/viral`, follow `commands/viral.md` for argument parsing first.

## Required inputs (gather before drafting)

- **Intent**: what is the post about? (free text, 1–3 sentences from the user)
- **Targets**: which platforms? Default `reddit, x, linkedin`. Reddit *requires* a specific subreddit — if not given, ask once.
- **Voice mode**: `growth-story` | `casual-hype` | `show-and-tell` | `contrarian-take`. Pick a default from the intent's tone; confirm if borderline.
- **Anchors**: at least one specific number, name, time anchor, or admission of doubt the post can hang on. If the user's intent has none, ask for one before drafting — this is what stops the output from feeling like AI slop.

## Step 1 — Plan

Print a one-block plan: target platforms, mode, subreddit (if any), and the anchor(s) you'll use. Wait for the user to nudge or say "go".

## Step 2 — Draft

Spawn the `viral-writer` agent **once per platform** in parallel. Pass it:

- The intent and anchors.
- The voice mode template from `voice/modes/<mode>.md`.
- The platform's register/length rules from `voice/platform-norms.md`.
- The 5–10 reference posts for that platform from `voice/reference-corpus/`.
- The banned-patterns list from `voice/ai-tells.md` (so the writer can avoid them up front).

Each draft is returned as plain text with no surrounding commentary.

## Step 3 — Sniff & rewrite

Spawn `ai-tell-sniffer` **on each draft separately**. The sniffer:

1. Runs the heuristic checks defined in `voice/ai-tells.md`.
2. If clean, returns the draft unchanged.
3. If flagged, rewrites once and re-checks. Up to **3 passes total**.
4. If still flagged after 3 passes, returns the cleanest version *and* a flag list.

Authoring (writer) and review (sniffer) MUST be different agent invocations. Do not collapse them.

## Step 4 — Show drafts

Print all drafts side by side (or stacked if width is tight). For each, show:

- Platform name and length (chars / words).
- The body.
- Any unresolved sniffer flags.
- The first ~80 chars as the preview hook.

Then ask the user, per-platform: `[edit] [regenerate] [post] [skip]`.

If the user asked for `--yes`, skip this step *unless* there are unresolved flags. Refuse to auto-post a flagged draft.

## Step 5 — Publish

For each platform with a `post` decision:

| Platform | Script | Behavior |
|---|---|---|
| Reddit | `./scripts/post_reddit.py --subreddit <sub> --title <title> --body -` | Reads body from stdin, posts via PRAW, returns the permalink. |
| LinkedIn | `./scripts/post_linkedin.py --body -` | Posts via UGC Posts API, returns the post URN/URL. |
| X (Twitter) | `./scripts/post_twitter.py --body -` | If `TWITTER_BEARER` is set, posts via API; otherwise opens a `https://twitter.com/intent/tweet?text=…` URL via `open` and prints the URL for the user to one-click send. |

Capture each script's stdout — the URL/URN — and print it. If a script exits non-zero, do **not** retry blindly: print the error, drop that platform, continue with others.

## Step 6 — Log

Append one JSON line per posted (or attempted) item to `~/.viralman/posts.jsonl`:

```json
{"ts":"2026-04-25T16:30:00Z","platform":"reddit","mode":"growth-story","subreddit":"programming","url":"https://reddit.com/...","chars":612,"flags":[]}
```

This is the user's only audit trail. Never write credentials, the original intent, or the full body into the log — just metadata + URL.

## Boundaries

- The skill never reads `~/.viralman/.env`. Only the `scripts/post_*.py` helpers do.
- The skill never invents a subreddit, company page, or handle.
- The skill never posts a draft that has unresolved sniffer flags without an explicit user `post` decision in the same turn.
- The skill never retries a failed post automatically — failure goes to the user.
