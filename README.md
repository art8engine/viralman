<h1 align="center">viralman</h1>

<p align="center">
  <b>You ship code. We ship reach.</b><br>
  Build it — viralman handles the hype.
</p>

<p align="center">
  <a href="README.md"><b>English</b></a> ·
  <a href="README.ko.md">한국어</a> ·
  <a href="README.zh.md">中文</a> ·
  <a href="README.ja.md">日本語</a>
</p>

<p align="center">
  <img src="assets/viralman.png" alt="viralman" width="520">
</p>

---

viralman takes your project description and drafts Twitter/X posts, Reddit threads, and cold emails to developers who starred similar repos on GitHub — then waits for you to say go. Works for anything you built: OSS, side project, indie tool.

```bash
viralman                 # opens http://localhost:8765
```

## Features

- **Multi-platform drafts** — `/viral` turns one intent into Reddit / X / LinkedIn drafts that don't sound like a chatbot.
- **Local dashboard** — black 4-step wizard. Project → Generate → Targets → Send. One unified login at the top.
- **gitmail outreach** — find GitHub repos like yours, walk their stargazers, send each a short personalized note. Up to 10,000 recipients with a one-click unsubscribe link baked in.
- **AI-tell sniffer** — ~30 heuristics scan every draft for clichés, em-dash floods, balanced tricolons, and missing anchors. Three rewrite passes; refuses to auto-post a still-flagged draft.
- **OAuth or manual** — sign in to X / Reddit / LinkedIn from the dashboard, or paste tokens. Secrets pipe through `read -s` and never enter the LLM context.
- **Multi-LLM** — Claude, OpenAI, or Gemini, your choice (auto-detected from saved keys).

## Use cases

- **Launching v1.0** — describe what shipped; get a Reddit post for r/programming, an X thread, a LinkedIn announcement, and an outreach list of devs who starred related tools.
- **Side project announcement** — one-shot multi-channel post without writing three different versions.
- **Finding the right place to post** — let viralman scrape and suggest subreddits, hashtags, and recent threads to comment on, instead of guessing.
- **Re-engaging old stargazers of similar tools** — gitmail builds a recipient list from public profile and commit emails, with a personalized opener mentioning the repo they starred.
- **Avoiding the AI-slop tax** — most "AI social posters" produce content that gets called out instantly. The sniffer is the headline feature.

## Install

### As a Claude Code plugin

```bash
claude plugin marketplace add https://github.com/art8engine/viralman
claude plugin install viralman
```

### As a CLI

```bash
git clone https://github.com/art8engine/viralman
cd viralman
python3 -m venv .venv
.venv/bin/pip install flask
.venv/bin/pip install -e .

mkdir -p ~/.local/bin
cat > ~/.local/bin/viralman <<'SH'
#!/usr/bin/env bash
exec "$HOME/path/to/viralman/.venv/bin/python" "$HOME/path/to/viralman/bin/viralman" "$@"
SH
chmod +x ~/.local/bin/viralman
```

> **Python 3.14**: setuptools' editable install relies on executable `.pth` files, which 3.14 disables. The shim above bypasses that and is the recommended path on 3.14+.

### Credentials (one-time)

Recommended — pick a channel in one command:

```bash
/viralman-setup                    # choose a category (gitmail / twitter / reddit / linkedin) → configure only that channel
/viralman-setup gitmail            # jump straight to the gitmail branch
/viralman-setup --check            # list currently saved keys
```

Legacy — if you want to configure a single channel by itself:

```bash
/viralman-login-reddit       # ~3 min, free
/viralman-login-twitter      # ~5 min, free tier (~1,500 posts/month)
/viralman-login-linkedin     # ~10 min, OAuth + 60-day token refresh
/viralman-login-gitmail      # ~5 min, GitHub token + SMTP + one LLM API key
```

Or skip the API key: if you have **Claude Code** installed, viralman auto-detects the local `claude` binary and routes LLM calls through it (your Claude Max quota applies). Pick provider `claude (Max via CLI)` in the dashboard.

Secrets stay out of the LLM context — skills pipe them via `read -s` into `~/.viralman/.env` (`chmod 600`).

## Just say it (Claude Code agent mode)

You don't have to memorize commands. Inside Claude Code, viralman ships as a plugin with skills that auto-trigger on natural-language intent. Saying any of the following gets the agent to do the right thing:

- *"set up viralman"* / *"viralman 셋업"* / *"viralman 깔아줘"* / *"set up gitmail credentials"* → `/viralman-setup` is the single entry point. Step 0 detects whether the package itself is installed and auto-bootstraps if needed (clone, venv, flask, shim, verify). Then it asks which channel to configure (gitmail / twitter / reddit / linkedin) and saves only that one. Plain-text token paste is allowed with a security warning; the recommended path is `read -s` so secrets never enter the chat log.
- *"open the dashboard"* / *"대시보드 띄워줘"* / *"打开面板"* / *"ダッシュボード を 開いて"* → launches `http://localhost:8765`. If viralman isn't bootstrapped yet, the agent runs install first, then the dashboard.
- *"email people who starred similar repos"* / *"이 프로젝트 홍보메일 보내줘"* → 5-step interactive gitmail flow: project → tone/emphasis → seed repos or keywords → recipients review → dry-run preview → live send.
- *"write a launch post for X"* / *"AI 같지 않게 트윗 써줘"* → drafts a non-AI-feeling post via the `viral-writer` agent + `ai-tell-sniffer` review pass.

