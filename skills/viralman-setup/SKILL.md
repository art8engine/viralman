---
name: viralman-setup
description: Single entry point that asks the user which channel to configure (gitmail / twitter / reddit / linkedin), then walks them through saving only that channel's credentials. Supports plain-text token paste with a security warning, in addition to the recommended `read -s` pipe.
level: 2
---

# viralman-setup Skill

Unified credential setup for all viralman channels. One invocation = one
channel. Run once per channel you want to activate.

## Trigger phrases

- `/viralman-setup`
- "viralman 셋업", "viralman setup"
- "set up viralman", "viralman 설정 도와줘"
- "viralman credentials", "viralman 자격증명 설정"
- "gitmail 셋업", "set up gitmail" (if a channel name is part of the phrase, auto-route to that channel)
- "twitter for viralman", "set up twitter for viralman"
- "reddit for viralman", "set up reddit for viralman"
- "linkedin for viralman", "set up linkedin for viralman"

**Korean**:
- "viralman 자격증명 저장해줘", "API 키 저장", "OAuth 등록"
- "viralman 키 등록", "twitter 자격증명 저장", "reddit 인증"
- "viralman 깔아줘", "viralman 설치해줘", "viralman 부트스트랩", "viralman 기본 세팅"

**English**:
- "save my viralman credentials", "register viralman api key"
- "configure viralman auth", "set up viralman tokens"
- "install viralman", "set up viralman from scratch", "bootstrap viralman", "make viralman work"

**Chinese**:
- "保存 viralman 凭证", "配置 viralman 密钥"
- "安装 viralman", "把 viralman 装好"

**Japanese**:
- "viralman の認証情報を保存", "viralman の API キーを設定"
- "viralman をインストール", "viralman をセットアップ"

## Boundaries (read before starting)

- **Never accept secrets in chat without warning.** Show the warning in Step 2
  once; after the user confirms, proceed silently with `--set`.
- **Never** run `read -s` yourself — it must land in the user's terminal.
- **Never** read, echo, or cat `~/.viralman/.env`. Only `--show-keys` is safe.
- **Do not** WebFetch any platform dashboard (logged-in surfaces).
- One channel per invocation. Do not touch other channels.
- No live sends or posts after setup — read-only verification only.

---

## Step 0 — environment check (auto-bootstrap if needed)

Before touching credentials, verify viralman itself runs.

1. **Locate the viralman binary** — try in this order:
   a. `which viralman 2>/dev/null` — use it if present
   b. `test -x ~/.local/bin/viralman` — use it if present
   c. `git rev-parse --show-toplevel` is the viralman repo root (confirm via `name: viralman` in `.claude-plugin/marketplace.json`) AND `<root>/.venv/bin/python` exists → use it
   d. `~/.claude/plugins/cache/*/viralman/*/.venv/bin/python` — newest version
   e. **None of the above** → bootstrap is required

2. **If bootstrap is required**, run this in place:
   - Decide REPO location (CWD git toplevel → plugin cache → `--path` → clone into `~/viralman`)
   - `python3 -m venv .venv` (require Python 3.10+)
   - `.venv/bin/pip install --upgrade pip`
   - `.venv/bin/pip install flask`
   - On Python ≤ 3.13: `.venv/bin/pip install -e .` (editable). On Python 3.14+: skip editable (the shim dispatches).
   - Write `~/.local/bin/viralman` shim + `chmod +x`
   - If `~/.local/bin` is not on PATH, print the addition guidance (do not auto-edit shell rc)
   - Run `~/.local/bin/viralman --no-browser --port 8765` in the background for 1.5 s, confirm response, then stop it
   - Print the verification OK message

3. **If already installed**, proceed to Step 0.5 (auto-update).

**Boundaries**:
- No sudo
- No auto-edit of shell rc files (advisory only)
- No global pip install outside the venv
- `git clone` never targets paths outside `$HOME` (exception: explicit `--path`)

---

## Step 0.5 — auto-update (when already installed)

If a newer version is published, tell the user and update before continuing to Step 1.

1. **Detect the current version** based on the install path found in Step 0:
   - Plugin install (`~/.claude/plugins/cache/.../viralman/`): `version` field in that folder's `.claude-plugin/plugin.json`
   - pipx install (`~/.local/pipx/venvs/viralman/`): `pipx list --short 2>/dev/null | awk '$1=="viralman"{print $2}'`
   - Local clone: `version` in `<repo>/.claude-plugin/plugin.json`

