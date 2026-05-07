<h1 align="center">viralman</h1>

<p align="center">
  <b>코드는 너가, 바이럴은 우리가.</b><br>
  만들기만 해. 홍보는 바이럴맨이 한다.
</p>

<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.ko.md"><b>한국어</b></a> ·
  <a href="README.zh.md">中文</a> ·
  <a href="README.ja.md">日本語</a>
</p>

<p align="center">
  <img src="assets/viralman.png" alt="viralman" width="520">
</p>

---

프로젝트 설명을 넣으면 Twitter/X 포스트, Reddit 글, 그리고 비슷한 GitHub 레포에 ★ 누른 개발자들한테 보낼 콜드 메일 초안을 만들어준다. OSS든 사이드 프로젝트든 상관없다. 보낼지 말지는 네가 결정한다.

```bash
viralman                 # http://localhost:8765 자동으로 열림
```

## 주요 기능

- **멀티플랫폼 초안** — `/viral` 한 줄로 Reddit / X / LinkedIn 초안. AI 티 안 남.
- **로컬 대시보드** — 검정 4단계 마법사: 프로젝트 → 생성 → 타깃 → 발송. 로그인은 상단 한 곳.
- **gitmail 아웃리치** — GitHub에서 비슷한 레포 찾아 별표 누른 사람들에게 짧은 개인 메일. 최대 1만 명, 원클릭 구독해지 자동.
- **AI-tell 스니퍼** — 클리셰, em-dash 폭주, 정형 3-tricolon, 앵커 누락 등 30여 가지 룰 검사. 3번 리라이트 후에도 안 되면 자동 발행 거부.
- **OAuth 또는 수동** — 대시보드에서 X / Reddit / LinkedIn 로그인하거나 토큰 직접 입력. 비밀값은 LLM 컨텍스트에 절대 안 들어감.
- **멀티 LLM** — Claude / OpenAI / Gemini 중 선택. 저장된 키로 자동 감지.

## 이런 때 쓴다

- **v1.0 런칭** — 출시 내용 적으면 r/programming용 레딧 글, X 스레드, LinkedIn 공지, 그리고 비슷한 도구 별표한 개발자 명단까지 한 번에.
- **사이드 프로젝트 공지** — 세 플랫폼용으로 따로 안 써도 됨. 한 번 → 멀티 채널.
- **어디 올릴지 막막할 때** — viralman이 키워드로 서브레딧, 해시태그, 댓글 달 만한 최근 스레드 스크랩해서 추천.
- **유사 툴 별표 유저 재타깃** — gitmail이 공개 프로필/커밋 이메일로 명단 만들고, 어떤 레포 별표했는지 언급하는 오프닝으로 개인화.
- **AI 슬롭 회피** — 대부분의 "AI 소셜 포스터"는 한눈에 들킴. 스니퍼가 viralman의 핵심.

## 설치

세 가지 경로가 있습니다. 일반적으로는 방법 1을 권장드리고, Claude Code를 안 쓰시면 방법 2, CI·자동화 용도라면 방법 3입니다.

> 이 가이드의 세팅을 따라도 괜찮지만, 클로드코드 플러그인 (방법 1) 을 받아서 프롬프트에 세팅 도움을 요청하시는 것을 권장드립니다.

### 방법 1 — Claude Code 플러그인 (권장)

Claude Code 사용자 대부분에게 권장드리는 marketplace/plugin 설치입니다. 아래 두 줄은 Claude Code 슬래시 명령이라 **한 줄씩 따로 입력**해 주세요. (두 줄을 한 번에 붙여넣으면 실패합니다.)

```
/plugin marketplace add https://github.com/art8engine/viralman
```

이어서:

```
/plugin install viralman
```

레포를 이미 로컬에 클론해 두셨다면 URL 대신 `./` 도 됩니다:

```
/plugin marketplace add ./
```

