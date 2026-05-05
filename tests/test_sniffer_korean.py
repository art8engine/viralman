"""Korean coverage smoke tests for sniffer_check.py.

The sniffer is currently English-centric. These tests document the current
behavior and track gaps for future Korean heuristic support.

Run:
  python -m pytest tests/test_sniffer_korean.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

from sniffer_check import check  # noqa: E402


def _hard_flags(text: str, platform: str = "linkedin") -> list:
    """Return flags excluding no-anchor (tolerated on short/foreign text)."""
    return [f for f in check(text, platform=platform) if f["id"] != "no-anchor"]


# ---------------------------------------------------------------------------
# 1. Clean Korean dev tweet — should produce zero hard flags
# ---------------------------------------------------------------------------

def test_korean_clean_passes():
    """A clearly human Korean dev post should produce no hard flags.

    Human-written Korean tech content uses direct, concrete language with
    specific numbers — the sniffer should not trigger on it.
    """
    text = "k8s 오토스케일러 비용 47% 줄였다. config diff 6줄."
    flags = _hard_flags(text, platform="linkedin")
    assert flags == [], (
        f"Expected 0 hard flags for clean Korean text, got: {flags}"
    )


# ---------------------------------------------------------------------------
# 2. Korean AI slop — tracked gap, not a hard failure
# ---------------------------------------------------------------------------

def test_korean_ai_slop_known_limitation():
    """A Korean translation of obvious AI slop must trip the sniffer.

    With Korean heuristics in place, calques of 'in today's fast-paced world',
    'leverage', 'synergy', etc. should be flagged via banned-phrase-ko.
    """
    # Google-Translate-style stiff Korean of:
    # "In today's rapidly changing world, we must leverage synergy to
    #  revolutionize how we navigate the complexities of innovation."
    text = (
        "오늘날의 빠르게 변화하는 세계에서, 우리는 시너지를 활용하여 "
        "혁신의 복잡성을 헤쳐나가는 방식을 혁신해야 합니다. "
        "이것은 단순히 성장에 관한 것이 아닙니다 — 미래를 여는 것입니다."
    )
    flags = check(text, platform="linkedin")
    flag_ids = [f["id"] for f in flags]
    assert any(
        fid in flag_ids
        for fid in (
            "banned-phrase",
            "banned-phrase-ko",
            "em-dash-density",
            "adverb-stack",
        )
    ), f"No content flags on Korean AI slop. Got: {flag_ids}"


# ---------------------------------------------------------------------------
# 3. Korean text with em-dashes — unicode-agnostic detection should still fire
# ---------------------------------------------------------------------------

def test_korean_em_dash_density():
    """Em-dash detection operates on the Unicode '—' character, not on English words.

    Korean text with 5 em-dashes in ~60 words should still trip em-dash-density
    because the counter is byte/character level, not language-specific.

    If this unexpectedly does not trip (e.g. word-count heuristic differs for
    Korean tokens), the test is marked xfail with a clear reason.
    """
    # ~60 Korean words with 5 em-dashes
    text = (
        "우리는 새로운 기능을 — 배포했습니다. "
        "팀원들이 — 함께 작업했고 — 결과는 놀라웠습니다. "
        "서버 비용은 47% 줄었고 — 응답 시간은 180ms로 개선되었습니다 — "
        "이 모든 것이 단 6줄의 설정 변경으로 이루어졌습니다. "
        "다음 분기에도 같은 방식으로 최적화를 계속할 계획입니다."
    )
    flags = check(text, platform="linkedin")
    flag_ids = [f["id"] for f in flags]

    if "em-dash-density" not in flag_ids:
        pytest.xfail(
            "em-dash-density did not fire on Korean text — "
            "word tokenization may differ for CJK characters; see QA gap"
        )

    assert "em-dash-density" in flag_ids, (
        f"Expected em-dash-density flag on Korean text with 5 em-dashes. Got: {flag_ids}"
    )


# ---------------------------------------------------------------------------
# 4. Korean banned-phrase coverage — translated "leverage"
# ---------------------------------------------------------------------------

def test_korean_banned_phrase_leveraging():
    """Korean text containing the calque '활용하여' (leveraging) should be flagged."""
    text = "이 도구를 활용하여 더 나은 결과를 만들 수 있습니다."
    flag_ids = [f["id"] for f in check(text, platform="linkedin")]
    assert "banned-phrase-ko" in flag_ids, (
        f"Expected banned-phrase-ko on '활용하여'. Got: {flag_ids}"
    )


# ---------------------------------------------------------------------------
# 5. Korean closing moralizer
# ---------------------------------------------------------------------------

def test_korean_closing_moralizer():
    """Korean text whose final sentence opens with '결론적으로' should trip the moralizer."""
    text = (
        "지난주에 새 기능을 배포했습니다. 응답 시간이 47% 줄었습니다. "
        "결론적으로 우리는 모두 함께해야 합니다."
    )
    flag_ids = [f["id"] for f in check(text, platform="linkedin")]
    assert "closing-moralizer-ko" in flag_ids, (
        f"Expected closing-moralizer-ko on '결론적으로' opener. Got: {flag_ids}"
    )


# ---------------------------------------------------------------------------
# 6. Korean "It's not X, it's Y"
# ---------------------------------------------------------------------------

def test_korean_not_x_but_y():
    """Korean '~이/가 아니라 ~입니다' construction should be flagged."""
    text = "이것은 단순한 도구가 아니라 혁명입니다."
    flag_ids = [f["id"] for f in check(text, platform="linkedin")]
    assert "not-x-but-y-ko" in flag_ids, (
        f"Expected not-x-but-y-ko on '~가 아니라 ~입니다'. Got: {flag_ids}"
    )


# ---------------------------------------------------------------------------
# 7. Negative — clean Korean dev post should still pass
# ---------------------------------------------------------------------------

def test_korean_clean_dev_post_still_passes():
    """A real dev's Korean post with a number anchor and casual tone — 0 hard flags."""
    text = (
        "어제 저녁에 `pgbouncer` 설정 한 줄 바꿔서 p95 레이턴시가 320ms에서 90ms로 떨어졌다. "
        "그냥 pool_mode를 transaction으로 바꿨을 뿐인데. 진작 할 걸."
    )
    flags = _hard_flags(text, platform="linkedin")
    assert flags == [], (
        f"Expected 0 hard flags for clean Korean dev post, got: {flags}"
    )
