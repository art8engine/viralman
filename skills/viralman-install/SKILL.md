---
name: viralman-install
description: One-time bootstrap that makes /dashboard, /gitmail, /viralman-setup all "just work". Detects existing viralman repos, creates the venv, installs flask + the package, drops a shim on PATH, verifies the dashboard responds. Idempotent — safe to re-run.
level: 2
---

# viralman-install Skill

viralman 환경을 처음부터 완전히 세팅합니다. venv 생성, flask 설치, PATH shim 배치, 대시보드 응답 확인까지 한 번에 처리합니다. 이미 설치된 것은 건드리지 않으므로 두 번 실행해도 안전합니다.

## Trigger phrases

Auto-trigger on:

- 슬래시: `/viralman-install`
- 한국어: "viralman 깔아줘", "viralman 설치해줘", "viralman 부트스트랩", "viralman 기본 세팅", "viralman 처음부터 설치", "viralman 환경 만들어줘"
- 영어: "install viralman", "set up viralman from scratch", "bootstrap viralman", "make viralman work", "viralman isn't installed", "set up the viralman environment"
- 中文: "安装 viralman", "把 viralman 装好", "初始化 viralman", "配置 viralman 环境"
- 日本語: "viralman をインストール", "viralman をセットアップ", "viralman の環境を作って", "viralman をインストールして"

### 유사 명령과 구분

| 사용자 말                                | 맞는 명령            |
|------------------------------------------|----------------------|
| "viralman 셋업", "viralman setup"        | 맥락에 따라 구분 필요 |
| "credentials / 자격증명 / API 키 설정"   | `/viralman-setup`    |
| "installation / 설치 / 깔기 / venv / pip" | **이 스킬**          |
| "gitmail 설정", "twitter 연결"           | `/viralman-setup`    |

모호한 경우 한 번만 물어보세요: "설치(venv·패키지)를 원하시나요, 아니면 자격증명(API 키·토큰) 설정을 원하시나요?"

---

## What this skill does

`commands/viralman-install.md` 에 정의된 절차를 그대로 따릅니다. 요약:

1. **Repo 탐지 또는 clone** — 현재 디렉터리, Claude Code 플러그인 캐시, `~/viralman` 순으로 탐색.
2. **venv 생성** — Python 3.10+ 확인 후 `.venv` 생성 (이미 있으면 스킵).
3. **의존성 설치** — `pip install flask`, Python < 3.14이면 `pip install -e .` 추가.
4. **shim 배치** — `~/.local/bin/viralman` 작성 + 실행 권한 부여.
5. **동작 확인** — 대시보드를 백그라운드로 기동해 HTTP 200 응답 체크.
6. **다음 단계 안내** — 자격증명 없으면 `/viralman-setup`, 있으면 `/gitmail` 또는 `/dashboard` 제안.

---

## Detection logic — 설치 경로 결정 (3단계 우선순위)

```
1순위: git repo 안에 있고 .claude-plugin/marketplace.json에 name: viralman 명시
       → REPO = git rev-parse --show-toplevel 결과

2순위: ~/.claude/plugins/cache/*/viralman/ 에 버전 디렉터리 존재
       → REPO = 가장 높은 버전 디렉터리
       (예: ~/.claude/plugins/cache/art8engine/viralman/0.3.0)

3순위: --path 옵션으로 지정된 경로, 없으면 ~/viralman
       → 경로 없으면 git clone https://github.com/art8engine/viralman <path>
       → 경로 있고 git repo면 git pull --ff-only (실패해도 계속 진행)
```

`REPO` 확정 후 반드시 사용자에게 출력: `REPO resolved to: <absolute path>`

---

## Step-by-step (ko/en 혼합)

### Step 1 — Repo 탐지 또는 clone

```bash
# 현재 위치가 viralman repo인지 확인
git rev-parse --show-toplevel 2>/dev/null
```

결과 경로에 `.claude-plugin/marketplace.json` 이 있고 `name: viralman` 이면 그 경로를 REPO로 확정.
없으면 플러그인 캐시 확인: `ls ~/.claude/plugins/cache/*/viralman/ 2>/dev/null`
둘 다 없으면 clone 또는 기존 `~/viralman` 사용.

### Step 2 — Python 버전 확인 + venv 생성

```bash
python3 --version   # 3.10+ 필요
```

3.10 미만이면 즉시 중단. 메시지:
> Python 3.10+ 필요. 현재 버전: `<version>`. 최신 Python을 설치 후 다시 실행해 주세요.

venv가 없거나 `--reinstall` 옵션이면:
```bash
python3 -m venv "$REPO/.venv"
```

### Step 3 — 패키지 설치

```bash
"$REPO/.venv/bin/pip" install --upgrade pip --quiet
"$REPO/.venv/bin/pip" install flask
```

