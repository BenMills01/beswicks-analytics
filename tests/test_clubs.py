"""
tests/test_clubs.py
Unit tests for src/clubs.py — weakness diagnosis, position filtering, style fit score.

Run with:
    cd .claude/worktrees/silly-nobel
    pytest tests/ -v
"""

from __future__ import annotations

import pytest

from src.clubs import (
    filter_weaknesses_by_position,
    get_club_weaknesses,
    get_league_medians,
    get_style_fit_score,
)


# ── Shared fixtures ────────────────────────────────────────────────────────────

_FULL_PROFILE = {
    # Original 8 metrics
    "avg_possession":       55.0,
    "avg_ppda":             9.0,
    "avg_pass_acc_pct":     78.0,
    "avg_long_pass_pct":    25.0,
    "avg_def_duel_win_pct": 62.0,
    "avg_aerial_win_pct":   56.0,
    "avg_goals_scored":     1.5,
    "avg_goals_conceded":   1.2,
    # Gap-2 additions — also included so profile is forward-compatible
    "avg_xg_scored":        1.3,
    "avg_shots_on_tgt_pct": 38.0,
    "avg_interceptions":    4.5,
    "avg_crosses":          9.0,
}


def _make_profile(**overrides) -> dict:
    base = {
        "avg_def_duel_win_pct": 65.0,
        "avg_aerial_win_pct":   58.0,
        "avg_goals_conceded":   1.0,
        "avg_possession":       55.0,
        "avg_pass_acc_pct":     80.0,
        "avg_goals_scored":     1.8,
    }
    base.update(overrides)
    return base


def _make_medians(**overrides) -> dict:
    base = {
        "avg_def_duel_win_pct": 62.0,
        "avg_aerial_win_pct":   55.0,
        "avg_goals_conceded":   1.4,
        "avg_possession":       52.0,
        "avg_pass_acc_pct":     78.0,
        "avg_goals_scored":     1.5,
    }
    base.update(overrides)
    return base


# ── get_league_medians ─────────────────────────────────────────────────────────

def test_get_league_medians_original_keys():
    """All 8 original metric keys are returned."""
    profiles = {"Club A": _FULL_PROFILE}
    medians = get_league_medians(profiles)
    expected = {
        "avg_possession", "avg_ppda", "avg_pass_acc_pct", "avg_long_pass_pct",
        "avg_def_duel_win_pct", "avg_aerial_win_pct",
        "avg_goals_scored", "avg_goals_conceded",
    }
    assert expected <= set(medians.keys())


def test_get_league_medians_extended_keys():
    """
    Gap 2: all 4 new metric keys appear in the medians output once Gap 2 is done.
    This test will FAIL until get_league_medians() is extended.
    """
    profiles = {"Club A": _FULL_PROFILE}
    medians = get_league_medians(profiles)
    gap2_keys = {"avg_xg_scored", "avg_shots_on_tgt_pct", "avg_interceptions", "avg_crosses"}
    assert gap2_keys <= set(medians.keys()), (
        "Gap 2 metrics missing — extend the `metrics` list in get_league_medians()"
    )


def test_get_league_medians_correct_median():
    """Median is correctly computed as the middle value across odd-N profiles."""
    profiles = {
        "A": {**_FULL_PROFILE, "avg_goals_scored": 1.0},
        "B": {**_FULL_PROFILE, "avg_goals_scored": 2.0},
        "C": {**_FULL_PROFILE, "avg_goals_scored": 3.0},
    }
    assert get_league_medians(profiles)["avg_goals_scored"] == 2.0


def test_get_league_medians_skips_none():
    """Profiles with None values for a metric are excluded from that metric's median."""
    profiles = {
        "A": {**_FULL_PROFILE, "avg_goals_scored": 1.0},
        "B": {**_FULL_PROFILE, "avg_goals_scored": None},  # missing — excluded
        "C": {**_FULL_PROFILE, "avg_goals_scored": 3.0},
    }
    med = get_league_medians(profiles)["avg_goals_scored"]
    # Only two valid values (1.0, 3.0) → median = 2.0
    assert med == 2.0


