# ADR 0001 — 한 파이프라인, 두 진입점

Status: accepted (2026-05-09)

## Context

gitmail outreach는 두 표면에서 시작될 수 있습니다.

1. `scripts/gitmail.py` CLI — 파워 유저, 스크립트 실행용.
2. 대시보드 (`dashboard/api.py`의 `/api/gitmail/*`) — 클릭 기반 로컬 Flask UI.

처음에는 두 표면이 각자 analyse → search → recipients → compose → send를
구현하고 있었습니다. 시간이 지나며 CLI 쪽에 최적화/안전장치가 추가됐고
(GraphQL bulk 프로필 조회, Gmail 일일 한도 사전 경고, SMTP 단절 시
abort marker 처리), 대시보드의 평행 구현은 이걸 따라잡지 못했습니다.
결과적으로 같은 UX 라벨 뒤에서 다른 동작을 하는 silent drift가 발생했습니다.

## Decision

두 진입점이 동일한 `step_*` 함수를 호출합니다 (`scripts/gitmail.py` 내).
파이프라인은 **이벤트 sink**(어디로 외치냐)와 **cancel check**(어떻게
취소하냐)를 인자로 받습니다. 진입점은 자기에게 맞는 sink/cancel만 공급하고,
나머지 로직은 공유합니다.

## Consequences

- 버그 수정과 최적화가 한 곳에 들어가서 두 표면 모두에 도달합니다.
- 대시보드가 `scripts/gitmail.py`에서 import합니다(sys.path 확장). `gitmail.py`는
  스크립트이자 모듈이라는 작은 어색함을 감수하는 대신, 별도 pipeline 패키지를
  만들지 않아도 되는 단순한 import 그래프를 얻습니다.
- step에 대한 단위 테스트는 step 옆에 둡니다. 대시보드 API 테스트는 sink/cancel
  연결과 라우트 핸들링만 검증하고, 파이프라인 내부를 다시 단언하지 않습니다.

## Alternatives considered

- step을 `scripts/lib/pipeline.py`로 이동. 더 깨끗한 import 구조, 다소 큰 diff.
  보류 — `gitmail.py`가 더 커지면 그때 분리합니다.
- step을 `OutreachRun` 클래스로 묶기. 거부: 5개 진입점 중 4개가 파이프라인의
  prefix/suffix만 쓰기 때문에 클래스는 절반만 인스턴스화된 상태로 살게 됨.
  step 자체가 이미 deep해서 클래스로 한 번 더 감쌀 동기가 약함.
