# viralman

A Claude Code plugin **and** a local dashboard for open-source maintainers. Three things in one:

1. **`/viral` — drafts** non-AI-feeling promo posts for **Reddit**, **X (Twitter)**, and **LinkedIn**, then publishes them under *your own* accounts after you confirm.
2. **`viralman` — local dashboard** at `http://localhost:8765`. One command starts a black-themed three-page UI: twitter / reddit / gitmail. Header switches between them. OAuth login per platform.
3. **`/gitmail` — outreach pipeline.** Describe your project; viralman finds related repos, walks their stargazers, resolves public emails, composes a personalized note via Claude / GPT / Gemini, and sends with a one-click unsubscribe footer + rate limiting.

```
> 이런 내용으로 바이럴해줘: 우리 팀이 만든 오픈소스 K8s autoscaler가 비용을 47% 줄였다
```

You get three drafts — one per platform — that don't read like AI slop, and a one-key confirm before anything goes live.

```
> viralman
viralman dashboard → http://localhost:8765
  twitter:  http://localhost:8765/twitter
  reddit:   http://localhost:8765/reddit
  gitmail:  http://localhost:8765/gitmail
```

## Why it exists

Most "AI social poster" tools produce posts that anyone can spot from across the room: balanced tricolons, em-dash floods, "It's not just X — it's Y" hooks, and a tidy moralizing closer. viralman's headline feature is a separate **ai-tell-sniffer** review pass that scores every draft against ~30 concrete heuristics and rewrites until it clears them.

## What you get

- `viralman` — start the local dashboard (Flask app at `http://localhost:8765` with three pages: twitter / reddit / gitmail).
- `/viral <intent>` — slash command that drives the multi-platform draft+publish flow.
- `/dashboard` — start the dashboard from inside Claude Code.
- `/gitmail` — outreach pipeline: similar-repo search → stargazer emails → LLM-composed body → SMTP send with unsubscribe + rate limit.
- `/viralman-login-{reddit,twitter,linkedin,gitmail}` — per-platform credential setup with secrets piped through `read -s` so they never hit the LLM context.
- Four voice modes: **growth-story** (struggle → insight → takeaway), **casual-hype** (no-way / this-slaps register), **show-and-tell** (project launch), **contrarian-take**.
- OAuth login (Twitter PKCE / Reddit web app / LinkedIn) plus a manual-tokens fallback in every login pane.
- AI-tell sniffer (~30 heuristics) runs on every draft before it can be posted.
- Per-platform register (a Reddit post is not a LinkedIn post) and length-aware trimming.
- Always-confirm safety default. Override with `--yes`.
- Local audit log at `~/.viralman/posts.jsonl`. Local unsubscribe log at `<repo>/.viralman_unsubscribes.jsonl`.
- MIT license — fork, vendor, ship.

## Install

### As a Claude Code plugin

```bash
# from anywhere
claude plugin marketplace add https://github.com/art8engine/viralman
claude plugin install viralman
```

Or symlink the repo into `~/.claude/plugins/` for local dev.

### As a CLI (so the literal `viralman` word works in your shell)

```bash
git clone https://github.com/art8engine/viralman
cd viralman
pip install --user -e .              # adds `viralman` to PATH

viralman                             # → http://localhost:8765, opens browser
viralman --port 9000 --no-browser
```

Without `pip install`, run from the repo root:

```bash
./bin/viralman                       # same flags
./scripts/dashboard.py               # equivalent
```

The dashboard needs Flask. If `pip install` isn't possible (PEP 668 / Homebrew Python), use a venv:

```bash
python3 -m venv .venv
.venv/bin/pip install flask
.venv/bin/python ./bin/viralman
```

### Credentials (one-time, per platform)

Four dedicated skills walk you through each setup separately. Run only the ones you need:

```
/viralman-login-reddit       # ~3 min, free (or use the dashboard's OAuth button)
/viralman-login-twitter      # ~5 min, free tier (~1,500 posts/month). Optional — compose URL fallback works without it.
/viralman-login-linkedin     # ~10 min, free, OAuth dance + 60-day token refresh
/viralman-login-gitmail      # ~5 min, GitHub token + SMTP + one LLM provider key
```

