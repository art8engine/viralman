# viralman — Manual QA Checklist

> Run before each release. Tick each box. Flag any P0 blocker → release is blocked.

## How to use
- ✅ pass / ❌ fail / 🚧 blocked / 💬 needs human judgment
- For "P0 (출시 차단)" sections: any ❌ blocks release.
- Record session in `tests/manual_qa_runs/<date>.md` (create file with your test notes).

## Setup
- [ ] Fresh `~/.viralman/.env` (rename existing for the run)
- [ ] Browser: latest Chrome + Firefox + Safari
- [ ] Test SMTP: a Gmail / Mailtrap account with credentials ready
- [ ] Test GitHub token with `public_repo + user:email` scopes (beta fine-grained or classic)
- [ ] Test OAuth apps created:
  - [ ] Twitter/X: OAuth 2.0 app (dev.twitter.com) with Read+Write permission + redirect URI
  - [ ] Reddit: OAuth web-app (reddit.com/prefs/apps) with redirect URI
  - [ ] LinkedIn: OAuth app (linkedin.com/developers/apps) with redirect URI configured
- [ ] Claude/LLM provider installed: `which claude` or OpenAI/Gemini API keys ready

## P0 — Onboarding (사용성)

### U-OB-01 First-run CTA
- [ ] `viralman` 실행 → http://localhost:8765 → /twitter 진입
- [ ] 헤더 아래 👋 "First time?" 배너가 보인다 (when 0 creds connected)
- [ ] "go to setup →" 클릭 시 /setup으로 이동

### U-OB-02 Connect count
- [ ] 자격증명 0개일 때 헤더 connect 버튼 "0/4"
- [ ] Twitter OAuth 1개 등록 후 즉시 "1/4"로 변경 (실시간 업데이트)
- [ ] LinkedIn/Reddit/Gitmail 각 추가 시 2/4, 3/4, 4/4로 증가
- [ ] /first-time CTA 자동 사라짐 (after 4/4)

### U-OB-03 Setup tab switching
- [ ] /setup의 4탭 (Twitter/Reddit/LinkedIn/Gitmail) 전환 정상
- [ ] 비활성 탭 콘텐츠가 .hidden 처리 (DOM에는 있되 표시 안 함)
- [ ] URL remains `/setup` when switching tabs

### U-OB-04 OAuth modes
- [ ] Twitter 페이지에 OAuth 2.0 (recommended, dashboard login) 표시
- [ ] Twitter 페이지에 OAuth 1.0a (legacy) 표시
- [ ] Reddit 페이지에 web-app (recommended) 명확히 표시
- [ ] Reddit 페이지에 script-app (legacy username+password) 옵션도 표시
- [ ] LinkedIn 페이지에 OAuth 2.0 (recommended) 표시
- [ ] 첫 사용자가 각 탭에서 추천 모드를 2초 내에 식별 가능

### U-OB-05 i18n coverage (EN, KO, ZH, JA)
- [ ] /setup 4탭 헤더 번역 (Twitter, Reddit, LinkedIn, Gitmail)
- [ ] /setup steps (li elements) 번역
- [ ] /setup labels (h3, button, input placeholder) 번역
- [ ] /twitter page-intro 번역 (title + one-liner)
- [ ] /reddit page-intro 번역
- [ ] /gitmail page-intro 번역
- [ ] connect 메뉴 상단 (X, Reddit, LinkedIn, Gitmail 텍스트) 번역
- [ ] 브라우저 개발자 콘솔에 "missing i18n key" 경고 0개 (any lang)

### U-OB-06 Claude Max auto-detect
- [ ] `which claude` 가 binary를 가리킴
- [ ] /setup 하단 "Using Claude Max?" 섹션 보이고 읽을 수 있음
- [ ] /api/creds/status 응답에 `claude_cli.available: true` 포함됨
- [ ] Project 블록에서 provider 드롭다운에 "claude (Max via CLI)" 옵션 표시

## P0 — Gitmail (사용성)

### U-GM-01 Collect recipients flow
- [ ] /gitmail "collect recipients" 버튼 클릭 가능
- [ ] Project name/URL/pitch 필드 채운 후 collect 시작
- [ ] "collecting…" 상태 표시 (로딩 바 또는 텍스트)
- [ ] 수초~수십초 후 recipients 테이블 표시 (GitHub API 호출)
- [ ] 테이블: GitHub login, email, starred_repo 컬럼 표시

