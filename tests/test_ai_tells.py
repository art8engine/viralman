"""Self-test for the AI-tell sniffer.

Pass criteria: sniffer flags >= 9/10 of the synthesized AI paragraphs and
passes >= 9/10 of the human paragraphs (i.e., human samples produce 0 flags
or only soft no-anchor flags we excuse).

Run:
  python -m pytest tests/test_ai_tells.py -v
or:
  python tests/test_ai_tells.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

from sniffer_check import check  # noqa: E402


AI_SAMPLES = [
    # 1. classic LinkedIn AI
    """In today's fast-paced world, leaders need to delve into what truly drives their teams. It's not just about hitting numbers — it's about empowering people to navigate the landscape of change. Here are 3 things that revolutionized how I think about leadership: vision, vulnerability, and velocity. What do you think?""",

    # 2. AI-flavored launch
    """We're excited to announce a game-changing platform that will revolutionize how teams collaborate. Our cutting-edge solution leverages state-of-the-art AI to unlock the potential of your workforce. Let's dive into why this matters now more than ever. #innovation #growth #leadership""",

    # 3. balanced tricolon + closing moralizer
    """Three weeks ago I started a new project. I learned to listen, I learned to lead, I learned to let go. The lesson here is that growth isn't linear — it's a tapestry woven from setbacks and breakthroughs. At the end of the day, what matters most is the journey.""",

    # 4. monotone sentence rhythm
    """Building products is hard work today. Teams must align on shared goals quickly. Communication is essential for any team. Leaders should foster open dialogue daily. Trust is the foundation of every team. Building trust takes consistent daily effort.""",

    # 5. "It's not just X — it's Y" + filler
    """Productivity isn't just about doing more, it's about doing what matters. Moreover, the best teams know that crucial conversations happen in the margins. Let's unpack what this means in practice.""",

    # 6. hashtag stuffing on Reddit-like context (will be tested with platform=reddit)
    """Just shipped a new feature that will supercharge your workflow. The tapestry of modern engineering demands robust, seamless solutions. #innovation #growth #tech #devlife #coding #productivity""",

    # 7. closing CTA + 3 bullets shape
    """A few weeks ago I had a conversation that changed everything.\n\n- Listen first\n- Speak with intent\n- Lead by example\n\nWhat do you think? Drop a 👇 below.""",

    # 8. "embark on a journey"
    """As we embark on a journey of digital transformation, it's vital that we leverage every tool at our disposal. The synergy between teams is what separates good companies from great ones. In conclusion, the future is now.""",

    # 9. abstract, no anchors
    """Innovation requires courage. Courage requires clarity. Clarity requires conversation. The companies that thrive are the ones that foster all three. They don't just navigate complexity — they redefine it.""",

    # 10. "harness the power"
    """If you want to harness the power of your team, you need to empower them holistically. This isn't just leadership — it's stewardship. The paradigm shift is here.""",
]


