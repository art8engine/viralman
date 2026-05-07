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
- "gitmail 셋업", "set up gitmail" (채널 이름이 포함되어 있으면 해당 채널로 자동 분기)
- "twitter for viralman", "set up twitter for viralman"
- "reddit for viralman", "set up reddit for viralman"
- "linkedin for viralman", "set up linkedin for viralman"

**한국어**:
- "viralman 자격증명 저장해줘", "API 키 저장", "OAuth 등록"
- "viralman 키 등록", "twitter 자격증명 저장", "reddit 인증"
- "viralman 깔아줘", "viralman 설치해줘", "viralman 부트스트랩", "viralman 기본 세팅"

**English**:
- "save my viralman credentials", "register viralman api key"
- "configure viralman auth", "set up viralman tokens"
- "install viralman", "set up viralman from scratch", "bootstrap viralman", "make viralman work"

**中文**:
- "保存 viralman 凭证", "配置 viralman 密钥"
- "安装 viralman", "把 viralman 装好"

**日本語**:
- "viralman の認証情報を保存", "viralman の API キーを設定"
- "viralman をインストール", "viralman をセットアップ"

## Boundaries (read before starting)

- **Never accept secrets in chat without warning.** Show the warning in Step 1
  once; after the user confirms, proceed silently with `--set`.
- **Never** run `read -s` yourself — it must land in the user's terminal.
- **Never** read, echo, or cat `~/.viralman/.env`. Only `--show-keys` is safe.
- **Do not** WebFetch any platform dashboard (logged-in surfaces).
- One channel per invocation. Do not touch other channels.
- No live sends or posts after setup — read-only verification only.

---

## Step 0 — environment check (auto-bootstrap if needed)

자격증명을 다루기 전에 viralman 자체가 동작하는지 먼저 확인합니다.

1. **viralman binary 탐색** — 이 순서로:
   a. `which viralman 2>/dev/null` — 있으면 사용
   b. `test -x ~/.local/bin/viralman` — 있으면 사용
   c. `git rev-parse --show-toplevel`이 viralman repo 루트(`.claude-plugin/marketplace.json`의 `name: viralman` 확인)이고 `<root>/.venv/bin/python`이 있으면 사용
   d. `~/.claude/plugins/cache/*/viralman/*/.venv/bin/python` — 가장 최신 버전
   e. **모두 없음** → 부트스트랩 필요

2. **부트스트랩이 필요하면** — 다음 절차를 그 자리에서 진행합니다:
   - REPO 위치 결정 (CWD git toplevel → plugin cache → `--path` → `~/viralman` clone)
   - `python3 -m venv .venv` (Python 3.10+ 확인)
   - `.venv/bin/pip install --upgrade pip`
   - `.venv/bin/pip install flask`
   - Python 3.13 이하면: `.venv/bin/pip install -e .` (editable). Python 3.14+이면 editable 스킵 (shim이 dispatch).
   - `~/.local/bin/viralman` shim 작성 + `chmod +x`
   - `~/.local/bin`이 PATH에 없으면 사용자에게 추가 안내문 출력 (자동 수정하지 않음)
   - `~/.local/bin/viralman --no-browser --port 8765` 백그라운드 1.5초, 응답 확인 후 종료
   - 검증 OK 메시지

3. **이미 설치되어 있으면** — Step 0.5(자동 업데이트)로 진행.

**경계**:
- sudo 사용 금지
- shell rc 자동 수정 금지 (안내만)
- venv 외 글로벌 pip 설치 금지
- `git clone`은 `$HOME` 외부로 가지 않음 (`--path` 명시 시 예외)

---

## Step 0.5 — auto-update (이미 설치된 경우)

신버전이 published 되어 있으면 사용자에게 알리고 업데이트한 뒤 Step 1로 넘어갑니다.

1. **현재 버전 확인** — Step 0에서 찾은 install 경로 기반으로:
   - 플러그인 설치 (`~/.claude/plugins/cache/.../viralman/`): 해당 폴더의 `.claude-plugin/plugin.json` 에서 `version`
   - pipx 설치 (`~/.local/pipx/venvs/viralman/`): `pipx list --short 2>/dev/null | awk '$1=="viralman"{print $2}'`
   - 로컬 clone: `<repo>/.claude-plugin/plugin.json` 의 `version`

2. **최신 버전 확인** (네트워크 1회):
   ```bash
   curl -fsSL --max-time 4 \
     https://raw.githubusercontent.com/art8engine/viralman/main/.claude-plugin/plugin.json \
     | python3 -c 'import json,sys; print(json.load(sys.stdin)["version"])'
   ```
   네트워크 실패 또는 4초 타임아웃이면 조용히 스킵(오프라인 환경일 수 있음).

