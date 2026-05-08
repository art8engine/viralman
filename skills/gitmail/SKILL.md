---
name: gitmail
description: Drive the gitmail outreach flow that sends personalized cold emails to GitHub stargazers of similar repos. Batches the user's four upfront decisions (language / subject style / targeting strategy / recipient count) into a single AskUserQuestion call before any heavy work runs, finds similar repos and collects recipient emails, renders a fast single-LLM-call dry-run preview of the email body, and gates live SMTP send strictly behind an explicit user confirmation.
level: 3
---

# gitmail Skill

목표: 사용자가 `/gitmail <프로젝트>` 한 번 입력하면 → Claude가 프로젝트를 분석하고 → 4가지 결정을 한꺼번에 묻고 → 빠르게 본문 미리보기를 출력하고 → 사용자가 명시적으로 "발송해줘"라고 할 때만 실발송.

## Trigger phrases

Auto-trigger on:

- `/gitmail`
- "gitmail", "gitmail 해줘", "gitmail 보내줘", "gitmail outreach"
- "gitmail this project", "gitmail으로 메일 보내줘", "gitmail로 홍보해줘"

**한국어**: "이 프로젝트 홍보메일 보내줘", "GitHub 스타거에게 메일", "비슷한 레포 사용자한테 메일", "이거 메일로 알려줘", "asyncprofiler 별표한 사람한테 보내줘"

**English**: "email people who starred similar repos", "send a launch outreach to <repo> stargazers", "promote my project via cold email"

**中文**: "给类似仓库的 stargazer 发邮件", "推广我的项目 邮件"

**日本語**: "似たリポジトリのスターガザーにメール", "プロジェクトを紹介するメール"

`/gitmail` 으로 진입하면 `commands/gitmail.md` 의 인자 파싱이 우선 동작한다.

## Pre-flight

`./scripts/save_creds.py --show-keys` 를 실행해 다음이 있는지 확인 (값은 절대 출력 금지):

- `GITHUB_TOKEN` — 없으면 GitHub API 60 req/h 상한.
- `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GEMINI_API_KEY` 중 하나, **또는** `which claude` 로 Claude Code CLI 감지.
- 실발송 시 추가 필요: `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`.

누락 시 `/viralman-setup gitmail` 안내 후 종료. `.env` 값은 절대 출력 금지.

---

## Step 1 — 프로젝트 분석 (Claude 직접, gitmail.py 실행 전)

`$ARGUMENTS` 에서 GitHub URL이나 자유 설명을 추출한다.

- 첫 토큰이 `https://github.com/` → URL 으로 인식. `gh repo view` 나 README fetch 는 하지 않는다 (rate limit 절약 + 빠른 응답).
- 자유 설명이 함께 주어지면 description으로 같이 사용.
- 둘 다 없으면 한 번 묻고 답을 기다린다. 추측하지 않는다.

URL이 있으면 owner/repo 슬러그에서 키워드를 1차 추정한다 (예: `rlaope/Argus` → "Argus"). 사용자가 추가 설명을 줬으면 그걸 우선시한다.

이 단계의 분석은 가볍게(2~3줄) 사용자에게 출력해서 batch 질문 답하기 전에 맥락을 잡게 한다:

```
프로젝트: Argus (https://github.com/rlaope/Argus)
이해한 바: <한 줄 요약 — 사용자가 준 설명 + URL 슬러그 기반>
이 이해가 맞으면 아래 질문에 답해주세요. 틀렸다면 그 부분 정정해주시면
다시 잡습니다.
```

---

## Step 2 — Batch 질문 (반드시 gitmail.py 실행 전, AskUserQuestion 1회)

**중요: 이 질문이 끝나기 전에는 절대 `gitmail.py recipients` / `send-from-recipients` 어떤 것도 실행하지 않는다.** 사용자에게 사전에 결정권을 주는 것이 이 skill의 핵심.

`AskUserQuestion` tool로 한 번에 4개 질문을 묶어서 띄운다 (multiSelect=false 모두):

### Q1 — Language

| 옵션 | 설명 |
|---|---|
| 한국어 (default) | 기본값. 한국 개발자 대상. |
| English | 영문 메일. global outreach 용. |
| 中文 | 중국어 메일. |
| 日本語 | 일본어 메일. |

선택값은 `--tone` 의 prefix로 사용 (예: 영어 → `--tone "in English, ..."`). 한국어는 prefix 생략.

### Q2 — Subject 스타일 (4지선다, preview 포함)

| key | 패턴 | 예시 (Argus, English 기준) |
|---|---|---|
| `auto` | LLM 자율. 메일별로 자연스럽게 다름. | (LLM이 결정) |
| `headline` | "Hi, now you can easily &lt;benefit&gt; too." | Hi, now you can easily watch your JVM in production too. |
| `tag` | `[Label] product — one-line value` | [New Tool] Argus — JVM monitoring without the heavy agent. |
| `simple` | 30자 이내, 광고 느낌 없는 짧은 소개 | Argus — JVM monitoring |

