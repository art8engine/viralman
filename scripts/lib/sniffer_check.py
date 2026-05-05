"""Deterministic AI-tell heuristics.

Used by the ai-tell-sniffer agent (via Bash) and by tests/test_ai_tells.py.
Returns a list of flags; empty list means clean.

Each flag is a dict: {"id": str, "msg": str, "where": str|None}.
"""

from __future__ import annotations

import re
import statistics
from typing import List, Dict, Any


BANNED_REGEX = [
    (r"\bdelv(e|ing|ed)\b", "banned-phrase: delve"),
    (r"\btapestry\b", "banned-phrase: tapestry"),
    (r"\bleverag(e|ing|ed)\b", "banned-phrase: leverage (verb)"),
    (r"\bnavigate the (landscape|complexities|terrain|waters)\b", "banned-phrase: navigate the X"),
    (r"\bstands as a testament\b", "banned-phrase: stands as a testament"),
    (r"\bin today's (fast-paced|ever-evolving|rapidly changing|digital) world\b", "banned-phrase: in today's X world"),
    (r"\blet's (dive in|dive into|unpack|explore)\b", "banned-phrase: let's dive in"),
    (r"\bunleash(ing)?\b", "banned-phrase: unleash"),
    (r"\bunlock the (potential|power)\b", "banned-phrase: unlock the X"),
    (r"\bsupercharge\b", "banned-phrase: supercharge"),
    (r"\bharness the (power|potential)\b", "banned-phrase: harness the X"),
    (r"\bembark on a journey\b", "banned-phrase: embark on a journey"),
    (r"\bcutting[- ]edge\b", "banned-phrase: cutting-edge"),
    (r"\bstate[- ]of[- ]the[- ]art\b", "banned-phrase: state-of-the-art"),
    (r"\brevolutioniz(e|ing|ed)\b", "banned-phrase: revolutionize"),
    (r"\bparadigm shift\b", "banned-phrase: paradigm shift"),
    (r"\bsynerg(y|ies|ize|ized)\b", "banned-phrase: synergy"),
    (r"\bseamless(ly)?\b", "banned-phrase: seamless"),
    (r"\bholistic\b", "banned-phrase: holistic"),
    (r"\bempower(s|ing|ed)?\b", "banned-phrase: empower"),
    (r"\bfoster(s|ing|ed)?\b", "banned-phrase: foster (verb)"),
    (r"\b(crucial|vital|essential)\b", "filler-word: crucial/vital/essential"),
    (r"(?im)^\s*(moreover|furthermore|additionally)\b", "filler-word: moreover/furthermore/additionally at sentence start"),
    (r"\b(in conclusion|to summarize|in summary)\b", "summary-marker"),
    (r"\b(it|this) is( not)? (just|merely|simply) (about )?[A-Za-z\- ]{1,40}?,? (it|this)('s| is)\b", "banned-pattern: 'It's not just X — it's Y'"),
    (r"\bat its core\b", "empty-hedge: at its core"),
    (r"\bnow more than ever\b", "empty-hedge: now more than ever"),
    (r"\bin many ways\b", "empty-hedge: in many ways"),
]


CLOSING_MORALIZERS = [
    r"^the lesson here",
    r"^the takeaway is",
    r"^what this taught me",
    r"^if there's one thing",
    r"^sometimes the best thing",
    r"^at the end of the day",
]


# Korean banned phrases — patterns that consistently mark AI-translated/AI-generated
# Korean text. Plain regex; case-insensitivity is a no-op for Hangul.
BANNED_KO = [
    (r"오늘날의\s*빠르게\s*변화하는", "banned-phrase-ko: 오늘날의 빠르게 변화하는"),
    (r"활용하여", "banned-phrase-ko: 활용하여 (leverage)"),
    (r"활용한", "banned-phrase-ko: 활용한 (leveraging)"),
    (r"깊이\s*알아보(겠습니다|자|아)", "banned-phrase-ko: 깊이 알아보겠습니다 (let's dive deep)"),
    (r"자세히\s*알아보(겠습니다|자|아)", "banned-phrase-ko: 자세히 알아보겠습니다 (let's dive deep)"),
    (r"혁신적인", "banned-phrase-ko: 혁신적인 (innovative filler)"),
    (r"혁명적인", "banned-phrase-ko: 혁명적인 (revolutionary filler)"),
    (r"최첨단", "banned-phrase-ko: 최첨단 (cutting-edge)"),
    (r"패러다임", "banned-phrase-ko: 패러다임 (paradigm filler)"),
    (r"시너지", "banned-phrase-ko: 시너지 (synergy)"),
    (r"심도\s*있는\s*분석", "banned-phrase-ko: 심도 있는 분석 (in-depth analysis)"),
    (r"깊이\s*있는\s*통찰", "banned-phrase-ko: 깊이 있는 통찰 (deep insights)"),
]