3. **버전이 다르면** — 사용자에게 한 줄 안내 후 install 타입에 맞는 업데이트 실행:
   - 플러그인 설치: 직접 실행 불가. **사용자에게** 다음 두 슬래시 명령을 차례로 입력하도록 요청한 뒤 대기 (Claude Code에는 `/plugin update <name>` 단일 명령은 없습니다 — 반드시 marketplace 갱신 + reload 2단계).
     ```
     /plugin marketplace update viralman
     /plugin install viralman
     ```
     그 다음 새 세션을 시작하거나 `/reload-plugins` (있으면) 로 적용.
   - pipx 설치: `pipx install --force git+https://github.com/art8engine/viralman`
   - 로컬 clone: `cd <repo> && git pull --ff-only && .venv/bin/pip install --upgrade .` (3.14+ 는 editable 스킵, shim 그대로)

4. 업데이트 후 새 `version`이 latest와 일치하는지 재확인. 일치하면 Step 1로 진행. 불일치면 사용자에게 수동 업데이트 안내 출력 후 그래도 Step 1 진행.

**경계**:
- 버전 비교 실패(curl 에러, 파싱 에러)는 무조건 스킵. 절대 Step 1을 차단하지 않음.
- 사용자에게 묻지 않고 강제로 force-reinstall 하지 않음 — pipx `--force`도 신버전이 detected 되었을 때만.

---

## Step 1 — pick a channel

사용자가 `gitmail 셋업`, `set up twitter for viralman`처럼 채널 이름이 포함된 어구를 사용했다면, 카테고리 선택 단계는 자동으로 그 채널로 정해진 것으로 간주합니다. Step 1 질문을 건너뛰고 해당 채널 분기(Step 3a/3b/3c/3d)로 바로 이동하세요.

If `$ARGUMENTS` already contains the category, skip this. Otherwise ask once:

```
어떤 채널을 셋업하시겠어요?

  1. gitmail  — GitHub 스타거 대상으로 콜드 메일 발송 (이번에 가장 많이 쓰는 흐름)
  2. twitter  — X 트윗 자동 게시 (선택 — 기본은 compose URL 폴백)
  3. reddit   — 서브레딧 게시
  4. linkedin — LinkedIn 게시

번호 또는 이름으로 답해주세요.
```

Accept `1`–`4` or names. If the answer is still unclear after one follow-up, stop.

---

## Step 2 — plain-text warning (conditional)

Trigger if: `--plain` flag given, **or** the user pasted something that looks
like a token (`ghp_…`, `sk-…`, long alphanumeric, Bearer prefix).

Print **once**:

> ⚠ 토큰을 채팅창에 평문으로 입력하셨습니다. 이 내용은 LLM 컨텍스트와 대화
> 로그에 남을 수 있습니다.
>
> 더 안전한 방법:
> `read -rs -p '<KEY>: ' s && printf '%s' "$s" | ./scripts/save_creds.py --stdin <KEY>; unset s; echo`
>
> 그래도 진행하시면 `./scripts/save_creds.py --set <KEY>=<VALUE>`로 저장합니다.

Ask "진행할까요? y/n". On yes → use `--set` for this and all remaining keys.
On no → present the `read -s` pipe pattern for each key instead.

---

## Step 3a — gitmail branch

Needs three credential bundles: GitHub, SMTP, and one LLM provider.

**GitHub token** — direct the user to `https://github.com/settings/tokens?type=beta`,
Fine-grained token, Public Repositories read-only. Save:

```bash
read -rs -p 'GITHUB_TOKEN: ' s && printf '%s' "$s" | \
  ./scripts/save_creds.py --stdin GITHUB_TOKEN; unset s; echo
```

Verify: `./scripts/lib/github_search.py ratelimit` (expect 5000 req/hr).

**SMTP** — any provider. Gmail shortcut:

```bash
./scripts/save_creds.py --set SMTP_HOST=smtp.gmail.com --set SMTP_PORT=587 --set SMTP_SECURITY=starttls
./scripts/save_creds.py --set SMTP_USER=<gmail> --set SMTP_FROM=<gmail> --set SMTP_FROM_NAME='<name>'
read -rs -p 'gmail app password: ' s && printf '%s' "$s" | \
  ./scripts/save_creds.py --stdin SMTP_PASSWORD; unset s; echo
```

For SendGrid/Mailgun/SES: set `SMTP_HOST`, `SMTP_PORT=587`, `SMTP_USER=apikey`,
`SMTP_FROM`, then pipe `SMTP_PASSWORD` the same way.

**LLM provider** — check for Claude Code first (`which claude && claude --version`).
If found, no key needed. Otherwise save one of:

```bash
# Claude
read -rs -p 'ANTHROPIC_API_KEY: ' s && printf '%s' "$s" | \
  ./scripts/save_creds.py --stdin ANTHROPIC_API_KEY; unset s; echo
# OpenAI
read -rs -p 'OPENAI_API_KEY: ' s && printf '%s' "$s" | \
  ./scripts/save_creds.py --stdin OPENAI_API_KEY; unset s; echo
# Gemini
read -rs -p 'GEMINI_API_KEY: ' s && printf '%s' "$s" | \
  ./scripts/save_creds.py --stdin GEMINI_API_KEY; unset s; echo
```

