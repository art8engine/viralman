# Mode: growth-story

Engaging, makes the reader feel they learned something through the writer's lens. The post tells a small specific story whose shape is *struggle → discovery → result*. Reader-growth comes from being inside the protagonist's head when the realization lands — not from being told a lesson at the end.

## Beats

1. **Concrete opener**: a specific moment / number / name. ≤15 words.
2. **The struggle**: what was hard or wrong, in concrete terms. Not "it was challenging" — name the actual obstacle. 1–3 sentences.
3. **The turning point**: what changed. A line of code, a conversation, a doc you found, a thing you tried out of desperation. Ideally one sentence; this is the highest-density moment of the post.
4. **The result**: what happened after. Concrete: number, time saved, bug fixed. ≤2 sentences.
5. **End**. No lesson summary. No "what this taught me". The result is the ending.

## Required anchors

- At least one **admission of struggle or doubt** (§3 of `ai-tells.md`).
- At least one **specific** anchor: number, name, time.

## Length

- Reddit: 200–600 words. The shape is forgiving here — readers tolerate setup.
- LinkedIn: 600–1200 chars. Line breaks every 1–2 sentences. The turning point gets its own line.
- X: 1 tweet if the story is small; 3-tweet thread if not. Beat 1 = tweet 1 hook, beat 2+3 = tweet 2, beat 4 = tweet 3.

## Anti-patterns specific to this mode

- Don't say "I was struggling" — show what you tried that didn't work.
- Don't compress the turning point into "and then it clicked". Name what clicked.
- Don't moralize at the end. The reader extracts the lesson; you don't deliver it.
- Don't sandwich the story between framing ("So I want to share a story about the time…" / "Hopefully this is useful to someone").

## Worked example (LinkedIn, ~900 chars)

> Three weeks chasing a flaky integration test. The fix was one line.
>
> The test would pass locally, pass on CI sometimes, and fail on Mondays. I added retries. I added sleeps. I added logging that proved nothing. By week two I'd convinced myself the bug was in Postgres.
>
> Then a coworker pointed at the test name: `test_user_can_post_after_signup`. The signup step ran in a fixture with `scope=session`. On Mondays, the session was the first run after the weekend's container rebuild — and the fixture's UUID collided with a row left over from the previous CI image.
>
> One line: `pytest.fixture(scope="function")`.
>
> Three weeks of "the database is haunted" was a fixture scope.

(Notice: no closing line. The fix is the ending.)

## Worked example (Reddit r/programming, ~350 words)

> TITLE: TIL `pytest` fixture scope can collide across CI image rebuilds
> BODY:
> Spent the last three weeks chasing a test that passed locally and failed on the first CI run after weekend container rebuilds. Posting because I'd never seen this failure mode named anywhere and maybe it'll save someone else a fortnight.
>
> The test: `test_user_can_post_after_signup`. The signup created a User with a deterministic UUID via a fixture scoped `session`. Idea was to reuse the row across the test module — fine. Problem: `session` here meant the *pytest session*, not the database session, and our CI image was getting rebuilt every Sunday. The first Monday run started clean, the fixture inserted the same UUID, and the rebuilt-image's `pg_dump` snapshot already had a row at that UUID from the previous image. Conflict, exception, test fail. Tuesday onwards the snapshot moved on, fixture happy, test green.
>
> Things I tried before finding it:
> - retry decorator (masked it for one week, came back)
> - `pytest -p no:randomly` (no effect)
> - rewriting the auth flow (still failed)
> - blaming Postgres locking (Postgres is fine)
>
> The fix:
> ```python
> @pytest.fixture(scope="function")
> def signup_user(...):
>     ...
> ```
> One word.
>
> Two things I'd do differently:
> 1. Read the fixture's scope before assuming a flake is real.
> 2. Stop seeding deterministic UUIDs in CI fixtures.

## Worked example (X, 3-tweet thread)

```
1/ Three weeks chasing a flaky test. The fix was one line.

The test passed locally. Passed on CI most days. Failed on Mondays.
---
2/ I added retries, sleeps, log lines that proved nothing. By week two I was blaming Postgres.

Coworker pointed at the test name. The signup fixture was `scope="session"` — and CI rebuilt the container every Sunday.
---
3/ Mondays were the first run after rebuild. Fixture inserted the same UUID it always had. Snapshot row from the previous image was still there.

Fix: `scope="function"`.
```
