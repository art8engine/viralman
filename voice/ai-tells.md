# AI Tells — the things that make a post smell like a chat assistant wrote it

This file is the spec for `ai-tell-sniffer`. Every heuristic below is something a writer can check, and every flag below should cause a rewrite. The deterministic ones (regex/density) are also implemented in `scripts/lib/sniffer_check.py` so you can run them as a script instead of by eye.

---

## 1. Banned phrasings (hard regex)

If the draft contains any of these (case-insensitive, word-boundary), flag it.

- `\bdelve\b`, `\bdelving\b`, `\bdelved\b`
- `\btapestry\b`
- `\bleverage\b`, `\bleveraging\b` (verb sense; the noun "leverage" in finance is fine)
- `\bnavigate the\b` followed by `landscape|complexities|terrain|waters`
- `\bstands as a testament\b`
- `\bin today's (fast-paced|ever-evolving|rapidly changing|digital) world\b`
- `\blet's (dive in|dive into|unpack|explore)\b`
- `\bunleash\b`, `\bunleashing\b`
- `\bunlock the (potential|power)\b`
- `\bsupercharge\b`
- `\bgame[- ]?changer\b` — **except** the `casual-hype` mode, where it's allowed at most once
- `\bharness\b` (the verb sense, e.g., "harness the power of")
- `\bembark on a journey\b`
- `\bstreamline\b` (banned because every AI marketing post uses it; allow only if the post is literally about streamlining a pipeline)
- `\bcutting-edge\b`, `\bstate-of-the-art\b` — banned unless quoting someone
- `\brevolutionize\b`, `\brevolutionizing\b`
- `\bparadigm shift\b`
- `\bsynerg(y|ies|ize|ized)\b`
- `\brobust\b` when modifying anything other than statistics or APIs (i.e., "robust solution" → flag; "robust regression" → ok)
- `\bseamless\b`, `\bseamlessly\b`
- `\bholistic\b`
- `\bempower(s|ing|ed)?\b`
- `\bfoster(s|ing|ed)?\b` (verb)
- `\bcrucial\b`, `\bvital\b`, `\bessential\b` — these read as filler; replace with the specific stake
- `\bmoreover\b`, `\bfurthermore\b`, `\badditionally\b` at sentence starts — humans rarely write these in casual posts
- `\bin conclusion\b`, `\bto summarize\b`, `\bin summary\b`
- `\b(it|this) is( not)? (just|merely|simply) (about )?[A-Za-z\- ]+,? (it|this)('s| is)\b` — the "It's not just X — it's Y" / "It's not just X, it's Y" template, banned outright

## 2. Structural tells (heuristic, sometimes regex-able)

### 2a. Em-dash density
Count em-dashes (`—`, also normalize from `--`). If `count / words > 1/60`, flag.

### 2b. Balanced tricolon
A list/sentence with three items where `len(item_i)` is within ±15% of each other. Example trigger: "We need to ship faster, scale wider, and dream bigger." Break the parallel — make one item shorter or longer or syntactically different.

### 2c. Closing moralizer
The final paragraph (or final 2 sentences if it's a short post) starts with any of:

- "The lesson here…"
- "The takeaway is…"
- "What this taught me…"
- "If there's one thing…"
- "Sometimes the best thing…"
- "At the end of the day…"

Or it summarizes the post's point in abstract terms after the body has done so concretely. Flag and delete — the post should end on its last concrete beat.

### 2d. Hashtag rules
- Reddit: **0** hashtags. Any `#word` token in the body → flag.
- X: max **2**.
- LinkedIn: max **3**, and none of `#innovation`, `#growth`, `#leadership`, `#mindset`, `#success`, `#motivation`, `#entrepreneurship` (filler hashtags).

### 2e. Sentence length monotony
If `stdev(sentence_lengths_in_words) / mean(sentence_lengths_in_words) < 0.35`, flag. Real humans vary: short fragments, run-ons, mid-sentence pivots. AI writes evenly.

### 2f. The "Hook → 3 bullets → CTA" LinkedIn template
If a LinkedIn draft has: a one-line hook, then exactly 3 bulleted/dashed list items, then a closing question or CTA, flag it. This is the most cloned LinkedIn-AI shape on the planet. Either drop the bullets or make them 2 / 4 / 5 — anything but 3.

### 2g. Em-dash + parallel construction combo
Sentences shaped `<clause> — <clause that mirrors it grammatically>` are a strong AI tell. Limit to one per post.

### 2h. AI-favored adverb stack
Flag if the draft uses 2+ of these (or even 1 in a post under 60 words): "truly", "genuinely", "fundamentally", "essentially", "remarkably", "incredibly", "absolutely", "ultimately", "profoundly", "undoubtedly", "wholeheartedly", "inherently", "meaningfully", "effectively", "strategically", "holistically". This is a specific list, not "all -ly words" — humans use "actually" and "finally" all the time and that's fine.

### 2i. The "Three things changed everything" frame
Any sentence shaped "Here are 3 things that…" or "These 3 [nouns] changed how I…" → flag.

### 2j. Empty hedges
"At its core", "more than ever", "now more than ever", "in many ways" → all flag.

## 3. Voice anchors (must-have, not must-not)

Every draft must contain **at least one** of:

- A specific number that isn't suspiciously round (i.e., `47%` ✓, `50%` is fine if it's the real number, `100%` flagged unless contextually warranted).
- A specific name: a tool, a repo, a person, a company, a file path, a function name. NOT a placeholder like "the system" or "the team".
- A specific time anchor: "last Thursday", "after 3 weeks of X", "around 2am", "in March".
- An admission of doubt, struggle, embarrassment, or change of mind: "I was wrong about X", "I almost gave up at Y", "I didn't realize Z until …".