2. **Check the latest version** (one network call):
   ```bash
   curl -fsSL --max-time 4 \
     https://raw.githubusercontent.com/art8engine/viralman/main/.claude-plugin/plugin.json \
     | python3 -c 'import json,sys; print(json.load(sys.stdin)["version"])'
   ```
   On network failure or 4 s timeout, skip silently (offline is fine).

3. **If the versions differ**, give the user a one-line notice and run the update for that install type:
   - Plugin install: cannot be done directly. **Ask the user** to run the two slash commands below in order, then wait (Claude Code does not have a single `/plugin update <name>` — must do marketplace refresh + reload as two steps).
     ```
     /plugin marketplace update viralman
     /plugin install viralman
     ```
     Then start a new session, or `/reload-plugins` (if available) to apply.
   - pipx install: `pipx install --force git+https://github.com/art8engine/viralman`
   - Local clone: `cd <repo> && git pull --ff-only && .venv/bin/pip install --upgrade .` (skip editable on 3.14+, keep the shim)

4. After updating, re-check that the new `version` matches latest. If yes, proceed to Step 1. If no, print manual update guidance but proceed to Step 1 anyway.

**Boundaries**:
- Any version-check failure (curl error, parse error) → skip silently. Never block Step 1.
- Never force-reinstall without the user's go-ahead — pipx `--force` only when a newer version was actually detected.

---

## Step 1 — pick a channel

If the user's phrase already names a channel (e.g. "gitmail 셋업", "set up twitter for viralman"), treat the channel as decided. Skip the question and jump to that channel's branch (Step 3a/3b/3c/3d).

If `$ARGUMENTS` already contains the category, skip this. Otherwise ask once:

```
Which channel do you want to set up?

  1. gitmail  — cold email outreach to GitHub stargazers (most common)
  2. twitter  — automated X/Twitter posting (optional — default falls back to compose URL)
  3. reddit   — subreddit posting
  4. linkedin — LinkedIn posting

Reply with the number or the name.
```

Accept `1`–`4` or names. If the answer is still unclear after one follow-up, stop.

---

## Step 2 — plain-text warning (conditional)

Trigger if: `--plain` flag given, **or** the user pasted something that looks
like a token (`ghp_…`, `sk-…`, long alphanumeric, Bearer prefix).

Print **once**:

> ⚠ You pasted a token in plain text in this chat. The contents may be
> retained in the LLM context and the conversation log.
>
> Safer alternative:
> `read -rs -p '<KEY>: ' s && printf '%s' "$s" | viralman save-creds --stdin <KEY>; unset s; echo`
>
> If you continue anyway, the token will be saved via `viralman save-creds --set <KEY>=<VALUE>`.

Ask "Proceed? y/n". On yes → use `--set` for this and all remaining keys.
On no → present the `read -s` pipe pattern for each key instead.

---

## Step 3a — gitmail branch

Needs three credential bundles: GitHub, SMTP, and one LLM provider.

**GitHub token** — direct the user to `https://github.com/settings/tokens?type=beta`,
Fine-grained token, Public Repositories read-only. Save:

```bash
read -rs -p 'GITHUB_TOKEN: ' s && printf '%s' "$s" | \
  viralman save-creds --stdin GITHUB_TOKEN; unset s; echo
```

Verify: `curl -fsS -H "Authorization: Bearer $(grep ^GITHUB_TOKEN= ~/.viralman/.env | cut -d= -f2-)" https://api.github.com/rate_limit | python3 -c 'import json,sys; print(json.load(sys.stdin)["resources"]["core"]["limit"])'` (expect 5000).

**SMTP** — any provider. Gmail shortcut:

```bash
viralman save-creds --set SMTP_HOST=smtp.gmail.com --set SMTP_PORT=587 --set SMTP_SECURITY=starttls
viralman save-creds --set SMTP_USER=<gmail> --set SMTP_FROM=<gmail> --set SMTP_FROM_NAME='<name>'
read -rs -p 'gmail app password: ' s && printf '%s' "$s" | \
  viralman save-creds --stdin SMTP_PASSWORD; unset s; echo
```