The agent will ask for missing inputs once, never twice. It will refuse to proceed when something's hard-to-reverse (live send, OAuth save) without your explicit OK.

If you prefer typed commands, every natural-language intent has an explicit slash form — see the Usage section below.

## Usage

### Dashboard (recommended)

```bash
viralman                              # → http://localhost:8765
```

The dashboard walks the 4-step flow:

1. **Project** — name, URL, one-line pitch, description.
2. **Generate** — pick channels (X / Reddit / Gitmail), get drafts.
3. **Targets** — pick subreddits, hashtags, comment threads, recipient list. Each is auto-suggested from your project keywords.
4. **Send** — confirm, watch live progress.

### Slash commands

```bash
/viral our open-source K8s autoscaler cut a real prod bill by 47% in 3 weeks
/viral --mode casual-hype "we shipped the gnarliest race-condition fix of my life"
/viral --only reddit,x "looking for r/programming feedback on this go regex lib"
/viral --lang ko "..."

/dashboard                                       # opens the web UI
/gitmail https://github.com/you/jvm-monitor
```

### gitmail — 5-step interactive flow (CLI or slash)

One slash command is all it takes:

```bash
/gitmail https://github.com/you/jvm-monitor
```

You'll be walked through 5 steps:
1. **Target** — GitHub URL or a free-form description
2. **Tone & emphasis** — free-form input like "friendly developer tone" or "47% cost reduction"
3. **Recipients** — set max_users + seed repos directly, or search by keyword
4. **Collect & review** — preview recipients before confirming send
5. **Draft & send** — dry-run preview → confirm → live send

To run the 2-phase flow directly from the CLI:

```bash
# Phase 1: collect (seed repos specified directly)
./scripts/gitmail.py recipients \
  --seed-repos jvm-profiling/async-profiler,oracle/graal \
  --max-users 100 \
  --provider claude \
  > recipients.json

# Phase 2: dry-run with tone & emphasis applied
./scripts/gitmail.py send-from-recipients \
  --recipients-file recipients.json \
  --project-name jvm-monitor \
  --description "JVM monitoring SaaS" \
  --tone "friendly developer, keep it short" \
  --emphasis "free, OSS, JVM monitoring" \
  --dry-run

# After review — send for real (drop --dry-run)
./scripts/gitmail.py send-from-recipients \
  --recipients-file recipients.json \
  --project-name jvm-monitor \
  --description "JVM monitoring SaaS" \
  --tone "friendly developer, keep it short" \
  --emphasis "free, OSS, JVM monitoring"
```

### gitmail CLI (one-shot)

```bash
./scripts/gitmail.py run \
  --description "A K8s autoscaler in Go that cuts cost by 47%" \
  --project-name k8s-autoscaler \
  --project-url https://github.com/you/k8s-autoscaler \
  --max-users 100 \
  --provider claude \
  --dry-run
```

The `run` subcommand accepts the same new flags:

```bash
./scripts/gitmail.py run \
  --description "JVM monitoring SaaS" \
  --tone "casual" \
  --emphasis "free, OSS" \
  --seed-repos jvm-profiling/async-profiler \
  --max-users 100 \
  --dry-run
```

### New flags

- `--tone "..."` — free-form mail tone ("friendly developer", "technical detail", "keep it short")
- `--emphasis "..."` — free-form emphasis ("47% cost reduction", "free, OSS")
- `--seed-repos owner/repo,...` — skip the search step; collect stargazers directly from these repos
- `--keywords k1,k2` — use explicit keywords instead of auto-analysis
- `--topics t1,t2` — topics override

Every email gets a one-click unsubscribe link plus a `List-Unsubscribe` header. SMTP is rate-limited (default 30/min, override via `SMTP_RATE_PER_MIN`).

## How "doesn't feel AI" actually works

The `ai-tell-sniffer` agent runs on every draft. It checks for banned phrases ("delve", "leverage", "let's dive in", "supercharge", and ~20 more), em-dash density above 1 per 60 words, balanced tricolons, closing moralizers, hashtag stuffing, and posts with no concrete anchor (number, name, time, or admission). Three rewrite passes. If flagged content remains, it surfaces to you with warnings and refuses to auto-post.

Korean output also gets 12 pattern checks (활용하여 / 결론적으로 / "X 아니라 Y" forms, etc.), moralizer detection, and em-dash density analysis.

Every send path — dashboard, CLI slash command, direct script — shares the same unsubscribe log. An address unsubscribed once is automatically skipped in every future campaign, keeping policy consistent across all channels.

## Status

181 regression tests guard behavior and policy (Flask routes, AI-tell EN/KO, OAuth, MIME RFC, i18n parity, unsubscribe consistency, 5-step user story).

v0.3.0 — 5-step interactive gitmail flow + `/viralman-setup` unified credential entry + `--tone` / `--emphasis` / `--seed-repos` flags. The local dashboard and the original `/viral` flow from v0.1.0 are unchanged.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md). Security issues: [`SECURITY.md`](SECURITY.md).

## License

MIT.
