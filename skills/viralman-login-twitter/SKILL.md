---
name: viralman-login-twitter
description: Walk the user through registering an X (Twitter) developer app and saving credentials so viralman can post via the API. The free tier supports ~1,500 posts/month — plenty for personal use. Skipping this still works (compose-URL fallback).
level: 2
---

# viralman-login-twitter

> **권장 진입점**: 새로 시작하시면 `/viralman-setup`을 사용하시는 것이 더 빠릅니다. 한 번에 채널을 고르고 그 채널만 설정합니다. 이 스킬은 특정 채널만 따로 손볼 때 또는 자동화 스크립트에서 호출 시 그대로 동작합니다.

This skill guides the user through getting X (Twitter) API credentials. **Skipping this entirely is a valid choice** — viralman will fall back to opening a `https://twitter.com/intent/tweet?text=…` URL in the user's browser for one-click posting. Set up API access only if you want fully automatic posting (e.g., for threads or scheduled batch posts).

## Trigger phrases

Auto-trigger ONLY on:
- `/viralman-login-twitter`
- "set up twitter credentials only", "twitter 자격증명만 다시 설정"

If the user says generic things like "viralman setup", "viralman 셋업",
"set up twitter for viralman", "twitter for viralman",
defer to the `viralman-setup` skill instead — it's the unified entry.

## Step 0 — 통합 셋업과의 차이

- 한 번에 채널을 고르고 싶다면 `/viralman-setup`을 사용하세요. 그 명령이 이 스킬의 절차를 그대로 호출합니다.
- 이미 다른 채널들은 셋업되어 있고 이 채널만 다시 설정하려면 이 스킬을 그대로 진행하세요.

## Decide first: do they actually need API access?

Before walking through the dev-portal steps, ask the user:

```
Two ways to post to X with viralman:

  1. compose URL (default, no setup) — viralman opens a pre-filled tweet in
     your browser, you click "post". Works for any account, no rate limits
     on viralman's side.

  2. API access (this skill) — viralman posts automatically, supports
     threads of >1 tweet, no browser tab. Free tier: ~1,500 posts/month.

If you mostly post one-off tweets, option 1 is fine. Set up the API
only if you want threads or batch posting.

Continue with API setup?
```

If they say no, exit the skill and tell them they're already done — viralman uses option 1 by default.

## Boundaries (read first)

- **Never accept API secrets in chat.** Use `read -s` → `save_creds.py --stdin`.
- **Do not** WebFetch https://developer.twitter.com — it's a logged-in dashboard.
- **App permissions matter.** The default "Read" tier won't post. The user MUST set the app to "Read and write" before generating tokens. If they generate tokens at "Read" level and then upgrade later, the existing tokens will still be read-only — they have to regenerate.

## Step 1 — Register a dev account + app

Print this verbatim:

```
1. Open https://developer.twitter.com/en/portal/dashboard (logged into the
   account you want viralman to post from).
2. If you don't have a developer account yet:
     - Click "Sign up for Free Account".
     - Describe your use case in 250+ chars (just be honest: personal posting
       automation via a CLI tool you're using).
     - Accept the terms.
3. Once approved (usually instant for free tier), create a new project + app:
     - Project name:  viralman
     - Use case:      "Building tools for myself"
     - App name:      viralman-<your-handle>  (must be globally unique on X)
4. In the app settings page, find "User authentication settings" → click
   "Set up".
     - App permissions:  ⦿ Read and write    ← important
     - Type of App:      Web App / Native App  (either works)
     - Callback URI:     http://localhost:8765
     - Website URL:      https://example.com  (any valid URL)
   Save.
5. Go to "Keys and tokens" tab.
6. You'll see four things to copy:
     - API Key  (also called "Consumer Key")
     - API Key Secret
     - Access Token
     - Access Token Secret
   Click "Generate" or "Regenerate" if any are missing.

   IMPORTANT: regenerate the Access Token AFTER setting permissions to
   Read and write — otherwise the token will be read-only.
```

Wait for confirmation that the user has these four values in front of them.

## Step 2 — Ask for the handle (non-secret)

```bash
./scripts/save_creds.py --set TWITTER_HANDLE=<handle without @>
```

## Step 3 — Save the four secrets via `read -s`

Tell the user to run these in their own terminal:

```bash
read -rs -p 'TWITTER_API_KEY: ' s && printf '%s' "$s" | \
  ./scripts/save_creds.py --stdin TWITTER_API_KEY; unset s; echo

read -rs -p 'TWITTER_API_SECRET: ' s && printf '%s' "$s" | \
  ./scripts/save_creds.py --stdin TWITTER_API_SECRET; unset s; echo

read -rs -p 'TWITTER_ACCESS_TOKEN: ' s && printf '%s' "$s" | \
  ./scripts/save_creds.py --stdin TWITTER_ACCESS_TOKEN; unset s; echo

read -rs -p 'TWITTER_ACCESS_SECRET: ' s && printf '%s' "$s" | \
  ./scripts/save_creds.py --stdin TWITTER_ACCESS_SECRET; unset s; echo
```

## Step 4 — Verify

```bash
./scripts/check_creds.py --platform twitter
```

Expected: `twitter OK — @<handle> (id=...)`.

Common failures:
- `403` with "oauth1 app permissions" message → app is still at Read-only. Go back to Step 1.4 and Step 1.6.
- `401 Unauthorized` → tokens were generated *before* setting Read+Write. Regenerate them under "Keys and tokens" and re-run Step 3.
- `429 rate limit` → free tier monthly cap hit. Wait for the next billing cycle.

## Step 5 — Done

Tell the user: "X is hooked up. `/viral --only x` will now post via the API and support threads."

Do not auto-trigger a test post — even one tweet eats their monthly quota.

---

이 채널만 다시 설정할 때는 `/viralman-login-twitter`도 동일한 절차를 안내합니다. 다른 채널도 함께 설정하시려면 `/viralman-setup`을 사용하세요.
