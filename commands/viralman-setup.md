---
description: Single entry point for viralman — bootstraps the package itself if not installed (clone, venv, flask, shim), auto-updates to the latest published version when a newer one is available, then walks the user through saving only the channel(s) they need (gitmail / twitter / reddit / linkedin). Plain-text token paste allowed with a security warning; recommended path is `read -s`.
allowed-tools: Read, Bash(./scripts/save_creds.py:*), Bash(./scripts/lib/github_search.py:*), Bash(./scripts/gitmail.py:*), Bash(./scripts/check_creds.py:*), Bash(curl:*), Bash(python3:*), Bash(git pull:*), Bash(pipx:*), Bash(.venv/bin/pip:*), Bash(pipx list:*)
argument-hint: "[gitmail|twitter|reddit|linkedin] [--plain] [--check] [--reinstall]"
---

# /viralman-setup — pick one channel and configure it

Configure credentials for exactly one viralman channel at a time. Calling this
command multiple times (once per channel) is the intended workflow — do not try
to set up more than one channel in a single invocation.

## Arguments

`$ARGUMENTS` first token: category (`gitmail` / `twitter` / `reddit` / `linkedin`).
If omitted, ask the user once and wait for their answer. Do not guess or assume.

Flags:
- `--plain` : plain-text token mode — the user will paste credentials directly
  into the chat. Output the security warning once, then proceed with
  `./scripts/save_creds.py --set KEY=VALUE`. Do not refuse.
- `--check` : show the list of currently saved key names, then exit.
  Runs `./scripts/save_creds.py --show-keys`. Does not reveal values.
- `--reinstall` : force-recreate the `.venv` even if it already exists (passed
  through to the Step 0 bootstrap). Use when dependencies are corrupted or a
  Python version change requires a fresh environment.

Only one flag is accepted at a time. If both appear, `--check` wins (it's
read-only and safe).

## Pre-flight check

If `--check` is passed (or the user types "check what's saved" / "show my keys"):

```bash
./scripts/save_creds.py --show-keys
```

Print the key list and stop. Do not proceed to any setup steps.

## Step 0 — pick a channel (if not given)

If the category was not provided as the first argument, print exactly once:

```
Which channel do you want to set up?

  1. gitmail  — cold email outreach to GitHub stargazers (most common)
  2. twitter  — automated X/Twitter posting (optional — default falls back to compose URL)
  3. reddit   — subreddit posting
  4. linkedin — LinkedIn posting

Reply with the number or the name.
```

Wait for the user's reply. Do not proceed until you have an unambiguous answer.
Accept both numbers (`1`–`4`) and names (`gitmail`, `twitter`, `reddit`,
`linkedin`). If the answer is unclear, ask once more — then stop.

## Step 1 — plain-text warning (when applicable)

If `--plain` was passed **or** the user pastes something that looks like an API
key / token directly into the chat (long alphanumeric string, Bearer prefix,
`ghp_…`, etc.), print this warning **once**:

> ⚠ You pasted a token in plain text in this chat. The contents may be
> retained in the LLM context and the conversation log.
>
> Safer alternative:
> `read -rs -p '<KEY>: ' s && printf '%s' "$s" | ./scripts/save_creds.py --stdin <KEY>; unset s; echo`
>
> If you continue anyway, the token will be saved via `./scripts/save_creds.py --set <KEY>=<VALUE>`.

Ask for confirmation ("Proceed? y/n"). After the user confirms, proceed with
`./scripts/save_creds.py --set KEY=VALUE`. Do not show the warning again for
subsequent keys in the same session.

## Step 2 — run the channel-specific setup

Branch on the chosen category and follow the matching section in
`skills/viralman-setup/SKILL.md` (Step 3a/3b/3c/3d). The skill file is the
single source of truth for per-channel procedures.

- Plain-text `--plain` mode is accepted here (with the warning above).
- Only the chosen channel is touched. Never ask about or modify credentials for
  other channels during this run.

## Step 3 — verify

After saving credentials, run the appropriate smoke test:

```bash
# gitmail
./scripts/lib/github_search.py ratelimit
./scripts/gitmail.py analyse "A quick test project"

# twitter / reddit / linkedin
./scripts/check_creds.py --platform <category>
```

Report the outcome. If the check fails, surface the error and suggest the most
likely fix (see the skill file for common failure modes).

## Boundaries

- **Never** read, echo, or `cat` `~/.viralman/.env`. `--show-keys` only shows
  key names, not values. That is the only safe introspection command.
- Plain-text token warning is shown **once per session**, not once per key.
  After the user confirms, proceed silently for subsequent keys.
- Category must come from the user — never infer it from context or prior
  conversation. Ask if missing.
- Do not set up more than one channel per invocation.
- Do not trigger a live send/post after setup completes, even as a "smoke test".
  Read-only checks (`ratelimit`, `check_creds.py --platform`) are fine.
- If the user provides a category that is not one of the four listed, tell them
  which four are supported and ask again.
