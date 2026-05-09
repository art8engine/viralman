# Context — viralman

도메인 용어집. 코드, 문서, 대화에서 같은 표현을 쓰기 위한 단일 출처입니다.
새 개념이 생기면 여기에 한 줄짜리 정의를 추가하세요.

## Outreach

본인의 프로젝트를 다른 개발자에게 알리는 행위. 현재 채널은
**gitmail**(개인화 콜드 메일), **twitter-reply**(자연스러운 답글),
**viral**(트위터/레딧/링크드인 다채널 드래프트) 셋입니다.

## Outreach Pipeline

gitmail 채널의 5단계 시퀀스: **analyse → search → recipients → compose → send**.
구현은 `scripts/gitmail.py`의 `step_*` 다섯 함수. 두 진입점(CLI / 대시보드)이
같은 함수를 호출하며, 결과가 항상 동일해야 합니다 (ADR 0001).

## Step

Outreach Pipeline의 한 단계. `scripts/gitmail.py`의 `step_*`로 명명된 자유함수.
이전 단계의 출력을 받아 다음 단계의 입력을 내고, 진행 상황을 sink로 외칩니다.

## Event Sink

Step이 외치는 이벤트를 받는 함수. 시그니처: `(event: str, **fields) -> None`.
어댑터 둘:
- `_stdout_sink` — CLI. JSONL을 stdout에 쓰며, 시끄러운 `recipient` 이벤트는 거름.
- `job_sink` — 대시보드. `GitmailJob.events`에 append.

## Cancel Check

장시간 도는 Step이 루프 중간에 폴링하는 콜러블 `() -> bool`. True면 Step이
조기 종료하고 `cancelled` 이벤트를 외칩니다. 대시보드는
`lambda: job.status == "cancelled"`로 연결, CLI는 None을 넘깁니다.

## Recipient

outreach 대상 한 명. 모양: `{login, email, starred_repo, profile}`.
`step_recipients`가 seed repo 목록에서 이걸 만들어냅니다.

## Prewritten Template

LLM compose를 건너뛰고 사용자가 미리 작성한 본문을 쓸 때의 템플릿.
플레이스홀더는 이중 중괄호:
`{{login}}`, `{{starred_repo}}`, `{{project_name}}`, `{{project_url}}`.
치환은 `.replace()`로, Python format이 아닙니다 — 본문에 `{` `}` 문자가
들어가도 안 깨지게.

## Sniffer

생성된 카피가 "AI같다"는 신호를 검출하는 결정론적 휴리스틱.
`scripts/lib/sniffer_check.py`에 살며, viral 채널의 후처리와
`viralman:ai-tell-sniffer` 에이전트가 같이 사용합니다.

## Unsubscribe Token

각 발송 메일에 박히는 1회용 토큰. 수신자가
`http://<dashboard>/u/<token>`을 누르면 토큰이 unsubscribe 로그에 기록되고,
다음 발송부터 같은 이메일은 제외됩니다. 토큰↔이메일 매핑은 발송 시점에 별도
파일로 남깁니다.
