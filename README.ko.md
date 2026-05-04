<p align="center">
  <img src="assets/viralman.png" alt="viralman" width="520">
</p>

<h1 align="center">viralman</h1>

<p align="center">
  <b>당신의 코드는 당신이. 바이럴은 우리가.</b><br>
  만들기만 하세요 — 홍보는 바이럴맨이 할게요.
</p>

<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.ko.md"><b>한국어</b></a> ·
  <a href="README.zh.md">中文</a> ·
  <a href="README.ja.md">日本語</a>
</p>

---

오픈소스 메인테이너를 위한 로컬 대시보드 + 멀티플랫폼 포스터 + 타게팅 아웃리치 도구. 한 줄 의도를 던지면 AI 티 안 나는 플랫폼별 초안을 만들어주고, 당신 계정으로 발행 — 단, 당신이 OK 한 후에만.

```bash
viralman                 # 브라우저에서 http://localhost:8765 자동 오픈
```

> 이런 내용으로 바이럴해줘: 우리 팀이 만든 오픈소스 K8s autoscaler가 비용을 47% 줄였다

세 개 플랫폼 초안이 한 번에 나오고 — AI슬롭 같은 표현 없이 — 발행 전 한 번 더 확인합니다.

## viralman이 하는 일

| | 무엇 |
|---|---|
| **`/viral`** | 한 줄 의도 → **Reddit / X / LinkedIn**용 플랫폼별 초안. AI-tell 스니퍼가 약 30가지 휴리스틱으로 챗봇 냄새를 빼냅니다. |
| **`viralman`** | 로컬 대시보드 (`http://localhost:8765`). 세 페이지 — twitter / reddit / gitmail — 헤더에서 즉시 전환. 플랫폼별 OAuth 로그인. |
| **`/gitmail`** | 당신 프로젝트를 알려주면, 깃허브에서 가장 비슷한 레포를 찾아 그걸 별표한 사람들의 공개 이메일을 수집하고 — Claude / GPT / Gemini 골라서 — 짧고 개인화된 메일을 보냅니다. 원클릭 구독해지 자동 포함. |
| 안전장치 | 기본은 항상-확인. 스니퍼가 발행을 거부할 수 있음. 모든 발송에 rate limit. 비밀값은 `read -s`로만, LLM 컨텍스트에 안 들어감. |

## 대시보드

세 페이지, 다크 테마, 헤더로 즉시 전환.

- **Twitter** — 본문 입력하면 글자 수 + 스니퍼 플래그가 실시간 업데이트. API 발행 또는 compose URL 폴백.
- **Reddit** — 서브레딧 + 타이틀 + 플레어 + 본문. 레딧 특유의 패턴 검사 (해시태그 0개 룰, 앵커 검사 등).
- **gitmail** — 1~10,000명 슬라이더, LLM 프로바이더 선택, 시작. 라이브 진행 표시: analyse → 레포 검색 → 이메일 수집 → 작성 → 발송. 수신자별 미리보기.

## "AI 같지 않게" 작동 원리

`ai-tell-sniffer` 에이전트가 모든 초안을 검사:

- 금지 표현 — "delve", "tapestry", "leverage", "navigate the landscape", "let's dive in", "supercharge", 그 외 약 20개.
- 60단어당 em-dash 1개 초과.
- 균형 잡힌 3-tricolon. 마무리 모럴라이저. 해시태그 남발.
- 앵커 없는 일반 주장 — 모든 초안에 숫자/이름/시간/회의(疑) 중 최소 하나 필수.

3회 리라이트 후에도 플래그가 남으면, 가장 깨끗한 버전을 경고와 함께 보여주고 — 자동 발행은 거부합니다.

## 설치

### Claude Code 플러그인으로

```bash
claude plugin marketplace add https://github.com/art8engine/viralman
claude plugin install viralman
```

### CLI로 (`viralman` 한 단어를 셸에서 쓰려면)