For SendGrid/Mailgun/SES: set `SMTP_HOST`, `SMTP_PORT=587`, `SMTP_USER=apikey`,
`SMTP_FROM`, then pipe `SMTP_PASSWORD` the same way.

**LLM provider** — check for Claude Code first (`which claude && claude --version`).
If found, no key needed. Otherwise save one of:

```bash
# Claude
read -rs -p 'ANTHROPIC_API_KEY: ' s && printf '%s' "$s" | \
  viralman save-creds --stdin ANTHROPIC_API_KEY; unset s; echo
# OpenAI
read -rs -p 'OPENAI_API_KEY: ' s && printf '%s' "$s" | \
  viralman save-creds --stdin OPENAI_API_KEY; unset s; echo
# Gemini
read -rs -p 'GEMINI_API_KEY: ' s && printf '%s' "$s" | \
  viralman save-creds --stdin GEMINI_API_KEY; unset s; echo
```

**Public unsubscribe base (required for real sends, optional for dry-runs)** —
every outgoing mail carries an `Unsubscribe: <base>/u/<token>` link. If
`VIRALMAN_UNSUBSCRIBE_BASE` is unset and the user runs a real send,
gitmail aborts with a clear error rather than emit a localhost link
recipients can't click. Save once:

```bash
viralman save-creds --set VIRALMAN_UNSUBSCRIBE_BASE=https://your-domain.example.com
```

The host needs the dashboard's `/u/<token>` route reachable on the open
internet. If the user doesn't have a public deployment yet, point them at
options like a tunnel (`cloudflared tunnel`, `ngrok`) or skipping the
real-send step until they do — dry-runs work without it.

Verify end-to-end: `viralman gitmail analyse "A quick test project"`.
Done: "gitmail is hooked up — go to `http://localhost:8765/gitmail` and start
a dry-run job."

---

## Step 3b — twitter branch

First ask whether they need API posting or the compose-URL default is enough
(one tweet at a time, no setup). If they pick the default, exit here.

For API posting there are **two paths**. Recommend OAuth 2.0 unless the user
already has 4 OAuth 1.0a keys saved.

### Default — OAuth 2.0 PKCE via dashboard (recommended)

One browser click; refresh tokens auto-renew. No 4-token paste.

1. **App setup** — go to `https://developer.twitter.com/en/portal/dashboard`,
   create an app under any project. In the app's **User authentication
   settings**: enable OAuth 2.0, type **Confidential client**, app permissions
   **Read and write**, callback URL
   `http://127.0.0.1:8765/oauth/twitter/callback`. Save Client ID + Client Secret.

2. **Save the client values**:

   ```bash
   viralman save-creds --set TWITTER_HANDLE=<handle>
   viralman save-creds --set TWITTER_OAUTH2_CLIENT_ID=<id>
   read -rs -p 'TWITTER_OAUTH2_CLIENT_SECRET: ' s && printf '%s' "$s" | \
     viralman save-creds --stdin TWITTER_OAUTH2_CLIENT_SECRET; unset s; echo
   ```

3. **Run the OAuth flow** — start the dashboard locally, then open the start URL:

   ```bash
   .venv/bin/python -m dashboard.server --host 127.0.0.1 --port 8765 &
   open http://127.0.0.1:8765/oauth/twitter/start
   ```

   X's "Authorize app" page → redirected back to `127.0.0.1:8765/oauth/twitter/callback`,
   which exchanges the code, persists `TWITTER_OAUTH2_BEARER` and
   `TWITTER_OAUTH2_REFRESH` to `~/.viralman/.env`, then renders a green
   "connected" page.

4. **Verify**:

   ```bash
   viralman save-creds --show-keys | grep TWITTER_OAUTH2
   ```

   Expect 4 keys: `TWITTER_OAUTH2_CLIENT_ID`, `TWITTER_OAUTH2_CLIENT_SECRET`,
   `TWITTER_OAUTH2_BEARER`, `TWITTER_OAUTH2_REFRESH`.

`viralman post-twitter` prefers the OAuth 2.0 bearer; on a 401 it auto-refreshes
using the refresh token and persists the rotated pair.

### Legacy — OAuth 1.0a 4-key (fallback)

