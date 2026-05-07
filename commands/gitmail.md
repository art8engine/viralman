---
description: GitHub 스타게이저에게 맞춤 이메일 발송 — 프로젝트 분석, 유사 repo 탐색, 수신자 수집, 톤·강조 반영한 이메일 작성, SMTP 발송까지 5단계 인터랙티브 흐름.
allowed-tools: Read, Bash(./scripts/gitmail.py:*), Bash(./scripts/save_creds.py:*), Bash(./bin/viralman:*)
argument-hint: "<project-url|description> [--tone '...'] [--emphasis '...'] [--seed-repos a/b,c/d] [--keywords k1,k2] [--max-users N] [--provider claude|openai|gemini]"
---

# /gitmail — 유사 repo 스타게이저에게 맞춤 이메일 보내기

사용자가 GitHub 링크나 프로젝트 설명을 주면, gitmail이 관심 있을 개발자를 찾아 개인화된 이메일을 보냅니다.
모든 흐름은 CLI/슬래시 명령 only. 인자를 미리 주면 해당 단계는 건너뜁니다.

```
/gitmail https://github.com/user/jvm-monitor
/gitmail "JVM 모니터링 SaaS 알리고 싶어" --tone "친근한 개발자, 짧게" --emphasis "free, OSS 친화"
/gitmail --seed-repos jvm-profiling/async-profiler,oracle/graal --max-users 100
```

## Pre-flight

시작 전 `~/.viralman/.env` 에 다음이 있는지 확인:

- `GITHUB_TOKEN` — 없으면 GitHub API가 시간당 60 req 상한으로 죽음.
- `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GEMINI_API_KEY` 중 하나.
- 실발송 시 추가 필요: `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`.

누락 항목이 있으면 `/viralman-setup` 으로 안내. `.env` 내용 자체는 절대 읽거나 출력하지 않는다.

---

## Step 1 — 대상 받기

`$ARGUMENTS` 를 파싱한다:

- 첫 토큰이 `https://github.com/` 으로 시작하면 → GitHub URL로 취급.
  - URL 자체 + 사용자가 추가 입력한 설명을 결합해 project_description 으로 사용.
  - `gh repo view` 나 README fetch 는 하지 않는다.
- 나머지 텍스트가 있으면 → 자유 설명으로 취급.
- 둘 다 없으면 한 번만 묻는다:

```
어떤 프로젝트를 알리고 싶으신가요?
GitHub URL 또는 3~5줄 설명을 주세요.
(예: https://github.com/you/myproject, 또는 "JVM 실시간 프로파일러, 무료 OSS")
```

---

## Step 2 — 톤·강조 받기

`--tone` / `--emphasis` 인자가 있으면 그대로 사용하고 이 단계를 건너뛴다.
없으면 한 번만 묻는다:

```
메일 톤이나 강조하실 점 있으세요? (엔터로 스킵 가능)

  톤 예시: "친근한 개발자 톤", "간결하게", "기술 디테일 위주", "영어로"
  강조 예시: "47% 비용 절감", "OSS 무료", "Postgres 대비 5배 빠름"
```

사용자가 입력하면 `--tone` / `--emphasis` 값으로 저장. 스킵하면 LLM이 프로젝트 설명에서 자동 도출.

---

## Step 3 — 타깃 받기

`--max-users`, `--seed-repos`, `--keywords` 인자가 모두 있으면 이 단계를 건너뛴다.
없는 인자에 대해서만 질문한다:

```
몇 명에게 보낼까요? (1-10000, 기본 100)

어떤 사용자를 타깃하실까요?
  A) 시드 repo 직접 지정 (예: jvm-profiling/async-profiler, oracle/graal)
  B) 키워드로 검색 (예: jvm, profiler, monitoring)
  C) 자동 — 프로젝트 설명에서 추출
```

- A 선택 → `--seed-repos` 값으로 저장.
- B 선택 → `--keywords` 값으로 저장.
- C 선택 → 두 인자 모두 생략 (gitmail.py 가 자동 도출).

---

## Step 4 — 수집 + 검토

다음 명령으로 수신자를 수집한다:

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

> `recipients` prints JSON to stdout. Redirect (`>`) it to a file you can pass to the next step.

결과 JSON을 읽어 사용자에게 다음 형식으로 요약한다:

```
N명 수집했습니다. 미리보기:
1. @asyncuser (alice@example.com) — async-profiler 별표
2. @graalfan (bob@example.com) — graalvm 별표
... (최대 10명까지)

이대로 발송 준비할까요? (y / n / edit)
  y    → 이메일 작성·미리보기로 이동
  edit → 수 / 시드 / 키워드 다시 지정 (Step 3으로 돌아감)
  n    → 종료
```

- `y` → Step 5로.
- `edit` → Step 3으로 돌아가 새 인자로 재수집.
- `n` → 흐름 종료. 수집 파일은 남겨두지 않는다.

---

## Step 5 — 작성 + 발송

두 단계로 분리한다.

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

첫 번째로 작성된 이메일 본문을 사용자에게 출력한다:

```
[미리보기] 첫 번째 이메일
수신자: alice@example.com (@asyncuser)
제목: ...
---
(본문)
---

이 톤이 맞나요? (send / tweak)
  send  → 전체 발송 시작
  tweak → 톤·강조 다시 지정하고 미리보기 재생성
```

- `tweak` → Step 2로 돌아가 tone/emphasis 재입력, 5a 재실행.
- `send` → Step 5b로.

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

완료 후 결과 요약:

```
발송 완료.
  성공: N건
  실패: M건 (실패 사유 그룹별로 표시)
  언섭스크라이브 로그: .viralman_unsubscribes.jsonl
```

실패 목록은 주소 + 사유를 간결하게 나열한다. 재시도는 자동으로 하지 않는다.

---

## Boundaries

- **절대로** unsubscribe footer 또는 List-Unsubscribe 헤더를 제거하지 않는다. 제거 요청은 거부하고 이유를 설명한다.
- **절대로** `--max-users 10000` 초과 값을 사용하지 않는다. 스크립트가 reject 하지만 시도조차 하지 않는다.
- **절대로** `~/.viralman/.env` 내용을 읽거나 출력하지 않는다.
- **절대로** 이메일 주소를 발명하거나 추측하지 않는다. GitHub Users API / PushEvent 반환값만 사용.
- **절대로** 실패한 발송을 자동 재시도하지 않는다. 실패는 사용자에게 전달한다.
- per-minute 레이트 리밋을 무단 변경하지 않는다. 더 빠른 발송이 필요하면 `SMTP_RATE_PER_MIN` 을 사용자가 직접 설정하도록 안내.
- 프라이빗 repo 커밋 이메일 스크래핑 또는 GitHub 레이트 리밋 우회 요청은 거부한다.