Python 버전에 따라 분기:
- `< 3.14`: `"$REPO/.venv/bin/pip" install -e "$REPO"` — 편집 가능 설치로 repo 코드 직접 사용
- `>= 3.14`: editable install 스킵. 이유: setuptools의 `.pth` 실행이 3.14에서 비활성화됨.
  shim이 Python 인터프리터와 진입점을 직접 연결하므로 동일하게 동작.

### Step 4 — shim 배치 (`--no-shim` 없을 때)

```bash
mkdir -p ~/.local/bin
```

`~/.local/bin/viralman` 파일 내용 (REPO는 실제 절대경로로 치환):
```bash
#!/usr/bin/env bash
exec "<REPO>/.venv/bin/python" "<REPO>/bin/viralman" "$@"
```

```bash
chmod +x ~/.local/bin/viralman
```

PATH 확인:
```bash
echo "$PATH" | tr ':' '\n' | grep -qx "$HOME/.local/bin"
```

PATH에 없으면 사용자에게 출력 (rc 파일은 절대 직접 수정하지 않음):
> `~/.local/bin`이 PATH에 없습니다. 아래 줄을 `~/.zshrc` (또는 `~/.bashrc`)에 추가하세요:
> ```
> export PATH="$HOME/.local/bin:$PATH"
> ```
> 추가 후 `source ~/.zshrc` 또는 터미널 재시작.

### Step 5 — 동작 확인

```bash
~/.local/bin/viralman --no-browser --port 8765 &
VIRALMAN_PID=$!
sleep 2
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8765/twitter)
kill $VIRALMAN_PID 2>/dev/null
wait $VIRALMAN_PID 2>/dev/null
```

- HTTP 200 → 성공 메시지 출력 후 Step 6으로
- 그 외 → 실제 에러 출력 + 백그라운드 프로세스 종료 후 중단

---

## Recovery — 단계별 실패 처방

| 실패 상황 | 처방 |
|-----------|------|
| `git clone` 실패 (network, auth) | 에러 원문 그대로 표시 후 중단. VPN/방화벽 확인 또는 `--path`로 수동 경로 지정 안내. |
| `python3 --version` < 3.10 | 중단. pyenv/mise/homebrew로 최신 Python 설치 후 재실행 안내. |
| `python3 -m venv` 실패 | `python3-venv` 패키지 누락일 가능성 — `sudo apt install python3-venv` (Linux) 또는 Python 재설치(macOS) 안내. sudo는 venv 생성 자체엔 불필요. |
| `pip install flask` 실패 | pip 로그 원문 표시. 네트워크 차단이면 `--index-url`이나 mirror 설정 안내. |
| shim 생성 실패 (권한) | `~/.local/bin` 소유자 확인. sudo 사용 금지 — 소유권 문제면 `chown $USER ~/.local/bin` 안내. |
| PATH 누락 | rc 파일 수정하지 않음. 위의 `export PATH` 줄을 출력하고 사용자에게 직접 추가하도록 안내. |
| 대시보드 HTTP 200 아님 | curl 에러 또는 응답 바디 표시. 포트 충돌이면 `lsof -i :8765` 확인 안내. Flask 미설치는 Step 3 재실행. |
| Python 3.14 editable install 경고 | 정상 동작 — shim 방식이므로 무시해도 됨. Step 4 shim이 올바르게 배치됐는지 확인. |
| `--reinstall` 후에도 import 오류 | `.venv` 디렉터리를 수동으로 삭제 후 `--reinstall` 재실행. `rm -rf "$REPO/.venv"` 안내. |

---

## Idempotency (멱등성)

각 단계는 이미 완료된 상태를 감지하고 스킵합니다:

- Repo: 이미 존재하면 clone 스킵, `git pull --ff-only`만 시도
- venv: `.venv/bin/python` 존재하면 스킵 (`--reinstall` 없으면)
- pip: 이미 설치된 패키지는 pip이 알아서 스킵
- shim: 동일 내용이면 덮어쓰기 무방 (idempotent write)
- verify: 매 실행마다 수행 (상태 확인 목적)

---

## Boundaries

- **Never** `$HOME` 바깥에 clone (`--path` 없을 때).
- **Never** `sudo` 사용. 권한 필요 시 에러 출력 후 중단.
- **Never** shell rc 파일 (`~/.zshrc`, `~/.bashrc` 등) 직접 수정. 추가할 줄만 출력.
- **Never** venv 밖에 패키지 설치 (항상 `$REPO/.venv/bin/pip` 사용).
- `git clone` 실패 시 fallback 다운로드 시도 금지 — 에러 원문 표시 후 중단.
- 대시보드 verify 실패 시 백그라운드 프로세스를 반드시 종료 후 중단.
- 자격증명(API 키, 토큰) 설정은 이 스킬의 범위 밖 — `/viralman-setup`으로 안내.