Keep this only if the user already has the 4 keys configured. New users should
use OAuth 2.0 above.

App permissions **Read and write**, generate Keys and tokens. **Regenerate the
Access Token *after* setting Read+Write** — pre-upgrade tokens are read-only.

```bash
viralman save-creds --set TWITTER_HANDLE=<handle>
# four secrets, each via read -s | viralman save-creds --stdin:
#   TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET
```

Verify: `viralman check-creds --platform twitter`
→ `twitter OK — @<handle> (id=...)`.

### Common failures

- `403` = app still Read-only (regenerate tokens / re-authorize).
- `401` after a previous success → OAuth 2.0 refresh token expired or app
  permissions revoked; re-run the OAuth flow above.
- `429` = monthly free-tier cap.

Done: "X is hooked up. `/viral --only x` posts via the v2 Tweets endpoint."

---

## Step 3c — reddit branch

Direct the user to `https://www.reddit.com/prefs/apps`. Create a **script**
type app (not web, not installed) named `viralman`, redirect URI
`http://localhost:8765`. Note the **CLIENT_ID** (short string under app name)
and **CLIENT_SECRET** ("secret" field).

Save non-secrets:

```bash
viralman save-creds --set REDDIT_CLIENT_ID=<client_id>
viralman save-creds --set REDDIT_USERNAME=<username>
viralman save-creds --set REDDIT_USER_AGENT='viralman/0.1.0 by <username>'
```

Save secrets via `read -s`:

```bash
read -rs -p 'reddit client_secret: ' s && printf '%s' "$s" | \
  viralman save-creds --stdin REDDIT_CLIENT_SECRET; unset s; echo
read -rs -p 'reddit password: ' s && printf '%s' "$s" | \
  viralman save-creds --stdin REDDIT_PASSWORD; unset s; echo
```

Note: Reddit 2FA breaks PRAW password auth. Use a dedicated account without
2FA, or disable 2FA on this account.

Verify: `viralman check-creds --platform reddit` → `reddit OK — u/<username>`.

Common failures: `401`/`invalid_grant` = whitespace in secret (re-run `read -s`),
wrong app type, or 2FA active.

Done: "Reddit is hooked up. `/viral --only reddit --subreddit <name>` will post."

---

## Step 3d — linkedin branch

LinkedIn requires a browser OAuth flow. Tokens expire in 60 days; re-run
Steps 3–5 (below) to refresh without repeating app setup.

**App setup** — user goes to `https://www.linkedin.com/developers/apps`,
creates an app tied to a company/org page (free personal page is fine). In the
**Products** tab, request both "Sign In with LinkedIn using OpenID Connect" and
"Share on LinkedIn" (auto-approved). In the **Auth** tab, add redirect URL
`http://localhost:8765/callback` and note Client ID + Client Secret.

Save client_id: `viralman save-creds --set LINKEDIN_CLIENT_ID=<id>`

Save client_secret:

```bash
read -rs -p 'LINKEDIN_CLIENT_SECRET: ' s && printf '%s' "$s" | \
  viralman save-creds --stdin LINKEDIN_CLIENT_SECRET; unset s; echo
```

**OAuth flow** — construct and print this URL (fill in the saved client_id):

```
https://www.linkedin.com/oauth/v2/authorization?response_type=code
  &client_id=<LINKEDIN_CLIENT_ID>
  &redirect_uri=http%3A%2F%2Flocalhost%3A8765%2Fcallback
  &scope=openid%20profile%20email%20w_member_social
  &state=<random_8_chars>
```

User opens URL, clicks Allow, browser redirects to a localhost URL that won't
load. They copy the `code=` parameter from the address bar.

**Token exchange** — have the user run:

```bash
read -rs -p 'LinkedIn auth code: ' code && \
  python3 - "$code" <<'PY'
import sys; sys.path.insert(0, "scripts/lib")
from creds import load
import urllib.parse, urllib.request, json, subprocess
c = load()
data = urllib.parse.urlencode({"grant_type":"authorization_code","code":sys.argv[1],
    "redirect_uri":"http://localhost:8765/callback",
    "client_id":c["LINKEDIN_CLIENT_ID"],"client_secret":c["LINKEDIN_CLIENT_SECRET"]}).encode()
resp = json.loads(urllib.request.urlopen(urllib.request.Request(
    "https://www.linkedin.com/oauth/v2/accessToken", data=data,
    headers={"Content-Type":"application/x-www-form-urlencoded"})).read())
print("token_received_chars:", len(resp.get("access_token","")))
subprocess.run(["viralman save-creds","--stdin","LINKEDIN_ACCESS_TOKEN"],
    input=resp["access_token"], text=True, check=True)
PY
unset code; echo
```

