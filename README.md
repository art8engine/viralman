# viralman

A Claude Code plugin that turns a one-line intent into platform-tuned posts for **Reddit**, **X (Twitter)**, and **LinkedIn**, then publishes them under *your own* accounts after you confirm.

```
> 이런 내용으로 바이럴해줘: 우리 팀이 만든 오픈소스 K8s autoscaler가 비용을 47% 줄였다
```

You get three drafts — one per platform — that don't read like AI slop, and a one-key confirm before anything goes live.

## Why it exists

Most "AI social poster" tools produce posts that anyone can spot from across the room: balanced tricolons, em-dash floods, "It's not just X — it's Y" hooks, and a tidy moralizing closer. viralman's headline feature is a separate **ai-tell-sniffer** review pass that scores every draft against ~30 concrete heuristics and rewrites until it clears them.

## What you get

- `/viral <intent>` — slash command that drives the whole flow.
- Four voice modes: **growth-story** (struggle → insight → takeaway), **casual-hype** (no-way / this-slaps register), **show-and-tell** (project launch), **contrarian-take**.
- Per-platform register (a Reddit post is not a LinkedIn post) and length-aware trimming.
- Always-confirm safety default. Override with `--yes`.
- Local audit log at `~/.viralman/posts.jsonl`.
- MIT license — fork, vendor, ship.

## Install

### As a Claude Code plugin

```bash
# from anywhere
claude plugin marketplace add https://github.com/art8engine/viralman
claude plugin install viralman
```

Or symlink the repo into `~/.claude/plugins/` for local dev.

### Credentials (one-time)

```bash
cd ~/.claude/plugins/viralman
./scripts/setup.sh
```

The wizard walks you through:

| Platform | Free? | Steps |
|---|---|---|
| Reddit | ✅ | Register a *script* app at https://www.reddit.com/prefs/apps. |
| LinkedIn | ✅ | Register at https://www.linkedin.com/developers/apps, request `w_member_social` scope, complete the local OAuth callback. |
| X (Twitter) | ✅ Free tier | The X API free tier allows ~1,500 posts/month, plenty for personal use. Register at https://developer.twitter.com, generate API + access keys with read+write permission. If you skip it, viralman opens a pre-filled `intent/tweet` URL in your browser and you click post. |

Credentials are written to `~/.viralman/.env` with `chmod 600`. **They never enter the LLM context** — the agent shells out to scripts that read the env directly.

## Usage

```bash
# default: drafts for all three platforms, growth-story mode, ask before posting
/viral our open-source K8s autoscaler cut a real prod bill by 47% in 3 weeks

# pick mode
/viral --mode casual-hype "we shipped the gnarliest race-condition fix of my life"

# pick targets
/viral --only reddit,x "looking for r/programming feedback on this go regex lib"

# auto-publish (be sure)
/viral --yes "..."

# Korean-language output
/viral --lang ko "..."
```

## How "doesn't feel AI" actually works

The `ai-tell-sniffer` agent runs on every draft, looking for:

- **Banned phrases**: "delve", "tapestry", "leverage", "navigate the landscape", "it's not just X — it's Y", "in today's fast-paced world", "stands as a testament", "let's dive in", "unleash", "supercharge", and ~20 more.
- **Em-dash density** > 1 per 60 words.
- **Balanced tricolons** (three list items of nearly identical length).
- **Closing moralizers** — humans don't summarize their own anecdotes.
- **Hashtag stuffing** — caps per platform; Reddit gets zero.
- **Generic-claim anchors** — every draft must contain a specific number, name, time anchor, or admission of doubt.

If three rewrite passes still trip flags, the unflagged version is shown to you with the warnings surfaced.

## Repo layout

See [the plan document](.claude/plans/) or browse the tree:

```
viralman/
├── .claude-plugin/   # plugin & marketplace manifests
├── commands/         # /viral slash command
├── skills/viral/     # multi-step flow
├── agents/           # writer, sniffer, publisher
├── voice/            # ai-tells, platform-norms, mode templates, reference corpus
├── scripts/          # setup.sh + per-platform posters
├── tests/            # sniffer self-test
└── examples/         # end-to-end transcripts
```

## Status

v0.1.0 — first cut. Expect rough edges. Issues and PRs welcome.

## License

MIT.