HUMAN_SAMPLES = [
    # 1. growth-story example from voice/modes/growth-story.md
    """Three weeks chasing a flaky integration test. The fix was one line.

The test would pass locally, pass on CI sometimes, and fail on Mondays. I added retries. I added sleeps. I added logging that proved nothing. By week two I'd convinced myself the bug was in Postgres.

Then a coworker pointed at the test name: `test_user_can_post_after_signup`. The signup step ran in a fixture with `scope=session`. On Mondays, the session was the first run after the weekend's container rebuild — and the fixture's UUID collided with a row left over from the previous CI image.

One line: `pytest.fixture(scope="function")`.

Three weeks of "the database is haunted" was a fixture scope.""",

    # 2. casual-hype tweet
    """ok we just got the autoscaler down to 47% of last month's k8s bill and i'm not sure how. one of those "ship it before it un-ships itself" moments. config diff is 6 lines.""",

    # 3. casual-hype 2
    """three weeks debugging the flakiest test of my life. fix was scope=function. one word. absolute W.""",

    # 4. show-and-tell short
    """I built `gnarly` — a CLI that shows which characters in your stdin a given regex matched. Built it because every regex debugger is a JS web app with ads and I wanted to pipe a 50MB log into something. Repo: https://github.com/me/gnarly. Would love to see what regex you're using that breaks it.""",

    # 5. contrarian-take
    """Most "best practices for code review" guides recommend reviewing every PR with a structured checklist. I followed this for two years on a team of seven and our review latency was 36 hours.

Here's where the checklist version is wrong: it treats every PR the same. A typo fix and a 600-line refactor get the same 5-section review and the same reviewer attention budget.

What I do now: triage at the PR title. `chore` gets a glance. `bugfix` gets the diff and a question about how it was tested. `change` gets the full review and the reviewer is allowed to take half a day. Latency dropped from 36 hours to 4.""",

    # 6. plain Reddit-style technical
    """TIL pytest fixture scope can collide across CI image rebuilds. Spent three weeks chasing a test that passed locally and failed on the first CI run after weekend container rebuilds. The signup created a User with a deterministic UUID via a fixture scoped session. The fixture session meant the pytest session, not the database session, and our CI image was getting rebuilt every Sunday. Fix was one word.""",

    # 7. casual personal
    """just shipped my dumb little CLI and someone actually used it. made a thing called gnarly that takes a regex and shows you what it would match in your stdin. spent two weekends on it. just got my first non-me star on github.""",

    # 8. another growth-story
    """Spent four hours yesterday convinced our load balancer was misconfigured. Logs showed 502s on a third of requests. Restarted the LB. Restarted the upstreams. Read the LB config three times. Eventually checked the upstream health check path: `/healthz` returned 200 but the LB was hitting `/health`. Three letters.""",

    # 9. hype + specific
    """We finally got the cold-start latency on the worker pool down to 180ms from 2.4s. Six week side quest. The fix was switching from per-request boto3 sessions to a shared one — exactly the thing the AWS docs warn you about.""",

    # 10. casual personal launch
    """tiny weekend project: a tool called `kdiff` that diffs two kubernetes manifests by their effective rendered output, not by line. like `git diff` but it understands that field order in YAML doesn't matter. https://github.com/me/kdiff. let me know what breaks.""",
]


def run_self_test() -> tuple[int, int, int, int]:
    ai_flagged = 0
    for i, text in enumerate(AI_SAMPLES):
        platform = "reddit" if i == 5 else "linkedin"
        flags = check(text, platform=platform)
        if flags:
            ai_flagged += 1
        else:
            print(f"  [MISS] AI sample {i+1} did not trip any flag")

    human_clean = 0
    for i, text in enumerate(HUMAN_SAMPLES):
        flags = check(text, platform="linkedin", mode="growth-story")
        # tolerate the no-anchor flag if it slips on a short sample
        hard = [f for f in flags if f["id"] != "no-anchor"]
        if not hard:
            human_clean += 1
        else:
            print(f"  [FALSE POSITIVE] human sample {i+1}: {hard}")

    return ai_flagged, len(AI_SAMPLES), human_clean, len(HUMAN_SAMPLES)


def test_sniffer_catches_ai():
    ai_flagged, ai_total, _, _ = run_self_test()
    assert ai_flagged >= 9, f"only flagged {ai_flagged}/{ai_total} AI samples"


def test_sniffer_passes_humans():
    _, _, human_clean, human_total = run_self_test()
    assert human_clean >= 9, f"only passed {human_clean}/{human_total} human samples"


if __name__ == "__main__":
    ai_flagged, ai_total, human_clean, human_total = run_self_test()
    print()
    print(f"AI flagged: {ai_flagged}/{ai_total}  (need >= 9)")
    print(f"Human clean: {human_clean}/{human_total}  (need >= 9)")
    ok = ai_flagged >= 9 and human_clean >= 9
    print()
    print("PASS" if ok else "FAIL")
    raise SystemExit(0 if ok else 1)
