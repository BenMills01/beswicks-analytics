"""
src/clubs.py
Beswicks Sports Analytics — Club data loader and profile builder.

Loads Wyscout team stats exports from data/clubs/ and returns tactical
profiles suitable for pre-populating the club report narrative prompt.

No Streamlit imports — all functions are @st.cache_data-compatible.

File naming convention: data/clubs/Team Stats {Club Name}.xlsx
"""

import os
import glob
import difflib
from pathlib import Path
from typing import Optional

import pandas as pd

CLUBS_DIR = "data/clubs"

# iloc positions for columns with duplicate names in Wyscout team exports
# (verified against Team Stats Crewe Alexandra.xlsx — 109-column export)
_PASS_ACC_PCT_COL    = 13  # Passes accurate %
_DEF_DUEL_WIN_PCT    = 66  # Defensive duels won %
_AERIAL_WIN_PCT      = 69  # Aerial duels won %


def get_club_list() -> dict[str, str]:
    """
    Returns {club_name: filepath} for all 'Team Stats *.xlsx' files in CLUBS_DIR.

    Club name is extracted from the filename:
        'Team Stats Crewe Alexandra.xlsx' → 'Crewe Alexandra'
    """
    pattern = os.path.join(CLUBS_DIR, "Team Stats *.xlsx")
    files   = glob.glob(pattern)
    result: dict[str, str] = {}
    for f in sorted(files):
        stem = Path(f).stem  # e.g. "Team Stats Crewe Alexandra"
        if stem.startswith("Team Stats "):
            club_name = stem[len("Team Stats "):]
            result[club_name] = f
    return result


def load_club_raw(filepath: str) -> pd.DataFrame:
    """
    Reads the TeamStats sheet from a Wyscout team stats export.

    The export includes two metadata label rows (team name + "Opponents")
    before the actual match data. These are dropped by filtering on parseable
    Date values.

    Returns a DataFrame of actual match rows for all teams in the file
    (alternating club row / opponent row per match).
    """
    df = pd.read_excel(filepath, sheet_name="TeamStats", header=0)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).reset_index(drop=True)
    return df


def get_club_profile(club_name: str, filepath: str) -> dict:
    """
    Builds a tactical profile dict for a given club from their team stats file.

    Filters to club-perspective rows (Team == club_name) and aggregates key
    metrics. Named column access is used where column names are unique;
    iloc is used for columns that are deduplicated by pandas (e.g. 'won').

    Returns a dict with keys:
        club_name, matches, wins, draws, losses,
        primary_formation, avg_possession, avg_ppda,
        avg_pass_acc_pct, avg_long_pass_pct,
        avg_def_duel_win_pct, avg_aerial_win_pct,
        avg_goals_scored, avg_goals_conceded,
        press_intensity, play_style
    """
    df = load_club_raw(filepath)

    # Filter to club-perspective rows
    club_df = df[df["Team"] == club_name].copy()
    if club_df.empty:
        # Fallback: case-insensitive strip
        mask = df["Team"].str.strip().str.lower() == club_name.strip().lower()
        club_df = df[mask].copy()

    if club_df.empty:
        return {"club_name": club_name, "matches": 0}

    n = len(club_df)

    # ── Formation ─────────────────────────────────────────────────────────────
    # Scheme column: "4-2-3-1 (80.17%)" → extract "4-2-3-1"
    primary_formation = "Unknown"
    if "Scheme" in club_df.columns:
        parsed = club_df["Scheme"].dropna().str.extract(r"^([0-9][0-9\-]+[0-9])")
        if not parsed.empty and not parsed[0].dropna().empty:
            primary_formation = parsed[0].dropna().mode().iloc[0]

    # ── Results ───────────────────────────────────────────────────────────────
    goals_col    = club_df["Goals"]          if "Goals"          in club_df.columns else pd.Series(dtype=float)
    conceded_col = club_df["Conceded goals"] if "Conceded goals" in club_df.columns else pd.Series(dtype=float)

    wins   = int((goals_col > conceded_col).sum())
    draws  = int((goals_col == conceded_col).sum())
    losses = int((goals_col < conceded_col).sum())

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _mean(col: pd.Series) -> Optional[float]:
        v = col.dropna()
        return round(float(v.mean()), 2) if not v.empty else None

    def _iloc_mean(idx: int) -> Optional[float]:
        if idx >= len(club_df.columns):
            return None
        return _mean(club_df.iloc[:, idx])

    def _named(col: str) -> Optional[float]:
        return _mean(club_df[col]) if col in club_df.columns else None

    # ── Aggregated metrics ────────────────────────────────────────────────────
    avg_possession       = _named("Possession, %")
    avg_ppda             = _named("PPDA")
    avg_long_pass_pct    = _named("Long pass %")
    avg_goals_scored     = _mean(goals_col)
    avg_goals_conceded   = _mean(conceded_col)
    avg_pass_acc_pct     = _iloc_mean(_PASS_ACC_PCT_COL)
    avg_def_duel_win_pct = _iloc_mean(_DEF_DUEL_WIN_PCT)
    avg_aerial_win_pct   = _iloc_mean(_AERIAL_WIN_PCT)

    # ── Press intensity ───────────────────────────────────────────────────────
    # PPDA: passes per defensive action — lower = presses more aggressively
    if avg_ppda is not None:
        if avg_ppda < 8:
            press_intensity = "High press"
        elif avg_ppda < 12:
            press_intensity = "Moderate press"
        else:
            press_intensity = "Low block"
    else:
        press_intensity = None

    # ── Play style ────────────────────────────────────────────────────────────
    play_style = None
    if avg_possession is not None and avg_long_pass_pct is not None:
        if avg_possession > 55:
            play_style = "Possession-based"
        elif avg_long_pass_pct > 35:
            play_style = "Direct"
        else:
            play_style = "Balanced"

    return {
        "club_name":             club_name,
        "matches":               n,
        "wins":                  wins,
        "draws":                 draws,
        "losses":                losses,
        "primary_formation":     primary_formation,
        "avg_possession":        avg_possession,
        "avg_ppda":              avg_ppda,
        "avg_pass_acc_pct":      avg_pass_acc_pct,
        "avg_long_pass_pct":     avg_long_pass_pct,
        "avg_def_duel_win_pct":  avg_def_duel_win_pct,
        "avg_aerial_win_pct":    avg_aerial_win_pct,
        "avg_goals_scored":      avg_goals_scored,
        "avg_goals_conceded":    avg_goals_conceded,
        "press_intensity":       press_intensity,
        "play_style":            play_style,
    }


