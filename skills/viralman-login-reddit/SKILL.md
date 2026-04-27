---
name: viralman-login-reddit
description: Walk the user through registering a Reddit script app and saving credentials so viralman can post to Reddit. Secrets never enter the LLM context — they go through `read -s` directly into save_creds.py.
level: 2
---

# viralman-login-reddit

This skill guides the user through getting Reddit API credentials and saving them to `~/.viralman/.env` so `post_reddit.py` can authenticate. Reddit's API is free for personal script-app use.

## Trigger phrases

Auto-trigger on:
- `/viralman-login-reddit`
- "set up reddit for viralman"
- "viralman reddit 로그인", "viralman 레딧 연결"

## Boundaries (read first)

- **Never accept a password or client_secret in the chat.** They get logged. Always have the user pipe them through `read -s` into `scripts/save_creds.py --stdin`.
- **Do not** try to scrape https://www.reddit.com/prefs/apps with WebFetch — Reddit blocks unauthenticated bots and the page is logged-in only.
- The user runs the shell commands; you only print them. Do not run `read -s` yourself; that prompt has to land in the user's terminal, not in your tool output.

## Step 1 — Register a script app

Print this verbatim and wait for the user to confirm they've completed it:

```
1. Open https://www.reddit.com/prefs/apps in your browser (logged into the account
   you want viralman to post from).
2. Scroll to the bottom and click "are you a developer? create an app...".
3. Fill in:
     name:         viralman (or whatever you prefer)
     type:         ⦿ script   ← important, must be "script"
     description:  (leave blank)
     about url:    (leave blank)
     redirect uri: http://localhost:8765
4. Click "create app".
5. The new app will show:
     - A short string under the app name  →  this is your CLIENT_ID
     - A "secret" field                   →  this is your CLIENT_SECRET
```

After the user confirms, ask them for the **client_id** in the chat (it's not a secret — it's visible to anyone with access to the app management page).

## Step 2 — Save the client_id (non-secret)

When the user provides the client_id, save it via Bash:

```bash
./scripts/save_creds.py --set REDDIT_CLIENT_ID=<client_id>
```

Also ask for and save the username:

```bash
./scripts/save_creds.py --set REDDIT_USERNAME=<username>
```

And optionally a custom user agent (default is fine):

```bash
./scripts/save_creds.py --set REDDIT_USER_AGENT='viralman/0.1.0 by <username>'
```

## Step 3 — Save the secrets via `read -s` (CRITICAL: do not type them in chat)

Tell the user to run these two one-liners in their **own terminal** (don't run them yourself — they need to type their secrets directly into their shell, not into your tool calls):

```bash
read -rs -p 'reddit client_secret: ' s && printf '%s' "$s" | \
  ./scripts/save_creds.py --stdin REDDIT_CLIENT_SECRET; unset s; echo

read -rs -p 'reddit password: ' s && printf '%s' "$s" | \
  ./scripts/save_creds.py --stdin REDDIT_PASSWORD; unset s; echo
```

If the user has 2FA enabled on Reddit, password auth via PRAW will fail. Tell them: "Reddit 2FA breaks PRAW password auth. You'll need to either disable 2FA on this account or use an app password — Reddit doesn't currently support app passwords, so the practical option is to use a dedicated posting account without 2FA."

## Step 4 — Verify

Once the user confirms the secrets are saved, run the smoke test:

```bash
./scripts/check_creds.py --platform reddit
```

Expected output: `reddit OK — u/<username>`.

If you see `401` or `invalid_grant`, the most common causes are:
- The client_secret was copied with whitespace (re-run the `read -s` line).
- The app type isn't "script" (recreate the app).
- 2FA is on (see Step 3 note).

## Step 5 — Tell the user they're done

Tell them: "Reddit is hooked up. You can now run `/viral` with `--only reddit --subreddit <name>` and it'll publish to your account."

Do not auto-trigger a test post.
