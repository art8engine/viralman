# ADR 0002 — Twitter v2 클라이언트는 단일 모듈로 분리

Status: accepted (2026-05-09)

## Context

`post_twitter.py`와 `twitter_reply.py`가 Twitter v2 user-context bearer 호출을
각자 처리하고 있었습니다. 둘 다 같은 4-단계 댄스를 한 카피씩 들고 있었습니다.

1. 저장된 `TWITTER_OAUTH2_BEARER`로 호출
2. 401이면 `TWITTER_OAUTH2_REFRESH` + client id/secret으로 토큰 회전
3. 회전된 토큰을 `creds.save_many()`로 디스크에 persist
4. 1회만 retry, 그래도 401이면 포기

같은 동작이 두 군데 있어서 미묘하게 갈라질 위험이 있었고(예외 클래스
`_OAuth2Unauthorized`/`_V2Error`/`_V2PostError`가 이름까지 겹쳤음), 새 v2
엔드포인트를 추가하려면 또 같은 패턴을 세 번째로 복사해야 했습니다.

## Decision

`scripts/lib/twitter_v2.py` 한 모듈이 v2 호출과 토큰 회전을 모두 책임집니다.
공개 표면은 좁게 유지합니다.

- `request(creds, method, path_or_url, *, json=None) -> dict` — generic v2 호출.
  401→refresh→retry, 회전된 토큰 persist까지 안에서 처리.
- `post_tweet(creds, *, text, in_reply_to_tweet_id=None) -> tweet_id` — thread/
  reply 공통으로 쓰이는 패턴이라 헬퍼로 노출.
- `TwitterAuthError`, `TwitterApiError` — 외부 콜러가 catch할 두 예외.

search 빌드처럼 호출자 고유 로직은 모듈에 들이지 않습니다 (twitter_reply가
lang/retweet/keyword OR-ing 등을 자기 안에서 빌드하고 `request("GET", url)`로
호출).

OAuth1.0a (tweepy) fallback은 별개 인증 모드라 그대로 `post_twitter.py`에
남깁니다.

## Consequences

- v2 동작 변경 한 곳에서 수정. 새 엔드포인트 추가 = `request` 한 줄.
- 두 스크립트의 `_refresh_oauth2`/`_v2_*` 헬퍼와 중복 예외 클래스가 사라집니다.
- 회전된 토큰의 persist 책임이 `twitter_v2._refresh_token` 안으로 들어갑니다.
  콜러는 `creds` dict를 넘기고, 모듈이 in-place 업데이트 + 디스크 persist까지
  맡습니다.

## Alternatives considered

- **그대로 두 카피로 유지**: 거부. silent drift가 이미 두 파일에서 일어나고
  있었음 (각자 약간 다른 에러 메시지, 다른 retry 카운팅). #1과 같은 패턴.
- **Reddit/LinkedIn까지 묶는 일반 `social_api` 모듈**: 거부. Reddit는 PRAW를
  쓰고, LinkedIn은 refresh가 필요 없음. 인증 모델이 셋 다 다름 — 한 추상화로
  덮으면 leaky가 됨. 각 플랫폼은 자기 인증 패턴에 맞는 모듈을 가짐 (Twitter는
  v2 bearer + refresh, 나머지는 단순).
- **`TwitterClient` 클래스로 묶기**: 거부. creds dict가 모든 호출에 따라가는
  유일한 상태이고, 그건 dict로 충분히 표현됨. 클래스는 추가 인디렉션만 만듦.