### U-GM-02 Recipients pagination
- [ ] Recipients 페이지네이션: "prev" / "next" 버튼
- [ ] "select all on this page" 체크박스 동작
- [ ] 페이지당 ~25 recipients 표시 (또는 설정된 수)
- [ ] 마지막 페이지에서 "next" 비활성화

### U-GM-03 Email template validation
- [ ] "email template" 텍스트 영역에 {{login}} placeholder 가이드
- [ ] "email template" 텍스트 영역에 {{starred_repo}} placeholder 가이드
- [ ] template 비어있으면 "send selected" 버튼 비활성화 또는 경고

### U-GM-04 2-phase send (collect → review → send)
- [ ] Phase 1: "collect recipients" 완료하면 recipients 테이블 표시
- [ ] Phase 2: "send selected" 클릭 후 dry-run 옵션 표시
- [ ] Dry-run toggle: "send real check" 변경 (dry-run은 SMTP 호출 안 함)
- [ ] "I confirm I want to send under my account" 체크박스 표시
- [ ] 확인 후 최종 "send" 클릭 시 진행

### U-GM-05 Rate limiting + unsubscribe
- [ ] SMTP send 중 rate limiting 적용 (기본 30/min)
- [ ] 각 email에 `List-Unsubscribe` 헤더 포함 (SMTP raw MIME 확인 가능)
- [ ] Email 본문에 one-click unsubscribe 링크 포함

### U-GM-06 SMTP real send test
- [ ] Test SMTP credentials (Gmail or Mailtrap) 입력
- [ ] Dry-run first: "send selected" → toggle off dry-run → "I confirm" → "send"
- [ ] Dry-run log 확인 (실제 SMTP 호출 없음, 메시지만)
- [ ] Real send: dry-run toggle on → confirm → send
- [ ] Test inbox 확인 (emails arrive, valid headers, unsubscribe link works)

### U-GM-07 GitHub API rate limit respected
- [ ] max-users parameter 설정 (e.g., 50, 100)
- [ ] Collect 중 GitHub API 호출 수 ≤ 예상치 (token 사용 시 5000/hour, 아니면 60/hour)
- [ ] X-RateLimit-Remaining header 확인 (API call 후)
- [ ] Rate limit 초과 시 에러 메시지 표시

### U-GM-08 Template personalization
- [ ] {{login}} 각 email에서 실제 GitHub login으로 치환
- [ ] {{starred_repo}} 각 email에서 실제 starred_repo 로 치환
- [ ] Template에 다른 placeholder (e.g., {{email}}) 시도 → 무시되거나 그대로 남음

### U-GM-09 Collect filters (min stars, keywords)
- [ ] Repository min stars filter 적용 (기본값 확인)
- [ ] Keywords 또는 repo description match 적용
- [ ] 필터 없이 수동 max-users 설정 가능
- [ ] API 호출 건수 표시 (diagnostics)

### U-GM-10 MIME export
- [ ] 각 email을 raw MIME로 export 가능 ("copy raw MIME" 버튼)
- [ ] MIME 내용: From, To, Subject, headers, body 포함
- [ ] MIME를 클립보드에 복사 후 텍스트 에디터 확인 가능

## P0 — Security (보안)

### U-SC-01 Secrets never logged
- [ ] Dashboard console (F12) 확인: 어떤 credential도 로그되지 않음
- [ ] Server logs (stdout) 확인: credential 로그 없음
- [ ] ~/.viralman/.env 파일 권한: `chmod 600` 또는 owner-read-only
- [ ] OAuth tokens/secrets 절대 URL에 나타나지 않음

### U-SC-02 HTTPS enforcement (production)
- [ ] OAuth redirect URIs: https:// (localhost OK for dev)
- [ ] Cookies (if any): secure flag 확인
- [ ] Dashboard 실행 시 경고: "HTTP는 localhost만 지원" (또는 비슷)

### U-SC-03 CSRF protection (if forms present)
- [ ] Form submissions: CSRF token 또는 SameSite cookie 확인
- [ ] Send 버튼 누르기 → POST request intercepted (F12 Network) → CSRF 헤더 또는 쿠키 확인

### U-SC-04 OAuth state + nonce
- [ ] /api/oauth/twitter/authorize 호출 → state parameter 생성
- [ ] Callback URL에 state 포함
- [ ] state 값 검증 (server-side session과 비교)
- [ ] Reddit/LinkedIn OAuth도 동일 원칙 적용

## P0 — Promotion content quality (홍보효과)

