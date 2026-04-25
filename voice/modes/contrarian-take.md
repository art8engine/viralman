# Mode: contrarian-take

A specific opinion that pushes back against a specific claim. High-engagement when grounded in real experience; cringe when it isn't. Use sparingly — most "contrarian" content is performative.

## Beats

1. **The opposing position**, named specifically. Not "everyone says X" — name a piece, a talk, a meme, a specific common practice. "The version of TDD that says 'no code without a failing test first'…" — not "people who like TDD…".
2. **Why you disagree**, with a concrete experience or piece of evidence. Not "in my opinion" — show the moment you stopped agreeing.
3. **The nuanced re-statement**: what you actually believe, including where the opposing position is right.
4. **End**. No "what do you think?" — invite disagreement by being clear, not by asking.

## Required anchors

- The opposing position must be named with enough specificity that someone who holds it could nod and say "yes, that's what I believe".
- A concrete experience, project, or counter-example. No "in theory" arguments.

## Length

- LinkedIn: 800–1500 chars. The setup needs room.
- Reddit (r/programming, r/cscareerquestions, r/ExperiencedDevs): 300–700 words.
- X: 4-tweet thread. Tweet 1 = the position you're attacking, tweet 2 = your evidence, tweet 3 = the steelman, tweet 4 = your version.

## Anti-patterns

- Don't be smug. The most common failure mode of contrarian posts is the writer sounding like they're sneering.
- Don't strawman. If the opposing position is named at its weakest, the post fails — and so does the engagement.
- Don't claim the consensus is wrong about something where you don't have lived experience. Theoretical contrarianism reads as bait.
- Don't end on "this is why X is wrong". End on "this is what I do instead", with specifics.

## Worked example (LinkedIn, ~1100 chars)

> Most "best practices for code review" guides recommend reviewing every PR with a structured checklist: correctness, readability, performance, security, tests. I followed this for two years on a team of seven and our review latency was 36 hours.
>
> Here's where I think the checklist version is wrong: it treats every PR the same. A typo fix, a config bump, and a 600-line refactor all get the same 5-section review and the same reviewer attention budget. The result is reviewers exhausted on the small stuff and fast-tracking the big stuff because they ran out of focus.
>
> What I do now: triage at the PR title. Three buckets — `chore`, `bugfix`, `change`. `chore` gets a glance. `bugfix` gets the diff and a question about how it was tested. `change` gets the full review, and the reviewer is allowed to take half a day. Latency dropped from 36 hours to 4 because reviewers stopped budget-spreading.
>
> The checklist isn't wrong, it's just applied at the wrong granularity. The granularity is the PR type, not every PR.

## Worked example (X, 4-tweet thread)

```
1/ "Every PR needs a 5-section structured review" gave my team a 36-hour review latency.

The advice isn't wrong. It's applied at the wrong granularity.
---
2/ A typo fix and a 600-line refactor were getting the same review attention. Reviewers burned out on small stuff and fast-tracked big stuff because they were out of focus.
---
3/ The structured-review people are right that the dimensions matter (correctness, tests, perf, security, readability). They're wrong that every PR needs every dimension.
---
4/ What I do now: triage at the title. `chore` gets a glance. `bugfix` gets a diff + a "how was this tested?". `change` gets the full review with a half-day budget. 36hr → 4hr.
```
