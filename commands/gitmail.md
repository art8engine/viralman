---
description: Send personalized cold emails to GitHub stargazers of similar repos. Asks four upfront questions in one batch (language / subject style / targeting / recipient count), collects recipients, generates a fast template-only dry-run preview of the email body, and only sends for real after the user explicitly confirms. Single source of truth lives in `skills/gitmail/SKILL.md`.
allowed-tools: Read, Bash(.venv/bin/python:*), Bash(./scripts/gitmail.py:*), Bash(./scripts/save_creds.py:*), Bash(./bin/viralman:*), Bash(grep:*), Bash(tail:*), Bash(head:*), Bash(wc:*)
argument-hint: "<project-url|description> [--tone '...'] [--emphasis '...'] [--seed-repos a/b,c/d] [--keywords k1,k2] [--max-users N] [--subject-style auto|headline|tag|simple]"
---

# /gitmail — 유사 repo 스타게이저에게 맞춤 이메일

전체 흐름은 `skills/gitmail/SKILL.md` 가 단일 진실 원천. 여기서는 진입점·인자 파싱·boundary만 빠르게 정리.

```
/gitmail https://github.com/rlaope/Argus
/gitmail "JVM 모니터링 SaaS 알리고 싶어"
/gitmail https://github.com/foo/bar --subject-style tag --max-users 100
```

## 진입 시 동작

1. **Pre-flight** — `./scripts/save_creds.py --show-keys` 로 `GITHUB_TOKEN` + 1개 LLM 키 + (실발송 시) SMTP 풀세트 확인. 누락이면 `/viralman-setup gitmail` 안내 후 종료.
2. **Step 1 — 프로젝트 분석 (Claude 직접)** — `$ARGUMENTS` 첫 토큰 GitHub URL이면 owner/repo 슬러그에서 1차 추정 + 사용자가 준 자유 설명 결합. README fetch 금지. 분석 결과 2~3줄로 사용자에게 출력해 batch 답변 전 맥락 제공.
3. **Step 2 — Batch 질문 (AskUserQuestion 1회)** — 4개 묶음으로 띄운다. 이 질문이 끝나기 전에는 절대 `gitmail.py recipients` / `send-from-recipients` 어떤 것도 호출하지 않는다.
   - **Q1 Language**: 한국어 / English / 中文 / 日本語
   - **Q2 Subject 스타일**: `auto` / `headline` / `tag` / `simple` (각 옵션에 preview 텍스트 첨부)
   - **Q3 타깃팅 전략**: 추천 시드 (Claude 즉석 추천) / 키워드 검색 / 자동
   - **Q4 인원**: 100 / 500 / 1000 / 1500 (Other 자동 추가, 1-1500). 캡 두 개가 별개임을 사용자에게 안내:
     - **수집 캡 1,500** — GitHub GraphQL+REST 듀얼 5,000/hr 버킷에서 3x oversample 로 안전한 상한.
     - **SMTP 발송 캡 (1일)** — *무료 @gmail.com 500*, *Workspace 2,000*. 수집 1500 해도 무료 Gmail 이면 3일 분할 필요. step_send 가 자동 abort + unprocessed 카운트 분리.
4. **Step 3 — 수집** — `.venv/bin/python ./scripts/gitmail.py recipients ...` 실행. JSONL 스트림 끝의 recipients 배열만 잘라 `/tmp/gitmail_recipients_clean.json` 으로 저장. 8명까지만 미리보기로 출력.
5. **Step 4 — Fast dry-run preview** — `send-from-recipients --template-only --dry-run` 으로 LLM 1번 호출 → 첫 본문 출력. (50명 dry-run 13분 → ~16초 단축의 핵심.)
6. **Step 5 — 실발송 대기** — 사용자가 "발송해줘" / "send" / "go" 같이 명시적 OK 줄 때만 `--template-only` (dry-run 제외) 로 실행. 피드백을 주면 인자만 바꿔 Step 4 재실행.

`$ARGUMENTS` 에 `--subject-style` / `--tone` / `--emphasis` / `--seed-repos` / `--keywords` / `--max-users` 가 이미 있으면 해당 항목은 batch 질문에서 제외하고 그 값을 그대로 사용한다.

## Boundaries (요약 — 자세히는 SKILL.md)

- 사용자가 명시적으로 "발송해줘" 의사를 보이기 전에는 절대 `--dry-run` 없는 `send-from-recipients` 를 호출하지 않는다.
- unsubscribe footer / `List-Unsubscribe` 헤더는 절대 제거하지 않는다.
- `--max-users` 는 1-1500 범위 내에서만 허용 (GraphQL 5,000 pt/hr + REST 5,000 req/hr 듀얼 버킷에서 안전한 상한; 그 이상은 둘 중 하나가 rate-limit 에 막혀 stall).
- SMTP 발송 한도는 별개. 무료 @gmail.com 500/24h, Workspace 2,000/24h. 수집 인원이 SMTP 한도 초과면 step_send 가 자동 abort 하고 `send_aborted` 이벤트 + stderr 한국어 메시지로 알린다. 미발송분은 `unprocessed` 카운트로 분리되니 rolling 24h 후 retry 안내.
- 실시간 발송 진행률은 `./scripts/gitmail_watch.py --auto` (또는 `--once` 로 statusLine 1회 출력) 사용.
- `~/.viralman/.env` 값은 절대 읽거나 출력하지 않는다 (`--show-keys` 만 안전).
- 이메일 주소를 발명하지 않는다. GitHub Users API / PushEvent 반환값만 사용.
- 실패 발송 자동 재시도 금지.
- 프라이빗 repo 스크래핑 / GitHub rate-limit 우회 요청은 거부.
