---
name: gitmail
description: GitHub 스타게이저에게 맞춤 이메일 발송 — 유사 repo 탐색, 수신자 수집, 톤·강조 반영 이메일 작성, SMTP 발송까지 5단계 인터랙티브 흐름. Drive the gitmail outreach flow — find similar GitHub repos, collect stargazer emails, compose personalized notes reflecting user-specified tone/emphasis via Claude/OpenAI/Gemini, and send via SMTP with rate limiting and a one-click unsubscribe footer.
level: 3
---

# gitmail Skill

사용자의 오픈소스 프로젝트를 관심 있을 개발자에게 알립니다. 비슷한 프로젝트를 별표한 GitHub 사용자를 찾아 개인화된 이메일을 보내는 것이 핵심입니다.

이 스킬은 2-phase 구조로 동작합니다:
1. **수집 phase** (`gitmail.py recipients`) — 타깃 사용자 목록 구성 + 사용자 검토.
2. **작성·발송 phase** (`gitmail.py send-from-recipients`) — 톤/강조를 반영해 이메일 작성, dry-run 미리보기, 실발송.

사용자 톤(`--tone`)과 강조(`--emphasis`)는 `compose_email` 의 system prompt에 자연어 그대로 주입되어 LLM이 문체와 강조 포인트를 조절합니다.

## Trigger phrases

Auto-trigger on:

- `/gitmail`
- "gitmail", "gitmail 해줘", "gitmail 보내줘", "gitmail outreach"
- "gitmail this project", "gitmail으로 메일 보내줘", "gitmail로 홍보해줘"
- "send a launch email to stargazers of similar repos"
- "find users who'd care about my project"
- "스타게이저에게 이메일 보내줘", "유사 repo 사용자에게 메일 보내줘"

**한국어**:
- "이 프로젝트 홍보메일 보내줘", "내 OSS 알리는 콜드메일"
- "GitHub 스타거에게 메일", "비슷한 레포 사용자한테 메일"
- "이거 바이럴 시켜줘 메일로", "asyncprofiler 별표한 사람한테 보내줘"

**English**:
- "email people who starred similar repos", "send a launch outreach to <repo> stargazers"
- "promote my project via cold email", "outreach to github users"
- "blast a personalized email to relevant developers"

**中文**:
- "给类似仓库的 stargazer 发邮件", "推广我的项目 邮件"

**日本語**:
- "似たリポジトリのスターガザーにメール", "プロジェクト を 紹介する メール"

`/gitmail` 으로 진입하면 `commands/gitmail.md` 의 인자 파싱을 먼저 따른다.

## Required inputs

| Input | Required? | Notes |
|---|---|---|
| **description / url** | yes | GitHub URL 또는 3~5줄 자유 설명. |
| **tone** | optional | 이메일 문체. 예: "친근한 개발자 톤", "간결하게", "영어로". |
| **emphasis** | optional | 강조 포인트. 예: "47% 비용 절감", "OSS 무료". |
| **max_users** | yes | 1–10000. 기본 100. 500 초과 시 시간 오래 걸림. |
| **seed_repos** | optional | 직접 지정할 시드 repo 목록. 타깃팅 정확도 핵심. |
| **keywords** | optional | 키워드로 유사 repo 검색. seed_repos 와 택일 또는 병행. |
| **provider** | optional | claude / openai / gemini. 자격증명에서 자동 감지. |

누락 항목은 한 번만 묻는다. 추측하거나 발명하지 않는다.

## Pre-flight

`~/.viralman/.env` 에 다음이 있는지 확인:

- `GITHUB_TOKEN` — 없으면 GitHub API가 60 req/h 상한으로 즉시 고갈.
- `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GEMINI_API_KEY` 중 하나.
- 실발송 시 추가 필요: `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`.

누락 항목이 있으면 `/viralman-setup` 으로 안내한다. `.env` 값 자체는 절대 출력하지 않는다.

---

## Step 1 — 대상 받기

`$ARGUMENTS` 첫 토큰이 GitHub URL이면 URL + 추가 설명을 결합.
자유 설명이면 그대로 사용.
둘 다 없으면 한 번 묻는다.

- `gh repo view` 나 README fetch 는 하지 않는다. URL 자체와 사용자 입력만 활용.

---

## Step 2 — 톤·강조 받기