def fuzzy_match_club(
    query: str,
    club_list: dict[str, str],
) -> tuple[str, str] | None:
    """
    Case-insensitive fuzzy match of query against club_list keys.

    Resolution order:
        1. Exact match (case-insensitive)
        2. Substring match (query in name or name in query)
        3. difflib fuzzy match (cutoff=0.6)

    Returns (matched_club_name, filepath) or None if no match.
    """
    if not query or not club_list:
        return None

    q = query.strip().lower()
    keys = list(club_list.keys())
    keys_lower = [k.lower() for k in keys]

    # 1 — Exact
    for i, k in enumerate(keys_lower):
        if q == k:
            return keys[i], club_list[keys[i]]

    # 2 — Substring
    for i, k in enumerate(keys_lower):
        if q in k or k in q:
            return keys[i], club_list[keys[i]]

    # 3 — Fuzzy
    matches = difflib.get_close_matches(q, keys_lower, n=1, cutoff=0.6)
    if matches:
        idx = keys_lower.index(matches[0])
        return keys[idx], club_list[keys[idx]]

    return None


def format_club_context(profile: dict) -> str:
    """
    Formats a club profile dict into a compact bullet-style string for
    injection into the Anthropic prompt context block.

    Returns empty string if profile is empty or has no match data.
    """
    if not profile or profile.get("matches", 0) == 0:
        return ""

    parts: list[str] = []

    if profile.get("primary_formation") and profile["primary_formation"] != "Unknown":
        parts.append(f"Formation: {profile['primary_formation']}")
    if profile.get("press_intensity"):
        parts.append(profile["press_intensity"])
    if profile.get("play_style"):
        parts.append(profile["play_style"])
    if profile.get("avg_ppda") is not None:
        parts.append(f"PPDA {profile['avg_ppda']:.1f}")
    if profile.get("avg_possession") is not None:
        parts.append(f"Possession {profile['avg_possession']:.0f}%")
    if profile.get("avg_pass_acc_pct") is not None:
        parts.append(f"Pass acc {profile['avg_pass_acc_pct']:.0f}%")
    if profile.get("avg_def_duel_win_pct") is not None:
        parts.append(f"Def duel win {profile['avg_def_duel_win_pct']:.0f}%")
    if profile.get("avg_aerial_win_pct") is not None:
        parts.append(f"Aerial win {profile['avg_aerial_win_pct']:.0f}%")
    if profile.get("avg_goals_scored") is not None and profile.get("avg_goals_conceded") is not None:
        parts.append(
            f"{profile['avg_goals_scored']:.1f} scored / "
            f"{profile['avg_goals_conceded']:.1f} conceded per game"
        )

    w = profile.get("wins", 0)
    d = profile.get("draws", 0)
    l = profile.get("losses", 0)
    n = profile.get("matches", 0)
    if n:
        parts.append(f"W{w}/D{d}/L{l} ({n} games)")

    return " · ".join(parts)
