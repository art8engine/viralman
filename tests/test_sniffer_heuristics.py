"""Deterministic heuristic-by-heuristic regression tests for sniffer_check.py.

For each heuristic id, we verify:
  - positive: the flag id DOES appear in check() output
  - negative: the flag id does NOT appear in check() output

Run:
  python -m pytest tests/test_sniffer_heuristics.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

from sniffer_check import check  # noqa: E402


def _ids(text: str, platform: str = "linkedin", mode: str = "growth-story"):
    return [f["id"] for f in check(text, platform=platform, mode=mode)]


# ---------------------------------------------------------------------------
# banned-phrase
# ---------------------------------------------------------------------------

def test_banned_phrase_positive():
    """Classic banned phrases should trip the heuristic."""
    text = "Let's delve into what makes great leaders truly stand out."
    assert "banned-phrase" in _ids(text)


def test_banned_phrase_negative():
    """Plain human prose with no banned words should not trip banned-phrase."""
    text = "I shipped a fix for the flaky integration test. One line change."
    assert "banned-phrase" not in _ids(text)


# ---------------------------------------------------------------------------
# em-dash-density
# ---------------------------------------------------------------------------

def test_em_dash_density_positive():
    """Five em-dashes in ~50 words should exceed budget and trip the flag."""
    text = (
        "We shipped — the product — after months — of iteration — and learning. "
        "The team worked hard — every single day — to make this happen."
    )
    assert "em-dash-density" in _ids(text)


def test_em_dash_density_negative():
    """A single em-dash in a long passage should stay within budget."""
    text = (
        "We shipped the product after months of iteration. "
        "The team worked hard every single day to make it happen. "
        "One thing surprised us — the users loved it immediately. "
        "We measured retention at 87% after the first week, up from 61%."
    )
    assert "em-dash-density" not in _ids(text)


# ---------------------------------------------------------------------------
# closing-moralizer
# ---------------------------------------------------------------------------

def test_closing_moralizer_positive():
    """'The lesson here' opener in the closing tail should trip closing-moralizer.

    The sniffer joins the LAST 2 sentences into `tail` and runs re.search with
    a `^` anchor (no MULTILINE), so the moralizer phrase must sit at the very
    start of `tail`. Using a single sentence guarantees the moralizer is at
    position 0 of the joined tail.
    """
    # Single sentence → sentences[-2:] == [this sentence] → tail starts with moralizer
    text = "The lesson here is that premature optimization costs more than it saves."
    assert "closing-moralizer" in _ids(text)


def test_closing_moralizer_negative():
    """A post ending with a concrete observation should not trip the moralizer."""
    text = (
        "We tried three different architectures over six months. "
        "None of them scaled past 10k users. "
        "Switched to a queue-based design last Tuesday. Now at 40k with room to grow."
    )
    assert "closing-moralizer" not in _ids(text)


# ---------------------------------------------------------------------------
# hashtags-on-reddit
# ---------------------------------------------------------------------------

def test_hashtags_on_reddit_positive():
    """Any hashtag on Reddit platform should trip hashtags-on-reddit."""
    text = "Just shipped a cool feature. #devlife"
    assert "hashtags-on-reddit" in _ids(text, platform="reddit")


def test_hashtags_on_reddit_negative():
    """No hashtags on Reddit should not trip the flag."""
    text = "Just shipped a cool feature. Check the repo for details."
    assert "hashtags-on-reddit" not in _ids(text, platform="reddit")


# ---------------------------------------------------------------------------
# too-many-hashtags-x
# ---------------------------------------------------------------------------

def test_too_many_hashtags_x_positive():
    """More than 2 hashtags on X platform should trip the flag."""
    text = "New post! #dev #code #python #ai"
    assert "too-many-hashtags-x" in _ids(text, platform="x")


def test_too_many_hashtags_x_negative():
    """Two or fewer hashtags on X should not trip the flag."""
    text = "New post! #dev #code"
    assert "too-many-hashtags-x" not in _ids(text, platform="x")


# ---------------------------------------------------------------------------
# too-many-hashtags-linkedin
# ---------------------------------------------------------------------------

def test_too_many_hashtags_linkedin_positive():
    """More than 3 hashtags on LinkedIn should trip the flag."""
    text = "Excited to share! #growth #leadership #innovation #mindset #hustle"
    assert "too-many-hashtags-linkedin" in _ids(text, platform="linkedin")


def test_too_many_hashtags_linkedin_negative():
    """Three or fewer hashtags on LinkedIn should not trip the flag."""
    text = "Excited to share! #growth #leadership #innovation"
    # Use a clean text that avoids other heuristics triggering filler-hashtag
    ids = _ids(text, platform="linkedin")
    assert "too-many-hashtags-linkedin" not in ids


# ---------------------------------------------------------------------------
# filler-hashtag
# ---------------------------------------------------------------------------

def test_filler_hashtag_positive():
    """Known filler hashtags (#innovation, #growth, etc.) should trip filler-hashtag."""
    text = "Here is my take on the market. #innovation"
    assert "filler-hashtag" in _ids(text, platform="linkedin")


def test_filler_hashtag_negative():
    """Non-filler hashtags should not trip filler-hashtag."""
    text = "Shipping today. #rustlang"
    assert "filler-hashtag" not in _ids(text, platform="linkedin")


# ---------------------------------------------------------------------------
# sentence-monotony
# ---------------------------------------------------------------------------

def test_sentence_monotony_positive():
    """Five sentences of nearly identical length should trip sentence-monotony."""
    text = (
        "Building products is a hard challenge. "
        "Teams must align on their shared goals. "
        "Communication matters for every single team. "
        "Leaders should foster open daily dialogue. "
        "Trust is the bedrock of successful teams."
    )
    assert "sentence-monotony" in _ids(text)


def test_sentence_monotony_negative():
    """High variance in sentence length should not trip sentence-monotony."""
    text = (
        "No. "
        "I shipped it on a Tuesday after a three-week sprint that nearly broke us. "
        "Six lines of config. "
        "The kind of fix that makes you feel both relieved and a little cheated after weeks of digging through logs. "
        "Worth it."
    )
    assert "sentence-monotony" not in _ids(text)


# ---------------------------------------------------------------------------
# linkedin-template
# ---------------------------------------------------------------------------

def test_linkedin_template_positive():
    """Hook + exactly 3 bullets + CTA should trip linkedin-template."""
    text = (
        "A conversation last week changed how I think about leadership.\n\n"
        "- Listen first\n"
        "- Speak with intent\n"
        "- Lead by example\n\n"
        "What do you think?"
    )
    assert "linkedin-template" in _ids(text, platform="linkedin")


def test_linkedin_template_negative():
    """Four bullets with no CTA should not trip linkedin-template."""
    text = (
        "Here is what I learned building in public:\n\n"
        "- Ship early\n"
        "- Gather feedback\n"
        "- Iterate fast\n"
        "- Repeat the cycle\n\n"
        "It took three months to see results."
    )
    assert "linkedin-template" not in _ids(text, platform="linkedin")


# ---------------------------------------------------------------------------
# three-things-frame
# ---------------------------------------------------------------------------

def test_three_things_frame_positive():
    """'Here are 3 things' opener should trip three-things-frame."""
    text = "Here are 3 things that changed how I approach engineering."
    assert "three-things-frame" in _ids(text)


def test_three_things_frame_negative():
    """Text without the 'here are N things' pattern should not trip the flag."""
    text = "I changed how I approach engineering after a painful on-call incident."
    assert "three-things-frame" not in _ids(text)


# ---------------------------------------------------------------------------
# no-anchor
# ---------------------------------------------------------------------------

def test_no_anchor_positive():
    """Purely abstract prose with no numbers, names, dates, or admissions trips no-anchor."""
    text = (
        "Innovation requires courage and clarity. "
        "The best teams foster open communication. "
        "Growth comes from embracing uncertainty."
    )
    assert "no-anchor" in _ids(text)


def test_no_anchor_negative():
    """Text with a concrete number provides an anchor and clears no-anchor."""
    text = (
        "We cut our p95 latency from 2.4s to 180ms over six weeks. "
        "The fix was switching to a shared boto3 session."
    )
    assert "no-anchor" not in _ids(text)


# ---------------------------------------------------------------------------
# adverb-stack
# ---------------------------------------------------------------------------

def test_adverb_stack_positive():
    """Two AI-favored adverbs in a short text should trip adverb-stack."""
    text = "This approach is truly remarkable and fundamentally changes how we work."
    assert "adverb-stack" in _ids(text)


def test_adverb_stack_negative():
    """Text with no AI-favored adverbs should not trip adverb-stack."""
    text = (
        "We shipped the fix on Tuesday. "
        "The change was three lines in the config file. "
        "Latency dropped fast."
    )
    assert "adverb-stack" not in _ids(text)