# Korean closing-moralizer openers — anchored at the start of the final sentence.
KO_CLOSING_MORALIZERS = [
    r"^결론적으로",
    r"^결국에는",
    r"^마지막으로",
    r"^요컨대",
]


# Korean "It's not X, it's Y" — `~이/가 아니라 ~입니다`.
KO_NOT_X_BUT_Y = re.compile(
    r"[가-힣A-Za-z0-9][^\s].{0,40}?(?:이|가)\s*아니라\s*.{1,40}?(?:입니다|이다)"
)


CASUAL_HYPE_ALLOWED = {
    "wild", "actually nuts", "goated", "cracked", "slaps", "absolute w",
    "no way", "lowkey", "fr", "legit", "tbh", "game-changer", "game changer",
}


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\w']+\b", text))


def _split_sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if p.strip()]


def _has_hangul(text: str) -> bool:
    """Return True if text contains any Hangul syllables."""
    return bool(re.search(r"[가-힣]", text))


def _check_korean(text: str) -> List[Dict[str, Any]]:
    """Run Korean-specific heuristics. Only invoked when Hangul is present."""
    flags: List[Dict[str, Any]] = []

    # ko banned phrases
    for pattern, msg in BANNED_KO:
        if re.search(pattern, text):
            flags.append({"id": "banned-phrase-ko", "msg": msg, "where": None})

    # ko closing moralizer — check the last sentence, split on Korean/Western terminators.
    ko_sentences = [
        s.strip() for s in re.split(r"(?<=[.!?。！？])\s+|\n+", text.strip()) if s.strip()
    ]
    if ko_sentences:
        tail = ko_sentences[-1].lstrip()
        for pattern in KO_CLOSING_MORALIZERS:
            if re.search(pattern, tail):
                flags.append({
                    "id": "closing-moralizer-ko",
                    "msg": f"matches /{pattern}/",
                    "where": "end",
                })
                break

    # ko "It's not X, it's Y"
    if KO_NOT_X_BUT_Y.search(text):
        flags.append({
            "id": "not-x-but-y-ko",
            "msg": "matches Korean '~이/가 아니라 ~입니다' pattern",
            "where": None,
        })

    return flags


