---
name: copy-prep
description: Shared building blocks for project-promotion skills — project intent capture, language picker, subject format presets, and the "manual / 직접 입력하기" override pattern. Not user-invokable on its own; channel skills (gitmail / viral / future channels) reference this file so each channel skill can stay focused on its unique pipeline (collection, send, post, log).
level: 0
---

# copy-prep — shared content-prep building blocks

Not user-invokable. Channel skills cite a section here when they need the shared sub-routine, so they don't each redefine the same option lists / prompts.

When another skill says "follow §Foo from `skills/copy-prep/SKILL.md`", read this file and apply the named section.

---

## §Project intent capture

Goal: turn `$ARGUMENTS` (URL and/or free text) into a stable struct the caller can use:

```
{
  url: "<github URL or empty>",
  name: "<owner/repo or user-supplied name>",
  description: "<free-text description, ≤200 chars>",
  keyword: "<first-pass keyword for search>",
}
```

Rules:

1. First token starts with `https://github.com/` → treat as URL. Do NOT fetch the README, do NOT call `gh repo view` — saves rate budget and responds faster. Derive `name` from the owner/repo path. Derive `keyword` from the repo slug.
2. If extra free text is present, it becomes `description` (overrides the keyword guess).
3. If both URL and description are missing, ask once and wait. Do not guess.

Print 2–3 lines back to the user before the batch question so they have shared context:

```
Project: <name> (<url>)
What I understood: <one-line summary — based on user description + URL slug>
If this is right, please answer the questions below. If wrong, correct me
and I'll redo it.
```

---

## §Language picker

Used wherever the caller needs to pick the user-facing language of the output.

| option | description |
|---|---|
| Korean (default) | 기본값. Korean audience. |
| English | English output. For global outreach. |
| Chinese | 中文. |
| Japanese | 日本語. |

Caller maps the picked value into its own arg shape (e.g. gitmail prefixes `--tone "in English, …"`; viral sets `--lang ko/en`). For Korean, the prefix is omitted.

---

## §Voice register vs language (caveat for callers)

Don't confuse the two:

- **Language** (above) is the output language — shared across channels.
- **Voice register** is how it sounds *within* that language. Each channel skill defines its own register options because the right register depends on the channel:
  - gitmail's register options are short tone hints (cold-email-appropriate).
  - viral's register options are `growth-story | casual-hype | show-and-tell | contrarian-take` (post-appropriate).

The language picker IS shared via this file; the register picker is NOT — keep it in the channel skill.

---

## §Subject format presets

Used only by callers that produce a subject line (gitmail; LinkedIn announcement posts; Reddit titles when user wants help). Skip in channels with no subject (X posts; Reddit body-only flow when the title is user-supplied).

| key | pattern | example (Argus, English) |
|---|---|---|
| `auto` | LLM picks freely. May vary per recipient. | (LLM-decided) |
| `headline` | "Hi, now you can easily &lt;benefit&gt; too." | Hi, now you can easily watch your JVM in production too. |
| `tag` | `[Label] product — one-line value` | [New Tool] Argus — JVM monitoring without the heavy agent. |
| `simple` | Under 30 chars, no marketing tone | Argus — JVM monitoring |
| `manual` (직접 입력하기) | User provides the exact subject AND body. Skips the LLM entirely — placeholder substitution per recipient is supported by callers that have per-recipient placeholders (e.g. gitmail). | (waiting for your input) |

Pass each option's example text into the `preview` field of `AskUserQuestion` so the user can compare side-by-side. The `manual` option must be placed **last** so the LLM-driven choices stay grouped.

---

## §Manual override pattern (직접 입력하기)

Common pattern: when the user picks `manual` (subject) or otherwise signals "I'll write it myself", do NOT proceed to the next pipeline step. Ask one follow-up prompt that requests:

1. the subject line, if the channel has one (free text; placeholders allowed per channel — gitmail supports `{login}`, `{starred_repo}`, `{project_name}`, `{project_url}`).
2. the body (free text; multi-line OK; same placeholders as above).

The caller routes user-provided content through its channel's "no-LLM" path:

| channel | no-LLM path |
|---|---|
| gitmail | `--prewritten-subject "<subject>" --prewritten-body /tmp/gitmail_user_body.txt` (skips compose step entirely; placeholders substitute per recipient). |
| viral / X / Reddit / LinkedIn | Skip the `viral-writer` agent. Pass the user-provided body directly to the matching `scripts/post_*.py`. Run the `ai-tell-sniffer` once for safety; if the user explicitly says "post as-is", honor that and skip sniffer. |

Always preview what will be sent before the live action — even on the no-LLM path. The preview proves placeholder substitution worked.

---

## §Boundaries

- This file never holds credentials, never reads `~/.viralman/.env`, never calls scripts on its own. Channel skills do that.
- The structs and option tables defined here are stable contracts; if a channel skill needs a new field, add it here so all callers see the same shape.
- This skill is not user-invokable. There is no `/copy-prep` slash command. Trigger phrases are intentionally absent.
