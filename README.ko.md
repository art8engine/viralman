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

### Claude Code 플러그인

```bash
claude plugin marketplace add https://github.com/art8engine/viralman
claude plugin install viralman
```

### CLI

```bash
git clone https://github.com/art8engine/viralman
cd viralman
python3 -m venv .venv
.venv/bin/pip install flask
.venv/bin/pip install -e .

# 어디서든 viralman이 동작하도록 PATH에 shim
mkdir -p ~/.local/bin
cat > ~/.local/bin/viralman <<'SH'
#!/usr/bin/env bash
exec "$HOME/path/to/viralman/.venv/bin/python" "$HOME/path/to/viralman/bin/viralman" "$@"
SH
chmod +x ~/.local/bin/viralman
```

> **Python 3.14**: setuptools editable install이 쓰는 실행 가능한 `.pth` 파일을 3.14가 막아놨다. 위 shim이 권장 경로.

### 자격증명 (한 번만)

권장 — 한 명령으로 채널을 고르세요:

```bash
/viralman-setup                    # 카테고리 선택 (gitmail / twitter / reddit / linkedin) → 그 채널만 설정
/viralman-setup gitmail            # 바로 gitmail 분기로
/viralman-setup --check            # 현재 저장된 키 목록만 확인
```

레거시 — 채널 하나만 따로 손볼 때:

```bash
/viralman-login-reddit       # 약 3분, 무료
/viralman-login-twitter      # 약 5분, 무료 티어 (월 ~1,500 포스트)
/viralman-login-linkedin     # 약 10분, OAuth + 60일 토큰 갱신
/viralman-login-gitmail      # 약 5분, GitHub 토큰 + SMTP + LLM API 키 1개
```

API 키 없이 가도 된다: **Claude Code**가 깔려 있으면 viralman이 로컬 `claude` 바이너리를 자동으로 감지해 LLM 호출을 그쪽으로 위임한다 (Claude Max plan quota 그대로). 대시보드에서 provider를 `claude (Max via CLI)`로 고르면 끝.

비밀값은 LLM 컨텍스트에 안 들어간다. `read -s`로 직접 `~/.viralman/.env` (mode 600)에 저장.

## 자연어로 시키기 (Claude Code 에이전트 모드)

명령 외울 필요 없습니다. Claude Code 안에서 viralman은 플러그인으로 동작하고, 스킬들이 자연어 의도에 자동 발화합니다. 다음 중 아무거나 말씀하시면 에이전트가 알아서 처리합니다:

- *"viralman 깔아줘"* / *"install viralman"* → 부트스트랩: 필요하면 clone, .venv 생성, flask + viralman 설치, `viralman` shim PATH에 설치, 대시보드 응답 확인. 멱등성 — 두 번 돌려도 안전합니다.
- *"대시보드 띄워줘"* / *"open the dashboard"* → `http://localhost:8765` 실행. viralman이 아직 안 깔려 있으면 자동으로 install 먼저 진행, 그 다음 대시보드.
- *"viralman 자격증명 저장해줘"* / *"set up gitmail"* → `/viralman-setup`이 발화돼서 필요한 채널만 저장. 채팅창에 평문 토큰 붙여넣기도 가능하지만 (경고 후 진행), 권장은 `read -s`로 비밀값이 LLM 컨텍스트에 안 남게.
- *"이 프로젝트 홍보메일 보내줘"* / *"비슷한 레포 사용자한테 메일"* → 5단계 인터랙티브 gitmail 흐름: 대상 → 톤·강조 → 시드 repo 또는 키워드 → 수신자 검토 → dry-run 미리보기 → 실발송.
- *"AI 같지 않게 트윗 써줘"* / *"이번 출시 Reddit 글"* → `viral-writer` 에이전트가 초안, `ai-tell-sniffer`가 리뷰·리라이트.

누락된 입력은 한 번만 물어봅니다. 되돌리기 어려운 동작(실발송, OAuth 저장)은 명시적 동의 없이 진행하지 않습니다.

직접 슬래시 명령을 치고 싶으시면 모든 자연어 의도에 대응하는 명시적 슬래시 형태가 있습니다 — 아래 사용법 섹션 참고.

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
