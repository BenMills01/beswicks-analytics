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
    find_comparable_players_pca,
    get_season_totals,
    compute_trajectory,
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


@patch("os.path.exists", return_value=True)
@patch("pandas.read_excel")
def test_find_comparable_players_no_duplicates(mock_excel, mock_exists):
    """
    When the same player appears in both L1 and L2 peer files (e.g. after a
    loan move), the result must contain that player at most once.
    Regression test for the J. Arron Yates duplicate in Will Goodwin's output.
    """
    # Both L1 and L2 files contain "J. Arron Yates"
    df_with_duplicate = _peer_df(18)
    duplicate_row = df_with_duplicate.iloc[0].copy()
    duplicate_row["Player"] = "J. Arron Yates"
    duplicate_row["Minutes played"] = 1800
    df_with_duplicate = pd.concat(
        [df_with_duplicate, pd.DataFrame([duplicate_row])], ignore_index=True
    )
    mock_excel.return_value = df_with_duplicate

    ws_files_both = {
        "League One": {"Center Forward": "/fake/l1_cf.xlsx"},
        "League Two": {"Center Forward": "/fake/l2_cf.xlsx"},
    }
    result = find_comparable_players(
        client_totals=_CLIENT_TOTALS,
        pos_key="Center Forward",
        league_filter="Both",
        min_mins=500,
        ws_files=ws_files_both,
        top_n=8,
    )
    counts = result["Player"].value_counts()
    assert counts.max() <= 1, f"Duplicate player in results: {counts[counts > 1].index.tolist()}"


@patch("os.path.exists", return_value=True)
@patch("pandas.read_excel")
def test_find_comparable_players_pca_no_duplicates(mock_excel, mock_exists):
    """PCA variant also deduplicates when league_filter='Both'."""
    df_with_duplicate = _peer_df(18)
    duplicate_row = df_with_duplicate.iloc[0].copy()
    duplicate_row["Player"] = "J. Arron Yates"
    df_with_duplicate = pd.concat(
        [df_with_duplicate, pd.DataFrame([duplicate_row])], ignore_index=True
    )
    mock_excel.return_value = df_with_duplicate

    ws_files_both = {
        "League One": {"Center Forward": "/fake/l1_cf.xlsx"},
        "League Two": {"Center Forward": "/fake/l2_cf.xlsx"},
    }
    result = find_comparable_players_pca(
        client_totals=_CLIENT_TOTALS,
        pos_key="Center Forward",
        league_filter="Both",
        min_mins=500,
        ws_files=ws_files_both,
        top_n=8,
    )
    counts = result["Player"].value_counts()
    assert counts.max() <= 1, f"Duplicate player in PCA results: {counts[counts > 1].index.tolist()}"


# ── compute_trajectory ────────────────────────────────────────────────────────

def _make_traj_df(recent_goals: float, prev_goals: float, window: int = 8) -> pd.DataFrame:
    """Build a Wyscout-shaped DataFrame with two distinct performance windows."""
    n = window * 2
    goals = [prev_goals] * window + [recent_goals] * window
    return pd.DataFrame({
        "Date":           pd.date_range("2024-08-01", periods=n, freq="7D"),
        "Minutes played": [90.0] * n,
        "Goals":          goals,
    })


def test_compute_trajectory_up():
    """Player doubling their goal rate → direction 'up'."""
    df = _make_traj_df(prev_goals=0.5, recent_goals=1.0)
    result = compute_trajectory(df, "Goals")
    assert result is not None
    assert result["direction"] == "up"
    assert result["symbol"] == "↑"
    assert result["pct_change"] > 0


def test_compute_trajectory_down():
    """Player halving their goal rate → direction 'down'."""
    df = _make_traj_df(prev_goals=1.0, recent_goals=0.3)
    result = compute_trajectory(df, "Goals")
    assert result is not None
    assert result["direction"] == "down"
    assert result["symbol"] == "↓"
    assert result["pct_change"] < 0


def test_compute_trajectory_flat():
    """Consistent output within threshold → direction 'flat'."""
    df = _make_traj_df(prev_goals=0.5, recent_goals=0.51)
    result = compute_trajectory(df, "Goals")
    assert result is not None
    assert result["direction"] == "flat"
    assert result["symbol"] == "→"


def test_compute_trajectory_missing_col_returns_none():
    """Non-existent column → None, not an exception."""
    df = _make_traj_df(0.5, 1.0)
    assert compute_trajectory(df, "NonExistent") is None


def test_compute_trajectory_too_few_matches_returns_none():
    """Fewer than min_total_matches rows → None."""
    df = pd.DataFrame({
        "Minutes played": [90.0] * 4,
        "Goals":          [1.0, 0.0, 1.0, 0.0],
    })
    assert compute_trajectory(df, "Goals") is None