# ── get_club_weaknesses ────────────────────────────────────────────────────────

def test_get_club_weaknesses_inverse_metric_flagged():
    """
    Goals conceded is inverse (higher = worse).
    Club conceding more than the median should be flagged as weak.
    """
    profile = _make_profile(avg_goals_conceded=2.0)   # > median 1.4 — weak
    medians = _make_medians(avg_goals_conceded=1.4)
    weaknesses = get_club_weaknesses(profile, medians)
    assert any(w["metric"] == "avg_goals_conceded" for w in weaknesses)


def test_get_club_weaknesses_inverse_metric_not_flagged():
    """Club conceding less than the median should NOT be flagged."""
    profile = _make_profile(avg_goals_conceded=0.8)   # < median 1.4 — fine
    medians = _make_medians(avg_goals_conceded=1.4)
    weaknesses = get_club_weaknesses(profile, medians)
    assert not any(w["metric"] == "avg_goals_conceded" for w in weaknesses)


def test_get_club_weaknesses_not_weak_when_above_median():
    """No weaknesses returned when every metric beats the median."""
    profile = _make_profile(
        avg_def_duel_win_pct=70.0,   # > 62 ✓
        avg_aerial_win_pct=60.0,     # > 55 ✓
        avg_goals_conceded=1.0,      # < 1.4 ✓ (inverse)
        avg_possession=60.0,         # > 52 ✓
        avg_pass_acc_pct=85.0,       # > 78 ✓
        avg_goals_scored=2.0,        # > 1.5 ✓
    )
    assert get_club_weaknesses(profile, _make_medians()) == []


def test_get_club_weaknesses_sorted_by_gap():
    """Weaknesses are returned sorted descending by gap_pct (largest gap first)."""
    profile = _make_profile(
        avg_goals_scored=0.5,        # large gap vs median 1.5 → ~67% below
        avg_pass_acc_pct=77.0,       # tiny gap vs median 78.0 → ~1% below
    )
    weaknesses = get_club_weaknesses(profile, _make_medians())
    gaps = [w["gap_pct"] for w in weaknesses]
    assert gaps == sorted(gaps, reverse=True)


def test_get_club_weaknesses_includes_correct_fields():
    """Each weakness dict contains the required keys."""
    profile = _make_profile(avg_goals_scored=0.8)
    weaknesses = get_club_weaknesses(profile, _make_medians())
    assert weaknesses, "Expected at least one weakness"
    required = {"metric", "label", "club_val", "median_val", "gap_pct", "interpretation", "inverse"}
    for w in weaknesses:
        assert required <= set(w.keys()), f"Missing keys in weakness: {set(w.keys())}"


# ── filter_weaknesses_by_position ─────────────────────────────────────────────

def _sample_weaknesses() -> list[dict]:
    return [
        {
            "metric": "avg_goals_scored",     "label": "Goals scored/game",
            "gap_pct": 20.0, "club_val": 1.2, "median_val": 1.5,
            "interpretation": "Need more goals", "inverse": False,
        },
        {
            "metric": "avg_def_duel_win_pct", "label": "Defensive duel win %",
            "gap_pct": 10.0, "club_val": 56.0, "median_val": 62.0,
            "interpretation": "Struggle to win 1v1s", "inverse": False,
        },
        {
            "metric": "avg_aerial_win_pct",   "label": "Aerial duel win %",
            "gap_pct": 8.0,  "club_val": 48.0, "median_val": 55.0,
            "interpretation": "Losing aerials", "inverse": False,
        },
    ]


def test_filter_weaknesses_fullback_excludes_goals():
    """Full Backs cannot address a goals-scored weakness — it should be stripped."""
    filtered = filter_weaknesses_by_position(_sample_weaknesses(), "Full Back")
    metrics = {w["metric"] for w in filtered}
    assert "avg_goals_scored" not in metrics, (
        "avg_goals_scored should be excluded for Full Back position"
    )
    # defensive metrics should still be present
    assert "avg_def_duel_win_pct" in metrics