Each skill walks you through the platform's developer portal step by step. **Secrets never enter the LLM context** — the skills have you pipe passwords/tokens through `read -s` directly into a save script. The agent only sees non-secret values like usernames and client_ids.

Credentials are written to `~/.viralman/.env` with `chmod 600`. The `post_*.py` and `gitmail.py` scripts are the only place that file is read.

There's also a non-interactive shell wizard if you prefer doing it all at once: `./scripts/setup.sh`.

## Usage

### Drafting + posting (`/viral`)

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

### Dashboard

```bash
viralman                              # opens http://localhost:8765 in your browser
```

The dashboard has three pages:

| Page | What it does |
|---|---|
| `/twitter` | textarea + live preview (char count, sniffer flags, thread split). One-click post via API or compose-URL fallback. |
| `/reddit`  | subreddit + title + flair + body, live preview with Reddit-specific sniffer rules (no hashtags, etc.), one-click submit via PRAW. |
| `/gitmail` | start the outreach pipeline. Slider: 1–10000 target users. Live progress (analyse → search → recipients → compose → send). Per-recipient preview pane. |

OAuth login is a button on each platform's pane. The redirect URI to register is shown in the pane (`http://localhost:8765/oauth/<platform>/callback`).

### Outreach (`/gitmail`)

```bash
# one-shot CLI — dry-run by default, builds previews without sending
./scripts/gitmail.py run \
  --description "A K8s autoscaler in Go that cuts cost by 47%" \
  --project-name k8s-autoscaler \
  --project-url https://github.com/you/k8s-autoscaler \
  --max-users 100 \
  --provider claude \
  --dry-run

# template-only mode: one LLM call, reuse for all (~50x cheaper)
./scripts/gitmail.py run --template-only ...

# from inside Claude Code
/gitmail "A K8s autoscaler in Go that cuts cost by 47%" --max-users 100 --dry-run
```

Every email gets a one-click unsubscribe link and a `List-Unsubscribe` header. SMTP is rate-limited to 30/min by default (override with `SMTP_RATE_PER_MIN`).

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

```
viralman/
├── .claude-plugin/                 # plugin & marketplace manifests
├── bin/viralman                    # `viralman` CLI entry → starts dashboard
├── pyproject.toml                  # `pip install -e .` registers the command
├── viralman_cli/                   # console-script package mirror of bin/viralman
├── dashboard/                      # Flask app
│   ├── server.py                   # create_app + dev runner
│   ├── api.py                      # JSON endpoints + gitmail job tracker
│   ├── oauth.py                    # OAuth flows (twitter/reddit/linkedin)
│   ├── templates/                  # base + per-page jinja templates
│   └── static/{css,js}/            # dark theme + per-page JS
├── commands/                       # /viral, /dashboard, /gitmail
├── skills/
│   ├── viral/                      # main /viral flow
│   ├── dashboard/                  # /dashboard skill
│   ├── gitmail/                    # /gitmail skill
│   ├── viralman-login-reddit/
│   ├── viralman-login-twitter/
│   ├── viralman-login-linkedin/
│   └── viralman-login-gitmail/     # GitHub + SMTP + LLM-provider setup
├── agents/                         # viral-writer, ai-tell-sniffer, publisher
├── voice/                          # ai-tells, platform-norms, mode templates, reference corpus
├── scripts/
│   ├── post_{reddit,twitter,linkedin}.py
│   ├── gitmail.py                  # streams JSONL events for the dashboard
│   ├── dashboard.py                # alternate entry to bin/viralman
│   ├── lib/
│   │   ├── creds.py                # one-and-only ~/.viralman/.env reader
│   │   ├── compose_urls.py
│   │   ├── sniffer_check.py
│   │   ├── github_search.py        # search repos + iter stargazers + resolve email
│   │   ├── llm_compose.py          # Claude / OpenAI / Gemini abstraction
│   │   └── smtp_send.py            # SMTP + unsubscribe + rate limit
│   ├── setup.sh
│   └── save_creds.py
├── tests/                          # sniffer + gitmail compose tests
└── examples/                       # end-to-end transcripts
```

## Status

v0.2.0 — adds local dashboard + gitmail outreach + OAuth logins. v0.1.0's `/viral` flow is unchanged. Issues and PRs welcome.

## License

MIT.
