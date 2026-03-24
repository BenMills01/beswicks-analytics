"""
tests/test_metrics.py
Unit tests for src/metrics.py — core helpers, get_season_totals, find_comparable_players.

Run with:
    cd .claude/worktrees/silly-nobel
    pytest tests/ -v
"""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from src.metrics import (
    find_comparable_players,
    get_season_totals,
    ordinal,
    p90,
    pct,
    pct_colour,
    percentile_rank,
)


# ── p90 ────────────────────────────────────────────────────────────────────────

def test_p90_normal():
    """1 event in 90 minutes = 1.0 per 90."""
    assert p90(1, 90) == 1.0


def test_p90_proportional():
    """1 event in 180 minutes = 0.5 per 90."""
    assert p90(1, 180) == 0.5


def test_p90_zero_minutes():
    """Zero-minute denominator returns 0.0, not ZeroDivisionError."""
    assert p90(10, 0) == 0.0


def test_p90_rounding():
    """Result is rounded to 2 dp."""
    result = p90(1, 3)
    assert result == round(1 / 3 * 90, 2)


# ── pct ───────────────────────────────────────────────────────────────────────

def test_pct_normal():
    assert pct(75, 100) == 75.0


def test_pct_zero_denom():
    assert pct(75, 0) is None


def test_pct_none_denom():
    assert pct(75, None) is None


def test_pct_none_num():
    assert pct(None, 100) is None


def test_pct_rounding():
    result = pct(1, 3)
    assert result == round(1 / 3 * 100, 1)


# ── percentile_rank ───────────────────────────────────────────────────────────

def test_percentile_rank_basic():
    """Value in the upper half of a 10-element series gets > 50th percentile."""
    series = pd.Series(range(1, 11))  # 1..10
    rank = percentile_rank(8, series)
    assert rank is not None
    assert rank > 50


def test_percentile_rank_min_peers():
    """Fewer than 5 peers → None regardless of value."""
    series = pd.Series([1.0, 2.0, 3.0])
    assert percentile_rank(2.0, series) is None


def test_percentile_rank_min_value_is_none():
    assert percentile_rank(None, pd.Series([1, 2, 3, 4, 5, 6])) is None


def test_percentile_rank_inverse():
    """With inverse=True the rank is mirrored: inverse ≈ 100 − normal."""
    series = pd.Series(range(1, 11))
    rank_fwd = percentile_rank(2, series, inverse=False)
    rank_inv = percentile_rank(2, series, inverse=True)
    assert rank_fwd is not None and rank_inv is not None
    assert abs(rank_fwd + rank_inv - 100) < 2   # rounding tolerance


# ── ordinal ───────────────────────────────────────────────────────────────────

def test_ordinal_variants():
    assert ordinal(1)  == "1st"
    assert ordinal(2)  == "2nd"
    assert ordinal(3)  == "3rd"
    assert ordinal(4)  == "4th"
    assert ordinal(11) == "11th"
    assert ordinal(12) == "12th"
    assert ordinal(13) == "13th"
    assert ordinal(21) == "21st"
    assert ordinal(22) == "22nd"
    assert ordinal(100) == "100th"


# ── pct_colour ────────────────────────────────────────────────────────────────

def test_pct_colour_green():
    assert pct_colour(80)  == "#4ade80"
    assert pct_colour(100) == "#4ade80"


def test_pct_colour_light_green():
    assert pct_colour(55) == "#86efac"
    assert pct_colour(79) == "#86efac"


def test_pct_colour_yellow():
    assert pct_colour(35) == "#facc15"
    assert pct_colour(54) == "#facc15"


def test_pct_colour_red():
    assert pct_colour(0)  == "#f87171"
    assert pct_colour(34) == "#f87171"


def test_pct_colour_none():
    assert pct_colour(None) == "#666"


# ── get_season_totals helpers ─────────────────────────────────────────────────