def test_compute_trajectory_per_90_normalised():
    """Trajectory compares per-90 rates, not raw counts — different minutes handled."""
    # Recent window: 4 goals in 360 mins = 1.0 per 90
    # Prev window:   4 goals in 720 mins = 0.5 per 90 → direction should be up
    recent = pd.DataFrame({
        "Date":           pd.date_range("2025-01-01", periods=8, freq="7D"),
        "Minutes played": [45.0] * 8,   # 45 mins each = 360 total
        "Goals":          [0.5] * 8,    # 4 goals total
    })
    prev = pd.DataFrame({
        "Date":           pd.date_range("2024-08-01", periods=8, freq="7D"),
        "Minutes played": [90.0] * 8,   # 90 mins each = 720 total
        "Goals":          [0.5] * 8,    # 4 goals total
    })
    df = pd.concat([prev, recent], ignore_index=True)
    result = compute_trajectory(df, "Goals")
    assert result is not None
    assert result["direction"] == "up"


# ── Integration tests (require real data files) ───────────────────────────────
# These tests load actual files from data/ and verify the full pipeline.
# They are skipped automatically if the data directory is not present
# (e.g. in CI without the data repo).

import glob as _glob
import os as _os

_DATA_PLAYERS = _os.path.join("data", "players")
_HAS_DATA     = _os.path.isdir(_DATA_PLAYERS) and bool(_glob.glob(_os.path.join(_DATA_PLAYERS, "*.xlsx")))

pytestmark_integration = pytest.mark.skipif(
    not _HAS_DATA,
    reason="data/players/ not found — skipping integration tests",
)


@pytest.mark.skipif(not _HAS_DATA, reason="data/players/ not present")
def test_integration_get_season_totals_real_file():
    """
    Load the first available master XLSX and verify get_season_totals() returns
    a dict with all expected keys and sensible values.
    """
    files = sorted(_glob.glob(_os.path.join(_DATA_PLAYERS, "*.xlsx")))
    path  = files[0]
    df    = pd.read_excel(path, sheet_name="Wyscout")
    ws    = df[df["Minutes played"] >= 20].copy()

    result = get_season_totals(ws)

    # Required keys
    required = {
        "mins", "matches", "goals_raw", "assists_raw", "goals_p90", "assists_p90",
        "xg_p90", "xa_p90", "passes_p90", "pass_acc", "duels_p90", "duel_win",
        "aerial_p90", "aerial_win", "def_duels_p90", "def_duel_win",
        "interceptions_p90", "recoveries_p90", "losses_p90", "yellow", "red",
    }
    missing = required - set(result.keys())
    assert not missing, f"get_season_totals missing keys: {missing}"

    # Sanity bounds
    assert result["mins"] > 0, "Total minutes must be positive"
    assert result["matches"] >= 1
    assert 0 <= (result["pass_acc"] or 0) <= 100, "Pass accuracy must be 0–100"
    assert 0 <= (result["duel_win"] or 0) <= 100


@pytest.mark.skipif(not _HAS_DATA, reason="data/players/ not present")
def test_integration_season_totals_no_iloc_drift():
    """
    Verify iloc positions haven't drifted in real Wyscout exports.
    iloc[13] must return a value that makes pass_acc plausible (between 0 and 100%).
    """
    files = sorted(_glob.glob(_os.path.join(_DATA_PLAYERS, "*.xlsx")))
    for path in files[:3]:  # check first 3 clients
        df = pd.read_excel(path, sheet_name="Wyscout")
        ws = df[df["Minutes played"] >= 20].copy()
        if ws.empty or ws.shape[1] < 41:
            continue
        result = get_season_totals(ws)
        acc = result.get("pass_acc")
        assert acc is None or 0 <= acc <= 100, (
            f"pass_acc out of range in {path}: {acc} — "
            "check if Wyscout export added a column before iloc[13]"
        )
        assert result.get("yellow", 0) >= 0
        assert result.get("red", 0) >= 0


@pytest.mark.skipif(not _HAS_DATA, reason="data/players/ not present")
def test_integration_compute_trajectory_real_file():
    """
    compute_trajectory() on a real Wyscout sheet either returns a valid dict
    or None — never raises an exception.
    """
    files = sorted(_glob.glob(_os.path.join(_DATA_PLAYERS, "*.xlsx")))
    path  = files[0]
    df    = pd.read_excel(path, sheet_name="Wyscout")
    ws    = df[df["Minutes played"] >= 20].copy()

    for col in ["Goals", "xG", "Passes", "Duels"]:
        result = compute_trajectory(ws, col)
        assert result is None or (
            isinstance(result, dict)
            and result["direction"] in ("up", "down", "flat")
            and result["symbol"] in ("↑", "↓", "→")
        ), f"Unexpected trajectory result for {col}: {result}"