설치 후에는 명령어를 외우실 필요 없이 그냥 자연어로 말씀하시면 됩니다 — `"대시보드 띄워줘"`, `"viralman 셋업해줘"`, `"async-profiler 스타거한테 메일 보내줘"` 처럼요. 에이전트가 알아서 `/dashboard`, `/viralman-setup`, `/gitmail`, `/viral` 중 맞는 명령을 실행합니다. 발송 직전에는 (1) 언어 (2) subject 스타일 (3) 최종 OK 순서로 확인해 드립니다.

### 방법 2 — pipx 설치 (Claude Code 불필요)

Claude Code 없이 로컬 대시보드 + CLI만 쓰고 싶으시다면:

```bash
pipx install git+https://github.com/art8engine/viralman
viralman   # → http://localhost:8765
```

`pipx` 가 격리된 venv를 만들어 `viralman` 명령을 `$PATH` 에 자동 등록해 줍니다. 이미 venv를 쓰고 계시면 `pip install git+...` 도 동일하게 동작합니다. 대시보드 4탭(Twitter / Reddit / Gitmail / Setup)에서 모든 작업이 가능하며, 슬래시 명령은 Claude Code가 있어야 동작합니다.

### 방법 3 — 클론 후 직접 실행 (CI / headless / 자동화)

스크립트나 CI 파이프라인에서 명시적 인자로 호출하시는 경우:

```bash
git clone https://github.com/art8engine/viralman && cd viralman
pip install .
./scripts/gitmail.py run --description "..." --max-users 100 --dry-run
```