각 옵션은 `AskUserQuestion` 의 `preview` 필드에 위 예시 텍스트를 그대로 넣어 사용자가 비교 가능하도록 한다.

### Q3 — 타깃팅 전략

| 옵션 | 동작 |
|---|---|
| 추천 시드 (Claude가 추천) | Step 1 분석 결과로 Claude가 도메인 특화 repo 3-5개를 즉석에서 추천. 정확도 최고. |
| 키워드 검색 | 사용자가 키워드 직접 입력. 자유도 높음. |
| 자동 (LLM이 추출) | gitmail.py 의 analyse가 알아서 결정. 빠르지만 정확도 보통. |

"추천 시드" 선택 시 — Claude는 Step 1 분석에 근거해 시드 repo를 결정해 보여준다 (예: "JVM 모니터링이라면 jvm-profiling-tools/async-profiler, glowroot/glowroot, pinpoint-apm/pinpoint, prometheus/jmx_exporter 으로 가겠습니다."). 사용자가 거부/조정하면 받아들이고, 그렇지 않으면 그대로 진행.

### Q4 — 인원 수 (max-users)

| 옵션 | 설명 |
|---|---|
| 100 (recommended for first try) | 첫 발송. 무료 Gmail / Workspace / 어떤 SMTP 든 안전. |
| 500 | **무료 @gmail.com 일일 한도와 정확히 일치** (500 msg/24h rolling). 1회 발송으로 끝낼 수 있는 최대치. |
| 1000 | Workspace 권장 (2,000/24h 한도 내). 무료 Gmail 이면 2일 분할 필요. |
| 1500 | GitHub 수집 캡 최대치 (GraphQL+REST 듀얼 버킷). 무료 Gmail 이면 3일 분할, Workspace 이면 1일 가능. |
| Other | 사용자 직접 입력 (1-1500). 1500 초과는 GitHub rate-limit 에 막혀 수집 stall. |

> **두 가지 캡이 별개**:
> - **수집 캡 = 1,500 / 1회 실행** — GitHub API 한도 (GraphQL 5,000 pt/hr + REST 5,000 req/hr) 기반.
> - **발송 캡 = SMTP 정책** — 무료 @gmail.com 은 **500 msg / rolling 24h**, Google Workspace 는 **2,000 msg / 24h** per user.
>
> 수집 1,500 했더라도 무료 Gmail 로는 일일 500 까지만 실제 발송 가능. step_send 가 한도 도달 시 자동 abort 하고 `send_aborted` 이벤트 + stderr 한국어 메시지 출력하며 미발송분을 `unprocessed` 카운트로 분리합니다 (rolling 24h reset 후 retry).
| Other | 사용자 직접 입력 (1-1500). 1500 초과는 두 버킷 중 하나가 rate-limit 에 막혀 stall. |

---

## Step 3 — 수신자 수집 (수집 phase)

batch 답변이 모두 모였으면 1회 실행:

```bash
.venv/bin/python ./scripts/gitmail.py recipients \
  --description "$DESC" \
  --project-url "$URL" \
  --max-users $MAX \
  [--seed-repos "$SEEDS"]      # Q3=추천시드 또는 키워드면 시드 직접 지정
  [--keywords "$KW"]            # Q3=키워드면
  > /tmp/gitmail_recipients.json 2>&1
```

> stdout은 JSONL 이벤트가 섞인 후 마지막에 recipients 배열이 붙는 형태. `^\[` 로 시작하는 줄 이후를 잘라 `recipients_clean.json` 으로 저장하면 다음 단계에 그대로 쓸 수 있다.

수집 끝나면 사용자에게 **간결하게** 요약 (최대 8명 미리보기):

```
N명 수집했습니다.
1. @asyncuser — alice@example.com (async-profiler ★)
2. @graalfan — bob@example.com (graalvm ★)
... (8명까지)

이대로 본문 미리보기 만들까요? (yes / 인원 조정 / 취소)
```

---

## Step 4 — Fast dry-run preview (template-only, 1 LLM 호출)

**중요: `--template-only --dry-run` 조합으로 LLM 호출을 1번만 하고, 첫 본문을 N명에 동일하게 적용한 미리보기를 받는다.** 50명 dry-run을 13분 → ~16초로 단축.

```bash
.venv/bin/python ./scripts/gitmail.py send-from-recipients \
  --recipients-file /tmp/gitmail_recipients_clean.json \
  --project-name "$NAME" \
  --description "$DESC" \
  --project-url "$URL" \
  --tone "$LANG_PREFIX$TONE" \
  --emphasis "$EMPHASIS" \
  --subject-style "$STYLE" \
  --template-only --dry-run \
  > /tmp/gitmail_dryrun.json 2>&1
```