### P-AI-01 AI-tell sniffer runs before posting
- [ ] Twitter draft 작성 후 "post" 클릭 → ai-tell-sniffer 실행됨 (로그 또는 progress 표시)
- [ ] Banned phrases 감지 (e.g., "delve", "leverage", "let's dive in") → 경고 표시
- [ ] Em-dash density 체크 (> 1 per 60 words) → 경고
- [ ] 경고가 있으면 auto-post 차단 (사용자 확인 필요)

### P-AI-02 🚧 Human judgment: draft quality (사람 라벨링)
- [ ] 💬 Twitter draft: 전문적이고 자연스러운 톤? (발매 공지 기준)
- [ ] 💬 Reddit post: subreddit 커뮤니티 규범 준수? (r/programming 예상)
- [ ] 💬 LinkedIn post: formal하고 professional?
- [ ] 💬 Gitmail email: 너무 generic하지 않음? personalization 눈에 띔?

## P0 — Gitmail effectiveness (홍보효과)

### P-GM-01 🚧 Email delivery (사람 라벨링)
- [ ] 💬 Test recipient 메일함 확인: recipient@example.com 이메일 도착?
- [ ] 💬 Mail headers: From, Reply-To, Subject, List-Unsubscribe 모두 있음?
- [ ] 💬 Unsubscribe link 클릭 → 실제로 구독 해제됨?

### P-GM-02 Recipient list quality
- [ ] Recipients 테이블의 GitHub logins 확인 가능한가? (public profile 검증)
- [ ] Starred_repo 값이 실제로 프로젝트와 유사한 repos? (keyword match)
- [ ] Duplicates 없음?
- [ ] Email 주소 유효한 형식? (간단한 regex 확인)

### P-GM-03 Template rendering
- [ ] Email body: {{login}} → 실제 GitHub username
- [ ] Email body: {{starred_repo}} → 실제 repo name 또는 URL
- [ ] Email Subject: 각 recipient마다 고유한 내용? (또는 generic하지만 일관성 있음?)

### P-GM-04 Unsubscribe mechanism
- [ ] Email body에 "unsubscribe" 링크 포함되었나?
- [ ] List-Unsubscribe header 형식: `<https://viralman/unsub?token=...>`
- [ ] Unsubscribe link 클릭 → HTTP 200, user marked as unsubscribed
- [ ] Subsequent sends: unsubscribed users 제외됨

### P-GM-05 Rate limiting under load
- [ ] 100명 이상 recipients 시뮬레이션
- [ ] SMTP 연결 당 30/min 제한 준수 (또는 설정된 RATE_PER_MIN)
- [ ] Send progress: real-time 업데이트 (UI에서 진행률 표시)
- [ ] Send 도중 network 끊김 시 recovery? (또는 다시 시작 가능)

## P0 — Twitter / X integration (사용성)

### U-TW-01 OAuth login flow
- [ ] /setup "Twitter" 탭 → "login" 버튼 클릭
- [ ] dev.twitter.com 인증 페이지로 리다이렉트
- [ ] 허가 → localhost:8765 콜백
- [ ] 콜백 후 "connected ✓" 또는 유사 텍스트 표시

### U-TW-02 Draft composition
- [ ] /twitter 페이지 → "generate" 버튼 (project 설정 후)
- [ ] AI draft 생성 (초 단위)
- [ ] Draft 수동 편집 가능 (textarea)
- [ ] Thread: `---` separator로 여러 트윗 분리 가능

### U-TW-03 Hashtag targeting
- [ ] "hashtags" 필드: 추천 hashtags 표시 (또는 수동 입력)
- [ ] Hashtag 추가 → 개별 칩으로 표시
- [ ] "add hashtag" 버튼 동작

### U-TW-04 Post action
- [ ] "post" 버튼 활성화 (draft + hashtags 있을 때)
- [ ] OAuth token 존재 → POST /api/posts/twitter
- [ ] Response: `posted ✓` 또는 success 메시지
- [ ] Browser: X/twitter.com 새 탭 열기 또는 URL 제공

## P0 — Reddit integration (사용성)

### U-RD-01 OAuth login flow
- [ ] /setup "Reddit" 탭 → "login" (web-app) 클릭
- [ ] reddit.com/authorize 페이지로 리다이렉트
- [ ] 허가 → localhost:8765 콜백
- [ ] 콜백 후 "connected ✓" 텍스트 표시

### U-RD-02 Post composition
- [ ] /reddit 페이지 → "generate" 버튼 (project 설정 후)
- [ ] Title + body (markdown) draft 생성
- [ ] 수동 편집 가능 (textarea)