전체 gitmail / viral 플래그 목록은 아래 [사용](#사용-예시) 섹션을 참고해 주세요.

## 사용 예시

### Block A — Claude Code 안에서 자연어로 (방법 1 사용자)

그냥 말하면 됩니다 — 에이전트가 알맞은 슬래시 명령을 직접 발화합니다:

```
"이 프로젝트 비슷한 레포 스타거한테 메일 보내줘"
"async-profiler 별표한 사람한테 우리 JVM 모니터링 도구 알려줘"
"r/programming용 글 써줘, AI 같지 않게"
"대시보드 띄워줘"
"viralman 셋업해줘"
```

에이전트가 `/gitmail`, `/viral`, `/dashboard`, `/viralman-setup`을 알아서 발화합니다.
발송 직전에는 (1) 언어 (2) subject 스타일 (3) 발송 OK 차례로 묻습니다.

### Block B — 슬래시 명령 직접 입력 (방법 1 파워유저)

```
/viralman-setup gitmail
/gitmail https://github.com/myuser/myproj
/gitmail --seed-repos jvm-profiling/async-profiler --tone "친근한 개발자" --emphasis "47% 비용 절감"
/dashboard
/viral 우리 K8s 오토스케일러가 3주 만에 비용 47% 줄였다 --mode growth-story
```

### Block C — 스크립트 직접 호출 (방법 3 / CI / headless)

```bash
# 1) 자격증명 저장
read -rs -p 'GITHUB_TOKEN: ' s && printf '%s' "$s" | ./scripts/save_creds.py --stdin GITHUB_TOKEN; unset s
./scripts/save_creds.py --set SMTP_HOST=smtp.gmail.com --set SMTP_PORT=587 --set SMTP_USER=you@gmail.com --set SMTP_FROM=you@gmail.com
read -rs -p 'SMTP_PASSWORD: ' s && printf '%s' "$s" | ./scripts/save_creds.py --stdin SMTP_PASSWORD; unset s

# 2) 수신자 수집 (시드 repo 직접 지정)
./scripts/gitmail.py recipients \
  --seed-repos jvm-profiling/async-profiler,oracle/graal \
  --max-users 100 > recipients.json

# 3) 톤·강조·subject 스타일 반영 dry-run — 발송 전 검토
./scripts/gitmail.py send-from-recipients \
  --recipients-file recipients.json \
  --project-name myproj \
  --description "JVM monitoring SaaS" \
  --tone "친근한 개발자, 짧게" \
  --emphasis "47% 비용 절감" \
  --subject-style headline \
  --dry-run

# 4) 검토 OK이면 --dry-run 빼고 다시 실행 → 실발송
./scripts/gitmail.py send-from-recipients \
  --recipients-file recipients.json \
  --project-name myproj \
  --description "JVM monitoring SaaS" \
  --tone "친근한 개발자, 짧게" \
  --emphasis "47% 비용 절감" \
  --subject-style headline
```

## 발송 예시

### 한국어 자동 생성 (기본)

별다른 옵션 없이 호출하면 한국어로 작성됩니다 (시스템 기본값):

```
SUBJECT: 안녕하세요, 이제 당신도 쉽게 사이드 프로젝트를 알릴 수 있습니다.

안녕하세요, 저희 오픈소스 viralman 도구를 알려드리고자 메일을 보냈습니다.

이제 당신은 본인의 사이드 프로젝트를 자연스럽게 알릴 수 있습니다.

AI가 프로젝트를 분석해 어울리는 홍보 멘트를 만들어주고, 관심을 가질 만한 개발자에게 메일 발송까지 도와드립니다.

당신의 사이드 프로젝트를 쉽게 바이럴 해보세요.

관심이 있다면 이 링크를 확인하세요: https://github.com/art8engine/viralman
```

### 영어 (자연어 `--tone "in English"` 또는 `--tone "영어로 써줘"`)

Add `--tone "in English"` (or natural-language equivalents like `영어로 써줘` / `中文で`) to switch:

```
SUBJECT: Hi, now you can easily share your side project too.

Hi, we're reaching out to share our open-source project viralman.

Now you can easily get your own side project in front of the developers most likely to care about it.

The AI reads your repository, drafts a natural outreach note in your voice, and helps you deliver it to a relevant audience.

Try giving your side project the reach it deserves, without the awkward self-promotion.

If you're curious, here is the link: https://github.com/art8engine/viralman
```

## 자격증명

```bash
/viralman-setup            # 채널 선택 (gitmail / twitter / reddit / linkedin) 후 설정
/viralman-setup gitmail    # gitmail 분기로 바로
/viralman-setup --check    # 저장된 키 목록 확인
```

채널별 레거시 명령: `/viralman-login-reddit` (~3분), `/viralman-login-twitter` (~5분), `/viralman-login-linkedin` (~10분), `/viralman-login-gitmail` (~5분).

API 키 없어도 됨: **Claude Code**가 깔려 있으면 viralman이 로컬 `claude` 바이너리를 자동 감지해 LLM 호출을 위임한다 (Claude Max plan quota). 대시보드에서 `claude (Max via CLI)` 선택.

비밀값은 LLM 컨텍스트에 안 들어간다 — `read -s`로 `~/.viralman/.env` (mode 600)에 직접 저장.

## 사용법

### 대시보드 (권장)

```bash
viralman                              # → http://localhost:8765
```

4단계:

1. **프로젝트** — 이름, URL, 한 줄 핏치, 설명.
2. **생성** — 채널 (X / Reddit / Gitmail) 골라서 초안 받기.
3. **타깃** — 서브레딧, 해시태그, 댓글 달 스레드, 수신자 명단. 다 자동 추천.
4. **발송** — 확인하고 라이브 진행.

### 슬래시 커맨드

```bash
/viral 우리 K8s 오토스케일러가 3주 만에 운영 비용 47% 줄였다
/viral --mode casual-hype "인생 최고 골때리는 race condition 잡았다"
/viral --only reddit,x "이 Go regex 라이브러리에 대한 r/programming 피드백 받고 싶음"
/viral --lang ko "..."

/dashboard                                       # 웹 UI
/gitmail https://github.com/you/jvm-monitor
```

### gitmail — 5단계 인터랙티브 흐름 (CLI 또는 슬래시)

슬래시 한 번이면 끝:

```bash
/gitmail https://github.com/you/jvm-monitor
```

5단계로 안내됩니다:
1. **대상 받기** — GitHub URL 또는 자유 설명
2. **톤·강조 받기** — "친근한 개발자 톤", "47% 비용 절감 강조" 같은 자유 입력
3. **타깃 받기** — max_users + 시드 repo 직접 지정 또는 키워드
4. **수집·검토** — recipients 미리보기 후 발송 확인
5. **작성·발송** — dry-run 미리보기 → 확정 → 실발송

CLI에서 직접 2-phase로 돌리려면:

```bash
# Phase 1: 수집 (시드 repo 직접 지정)
./scripts/gitmail.py recipients \
  --seed-repos jvm-profiling/async-profiler,oracle/graal \
  --max-users 100 \
  --provider claude \
  > recipients.json

# Phase 2: 톤·강조 반영 dry-run
./scripts/gitmail.py send-from-recipients \
  --recipients-file recipients.json \
  --project-name jvm-monitor \
  --description "JVM monitoring SaaS" \
  --tone "친근한 개발자, 짧게" \
  --emphasis "free, OSS, JVM monitoring" \
  --dry-run

# 검토 후 실발송 (--dry-run 빼고)
./scripts/gitmail.py send-from-recipients \
  --recipients-file recipients.json \
  --project-name jvm-monitor \
  --description "JVM monitoring SaaS" \
  --tone "친근한 개발자, 짧게" \
  --emphasis "free, OSS, JVM monitoring"
```

### gitmail CLI (1-shot)

```bash
./scripts/gitmail.py run \
  --description "비용 47% 줄이는 Go 기반 K8s 오토스케일러" \
  --project-name k8s-autoscaler \
  --project-url https://github.com/you/k8s-autoscaler \
  --max-users 100 \
  --provider claude \
  --dry-run
```

`run` 서브커맨드도 동일 인자를 받습니다:

```bash
./scripts/gitmail.py run \
  --description "JVM monitoring SaaS" \
  --tone "casual" \
  --emphasis "free, OSS" \
  --seed-repos jvm-profiling/async-profiler \
  --max-users 100 \
  --dry-run
```

### 새 인자

- `--tone "..."` — 메일 톤 자유 입력 ("친근한 개발자", "기술 디테일", "간결하게")
- `--emphasis "..."` — 강조점 자유 입력 ("47% 비용 절감", "free, OSS")
- `--seed-repos owner/repo,...` — 검색 단계 스킵, 그 repo의 stargazer만 직접 수집
- `--keywords k1,k2` — 자동 분석 결과 대신 사용자 키워드로 검색
- `--topics t1,t2` — topics override

모든 메일에 원클릭 구독해지 + `List-Unsubscribe` 헤더. SMTP 분당 30건 기본 (`SMTP_RATE_PER_MIN`로 변경).

## "AI 같지 않게" 어떻게 굴러가나

`ai-tell-sniffer`가 모든 초안 검사. 금지 표현 ("delve", "leverage", "let's dive in", "supercharge" 등 20+), 60단어당 em-dash 1개 초과, 균형 잡힌 3-tricolon, 마무리 모럴라이저, 해시태그 남발, 앵커 없는 일반 주장 (숫자/이름/시간/회의 중 하나 필수). 3번 리라이트 후에도 플래그 남으면 자동 발행 거부.

한국어 출력에도 12종 패턴 (활용하여 / 결론적으로 / "X 아니라 Y" 등) 검출 + 모럴라이저 + em-dash 밀도 검사가 적용됩니다.

모든 메일 발송 경로(대시보드, CLI 슬래시 명령, 직접 스크립트)는 같은 unsubscribe 로그를 공유합니다. 한 번 unsubscribe된 주소는 다음 캠페인에서 자동으로 스킵됩니다 — 양 경로의 정책이 일관됩니다.

## 상태

181 회귀 테스트로 동작·정책 보호 (Flask 라우트, AI-tell 영/한, OAuth, MIME RFC, i18n 파리티, unsubscribe 일관성, 5단계 사용자 스토리).

v0.3.0 — 5단계 인터랙티브 gitmail 흐름 + `/viralman-setup` 통합 자격증명 입력 + `--tone` / `--emphasis` / `--seed-repos` 인자. 로컬 대시보드와 v0.1.0의 `/viral`은 그대로.

## 기여

[`CONTRIBUTING.md`](CONTRIBUTING.md), [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md). 보안 이슈는 [`SECURITY.md`](SECURITY.md).

## 라이선스

MIT.