def check(text: str, *, platform: str = "linkedin", mode: str = "growth-story") -> List[Dict[str, Any]]:
    flags: List[Dict[str, Any]] = []
    lower = text.lower()

    # 1. banned phrasings
    for pattern, msg in BANNED_REGEX:
        if re.search(pattern, text, flags=re.IGNORECASE):
            if mode == "casual-hype" and "game-changer" in msg.lower():
                hits = list(re.finditer(pattern, text, flags=re.IGNORECASE))
                if len(hits) <= 1:
                    continue
            flags.append({"id": "banned-phrase", "msg": msg, "where": None})

    # 1b. Korean heuristics — only if Hangul present, so English text stays unaffected.
    if _has_hangul(text):
        flags.extend(_check_korean(text))

    # 2a. em-dash density
    em_dashes = text.count("—") + text.count(" -- ")
    words = _word_count(text)
    em_budget = 0 if mode == "casual-hype" else max(1, words // 60)
    if em_dashes > em_budget:
        flags.append({
            "id": "em-dash-density",
            "msg": f"{em_dashes} em-dashes in {words} words; budget is {em_budget}",
            "where": None,
        })

    # 2c. closing moralizer
    sentences = _split_sentences(text)
    if sentences:
        tail = " ".join(sentences[-2:]).lower().lstrip()
        for pattern in CLOSING_MORALIZERS:
            if re.search(pattern, tail):
                flags.append({"id": "closing-moralizer", "msg": f"matches /{pattern}/", "where": "end"})
                break

    # 2d. hashtag rules
    hashtags = re.findall(r"(?<!\w)#\w+", text)
    if platform == "reddit" and hashtags:
        flags.append({"id": "hashtags-on-reddit", "msg": f"found {len(hashtags)} hashtags", "where": None})
    elif platform == "x" and len(hashtags) > 2:
        flags.append({"id": "too-many-hashtags-x", "msg": f"{len(hashtags)} > 2", "where": None})
    elif platform == "linkedin":
        if len(hashtags) > 3:
            flags.append({"id": "too-many-hashtags-linkedin", "msg": f"{len(hashtags)} > 3", "where": None})
        filler = {"#innovation", "#growth", "#leadership", "#mindset", "#success", "#motivation", "#entrepreneurship"}
        for h in hashtags:
            if h.lower() in filler:
                flags.append({"id": "filler-hashtag", "msg": h, "where": None})

    # 2e. sentence length monotony (only if enough sentences)
    if len(sentences) >= 5:
        lengths = [_word_count(s) for s in sentences]
        mean = statistics.mean(lengths)
        stdev = statistics.pstdev(lengths)
        if mean > 0 and stdev / mean < 0.35:
            flags.append({
                "id": "sentence-monotony",
                "msg": f"length stdev/mean = {stdev/mean:.2f} (< 0.35)",
                "where": None,
            })

    # 2f. LinkedIn hook + 3-bullets + CTA shape
    if platform == "linkedin":
        bullet_lines = [ln for ln in text.splitlines() if re.match(r"^\s*[-•*]\s+", ln)]
        last_line = sentences[-1].strip().lower() if sentences else ""
        cta_markers = ["what do you think", "agree?", "thoughts?", "drop a"]
        if len(bullet_lines) == 3 and any(m in last_line for m in cta_markers):
            flags.append({"id": "linkedin-template", "msg": "hook + 3 bullets + CTA shape", "where": None})

    # 2i. "Three things changed everything" / "Here are 3 things that…"
    if re.search(r"\b(here are|these are) (the )?(3|three) (things|reasons|ways|lessons)\b", text, re.IGNORECASE):
        flags.append({"id": "three-things-frame", "msg": "'here are 3 things…' opener", "where": None})

    # 3. anchors — must have at least one
    has_number = bool(re.search(r"\b\d+(\.\d+)?%?\b", text))
    has_specific_name = bool(re.search(r"`[^`]+`", text)) or bool(re.search(r"\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b", text)) or bool(re.search(r"\b[a-z]+\.[a-z]+\b", text))
    has_time_anchor = bool(re.search(r"\b(yesterday|last (week|month|year|thursday|friday|monday|tuesday|wednesday|saturday|sunday)|after \d+ (weeks?|months?|days?|hours?|years?)|in (january|february|march|april|may|june|july|august|september|october|november|december))\b", text, re.IGNORECASE))
    has_admission = bool(re.search(r"\b(i was wrong|i (almost )?gave up|i didn'?t (realize|know)|i (was )?(stuck|struggling|confused)|i thought it was|turned out i was|spent (\d+|three|two|four) (weeks?|days?|months?))\b", text, re.IGNORECASE))
    if not (has_number or has_specific_name or has_time_anchor or has_admission):
        flags.append({"id": "no-anchor", "msg": "no number, specific name, time anchor, or admission found", "where": None})

    # 2h. adverb stack — only the specific AI-tell adverbs, not all -ly words
    AI_ADVERBS = (
        r"\b(truly|genuinely|fundamentally|essentially|remarkably|incredibly|"
        r"absolutely|ultimately|profoundly|undoubtedly|wholeheartedly|inherently|"
        r"meaningfully|effectively|strategically|holistically)\b"
    )
    ai_adverbs = re.findall(AI_ADVERBS, text, flags=re.IGNORECASE)
    if len(ai_adverbs) >= 2 or (words >= 60 and len(ai_adverbs) >= 1):
        flags.append({
            "id": "adverb-stack",
            "msg": f"AI-favored adverbs: {ai_adverbs}",
            "where": None,
        })

    return flags


def main() -> int:
    import argparse
    import json
    import sys as _sys

    p = argparse.ArgumentParser(description="Run AI-tell heuristics on a draft.")
    p.add_argument("--platform", default="linkedin", choices=["reddit", "x", "linkedin"])
    p.add_argument("--mode", default="growth-story")
    p.add_argument("--json", action="store_true", help="emit JSON")
    args = p.parse_args()

    text = _sys.stdin.read()
    flags = check(text, platform=args.platform, mode=args.mode)

    if args.json:
        print(json.dumps(flags, indent=2))
    else:
        if not flags:
            print("CLEAN")
        else:
            for f in flags:
                where = f" @ {f['where']}" if f.get("where") else ""
                print(f"FLAG [{f['id']}]: {f['msg']}{where}")
    return 0 if not flags else 2


if __name__ == "__main__":
    raise SystemExit(main())
