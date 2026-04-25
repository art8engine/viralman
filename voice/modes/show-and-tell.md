# Mode: show-and-tell

Project-launch register. The post leads with the demo / artifact / result, then explains the why. Native to Show HN, r/SideProject, r/programming launches, LinkedIn product announcements.

## Beats

1. **The thing**: a specific name + a one-line description of what it does. Often: "I built X — Y."
2. **Why it exists**: 2–4 sentences on the problem you had with the existing options. Concrete.
3. **The interesting bit**: one technical/design choice that's non-obvious. Optional but increases retention.
4. **Link + invitation**: a single link, and an invitation to break it / give feedback / try it. Not "RT if useful" — a real ask.

## Required anchors

- A name (the project's name).
- A link.
- One specific problem it solves, named in concrete terms.

## Length

- Reddit (r/SideProject, r/programming): 200–500 words.
- LinkedIn: 600–1100 chars.
- X: usually a thread; tweet 1 = the thing + the link, tweets 2–3 = why and how.
- Show HN: 300–600 chars in the body, the title does the heavy lifting.

## Anti-patterns

- Don't list every feature. Pick the one that distinguishes you.
- Don't apologize ("it's still rough but…"). Either ship or don't.
- Don't bury the link. Top of post or end of post — never middle.
- Don't claim the project is "the X for Y" unless you can actually defend it.
- Don't pre-emptively address criticism the audience hasn't given yet.

## Worked example (Show HN body, ~400 chars)

> I built `gnarly` — a CLI that visualizes which characters in your stdin a given regex actually matches.
>
> Built it because every regex debugger is either a JS webpage with ads or a Python repl, and I wanted something I could pipe a 50MB log into. 6 colors, 2 modes (greedy/non-greedy), works on macOS and Linux.
>
> Repo: https://github.com/me/gnarly
> Would love to see what regex you're using that breaks it.

## Worked example (Reddit r/SideProject, ~250 words)

> TITLE: I built a CLI that shows which chars your regex actually matches, in color, on huge stdin
> BODY:
> Tool's called `gnarly`. Pipe anything to it with a regex and it prints your input back with each char colored by which capture group it landed in (or grey if it didn't match).
>
> ```
> cat access.log | gnarly '^(\S+) - (\S+) \[([^\]]+)\]'
> ```
>
> Built it because I kept switching between three half-good tools when debugging logs:
> - regex101 — great UX, but I have to paste 50MB of logs into a webpage
> - `grep --color` — fast, but only colors the whole match, not capture groups
> - python repl + a script — works, but I write it from scratch every time
>
> The thing I'm proud of: it streams. You can pipe an unbounded source into it and it'll keep colorizing as bytes come in. Most regex visualizers buffer.
>
> Stack: rust, ~600 lines. Single binary, zero deps at runtime.
>
> Repo: https://github.com/me/gnarly
>
> Would love to see what kinds of regex break it. I've been testing on Apache logs and JSON; the corner cases I haven't seen yet are probably the ones I'll fix this weekend.

## Worked example (LinkedIn, ~700 chars)

> I built `gnarly` — a CLI that takes a regex and shows you exactly which characters in your input it matched.
>
> Why: every existing regex debugger is a JS web app with ads, and I wanted to pipe access logs (50MB+) into something on the terminal. The existing `grep --color` only colors the whole match, not capture groups. So I wrote one.
>
> The piece I think is interesting: it streams. You can pipe an unbounded source into it and watch the colors update as bytes come in. Most visualizers buffer the whole input first, which means they choke on real logs.
>
> Single Rust binary, ~600 lines, zero runtime deps. Repo in the comments.
>
> If anyone has a regex that breaks it, I want to see it.
