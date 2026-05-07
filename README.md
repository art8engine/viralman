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

Three paths. Path 1 is the easy default; Path 2 if you don't use Claude Code; Path 3 for CI / scripting.

> You can follow the manual setup below, but installing the Claude Code plugin (Path 1) and asking the agent to walk you through setup is the recommended path.

### Path 1 — Claude Code plugin (recommended)

Marketplace/plugin install (recommended for most Claude Code users). These are Claude Code slash commands — enter them one at a time (pasting both lines at once will fail):

```
/plugin marketplace add https://github.com/art8engine/viralman
```

Then:

```
/plugin install viralman
```

From a local clone of the repo, swap the URL for `./`:

```
/plugin marketplace add ./
```

Once installed, just talk to the agent — `"open the dashboard"`, `"set up viralman"`, `"email people who starred async-profiler"` — and it dispatches the right slash command (`/dashboard`, `/viralman-setup`, `/gitmail`, `/viral`). Before any send, it asks (1) language (2) subject style (3) final OK.

### Path 2 — pipx install (no Claude Code needed)

If you prefer the local dashboard + bare CLI without Claude Code:

```bash
pipx install git+https://github.com/art8engine/viralman
viralman   # → http://localhost:8765
```

`pipx` installs into an isolated venv and exposes `viralman` on your `$PATH`. Plain `pip install git+...` also works inside an existing venv. The 4-tab dashboard (Twitter / Reddit / Gitmail / Setup) covers everything; slash commands require Claude Code.

### Path 3 — Clone + run (CI / headless / automation)

For explicit CLI args from a script or CI pipeline:

```bash
git clone https://github.com/art8engine/viralman && cd viralman
pip install .
./scripts/gitmail.py run --description "..." --max-users 100 --dry-run
```

See [Usage](#usage) below for the full gitmail / viral flag list.

## Examples

### Block A — Natural language inside Claude Code (Path 1)

Just say it in plain English — the agent picks the right slash command:

```
"set up viralman for me"
"email people who starred async-profiler about our JVM monitoring tool"
"write a post for r/programming, make it not feel AI"
"open the dashboard"
"set up viralman"
```

The agent fires `/gitmail`, `/viral`, `/dashboard`, or `/viralman-setup` automatically.
Before any send, it asks (1) language (2) subject style (3) final OK — in that order.

### Block B — Slash commands directly (Path 1 power users)

```
/viralman-setup gitmail
/gitmail https://github.com/myuser/myproj
/gitmail --seed-repos jvm-profiling/async-profiler --tone "friendly developer" --emphasis "47% cost reduction"
/dashboard
/viral our K8s autoscaler cut prod costs 47% in 3 weeks --mode growth-story
```

### Block C — Direct script (Path 3 / CI / headless)

```bash
# 1) Save credentials
read -rs -p 'GITHUB_TOKEN: ' s && printf '%s' "$s" | ./scripts/save_creds.py --stdin GITHUB_TOKEN; unset s
./scripts/save_creds.py --set SMTP_HOST=smtp.gmail.com --set SMTP_PORT=587 --set SMTP_USER=you@gmail.com --set SMTP_FROM=you@gmail.com
read -rs -p 'SMTP_PASSWORD: ' s && printf '%s' "$s" | ./scripts/save_creds.py --stdin SMTP_PASSWORD; unset s

# 2) Collect recipients (seed repos specified directly)
./scripts/gitmail.py recipients \
  --seed-repos jvm-profiling/async-profiler,oracle/graal \
  --max-users 100 > recipients.json

# 3) Dry-run with tone, emphasis, and subject style applied — review before sending
./scripts/gitmail.py send-from-recipients \
  --recipients-file recipients.json \
  --project-name myproj \
  --description "JVM monitoring SaaS" \
  --tone "friendly developer, keep it short" \
  --emphasis "47% cost reduction" \
  --subject-style headline \
  --dry-run

# 4) Drop --dry-run to send for real after review
./scripts/gitmail.py send-from-recipients \
  --recipients-file recipients.json \
  --project-name myproj \
  --description "JVM monitoring SaaS" \
  --tone "friendly developer, keep it short" \
  --emphasis "47% cost reduction" \
  --subject-style headline
```

## Sample gitmail output

### Korean auto-generated (default)

Calling with no options writes in Korean (system default):

```
SUBJECT: 안녕하세요, 이제 당신도 쉽게 사이드 프로젝트를 알릴 수 있습니다.

안녕하세요, 저희 오픈소스 viralman 도구를 알려드리고자 메일을 보냈습니다.

이제 당신은 본인의 사이드 프로젝트를 자연스럽게 알릴 수 있습니다.

AI가 프로젝트를 분석해 어울리는 홍보 멘트를 만들어주고, 관심을 가질 만한 개발자에게 메일 발송까지 도와드립니다.

당신의 사이드 프로젝트를 쉽게 바이럴 해보세요.

관심이 있다면 이 링크를 확인하세요: https://github.com/art8engine/viralman
```

### English (via natural-language `--tone "in English"`)

Add `--tone "in English"` (or natural-language equivalents like `영어로 써줘` / `中文で`) to switch:

```
SUBJECT: Hi, now you can easily share your side project too.

Hi, we're reaching out to share our open-source project viralman.

Now you can easily get your own side project in front of the developers most likely to care about it.

The AI reads your repository, drafts a natural outreach note in your voice, and helps you deliver it to a relevant audience.

Try giving your side project the reach it deserves, without the awkward self-promotion.

If you're curious, here is the link: https://github.com/art8engine/viralman
```

## Credentials

```bash
/viralman-setup            # pick a channel (gitmail / twitter / reddit / linkedin) and configure it
/viralman-setup gitmail    # jump straight to gitmail
/viralman-setup --check    # list saved keys
```

Per-channel legacy commands: `/viralman-login-reddit` (~3 min), `/viralman-login-twitter` (~5 min), `/viralman-login-linkedin` (~10 min), `/viralman-login-gitmail` (~5 min).

No API key needed: if **Claude Code** is installed, viralman auto-detects the local `claude` binary and routes LLM calls through it (Claude Max quota). Pick `claude (Max via CLI)` in the dashboard.

Secrets never enter the LLM context — piped via `read -s` into `~/.viralman/.env` (`chmod 600`).

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
