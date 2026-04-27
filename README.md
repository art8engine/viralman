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
- `/viralman-login-{reddit,twitter,linkedin}` — per-platform credential setup with secrets piped through `read -s` so they never hit the LLM context.
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

### Credentials (one-time, per platform)

Three dedicated skills walk you through each platform separately. Run only the ones you need:

```
/viralman-login-reddit       # ~3 min, free
/viralman-login-twitter      # ~5 min, free tier (~1,500 posts/month). Optional — compose URL fallback works without it.
/viralman-login-linkedin     # ~10 min, free, OAuth dance + 60-day token refresh
```

Each skill walks you through the platform's developer portal step by step. **Secrets never enter the LLM context** — the skills have you pipe passwords/tokens through `read -s` directly into a save script. The agent only sees non-secret values like usernames and client_ids.

Credentials are written to `~/.viralman/.env` with `chmod 600`. The `post_*.py` scripts are the only place that file is read.

There's also a non-interactive shell wizard if you prefer doing it all at once: `./scripts/setup.sh`.

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
├── skills/
│   ├── viral/                      # main /viral flow
│   ├── viralman-login-reddit/      # per-platform setup skills
│   ├── viralman-login-twitter/
│   └── viralman-login-linkedin/
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