**Capture person URN**:

```bash
viralman check-creds --platform linkedin
# output: linkedin OK — <name> (sub=<id>)
# hint: set LINKEDIN_PERSON_URN=urn:li:person:<id>
viralman save-creds --set LINKEDIN_PERSON_URN=urn:li:person:<id>
```

Re-run `viralman check-creds --platform linkedin` — hint should disappear.

Common failures: redirect URI mismatch (`Bummer` error on auth page); `401
invalid_token` = token expired, re-run OAuth steps; `403 ACCESS_DENIED` =
"Share on LinkedIn" product not added.

Done: "LinkedIn is hooked up. Token expires in 60 days — re-run
`/viralman-setup linkedin` (skip app setup, just redo OAuth steps) to refresh."

---

## Step 4 — final key-list confirmation

After any channel completes, run `viralman save-creds --show-keys` and
confirm that the expected keys for that channel are present:

| Channel  | Required keys                                                            |
|----------|--------------------------------------------------------------------------|
| gitmail  | GITHUB_TOKEN, SMTP_HOST/PORT/SECURITY/USER/FROM/PASSWORD, + one LLM key |
| twitter  | TWITTER_HANDLE + (OAuth 2.0: TWITTER_OAUTH2_CLIENT_ID / CLIENT_SECRET / BEARER / REFRESH) **or** (legacy: TWITTER_API_KEY / SECRET / ACCESS_TOKEN / ACCESS_SECRET) |
| reddit   | REDDIT_CLIENT_ID/SECRET, REDDIT_USERNAME, REDDIT_PASSWORD, USER_AGENT   |
| linkedin | LINKEDIN_CLIENT_ID/SECRET, LINKEDIN_ACCESS_TOKEN, LINKEDIN_PERSON_URN   |

If any expected key is missing from the list, flag it and offer to re-run the
relevant sub-step.

---

## Step 5 — Pre-approve viralman commands (optional but recommended)

Claude Code's permission layer prompts the user (and the auto-mode classifier may flag-and-block) on each fresh `viralman <subcommand>` invocation, and viralman's most common gitmail flows trigger this on **every collect/send call**. The fix is a one-time edit to `~/.claude/settings.json` — but **the agent must NOT self-edit it**. Claude Code's harness blocks agent-driven permission self-grants. The agent must surface the snippet and stop.

After Step 4 completes, present this block verbatim to the user (Korean default; mirror the user's language if they've been speaking another):

```
권한 프롬프트를 매번 통과하지 않으시려면 ~/.claude/settings.json 의
permissions.allow 배열에 아래 한 줄을 추가해 주세요 (한 번만 paste, 새
세션부터 적용):

  "Bash(viralman:*)"

이 한 줄로 viralman 의 모든 subcommand (gitmail, twitter-reply,
save-creds, post-*, check-creds, ...) 가 커버됩니다.

⚠ auto-mode classifier 는 별개 레이어라, 대량 발송 류 명령
(예: viralman gitmail recipients --max-users 500) 은 위 룰을
추가하셔도 한 번 권한 다이얼로그가 뜰 수 있습니다. 그땐 한 번만 Allow
누르시면 됩니다.

이 스킬은 settings.json 을 직접 편집하지 않습니다 — Claude Code 의 harness 가
agent 의 self-permission-grant 를 차단하므로, 위 내용을 사용자께서 직접
paste 해주셔야 합니다.
```

Then **stop** — do not run a follow-up command, do not offer to "edit it for you", do not call any tool that touches `~/.claude/settings.json`. Wait for the user to confirm they've pasted (or to skip).

This step is the canonical mitigation for the cross-project permission friction described in the gitmail / twitter-reply skill pre-flights. Users who skip this will keep hitting the permission dialog on every run; that's their call, not the agent's to bypass.