Verify end-to-end: `./scripts/gitmail.py analyse "A quick test project"`.
Done: "gitmail is hooked up — go to `http://localhost:8765/gitmail` and start
a dry-run job."

---

## Step 3b — twitter branch

First ask whether they need API access or the compose-URL default is sufficient
(one tweet at a time, no setup). If they choose the default, exit here.

For API setup: direct the user to `https://developer.twitter.com/en/portal/dashboard`.
Create a project + app (`viralman-<handle>`), set permissions to **Read and
write**, add callback `http://localhost:8765`, then generate Keys and tokens.
**Regenerate Access Token after setting Read+Write** — pre-upgrade tokens are
read-only.

Save handle (non-secret): `./scripts/save_creds.py --set TWITTER_HANDLE=<handle>`

Save four secrets via `read -s` (one command per key):
`TWITTER_API_KEY`, `TWITTER_API_SECRET`, `TWITTER_ACCESS_TOKEN`,
`TWITTER_ACCESS_SECRET` — each piped to `./scripts/save_creds.py --stdin`.

Verify: `./scripts/check_creds.py --platform twitter`
→ `twitter OK — @<handle> (id=...)`.

Common failures: `403` = still Read-only (regenerate tokens); `401` = tokens
pre-dated the permission change; `429` = monthly free-tier cap hit.

Done: "X is hooked up. `/viral --only x` now posts via the API."

---

## Step 3c — reddit branch

Direct the user to `https://www.reddit.com/prefs/apps`. Create a **script**
type app (not web, not installed) named `viralman`, redirect URI
`http://localhost:8765`. Note the **CLIENT_ID** (short string under app name)
and **CLIENT_SECRET** ("secret" field).

Save non-secrets:

```bash
./scripts/save_creds.py --set REDDIT_CLIENT_ID=<client_id>
./scripts/save_creds.py --set REDDIT_USERNAME=<username>
./scripts/save_creds.py --set REDDIT_USER_AGENT='viralman/0.1.0 by <username>'
```

Save secrets via `read -s`:

```bash
read -rs -p 'reddit client_secret: ' s && printf '%s' "$s" | \
  ./scripts/save_creds.py --stdin REDDIT_CLIENT_SECRET; unset s; echo
read -rs -p 'reddit password: ' s && printf '%s' "$s" | \
  ./scripts/save_creds.py --stdin REDDIT_PASSWORD; unset s; echo
```

Note: Reddit 2FA breaks PRAW password auth. Use a dedicated account without
2FA, or disable 2FA on this account.

Verify: `./scripts/check_creds.py --platform reddit` → `reddit OK — u/<username>`.

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

Save client_id: `./scripts/save_creds.py --set LINKEDIN_CLIENT_ID=<id>`

Save client_secret:

```bash
read -rs -p 'LINKEDIN_CLIENT_SECRET: ' s && printf '%s' "$s" | \
  ./scripts/save_creds.py --stdin LINKEDIN_CLIENT_SECRET; unset s; echo
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
subprocess.run(["./scripts/save_creds.py","--stdin","LINKEDIN_ACCESS_TOKEN"],
    input=resp["access_token"], text=True, check=True)
PY
unset code; echo
```

**Capture person URN**:

```bash
./scripts/check_creds.py --platform linkedin
# output: linkedin OK — <name> (sub=<id>)
# hint: set LINKEDIN_PERSON_URN=urn:li:person:<id>
./scripts/save_creds.py --set LINKEDIN_PERSON_URN=urn:li:person:<id>
```

Re-run `check_creds.py --platform linkedin` — hint should disappear.

Common failures: redirect URI mismatch (`Bummer` error on auth page); `401
invalid_token` = token expired, re-run OAuth steps; `403 ACCESS_DENIED` =
"Share on LinkedIn" product not added.

Done: "LinkedIn is hooked up. Token expires in 60 days — re-run
`/viralman-setup linkedin` (skip app setup, just redo OAuth steps) to refresh."

---

## Step 4 — final key-list confirmation

After any channel completes, run `./scripts/save_creds.py --show-keys` and
confirm that the expected keys for that channel are present:

| Channel  | Required keys                                                            |
|----------|--------------------------------------------------------------------------|
| gitmail  | GITHUB_TOKEN, SMTP_HOST/PORT/SECURITY/USER/FROM/PASSWORD, + one LLM key |
| twitter  | TWITTER_HANDLE, TWITTER_API_KEY/SECRET, TWITTER_ACCESS_TOKEN/SECRET      |
| reddit   | REDDIT_CLIENT_ID/SECRET, REDDIT_USERNAME, REDDIT_PASSWORD, USER_AGENT   |
| linkedin | LINKEDIN_CLIENT_ID/SECRET, LINKEDIN_ACCESS_TOKEN, LINKEDIN_PERSON_URN   |

If any expected key is missing from the list, flag it and offer to re-run the
relevant sub-step.