def _make_ws_df(n_rows: int = 1, minutes: float = 90.0) -> pd.DataFrame:
    """
    Minimal mock Wyscout DataFrame for get_season_totals tests.

    The first 45 columns are numeric padding so that iloc positions 13, 15, 19,
    21, 23, 31, 32, 39, 40 can be set independently.  Named Wyscout columns are
    appended after the padding so they never displace a positional column.
    """
    data = {f"_pad{i}": [0.0] * n_rows for i in range(45)}
    df = pd.DataFrame(data)

    named_defaults = {
        "Minutes played":           minutes,
        "Goals":                    0.0,
        "Assists":                  0.0,
        "xG":                       0.0,
        "xA":                       0.0,
        "Shots":                    0.0,
        "Shot assists":             0.0,
        "Touches in penalty area":  0.0,
        "Dribbles":                 0.0,
        "Progressive runs":         0.0,
        "Passes to final third":    0.0,
        "Passes":                   50.0,
        "Long passes":              5.0,
        "Crosses":                  0.0,
        "Duels":                    10.0,
        "Aerial duels":             3.0,
        "Interceptions":            0.0,
        "Recoveries":               0.0,
        "Clearances":               0.0,
        "Losses":                   0.0,
        "own half":                 0.0,
        "opp. half":                0.0,
        "Fouls":                    0.0,
    }
    for col, val in named_defaults.items():
        df[col] = val

    return df


# ── get_season_totals iloc regression tests ───────────────────────────────────

def test_get_season_totals_pass_acc_from_iloc_13():
    """
    pass_acc is derived from ws.iloc[:, 13] (accurate passes) divided by Passes.
    Regression guard: if col 13 drifts in the source file this test will catch it.
    """
    df = _make_ws_df()
    df.iloc[0, 13] = 40.0   # accurate passes
    df["Passes"] = 50.0
    result = get_season_totals(df)
    assert result["pass_acc"] == pct(40.0, 50.0)  # 80.0


def test_get_season_totals_drib_pct_from_iloc_19():
    """drib_pct is derived from ws.iloc[:, 19] (successful dribbles) / Dribbles."""
    df = _make_ws_df()
    df.iloc[0, 19] = 3.0
    df["Dribbles"] = 4.0
    result = get_season_totals(df)
    assert result["drib_pct"] == pct(3.0, 4.0)  # 75.0


def test_get_season_totals_yellow_from_iloc_39():
    """Yellow cards come from ws.iloc[:, 39]."""
    df = _make_ws_df()
    df.iloc[0, 39] = 2.0
    result = get_season_totals(df)
    assert result["yellow"] == 2


def test_get_season_totals_red_from_iloc_40():
    """Red cards come from ws.iloc[:, 40]."""
    df = _make_ws_df()
    df.iloc[0, 40] = 1.0
    result = get_season_totals(df)
    assert result["red"] == 1


def test_get_season_totals_goals_p90():
    """goals_p90 = goals / minutes * 90."""
    df = _make_ws_df(minutes=180.0)
    df["Goals"] = 2.0
    result = get_season_totals(df)
    assert result["goals_p90"] == 1.0


def test_get_season_totals_multi_row_sums():
    """Season totals correctly aggregate across multiple appearances."""
    df = _make_ws_df(n_rows=3, minutes=90.0)
    df["Goals"] = [1.0, 0.0, 1.0]  # 2 goals total
    df["Minutes played"] = [90.0, 45.0, 90.0]  # 225 mins total
    result = get_season_totals(df)
    assert result["goals_raw"] == 2
    assert result["mins"] == 225.0


# ── find_comparable_players ───────────────────────────────────────────────────

def _peer_df(n: int = 20, include_name: str | None = None) -> pd.DataFrame:
    """Build a plausible mock peer player DataFrame."""
    rng = np.random.default_rng(42)
    df = pd.DataFrame({
        "Player":                                [f"Peer_{i}" for i in range(n)],
        "Team":                                  ["Test Town"] * n,
        "Minutes played":                        [1800] * n,
        "Goals per 90":                          rng.uniform(0,    1,   n).tolist(),
        "Assists per 90":                        rng.uniform(0,    0.5, n).tolist(),
        "xG per 90":                             rng.uniform(0,    1,   n).tolist(),
        "xA per 90":                             rng.uniform(0,    0.5, n).tolist(),
        "Passes per 90":                         rng.uniform(20,   80,  n).tolist(),
        "Accurate passes, %":                    rng.uniform(60,   95,  n).tolist(),
        "Dribbles per 90":                       rng.uniform(0,    5,   n).tolist(),
        "Progressive runs per 90":               rng.uniform(0,    5,   n).tolist(),
        "Duels per 90":                          rng.uniform(5,    20,  n).tolist(),
        "Duels won, %":                          rng.uniform(40,   70,  n).tolist(),
        "Aerial duels per 90":                   rng.uniform(0,    5,   n).tolist(),
        "Aerial duels won, %":                   rng.uniform(40,   70,  n).tolist(),
        "Defensive duels per 90":                rng.uniform(1,    8,   n).tolist(),
        "Defensive duels won, %":                rng.uniform(40,   70,  n).tolist(),
        "Interceptions per 90":                  rng.uniform(0,    3,   n).tolist(),
        "Successful defensive actions per 90":   rng.uniform(0,    5,   n).tolist(),
    })
    if include_name:
        row = {
            c: (df[c].mean() if pd.api.types.is_numeric_dtype(df[c]) else include_name)
            for c in df.columns
        }
        row["Player"] = include_name
        row["Minutes played"] = 1800
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    return df


