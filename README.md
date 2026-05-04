<p align="center">
  <img src="assets/viralman.png" alt="viralman" width="520">
</p>

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

---

Local dashboard + multi-platform poster + targeted outreach for open-source maintainers. Paste a link, get platform-tuned drafts that don't read like AI, and let viralman send them under your own accounts — only after you say yes.

```bash
viralman                 # opens http://localhost:8765 in your browser
```

> 이런 내용으로 바이럴해줘: 우리 팀이 만든 오픈소스 K8s autoscaler가 비용을 47% 줄였다

You get three drafts — one per platform — that don't read like AI slop, plus a one-key confirm before anything goes live.

## What viralman does

| | What |
|---|---|
| **`/viral`** | One intent → platform-tuned drafts for **Reddit**, **X**, and **LinkedIn**. AI-tell sniffer scrubs each draft against ~30 heuristics until it stops smelling like a chatbot. |
| **`viralman`** | Local dashboard at `http://localhost:8765`. Three pages — twitter / reddit / gitmail — switch from the header. OAuth login per platform. |
| **`/gitmail`** | Tell us about your project. We find the GitHub repos most like yours, walk their stargazers, resolve public emails, and send each one a short, personalized note (Claude / GPT / Gemini, your choice). One-click unsubscribe baked in. |
| Safety | Always-confirm by default. Sniffer can refuse to ship a draft. Rate limits on every send. Secrets go through `read -s`, not the LLM. |

## The dashboard

Three pages, dark theme, header switches between them.

- **Twitter** — paste a draft, watch char count + sniffer flags update live, post via the API or fall back to the compose URL.
- **Reddit** — subreddit + title + flair + body. Built-in checks for Reddit-specific tells (no hashtags, anchored claims).
- **gitmail** — drag the slider (1 to 10,000 target users), pick an LLM provider, hit start. Live progress: analyse → search repos → collect emails → compose → send. Per-recipient preview pane.

## How "doesn't feel AI" actually works

The `ai-tell-sniffer` agent runs on every draft, looking for:

- Banned phrases — "delve", "tapestry", "leverage", "navigate the landscape", "it's not just X — it's Y", "let's dive in", "supercharge", and ~20 more.
- Em-dash density above 1 per 60 words.
- Balanced tricolons. Closing moralizers. Hashtag stuffing.
- Generic-claim posts with no anchor — every draft must contain a number, a name, a time anchor, or an admission of doubt.

Three rewrite passes. If it still trips flags, the cleanest version is shown to you with the warnings surfaced — and viralman refuses to auto-post it.

## Install

### As a Claude Code plugin

```bash
claude plugin marketplace add https://github.com/art8engine/viralman
claude plugin install viralman
```

### As a CLI (so the literal `viralman` word works in your shell)

```bash
git clone https://github.com/art8engine/viralman
cd viralman
python3 -m venv .venv
.venv/bin/pip install flask
.venv/bin/pip install -e .

# create a one-line shim so viralman is on your PATH from anywhere
mkdir -p ~/.local/bin
cat > ~/.local/bin/viralman <<'SH'
#!/usr/bin/env bash
exec "$HOME/path/to/viralman/.venv/bin/python" "$HOME/path/to/viralman/bin/viralman" "$@"
SH
chmod +x ~/.local/bin/viralman
```

> **Heads up — Python 3.14**: setuptools' editable install relies on executable `.pth` files, which 3.14 disables. The shim above bypasses that and is the recommended path on 3.14+.

### Credentials (one-time, per platform)

Four dedicated skills walk you through each setup. Run only the ones you need:

```
/viralman-login-reddit       # ~3 min, free
/viralman-login-twitter      # ~5 min, free tier (~1,500 posts/month)
/viralman-login-linkedin     # ~10 min, OAuth dance + 60-day token refresh
/viralman-login-gitmail      # ~5 min, GitHub token + SMTP + one LLM API key
```

**Secrets never enter the LLM context** — the skills have you pipe passwords and tokens through `read -s` directly into a save script. Credentials end up in `~/.viralman/.env` with `chmod 600`.

## Usage

### Drafting + posting

```bash
# default: drafts for all three platforms, growth-story mode, ask before posting
/viral our open-source K8s autoscaler cut a real prod bill by 47% in 3 weeks

# pick mode
/viral --mode casual-hype "we shipped the gnarliest race-condition fix of my life"

# pick targets
/viral --only reddit,x "looking for r/programming feedback on this go regex lib"

# Korean output
/viral --lang ko "..."
```

### Dashboard

```bash
viralman                              # → http://localhost:8765
viralman --port 9000 --no-browser
```

### gitmail outreach

```bash
./scripts/gitmail.py run \
  --description "A K8s autoscaler in Go that cuts cost by 47%" \
  --project-name k8s-autoscaler \
  --project-url https://github.com/you/k8s-autoscaler \
  --max-users 100 \
  --provider claude \
  --dry-run
```

Every email gets a one-click unsubscribe link plus a `List-Unsubscribe` header. SMTP is rate-limited to 30/min by default (override with `SMTP_RATE_PER_MIN`).

## Repo layout

```
viralman/
├── bin/viralman                    # `viralman` CLI entry → starts dashboard
├── pyproject.toml                  # `pip install -e .` registers the command
├── viralman_cli/                   # console-script package
├── dashboard/                      # Flask app (server, api, oauth, templates, static)
├── commands/                       # /viral, /dashboard, /gitmail
├── skills/                         # viral, dashboard, gitmail, viralman-login-*
├── agents/                         # viral-writer, ai-tell-sniffer, publisher
├── voice/                          # ai-tells, platform-norms, mode templates, reference corpus
├── scripts/                        # post_*.py, gitmail.py, dashboard.py, save_creds.py
│   └── lib/                        # creds, sniffer_check, github_search, llm_compose, smtp_send
├── tests/                          # sniffer + gitmail compose tests
├── examples/                       # end-to-end transcripts
└── assets/                         # README art
```

## Status

v0.2.0 — local dashboard + gitmail outreach + OAuth logins added. The original `/viral` flow from v0.1.0 is unchanged.

## License

MIT — fork, vendor, ship.
