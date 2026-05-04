---
name: viralman-login-gitmail
description: One-time setup for the gitmail flow — save GITHUB_TOKEN, SMTP credentials, and an LLM provider API key (Claude / OpenAI / Gemini) to ~/.viralman/.env. Secrets never enter the LLM context — they go through `read -s` directly into save_creds.py.
level: 2
---

# viralman-login-gitmail

This skill walks the user through the three credential bundles that gitmail
needs:

1. **GitHub** — for searching repos and listing stargazers.
2. **SMTP** — for sending the actual emails.
3. **One LLM provider** — for analysing the project and composing emails.

Everything is saved to `~/.viralman/.env` with mode 600 via the same
`save_creds.py` pattern the other login skills use. **Secrets stay out of the
LLM context** — the user pipes them through `read -s` in their own terminal.

## Trigger phrases

Auto-trigger on:

- `/viralman-login-gitmail`
- "set up gitmail", "set up viralman email"
- "viralman gitmail 로그인", "gitmail 셋업"

## Boundaries (read first)

- **Never accept passwords / API keys in chat.** They get logged. Always have
  the user pipe them through `read -s` into `scripts/save_creds.py --stdin`.
- **Never run** `read -s` yourself; the prompt has to land in the user's own
  terminal, not in your tool output.
- **Do not** WebFetch any platform dashboard — they're logged-in surfaces.
- The user runs the shell commands; you only print them.

## Step 1 — GitHub token

Print verbatim:

```
1. Open https://github.com/settings/tokens?type=beta in your browser.
2. Click "Generate new token". Choose Fine-grained tokens.
3. Token name: viralman-gitmail
   Expiration: pick whatever (90 days is fine).
   Repository access: Public Repositories (read-only) — that's it.
   Permissions: leave defaults — public read is enough.
4. Click "Generate token" and copy the token.
```

Then have the user save it via:

```bash
read -rs -p 'GITHUB_TOKEN: ' s && printf '%s' "$s" | \
  ./scripts/save_creds.py --stdin GITHUB_TOKEN; unset s; echo
```

Verify rate limit jumps from 60 → 5000:

```bash
./scripts/lib/github_search.py ratelimit
```

## Step 2 — SMTP

Tell the user the dashboard works with any SMTP. Two common paths:

### Gmail (free, requires app password)

```
1. Open https://myaccount.google.com/apppasswords (you must have 2FA enabled).
2. Create a new app password named "viralman".
3. Copy the 16-char password (no spaces).
```

```bash
./scripts/save_creds.py --set SMTP_HOST=smtp.gmail.com --set SMTP_PORT=587 --set SMTP_SECURITY=starttls
./scripts/save_creds.py --set SMTP_USER=<your-gmail-address>
./scripts/save_creds.py --set SMTP_FROM=<your-gmail-address>
./scripts/save_creds.py --set SMTP_FROM_NAME='<your name>'

read -rs -p 'gmail app password: ' s && printf '%s' "$s" | \
  ./scripts/save_creds.py --stdin SMTP_PASSWORD; unset s; echo
```

Tell the user: Gmail caps at ~500 emails/day per account. For larger runs use
SendGrid / Mailgun / SES.

### SendGrid / Mailgun / SES (recommended for larger sends)

Provider-specific. Common shape:

```bash
./scripts/save_creds.py --set SMTP_HOST=<provider-host> --set SMTP_PORT=587 --set SMTP_SECURITY=starttls
./scripts/save_creds.py --set SMTP_USER=apikey            # SendGrid uses literal 'apikey'
./scripts/save_creds.py --set SMTP_FROM=hello@yourdomain.com
read -rs -p 'SMTP password / API key: ' s && printf '%s' "$s" | \
  ./scripts/save_creds.py --stdin SMTP_PASSWORD; unset s; echo
```

Optional: bump the per-minute rate limit (default 30):

```bash
./scripts/save_creds.py --set SMTP_RATE_PER_MIN=60
```

## Step 3 — pick ONE LLM provider

The user only needs one of the three. If they already use Claude Code with an
Anthropic key, that's the easy choice.

### Claude (recommended)

```
1. Open https://console.anthropic.com/settings/keys
2. Create a new key.
```

```bash
read -rs -p 'ANTHROPIC_API_KEY: ' s && printf '%s' "$s" | \
  ./scripts/save_creds.py --stdin ANTHROPIC_API_KEY; unset s; echo
```

### OpenAI

```bash
read -rs -p 'OPENAI_API_KEY: ' s && printf '%s' "$s" | \
  ./scripts/save_creds.py --stdin OPENAI_API_KEY; unset s; echo
```

### Gemini

```bash
read -rs -p 'GEMINI_API_KEY: ' s && printf '%s' "$s" | \
  ./scripts/save_creds.py --stdin GEMINI_API_KEY; unset s; echo
```

## Step 4 — Verify

```bash
./scripts/lib/github_search.py ratelimit
./scripts/gitmail.py analyse "A K8s autoscaler in Go that cuts cost by 47%"
```

Both should succeed. The first prints `{"resources": ...}`; the second
prints a JSON object with `summary`, `keywords`, `topics`, `value_prop`.

If `gitmail.py analyse` errors with "No LLM provider configured", the user
hasn't saved any of the three keys yet.

## Step 5 — Done

Tell the user: "gitmail is hooked up. Go to http://localhost:8765/gitmail
in the dashboard and start a dry-run job to see it work end-to-end before
any email is actually sent."

Do not auto-trigger a real run. Even a dry-run hits the GitHub API; even
gentle traffic counts toward the daily LLM budget.