_CLIENT_TOTALS = {
    "goals_p90": 0.4,  "assists_p90": 0.1, "xg_p90": 0.5,   "xa_p90": 0.15,
    "passes_p90": 42.0, "pass_acc": 77.0,  "dribbles_p90": 1.8, "prog_runs_p90": 1.5,
    "duels_p90": 12.0,  "duel_win": 53.0,  "aerial_p90": 3.0,   "aerial_win": 58.0,
    "def_duels_p90": 4.0, "def_duel_win": 60.0,
    "interceptions_p90": 1.2, "recoveries_p90": 3.5,
}

_WS_FILES = {"League One": {"Central Defender": "/fake/l1_cd.xlsx"}}


@patch("os.path.exists", return_value=True)
@patch("pandas.read_excel")
def test_find_comparable_players_excludes_client(mock_excel, mock_exists):
    """The client player (matched by last name) is not present in the results."""
    mock_excel.return_value = _peer_df(20, include_name="Devon Matthews")

    result = find_comparable_players(
        client_totals=_CLIENT_TOTALS,
        pos_key="Central Defender",
        league_filter="League One",
        min_mins=500,
        ws_files=_WS_FILES,
        top_n=10,
        client_name="Devon Matthews",
    )
    assert "Devon Matthews" not in result["Player"].values


@patch("os.path.exists", return_value=True)
@patch("pandas.read_excel")
def test_find_comparable_players_top_n(mock_excel, mock_exists):
    """Result contains at most top_n rows."""
    mock_excel.return_value = _peer_df(20)

    result = find_comparable_players(
        client_totals=_CLIENT_TOTALS,
        pos_key="Central Defender",
        league_filter="League One",
        min_mins=500,
        ws_files=_WS_FILES,
        top_n=5,
    )
    assert len(result) <= 5


@patch("os.path.exists", return_value=True)
@patch("pandas.read_excel")
def test_find_comparable_players_similarity_ordered(mock_excel, mock_exists):
    """Similarity column is sorted descending (most similar first)."""
    mock_excel.return_value = _peer_df(20)

    result = find_comparable_players(
        client_totals=_CLIENT_TOTALS,
        pos_key="Central Defender",
        league_filter="League One",
        min_mins=500,
        ws_files=_WS_FILES,
        top_n=8,
    )
    if len(result) >= 2:
        sims = result["Similarity"].tolist()
        assert sims == sorted(sims, reverse=True), "Similarity must be descending"


@patch("os.path.exists", return_value=True)
@patch("pandas.read_excel")
def test_find_comparable_players_returns_empty_when_no_peers(mock_excel, mock_exists):
    """Returns an empty DataFrame when no peer file exists."""
    mock_exists.return_value = False  # no file on disk

    result = find_comparable_players(
        client_totals=_CLIENT_TOTALS,
        pos_key="Central Defender",
        league_filter="League One",
        min_mins=500,
        ws_files=_WS_FILES,
    )
    assert result.empty


def test_find_comparable_players_no_pos_key():
    """Returns an empty DataFrame when pos_key is None."""
    result = find_comparable_players(
        client_totals=_CLIENT_TOTALS,
        pos_key=None,
        league_filter="League One",
        min_mins=500,
        ws_files=_WS_FILES,
    )
    assert result.empty
