# Reference corpus

This folder is for **real human posts** you've collected as texture targets. The `viral-writer` and `ai-tell-sniffer` agents will be told to read 5–10 samples per platform when they're available.

## How to populate

For each platform, drop short markdown files like `reddit-01.md`, `x-01.md`, `linkedin-01.md`. Each file should contain:

```markdown
---
platform: reddit | x | linkedin
url: <link to the original post if public>
mode: growth-story | casual-hype | show-and-tell | contrarian-take | other
why_good: <one line on what makes this a good texture target>
---

<the post body, verbatim>
```

## Selection criteria

Choose posts that:
- Were written by an actual human (not a brand account, not a known AI-content account).
- Performed well organically — not bought engagement.
- Match one of the four voice modes you actually want viralman to produce.
- Have a distinct *texture* — sentence rhythm, anchor density, opener style — that you'd want copied.

## What NOT to put here

- Posts you wrote with ChatGPT/Claude.
- Marketing copy from companies.
- "Top LinkedIn influencer" posts that are themselves the AI-slop template.
- Posts under copyright restrictions you don't have permission to redistribute (if shipping the corpus publicly, prefer paraphrased seeds or links instead of full bodies).

## Bootstrapping

Until the corpus is populated, the agents fall back to the worked examples inside each `voice/modes/*.md` file. Those are deliberately written as anchors and will keep the system functional. Quality goes up sharply once you add 5–10 real samples per platform.