`--tone` / `--emphasis` 가 있으면 건너뛴다. 없으면 한 번 묻는다:

```
메일 톤이나 강조하실 점 있으세요? (엔터로 스킵 가능)

  톤 예시: "친근한 개발자 톤", "간결하게", "기술 디테일 위주"
  강조 예시: "47% 비용 절감", "OSS 무료", "Postgres 대비 5배 빠름"
```

입력값은 `compose_email` system prompt에 자연어 그대로 삽입된다.

---

## Step 3 — 타깃 받기

`--max-users`, `--seed-repos`, `--keywords` 가 모두 있으면 건너뛴다.
없는 항목만 묻는다:

```
몇 명에게 보낼까요? (1-10000, 기본 100)

어떤 사용자를 타깃하실까요?
  A) 시드 repo 직접 지정 — 타깃팅 정확도 최고
     예: jvm-profiling/async-profiler, oracle/graal
  B) 키워드로 검색
     예: jvm, profiler, monitoring
  C) 자동 — 프로젝트 설명에서 추출
```

시드 repo 직접 지정(A)이 P-GM 타깃팅 정확도 면에서 가장 효과적이다. 사용자가 도메인 특화 repo 를 알고 있다면 적극 권장.

---

## Step 4 — 수집 + 검토 (수집 phase)

```bash
./scripts/gitmail.py recipients \
  --description "$DESC" \
  --project-url "$URL" \
  --max-users $MAX \
  [--seed-repos "$SEEDS"] \
  [--keywords "$KW"] \
  --provider $PROVIDER \
  > /tmp/gitmail_recipients.json
```

> `recipients` writes JSON to stdout. Redirect it to a file for the next step.

결과를 사용자에게 요약 (최대 10명 미리보기):

```
N명 수집했습니다. 미리보기:
1. @asyncuser (alice@example.com) — async-profiler 별표
2. @graalfan (bob@example.com) — graalvm 별표
...

이대로 발송 준비할까요? (y / n / edit)
```

- `y` → Step 5.
- `edit` → Step 3 으로 돌아가 재수집.
- `n` → 종료.

---

## Step 5 — 작성 + 발송 (작성·발송 phase)

### Step 5a — 미리보기 (dry-run)

```bash
./scripts/gitmail.py send-from-recipients \
  --recipients-file /tmp/gitmail_recipients.json \
  --project-name "$NAME" \
  --description "$DESC" \
  --project-url "$URL" \
  --tone "$TONE" \
  --emphasis "$EMPHASIS" \
  --provider $PROVIDER \
  --dry-run
```

첫 번째 작성된 이메일 본문을 출력하고 사용자에게 확인:

```
이 톤이 맞나요? (send / tweak)
  send  → 전체 발송 시작
  tweak → 톤·강조 다시 지정 후 미리보기 재생성
```

- `tweak` → Step 2 로 돌아가 재입력, 5a 재실행.
- `send` → Step 5b.

### Step 5b — 실발송

```bash
./scripts/gitmail.py send-from-recipients \
  --recipients-file /tmp/gitmail_recipients.json \
  --project-name "$NAME" \
  --description "$DESC" \
  --project-url "$URL" \
  --tone "$TONE" \
  --emphasis "$EMPHASIS" \
  --provider $PROVIDER
```

완료 후 요약:
- 성공 건수 / 실패 건수
- 실패 사유 그룹별 나열
- 언섭스크라이브 로그 경로: `.viralman_unsubscribes.jsonl`

---

## Boundaries

- **절대로** unsubscribe footer 또는 List-Unsubscribe 헤더를 제거하지 않는다. 반스팸법 위반 소지 있으므로 거부하고 이유를 설명.
- **절대로** `--max-users 10000` 초과값을 넘기지 않는다.
- **절대로** `~/.viralman/.env` 내용을 읽거나 출력하지 않는다.
- **절대로** 이메일 주소를 발명하거나 추측하지 않는다. GitHub Users API / PushEvent 반환값만 사용.
- **절대로** 실패한 발송을 자동 재시도하지 않는다. 실패는 사용자에게 전달.
- per-minute 레이트 리밋 무단 변경 금지. 더 빠른 발송은 `SMTP_RATE_PER_MIN` 을 사용자가 직접 설정하도록 안내.
- 프라이빗 repo 커밋 이메일 스크래핑 또는 GitHub 레이트 리밋 우회 요청은 거부한다.