```bash
git clone https://github.com/art8engine/viralman
cd viralman
python3 -m venv .venv
.venv/bin/pip install flask
.venv/bin/pip install -e .

# 어디서든 viralman이 동작하도록 PATH에 shim 하나 만들기
mkdir -p ~/.local/bin
cat > ~/.local/bin/viralman <<'SH'
#!/usr/bin/env bash
exec "$HOME/path/to/viralman/.venv/bin/python" "$HOME/path/to/viralman/bin/viralman" "$@"
SH
chmod +x ~/.local/bin/viralman
```

> **참고 — Python 3.14**: setuptools editable install이 쓰는 실행 가능한 `.pth` 파일을 Python 3.14가 비활성화했습니다. 위 shim 방식이 3.14+에서 권장됩니다.

### 자격증명 (한 번만, 플랫폼별)

필요한 것만 실행하세요:

```
/viralman-login-reddit       # 약 3분, 무료
/viralman-login-twitter      # 약 5분, 무료 티어 (월 ~1,500 포스트)
/viralman-login-linkedin     # 약 10분, OAuth + 60일 토큰 갱신
/viralman-login-gitmail      # 약 5분, GitHub 토큰 + SMTP + LLM API 키 1개
```

**비밀값은 LLM 컨텍스트에 절대 안 들어갑니다** — 스킬이 `read -s`로 직접 저장 스크립트에 파이프하도록 안내합니다. 자격증명은 `~/.viralman/.env`에 `chmod 600`으로 저장됩니다.

## 사용법

### 초안 작성 + 발행

```bash
# 기본: 세 플랫폼 모두, growth-story 모드, 발행 전 확인
/viral 우리 팀이 만든 오픈소스 K8s 오토스케일러가 3주 만에 실 운영 비용을 47% 줄였다

# 모드 지정
/viral --mode casual-hype "내 인생 가장 골때리는 race condition을 잡았다"

# 타겟 지정
/viral --only reddit,x "이 Go regex 라이브러리에 대한 r/programming 피드백 받고 싶음"

# 한국어 출력
/viral --lang ko "..."
```

### 대시보드

```bash
viralman                              # → http://localhost:8765
viralman --port 9000 --no-browser
```

### gitmail 아웃리치

```bash
./scripts/gitmail.py run \
  --description "비용을 47% 줄여주는 Go 기반 K8s 오토스케일러" \
  --project-name k8s-autoscaler \
  --project-url https://github.com/you/k8s-autoscaler \
  --max-users 100 \
  --provider claude \
  --dry-run
```

모든 메일에 원클릭 구독해지 링크 + `List-Unsubscribe` 헤더가 들어갑니다. SMTP는 기본 분당 30건 제한 (`SMTP_RATE_PER_MIN`로 변경 가능).

## 저장소 구조

```
viralman/
├── bin/viralman                    # `viralman` CLI 엔트리 → 대시보드 시작
├── pyproject.toml                  # `pip install -e .`로 명령어 등록
├── viralman_cli/                   # console-script 패키지
├── dashboard/                      # Flask 앱 (server, api, oauth, templates, static)
├── commands/                       # /viral, /dashboard, /gitmail
├── skills/                         # viral, dashboard, gitmail, viralman-login-*
├── agents/                         # viral-writer, ai-tell-sniffer, publisher
├── voice/                          # ai-tells, platform-norms, 모드 템플릿, 레퍼런스 코퍼스
├── scripts/                        # post_*.py, gitmail.py, dashboard.py, save_creds.py
│   └── lib/                        # creds, sniffer_check, github_search, llm_compose, smtp_send
├── tests/                          # 스니퍼 + gitmail 작성 테스트
├── examples/                       # 엔드투엔드 트랜스크립트
└── assets/                         # README 아트
```

## 상태

v0.2.0 — 로컬 대시보드 + gitmail 아웃리치 + OAuth 로그인 추가. v0.1.0의 `/viral` 플로우는 그대로.

## 라이선스

MIT — 포크, 벤더링, 출시 모두 자유.
