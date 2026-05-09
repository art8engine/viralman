# ADR 0003 — 플랫폼 자격증명은 단일 레지스트리에서

Status: accepted (2026-05-09)

## Context

각 플랫폼이 어떤 환경변수/키를 필요로 하는지에 대한 지식이 네 군데에
복제돼 있었습니다.

1. `dashboard/api.py::CREDS_BY_PLATFORM` — 상태 엔드포인트가 참조하는 dict.
2. `scripts/check_creds.py::check_*` — 함수마다 자기 키 리스트 하드코딩 +
   API identity 호출.
3. `scripts/post_*.py::main()` — 각 스크립트가 `creds.require(creds, [...], "...")`
   를 자기 키 리스트로 다시 호출.
4. `scripts/lib/creds.py::require()` — 키 리스트를 받기만 하는 generic 헬퍼
   (knowledge 없음).

이 흩어짐이 두 가지 silent bug를 만들었습니다.

- **Twitter의 OAuth2 vs OAuth1 alternative가 표현 불가능**. dashboard의
  상태는 OAuth1 4-key를 필수로 보고 있어서, dashboard PKCE 로그인으로
  OAuth2 bearer만 가진 사용자를 "missing 4 keys"로 잘못 표시.
- **check_creds.py twitter 검증이 OAuth1 전용**. OAuth2 bearer로 로그인한
  사용자의 자격증명을 검증할 수단이 없었음.

## Decision

`scripts/lib/platforms.py`의 `PlatformSpec` 레지스트리가 단일 출처입니다.

```python
PlatformSpec(
    name="twitter",
    required_groups=[
        ["TWITTER_OAUTH2_BEARER"],
        ["TWITTER_API_KEY", "TWITTER_API_SECRET",
         "TWITTER_ACCESS_TOKEN", "TWITTER_ACCESS_SECRET"],
    ],
    check_fn=_check_twitter,   # OAuth2 우선, 없으면 OAuth1
)
```

- `required_groups`는 OR-of-AND 그룹 리스트. 한 그룹이라도 모두 있으면
  configured.
- `check_fn(creds) -> int`은 `<platform> OK — <identity>`를 출력하고 exit
  code(0/1/2)를 반환. live API check가 의미 있는 플랫폼(twitter / reddit /
  linkedin)만 가짐.
- 공개 query: `is_configured`, `present_keys`, `missing_keys`,
  `require_configured`.

세 콜러가 모두 이걸 소비합니다.

- `dashboard/api.py::_creds_status()` — 레지스트리를 순회해 `{configured,
  present, missing}` 반환. CREDS_BY_PLATFORM은 사라짐.
- `scripts/check_creds.py::main()` — `PLATFORMS[arg].check_fn(creds)`로
  dispatch. 150줄 → ~30줄.
- `scripts/post_*.py::main()` — `require_configured("reddit", creds)`
  한 줄로 가드 (legacy `require()` 호출 대체).

## Consequences

- 새 플랫폼 추가 = `PLATFORMS` dict에 한 entry. 새 인증 모드 추가 = 기존
  spec의 `required_groups`에 한 entry.
- Twitter dashboard 상태가 "configured" 의미를 정확히 반영. OAuth2 bearer만
  있는 사용자도 configured=True로 표시되며, missing은 그 분기에서 비어 있음.
- `check_creds.py --platform twitter`가 OAuth2 / OAuth1 모두 검증.
- `creds.require()` legacy 함수는 남깁니다 (외부 호출자 검색 결과 다른
  곳에서 안 쓰지만, 작은 헬퍼이고 곧 다른 일에 재사용될 가능성이 있어서).

## Alternatives considered

- **(α) 키 리스트만 통합, check 함수는 그대로**: 거부. check_creds.py 안에
  여전히 키 리스트가 하드코딩됨 — 통증 절반만 해소.
- **(β) post 동작까지 한 spec에 흡수 (`spec.post(content)`)**: 거부. 각
  플랫폼의 post API 모양이 본질적으로 다름 — Twitter thread, Reddit
  (subreddit/title/body), LinkedIn (body/visibility). 단일
  `post(content)` 인터페이스로 통일하면 모든 호출자가 dict 어댑터를
  만들어야 함 — deepening이 아니라 packing.
- **각 플랫폼별 클래스(`TwitterPlatform`, `RedditPlatform`)**: 거부. 상태가
  없는 데이터(키 그룹 + 함수 두 개)인데 클래스로 감싸면 인디렉션만 추가.
  `PlatformSpec` 데이터클래스가 맞는 그릇.