### U-RD-03 Subreddit targeting
- [ ] "subreddits" 필드: 추천 subreddits 표시 (e.g., r/programming)
- [ ] "scan threads" 버튼: 선택한 subreddit의 최근 스레드 fetch
- [ ] 스레드 목록: 제목, upvotes, comment count 표시
- [ ] Subreddit 추가 → 개별 칩으로 표시
- [ ] 첫 번째 subreddit으로 post 진행

### U-RD-04 Post action
- [ ] "post" 버튼 활성화 (title + body + subreddit)
- [ ] OAuth token 존재 → POST /api/posts/reddit
- [ ] Response: post URL (reddit.com/r/XXX/comments/...) 반환
- [ ] Browser: Reddit 새 탭 열기 또는 URL 제공

## P0 — LinkedIn integration (사용성)

### U-LI-01 OAuth login flow
- [ ] /setup "LinkedIn" 탭 (있는 경우) → "login" 클릭
- [ ] linkedin.com/oauth 페이지로 리다이렉트
- [ ] 허가 → localhost:8765 콜백
- [ ] 콜백 후 "connected ✓" 텍스트 표시
- [ ] Token expiration: 콜백 후 `expires_at` 저장 (60일 후 refresh 필요)

### U-LI-02 Post composition (if LinkedIn posting enabled)
- [ ] /linkedin 페이지 (또는 다른 경로) → "generate" 버튼
- [ ] LinkedIn-friendly draft 생성 (formal tone)
- [ ] 수동 편집 가능

## P1 — Targeting & Content

### P-TG-01 Hashtag suggestions
- [ ] Project keywords → hashtag suggestions (viralman-generated)
- [ ] User-added hashtags 병렬 처리 (AI suggestions + manual)

### P-TG-02 Subreddit suggestions
- [ ] Project keywords → subreddit suggestions (r/programming, r/opensource 등)
- [ ] "scan threads" 결과가 actual subreddit threads인지 확인

### P-NM-01 Name/URL validation
- [ ] Project name 비어있음 → 경고 또는 에러
- [ ] Project URL 비어있음 → 경고 또는 에러
- [ ] Description 비어있음 → "description is required" 에러

## P2 — Accessibility (A11y)

### U-A11-01 Keyboard navigation
- [ ] Tab 키로 모든 interactive 요소 순회 가능
- [ ] Focus indicator 명확함 (outline, border, highlight)
- [ ] Modal/dropdown: Escape로 닫기 가능

### U-A11-02 Color contrast
- [ ] Text vs. background: WCAG AA 기준 (≥4.5:1 for normal text)
- [ ] Button states (active, disabled, hover): 색상만으로 판단하지 않음

### U-A11-03 Form labels + ARIA
- [ ] 모든 input에 <label> 또는 aria-label
- [ ] Fieldsets (setup tabs) aria-labelledby 또는 제목

### U-A11-04 Responsive design
- [ ] Mobile (375px): 레이아웃 reflow, 터치 타겟 ≥44px
- [ ] Tablet (768px): 중단점 준수
- [ ] Desktop (1200px+): 최대 너비 또는 full-width OK

## P2 — Error handling & Edge cases

### U-EH-01 Network timeout
- [ ] Collect recipients 중 timeout → error toast 표시
- [ ] Retry 버튼 제공?
- [ ] State 복구 (timeout 후 다시 시작 가능)

### U-EH-02 OAuth token expiration
- [ ] LinkedIn token expiration (60일 후)
- [ ] Dashboard: "token expired, re-login" 메시지 표시
- [ ] Re-login 버튼 제공

### U-EH-03 SMTP failure
- [ ] Gitmail send 중 SMTP 실패 → error 로그 + user-facing message
- [ ] Partial send (10/100 성공) → progress 표시, 재시도 옵션

### U-EH-04 Invalid project data
- [ ] Empty description + generate 시도 → validation error
- [ ] Oversized description (> 5000 chars) → warning or truncation
- [ ] Special chars (emoji, non-ASCII) → properly handled

## End-of-run summary

- Total: __ / __ pass
- P0 fails: list (e.g., "U-OB-01, U-GM-03")
- P1 fails: list
- P2 fails: list
- Blockers: list (any P0 fail that blocks release)
- Notes: (e.g., "LinkedIn not enabled in this build", "Test SMTP used Mailtrap")
- Browser versions tested: (e.g., "Chrome 125, Firefox 123, Safari 17")
- Run by: ____ (your name/email)
- Date: ____ (YYYY-MM-DD)
- Time spent: __ minutes
