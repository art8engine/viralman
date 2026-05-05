---
description: One-stop setup for viralman — pick a category (gitmail / twitter / reddit / linkedin) and configure only that one. Plain-text token paste is allowed with a warning; the env-pipe path is recommended.
allowed-tools: Read, Bash(./scripts/save_creds.py:*), Bash(./scripts/lib/github_search.py:*), Bash(./scripts/gitmail.py:*), Bash(./scripts/check_creds.py:*)
argument-hint: "[gitmail|twitter|reddit|linkedin] [--plain] [--check]"
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
어떤 채널을 셋업하시겠어요?

  1. gitmail  — GitHub 스타거 대상으로 콜드 메일 발송 (가장 많이 쓰는 흐름)
  2. twitter  — X 트윗 자동 게시 (선택 — 기본은 compose URL 폴백)
  3. reddit   — 서브레딧 게시
  4. linkedin — LinkedIn 게시

번호 또는 이름으로 답해주세요.
```

Wait for the user's reply. Do not proceed until you have an unambiguous answer.
Accept both numbers (`1`–`4`) and names (`gitmail`, `twitter`, `reddit`,
`linkedin`). If the answer is unclear, ask once more — then stop.

## Step 1 — plain-text warning (when applicable)

If `--plain` was passed **or** the user pastes something that looks like an API
key / token directly into the chat (long alphanumeric string, Bearer prefix,
`ghp_…`, etc.), print this warning **once**:

> ⚠ 토큰을 채팅창에 평문으로 입력하셨습니다. 이 내용은 LLM 컨텍스트와 대화
> 로그에 남을 수 있습니다.
>
> 더 안전한 방법:
> `read -rs -p '<KEY>: ' s && printf '%s' "$s" | ./scripts/save_creds.py --stdin <KEY>; unset s; echo`
>
> 그래도 진행하시면 `./scripts/save_creds.py --set <KEY>=<VALUE>`로 저장합니다.

Ask for confirmation ("진행할까요? y/n"). After the user confirms, proceed with
`./scripts/save_creds.py --set KEY=VALUE`. Do not show the warning again for
subsequent keys in the same session.

## Step 2 — run the channel-specific setup

Branch on the chosen category. Follow the procedure from the corresponding skill
file exactly — see `skills/viralman-setup/SKILL.md` for the full per-channel
steps.

| Category  | Skill reference                                  |
|-----------|--------------------------------------------------|
| gitmail   | `skills/viralman-login-gitmail/SKILL.md`         |
| twitter   | `skills/viralman-login-twitter/SKILL.md`         |
| reddit    | `skills/viralman-login-reddit/SKILL.md`          |
| linkedin  | `skills/viralman-login-linkedin/SKILL.md`        |

Differences from the individual skills:
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
