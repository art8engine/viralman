# Platform norms

What "fits" each platform. Length, formatting, register, and the platform-specific tells to avoid.

---

## Reddit

**Title**: 1 line, under ~100 chars, no clickbait. Should answer "what is this post" not "click for shock". Avoid `[OC]`/`[Discussion]` tags unless the subreddit's rules require them.

**Body**: Markdown allowed and expected. Code blocks with triple-backtick. Paragraphs separated by blank lines. Inline links as `[text](url)`. Length: anywhere from 100–800 words depending on subreddit. Long-form is welcome on r/programming, r/MachineLearning, r/startups, r/personalfinance. Short is better on r/funny, r/gaming, r/AskReddit.

**Register**: depends entirely on the subreddit. r/programming = technical, dry, skeptical, prove-your-point. r/SideProject = enthusiastic but specific. r/learnprogramming = patient, helpful. r/AskReddit = personal, narrative.

**What gets you downvoted**:
- Self-promo without context. Don't drop a GitHub link with no story.
- Hashtags. Reddit doesn't use them. They mark you as "I crossposted this from elsewhere".
- Asking for upvotes ("if you found this useful, upvote!").
- Title that doesn't match body.
- "Hello fellow programmers!" — anything that signals you don't normally hang out there.

**The text the writer should produce** (as instructed in `viral-writer.md`):
```
TITLE: <title>
BODY:
<markdown body>
```

---

## X (Twitter)

**Length**: 280 chars per tweet. If the substance needs more, format as a thread of numbered tweets (`1/`, `2/`, …) up to ~4 tweets. Don't pre-announce ("🧵 thread on X coming up") — just start.

**Formatting**: No markdown. Line breaks within a tweet are fine and used for emphasis. No headers. URLs count toward chars (treat any URL as 23 chars per X's t.co rule). Hashtags up to 2; choose domain-specific (`#golang`, `#k8s`) over generic (`#tech`, `#growth`).

**Register**: Punchy, opinion-forward, often funny. The first 8–12 words are the entire game — they're the hook in the timeline preview. The post should reward the click but the click is optional.

**Threads**: Each tweet should stand alone *and* contribute to the thread. Don't end a tweet on a comma — end on a period or a beat that pulls the eye to the next.

**What gets you ratio'd**:
- "I didn't think this would happen, but…" cliffhanger openers.
- "🧵👇 a story about how I…" — the AI-marketing-thread cadence.
- Excessive emoji. Cap at 1 per tweet, often 0.
- Engagement bait at the end ("RT if you agree!").

**The text the writer should produce**: just the tweet body, or for a thread, body separated by `---` between tweets:

```
First tweet here, ≤280 chars.
---
2/ Second tweet here.
---
3/ ...
```

---

## LinkedIn

**Length**: up to 3000 chars total, but the "see more" truncation hits at ~210 chars on mobile, so the first 1–2 lines are the entire hook. Aim for 600–1200 chars total in most cases.

**Formatting**:
- Plain text. LinkedIn does not render Markdown.
- Line breaks every 1–2 sentences for skimmability. A wall of text gets scrolled.
- No headers (`#`) — they render as literal `#`.
- Hashtags: max 3, domain-specific only. **No** `#innovation`, `#growth`, `#leadership`, `#mindset`, `#success`, `#motivation`, `#entrepreneurship`.
- One emoji at most, and only if natural.

**Register**: Professional but personal. Stories beat lessons. Specifics beat platitudes. The platform rewards posts where the writer is the *protagonist* of a small concrete story, not the *narrator* of an abstract principle.

**The shape to avoid** (most-common LinkedIn-AI-slop pattern):
```
Hook line.
- Bullet 1
- Bullet 2
- Bullet 3
What do you think?
```
Anything resembling this gets flagged. Replace bullets with prose, or use 2 or 4+ bullets.

**Closers**: The post should end on a concrete beat from the story, not a "what do you think?" / "Agree?" / "Drop a 👇 below" optimization-theater question.

**The text the writer should produce**: just the post body, no header.

---

## Cross-platform: hook discipline

The first 8–15 words of every post is doing 90% of the work. They should:

- Name a specific thing (number, person, repo, moment).
- Promise a payoff that the body actually delivers.
- Not be a question, unless the question is genuinely intriguing and not "Have you ever wondered…".

Hooks the sniffer flags:
- "Have you ever wondered…"
- "Let me tell you about the time…"
- "I want to share something…"
- "Today I learned that…"
- "Here's a wild story…"

Hooks that work (texture only):
- "We accidentally ran the migration on prod at 4am."
- "The autoscaler I shipped last sprint hit a 47% bill cut. It also broke once."
- "Three weeks debugging a flaky test, fix was one line."
