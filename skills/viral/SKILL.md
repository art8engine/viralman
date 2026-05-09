---
name: viral
description: Drive the end-to-end flow that turns a one-line intent into platform-tuned, non-AI-feeling posts and publishes them to the user's Reddit / X / LinkedIn after explicit confirmation.
level: 3
---

# Viral Skill

This skill is the spine of the viralman plugin. The `/viral` slash command and any natural-language trigger ("바이럴해줘", "make a promo post for…") route here. The skill owns the multi-step flow; the agents do the writing and review; the scripts do the posting.

## Trigger phrases

Auto-trigger when the user's message contains any of:

### Generic intent (router asks for platform)

These have **no explicit platform**, so Step 0 below MUST run the 3-way router (X / Reddit / Gitmail):

- `바이럴해줘`, `바이럴 해줘`, `홍보글 작성해줘`, `홍보 글 써줘`, `홍보해줘`, `이거 홍보`
- `make this go viral`, `write a promo post`, `write a launch post`, `promote this`
- `내가 한 거 자랑해줘`, `이번 출시 글 써줘`

### Explicit-platform intent (skip router, go straight in)

The trigger names the channel(s) directly — Step 0 must be **skipped** and `Targets` set to exactly the named platform(s):

- **X / Twitter only**: `x에 올려줘`, `x에 써줘`, `x에 포스팅`, `트위터에 올려줘`, `트윗 써줘`, `tweet about this`, `post this to x/twitter`, `write an X thread`
- **Reddit only**: `reddit에 올려줘`, `reddit에 써줘`, `레딧에 올려줘`, `r/<sub>에 올려줘`, `post this to reddit`, `draft a reddit post`
- **Both X + Reddit**: `x랑 reddit에 올려줘`, `x하고 reddit에 올려줘`, `트위터랑 레딧에 올려줘`, `post this to x and reddit`
- **LinkedIn** (still supported, not in the router): `linkedin에 올려줘`, `LinkedIn 공지 써줘`, `post this to linkedin`

When parsing, normalize aliases: `트위터 == 트윗 == x == twitter`, `레딧 == reddit`. A bare reference like "스레드 만들어줘" without a platform name still counts as **generic** — run the router.

### Other natural-language hints (treat as generic unless they name a platform)

- 한국어: "이번 출시 글 써줘", "AI 같지 않게 써줘"
- English: "make a non-AI-feeling promo post"
- 中文: "写一条不像 AI 的 推文" (names X → explicit), "写一篇 reddit 帖子" (names Reddit → explicit)
- 日本語: "AI っぽくない 投稿 を 書いて", "ローンチ 投稿 を 作って"

If the user typed `/viral`, follow `commands/viral.md` for argument parsing first.

## Step 0 — Channel router (only when intent is generic)

Run **only** if no platform was named in the trigger (i.e., generic intent). Skip entirely when the trigger already named X / Reddit / X+Reddit / LinkedIn.

Use `AskUserQuestion` (multiSelect=true) with these three options, **in this order**:

| label | header | description |
|---|---|---|
| X (Twitter) | X | 단일 트윗 / 짧은 스레드. 빠른 도달, 캐주얼 톤. |
| Reddit | Reddit | 특정 서브레딧에 1건. 길이·논점 자유, 서브레딧 사양에 맞춰 작성. |
| Gitmail (cold email) | Gitmail | 비슷한 레포 스타거에게 개인화된 메일 발송. `gitmail` 스킬로 분기. |

Then:

- **X / Reddit / both** picked → set `Targets` accordingly and continue with Step 1 of THIS skill (viral).
- **Gitmail** picked → **hand off to the `gitmail` skill**: stop the viral flow, follow `skills/gitmail/SKILL.md` from its Step 1. Do not draft a Reddit/X post in this branch.
- **Mixed (e.g., X + Gitmail)** → run viral flow for X, then hand off to gitmail at the end. The two share the project intent but have distinct inputs (gitmail needs project URL + recipient cap).

LinkedIn is intentionally not in the 3-way router (its CLI helper still works via the explicit trigger above), to keep the default surface focused on the user's stated three channels.

## Required inputs (gather before drafting)

- **Intent**: what is the post about? (free text, 1–3 sentences from the user)
- **Targets**: which platforms? Set by **Step 0 router** for generic intent, or directly by the explicit-platform trigger. For `/viral` slash-command invocation, default is `reddit, x, linkedin` (per `commands/viral.md`). Reddit *requires* a specific subreddit — if not given, ask once.
- **Voice mode**: `growth-story` | `casual-hype` | `show-and-tell` | `contrarian-take`. Pick a default from the intent's tone; confirm if borderline.
- **Anchors**: at least one specific number, name, time anchor, or admission of doubt the post can hang on. If the user's intent has none, ask for one before drafting — this is what stops the output from feeling like AI slop.

## Step 1 — Plan

Print a one-block plan: target platforms, mode, subreddit (if any), and the anchor(s) you'll use. Wait for the user to nudge or say "go".

## Step 2 — Draft

If the user has explicitly said "I'll write the body myself" / "직접 입력할게" / pasted a finished draft, follow `skills/copy-prep/SKILL.md` §Manual override pattern instead — skip the writer agent and pass the user-provided body straight to the post script in Step 5. Otherwise:

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

Then ask the user, per-platform: `[post] [edit] [regenerate] [skip]`.

Use **`AskUserQuestion`** for this — and surface, in the option descriptions, that the user can attach free-form instructions in the same step:

- `Post` — send as-is via the matching `scripts/post_*.py`.
- `Edit` — describe the specific changes you want (tone, hook line, length cap, swap a phrase, etc.); the skill will surgically rewrite using only those instructions, then re-run the sniffer.
- `Regenerate` — optionally describe what to change about the framing/anchors; the skill will spawn a fresh `viral-writer` call with those instructions folded into the prompt, then re-run the sniffer.
- `Skip` — drop this platform.

When the user's response includes free-form text alongside an option (either via the option's `notes` annotation or via the `Other` free-text fallback), treat that text as **additional instructions**:

- For `Edit`: pass the notes verbatim to the writer as a "minimal-change rewrite" directive — keep the existing draft as the base, change only what the notes call out, then re-sniff.
- For `Regenerate`: prepend the notes to the writer's INTENT block as a `USER OVERRIDE` section so they take precedence over earlier defaults, then re-sniff.

When `Regenerate` is picked **without** notes, treat all prior user-supplied constraints from the same flow (added pillars, must-mention items, banned phrasings, length caps, language) as **still binding**. A note-less Regenerate means "try a different angle within the same constraints", not "reset everything". Carry every explicit prior constraint into the new writer prompt verbatim.

Never silently drop user notes. If the notes contradict a hard rule (e.g. "make it 500 chars" on X), apply the rule, surface the conflict in one line, and proceed with the rule honored.

If the user asked for `--yes`, skip this step *unless* there are unresolved flags. Refuse to auto-post a flagged draft.

## Step 5 — Publish

For each platform with a `post` decision:

| Platform | Script | Behavior |
|---|---|---|
| Reddit | `viralman post-reddit --subreddit <sub> --title <title> --body -` | Reads body from stdin, posts via PRAW, returns the permalink. |
| LinkedIn | `viralman post-linkedin --body -` | Posts via UGC Posts API, returns the post URN/URL. |
| X (Twitter) | `viralman post-twitter --body -` | If `TWITTER_BEARER` is set, posts via API; otherwise opens a `https://twitter.com/intent/tweet?text=…` URL via `open` and prints the URL for the user to one-click send. |

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