def test_filter_weaknesses_unknown_position_returns_all():
    """Unknown or None pos_key → all weaknesses returned unchanged."""
    original = _sample_weaknesses()
    assert filter_weaknesses_by_position(original, "Unknown Role") == original
    assert filter_weaknesses_by_position(original, None) == original


def test_filter_weaknesses_goalkeeper_excludes_goals_scored():
    """Goalkeepers' relevance set does not include avg_goals_scored."""
    filtered = filter_weaknesses_by_position(_sample_weaknesses(), "Goalkeeper")
    metrics = {w["metric"] for w in filtered}
    assert "avg_goals_scored" not in metrics


def test_filter_weaknesses_center_forward_excludes_def_duels():
    """Center Forwards should not be expected to address a defensive duel weakness."""
    filtered = filter_weaknesses_by_position(_sample_weaknesses(), "Center Forward")
    metrics = {w["metric"] for w in filtered}
    assert "avg_def_duel_win_pct" not in metrics


# ── get_style_fit_score ────────────────────────────────────────────────────────

_EMPTY_CLUB = {
    "press_intensity": "High press",
    "play_style":      "Balanced",
    "avg_ppda":        7.0,
    "avg_def_duel_win_pct": 55.0,
    "avg_aerial_win_pct":   50.0,
    "avg_goals_conceded":   1.5,
}

_MEDIANS = {
    "avg_def_duel_win_pct": 62.0,
    "avg_aerial_win_pct":   55.0,
    "avg_goals_conceded":   1.3,
}


def test_get_style_fit_score_returns_dict_with_overall():
    """Function always returns a dict that includes the 'overall' key."""
    scores = get_style_fit_score(
        season={}, phys=None,
        club_profile=_EMPTY_CLUB,
        ws_peers={}, phys_peers={},
        league_medians=_MEDIANS,
    )
    assert isinstance(scores, dict)
    assert "overall" in scores


def test_get_style_fit_score_none_when_no_peers():
    """Without any peer data every dimension and overall should be None."""
    scores = get_style_fit_score(
        season={}, phys=None,
        club_profile=_EMPTY_CLUB,
        ws_peers={}, phys_peers={},
        league_medians=_MEDIANS,
    )
    assert scores["overall"] is None


def test_get_style_fit_score_all_nine_combinations():
    """All 9 (press_intensity × play_style) combinations run without exception."""
    press_opts = ["High press", "Moderate press", "Low block"]
    style_opts = ["Possession-based", "Balanced", "Direct"]
    for press in press_opts:
        for style in style_opts:
            club = {**_EMPTY_CLUB, "press_intensity": press, "play_style": style}
            scores = get_style_fit_score(
                season={}, phys=None,
                club_profile=club,
                ws_peers={}, phys_peers={},
                league_medians=_MEDIANS,
            )
            assert isinstance(scores, dict), (
                f"get_style_fit_score raised for {press!r} / {style!r}"
            )


def test_get_style_fit_score_low_block_direct_in_possession_minimal():
    """
    Low block + Direct has the lowest in_possession weight (0.05).
    Without peer data overall is None; function must still return valid dict.
    """
    scores = get_style_fit_score(
        season={}, phys=None,
        club_profile={
            "press_intensity":      "Low block",
            "play_style":           "Direct",
            "avg_ppda":             16.0,
            "avg_def_duel_win_pct": 55.0,
            "avg_aerial_win_pct":   50.0,
            "avg_goals_conceded":   1.6,
        },
        ws_peers={}, phys_peers={},
        league_medians=_MEDIANS,
    )
    assert scores.get("overall") is None   # no peers → no score
    # in_possession key may or may not be present depending on whether ppda/style
    # thresholds produce a score; either None or absent is acceptable
    assert scores.get("in_possession") is None or "in_possession" not in scores