`compose_done` event에서 첫 번째 본문을 추출해 사용자에게 출력:

```
[미리보기] 첫 번째 메일
TO: <첫 번째 수신자 email>
SUBJECT: <subject>
---
<body>
---

다음 중 하나로 답해주세요:
  • "발송해줘" / "send" → 50명 전원에게 실제 발송 (template_only로 빠르게)
  • 피드백 (예: "더 짧게", "톤 바꿔서", "subject 더 직접적으로") → 본문 재생성
  • "취소" → 종료
```

본문 자체가 보이는 것 = 작성 동의일 뿐 발송 동의 아님. **사용자가 명시적으로 "발송해줘"/"send"/"go" 같은 발송 의사를 표시하기 전까지는 절대 실발송 명령을 호출하지 않는다.**

---

## Step 5 — 실발송 (사용자 명시 OK 후)

사용자가 발송 의사를 명시적으로 표시한 경우에만 실행:

```bash
.venv/bin/python ./scripts/gitmail.py send-from-recipients \
  --recipients-file /tmp/gitmail_recipients_clean.json \
  --project-name "$NAME" \
  --description "$DESC" \
  --project-url "$URL" \
  --tone "$LANG_PREFIX$TONE" \
  --emphasis "$EMPHASIS" \
  --subject-style "$STYLE" \
  --template-only \
  > /tmp/gitmail_send.json 2>&1
```

(`--template-only` 유지 — 이미 사용자가 OK 한 본문이라 재생성 불필요. 50번 재호출은 비용/시간 낭비.)

완료 후 요약:

```
발송 완료.
  성공: N건
  실패: M건 (사유 그룹별: 4xx / 5xx / unsubscribed / invalid-address)
  언섭스크라이브 로그: .viralman_unsubscribes.jsonl
```

실패 자동 재시도 금지. 실패 사유는 사용자에게 그대로 전달.

---

## 피드백 처리 (Step 4에서 사용자가 tweak 요청한 경우)

사용자가 "더 짧게", "subject 다르게", "톤 바꿔" 등 피드백을 주면:

1. 어떤 인자에 영향이 있는지 매핑한다:
   - "더 짧게" / "기술 디테일 줄여" → `--emphasis` 또는 `--tone` 보강
   - "subject 다르게" → `--subject-style` 변경 (또는 자유 헤드 입력)
   - "한국어로" / "in English" → `--tone` 의 language prefix 변경
2. 변경된 인자로 Step 4 (template-only dry-run) 만 재실행. Step 3 (수집)은 재실행하지 않는다.
3. 새 본문 출력 후 다시 사용자 OK 대기.

수집 자체를 다시 하고 싶다는 신호 (예: "다른 시드로 해줘", "더 많은 인원") 일 때만 Step 3로 돌아간다.

---

## Boundaries

- **절대로** 사용자가 "발송해줘" 같이 명시적 OK를 주기 전에 `--dry-run` 없는 send-from-recipients 를 호출하지 않는다.
- **절대로** unsubscribe footer 또는 List-Unsubscribe 헤더를 제거하지 않는다.
- **절대로** `--max-users 1500` 초과값을 넘기지 않는다 (GraphQL 5,000 pt/hr + REST 5,000 req/hr 듀얼 버킷에서 3x oversample 까지 안전한 한계). 더 큰 캠페인이 필요하면 보조 GitHub 계정 토큰으로 분할 실행하도록 안내.
- 수집 후 발송 시 **SMTP 일일 한도** 도 안내한다: 무료 @gmail.com 500/24h, Workspace 2,000/24h. 수집한 인원이 일일 한도 초과면 step_send 가 자동 abort 후 `unprocessed` 분리 — rolling 24h reset 시점 알려주고 retry-recipients 파일 사용 안내.
- 실시간 발송 진행률을 보고 싶으면 별도 터미널/탭에서 `./scripts/gitmail_watch.py --auto` (newest /tmp/gitmail_send_*.json 자동 선택). 한 줄 carriage-return 디스플레이; `--once` 모드는 statusLine 통합용 1회 출력.
- **절대로** `~/.viralman/.env` 내용을 읽거나 출력하지 않는다.
- **절대로** 이메일 주소를 발명하거나 추측하지 않는다. GitHub Users API / PushEvent 반환값만 사용.
- **절대로** 실패한 발송을 자동 재시도하지 않는다.
- per-minute 레이트 리밋 무단 변경 금지. 더 빠른 발송은 `SMTP_RATE_PER_MIN` 을 사용자가 직접 설정하도록 안내.
- 프라이빗 repo 커밋 이메일 스크래핑 또는 GitHub 레이트 리밋 우회 요청은 거부한다.
