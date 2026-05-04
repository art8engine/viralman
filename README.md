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

Local dashboard + multi-platform poster + targeted outreach for open-source maintainers. One project description in, platform-tuned drafts and recipient lists out. Posts go live only after you confirm.

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

### Credentials (one-time, per platform)

```
/viralman-login-reddit       # ~3 min, free
/viralman-login-twitter      # ~5 min, free tier (~1,500 posts/month)
/viralman-login-linkedin     # ~10 min, OAuth + 60-day token refresh
/viralman-login-gitmail      # ~5 min, GitHub token + SMTP + one LLM API key
```

Secrets stay out of the LLM context — skills pipe them via `read -s` into `~/.viralman/.env` (`chmod 600`).

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
/gitmail "A K8s autoscaler in Go" --max-users 100 --dry-run
```

### gitmail CLI

```bash
./scripts/gitmail.py run \
  --description "A K8s autoscaler in Go that cuts cost by 47%" \
  --project-name k8s-autoscaler \
  --project-url https://github.com/you/k8s-autoscaler \
  --max-users 100 \
  --provider claude \
  --dry-run
```

Every email gets a one-click unsubscribe link plus a `List-Unsubscribe` header. SMTP is rate-limited (default 30/min, override via `SMTP_RATE_PER_MIN`).

## How "doesn't feel AI" actually works

The `ai-tell-sniffer` agent runs on every draft. It checks for banned phrases ("delve", "leverage", "let's dive in", "supercharge", and ~20 more), em-dash density above 1 per 60 words, balanced tricolons, closing moralizers, hashtag stuffing, and posts with no concrete anchor (number, name, time, or admission). Three rewrite passes. If flagged content remains, it surfaces to you with warnings and refuses to auto-post.

## Status

v0.2.0 — local dashboard + gitmail outreach + OAuth logins. The original `/viral` flow from v0.1.0 is unchanged.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md). Security issues: [`SECURITY.md`](SECURITY.md).

## License

MIT.
