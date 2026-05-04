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

필요한 것만:

```
/viralman-login-reddit       # 약 3분, 무료
/viralman-login-twitter      # 약 5분, 무료 티어 (월 ~1,500 포스트)
/viralman-login-linkedin     # 약 10분, OAuth + 60일 토큰 갱신
/viralman-login-gitmail      # 약 5분, GitHub 토큰 + SMTP + LLM API 키 1개
```

비밀값은 LLM 컨텍스트에 안 들어간다. `read -s`로 직접 `~/.viralman/.env` (mode 600)에 저장.

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
/gitmail "Go 기반 K8s autoscaler" --max-users 100 --dry-run
```

### gitmail CLI

```bash
./scripts/gitmail.py run \
  --description "비용 47% 줄이는 Go 기반 K8s 오토스케일러" \
  --project-name k8s-autoscaler \
  --project-url https://github.com/you/k8s-autoscaler \
  --max-users 100 \
  --provider claude \
  --dry-run
```

모든 메일에 원클릭 구독해지 + `List-Unsubscribe` 헤더. SMTP 분당 30건 기본 (`SMTP_RATE_PER_MIN`로 변경).

## "AI 같지 않게" 어떻게 굴러가나

`ai-tell-sniffer`가 모든 초안 검사. 금지 표현 ("delve", "leverage", "let's dive in", "supercharge" 등 20+), 60단어당 em-dash 1개 초과, 균형 잡힌 3-tricolon, 마무리 모럴라이저, 해시태그 남발, 앵커 없는 일반 주장 (숫자/이름/시간/회의 중 하나 필수). 3번 리라이트 후에도 플래그 남으면 자동 발행 거부.

## 상태

v0.2.0 — 로컬 대시보드 + gitmail 아웃리치 + OAuth 로그인. v0.1.0의 `/viral`은 그대로.

## 기여

[`CONTRIBUTING.md`](CONTRIBUTING.md), [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md). 보안 이슈는 [`SECURITY.md`](SECURITY.md).

## 라이선스

MIT.