If none of the above is present, flag the whole draft as `no-anchor`. Anchors are what make writing read like writing instead of like a press release.

## 4. Mode-specific overlays

### casual-hype overlay
Allowed: `game-changer` (1x), `slaps`, `absolute W`, `no way`, `wild`, `actually nuts`, `goated`, `lowkey`, `fr`. Cap any of these at one each — too many in one post reads as forced.
Banned for this mode anyway: anything from §1.
Em-dash budget cut to 0 (this register doesn't use em-dashes).

### growth-story overlay
Required: at least one anchor of the "admission of doubt / struggle" type (§3 last bullet). Pure success stories without struggle read as marketing copy.
The post must have a turning point — a specific moment when something changed. If we can't point to "the line where the realization happens", flag.

### show-and-tell overlay
Required: a link or a name of the thing being shown (repo URL, product name, demo link). If absent, the post is just self-promo — flag.

### contrarian-take overlay
Required: a specific opposing view being argued against. "Everyone says X" without naming who says X is lazy. Either name a specific source or scope to "the version of X that says…".
Banned tone: smug. If the rewrite makes the writer sound like they're sneering, redo.

## 5. Platform-specific overlays

### Reddit
- No hashtags (§2d).
- TITLE: under 100 chars, no clickbait pattern ("You won't believe…", "The one thing…", "Why X is the best Y in 2026").
- The body must answer the implicit "why is this in r/<subreddit>?" — context-dropping a generic post into a specific sub flags as low-effort.

### X (Twitter)
- 280 chars OR a thread of ≤4 numbered tweets. If the post would be >280 chars, format as a numbered thread `1/`, `2/`, etc.
- Max 2 hashtags.
- No "🧵 thread incoming" type meta-announcements.

### LinkedIn
- 3000 chars max but ideally <1300 (truncation point).
- Line breaks every 1–2 sentences for skimmability — NOT one big wall.
- Banned shape: hook + 3 bullets + CTA (§2f).
- "What do you think?" / "Agree?" closers → flag. They're optimization theater.

## 6. Anti-overcorrection

Don't go too hard the other way:

- Forced typos read as fake too. Don't introduce typos to seem human.
- Forced slang read as fake too. Don't add "lol" or "ngl" if the input register is professional.
- Don't make every sentence a fragment to defeat the monotony check. Vary toward natural distribution, not toward chaos.

When in doubt, the texture target is the platform's reference corpus in `voice/reference-corpus/`.

---

## Korean (한국어)

The same kinds of tells show up in Korean — usually as stiff, translated-sounding phrasings that no real Korean dev tweet would use. Flag any of these:

- `오늘날의 빠르게 변화하는` — direct calque of "in today's fast-paced", rarely written by humans.
- `~을(를) 활용하여` / `~를 활용한` / `활용하여` / `활용한` — translated "leverage"; native Korean prefers `~을 써서` or `~으로`.
- `~에 대해 깊이 알아보겠습니다` / `자세히 알아보겠습니다` — calque of "let's dive deep into"; reads as a textbook intro.
- `혁신적인` / `혁명적인` as filler adjective — when used to describe ordinary tools, it's marketing copy.
- `최첨단` — calque of "cutting-edge"; banned unless quoting a vendor.
- `~을 통해 ~할 수 있습니다` — overused construction in AI-translated documentation; replace with a direct verb.
- `결론적으로` / `결국에는` / `마지막으로` / `요컨대` at the start of the closing sentence — Korean closing-moralizer tic.
- `~이 아니라 ~입니다` / `~가 아니라 ~입니다` — Korean equivalent of "It's not just X — it's Y", banned outright.
- `여러분` + 호소조 (e.g., `여러분, 함께 ~합시다`) — LinkedIn-evangelist tone; rare in casual Korean writing.
- `~의 시너지` / `~의 패러다임` — loanword filler; sounds like a corporate slide deck.
- `놀라운` / `놀라운 결과` — calque of "remarkable" / "remarkable results", typically empty.
- `깊이 있는 통찰` / `심도 있는 분석` — translated "deep insights / in-depth analysis", AI-marketing register.

When flagged, rewrite in concrete Korean: name the tool, the number, the moment. Same anchor rules as the English sections apply.
