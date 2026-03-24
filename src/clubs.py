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
from typing import Dict, Optional

import numpy as np
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

    # ── League ────────────────────────────────────────────────────────────────
    league = None
    if "Competition" in club_df.columns:
        comp_val = club_df["Competition"].dropna().mode()
        if not comp_val.empty:
            c = comp_val.iloc[0].lower()
            if "championship" in c:
                league = "Championship"
            elif "league one" in c:
                league = "League One"
            elif "league two" in c:
                league = "League Two"

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
        "league":                league,
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


# ── League-wide analysis ───────────────────────────────────────────────────────

def get_all_club_profiles() -> dict[str, dict]:
    """
    Load profiles for every club file in CLUBS_DIR.
    Returns {club_name: profile_dict}. Silently skips files that fail to load.
    Intended to be wrapped with @st.cache_data in the calling page.
    """
    profiles: dict[str, dict] = {}
    for club_name, filepath in get_club_list().items():
        try:
            profiles[club_name] = get_club_profile(club_name, filepath)
        except Exception:
            pass
    return profiles


def get_league_medians(all_profiles: dict[str, dict]) -> dict[str, float]:
    """
    Compute median values for each numeric club metric across all available
    club profiles. Used as the baseline for weakness diagnosis.

    Returns {metric_key: median_value}.
    """
    metrics = [
        "avg_possession", "avg_ppda", "avg_pass_acc_pct", "avg_long_pass_pct",
        "avg_def_duel_win_pct", "avg_aerial_win_pct",
        "avg_goals_scored", "avg_goals_conceded",
    ]
    medians: dict[str, float] = {}
    for m in metrics:
        values = [p[m] for p in all_profiles.values() if p.get(m) is not None]
        if values:
            medians[m] = round(float(np.median(values)), 2)
    return medians


def get_club_weaknesses(
    club_profile: dict,
    medians: dict[str, float],
) -> list[dict]:
    """
    Identify areas where the club falls below the league median.

    Returns a list of weakness dicts sorted by severity (largest gap first):
        {metric, label, club_val, median_val, gap_pct, interpretation}

    Only metrics where the club is on the wrong side of the median are included.
    """
    # (metric_key, display_label, inverse, interpretation)
    # inverse=True means higher value is worse (e.g. goals_conceded)
    checks = [
        ("avg_def_duel_win_pct", "Defensive duel win %", False,
         "Struggle to win defensive 1v1 battles — need a dominant ball-winner"),
        ("avg_aerial_win_pct",   "Aerial duel win %",    False,
         "Losing aerial battles — concede from set pieces and long balls"),
        ("avg_goals_conceded",   "Goals conceded/game",  True,
         "Conceding at an above-average rate — defensive solidity required"),
        ("avg_possession",       "Possession %",         False,
         "Below-average ball retention — need a composed, ball-playing profile"),
        ("avg_pass_acc_pct",     "Pass accuracy %",      False,
         "Higher turnover rate in possession — need a reliable passer"),
        ("avg_goals_scored",     "Goals scored/game",    False,
         "Below-average attacking output — need more end-product"),
    ]

    weaknesses: list[dict] = []
    for key, label, inverse, interpretation in checks:
        club_val   = club_profile.get(key)
        median_val = medians.get(key)
        if club_val is None or median_val is None or median_val == 0:
            continue
        if inverse:
            is_weak = club_val > median_val
            gap_pct = round((club_val - median_val) / median_val * 100, 1)
        else:
            is_weak = club_val < median_val
            gap_pct = round((median_val - club_val) / median_val * 100, 1)
        if is_weak:
            weaknesses.append({
                "metric":         key,
                "label":          label,
                "club_val":       club_val,
                "median_val":     median_val,
                "gap_pct":        gap_pct,
                "interpretation": interpretation,
                "inverse":        inverse,
            })

    return sorted(weaknesses, key=lambda x: x["gap_pct"], reverse=True)


# Metrics that a given position can realistically address.
# Weaknesses NOT in this set are excluded from the diagnosis for that position.
_POSITION_WEAKNESS_RELEVANCE: Dict[str, set] = {
    'Central Defender': {
        'avg_def_duel_win_pct', 'avg_aerial_win_pct',
        'avg_goals_conceded',   'avg_possession', 'avg_pass_acc_pct',
    },
    'Full Back': {
        'avg_def_duel_win_pct', 'avg_possession', 'avg_pass_acc_pct',
    },
    'Central Mid': {
        'avg_possession', 'avg_pass_acc_pct', 'avg_def_duel_win_pct',
    },
    'Att Mid': {
        'avg_goals_scored', 'avg_possession', 'avg_pass_acc_pct',
    },
    'Wide Mid': {
        'avg_goals_scored', 'avg_possession', 'avg_pass_acc_pct',
    },
    'Center Forward': {
        'avg_goals_scored', 'avg_aerial_win_pct',
    },
    'Goalkeeper': {
        'avg_goals_conceded', 'avg_possession', 'avg_pass_acc_pct',
    },
}


def filter_weaknesses_by_position(
    weaknesses: list[dict],
    pos_key: str | None,
) -> list[dict]:
    """
    Remove weaknesses that the given position cannot realistically address.

    A full-back cannot fix a goals-scored deficit; a centre-forward cannot fix
    a defensive-duel weakness. If pos_key is None or unknown, all weaknesses
    are returned unchanged.
    """
    if not pos_key or pos_key not in _POSITION_WEAKNESS_RELEVANCE:
        return weaknesses
    relevant = _POSITION_WEAKNESS_RELEVANCE[pos_key]
    return [w for w in weaknesses if w["metric"] in relevant]


def suggest_club_need(
    weaknesses: list[dict],
    club_profile: dict,
) -> str:
    """
    Generate a plain-English 'what they need' suggestion from weakness data
    and club tactical profile. Returns an editable pre-fill string.
    """
    parts: list[str] = []

    for w in weaknesses[:3]:
        m = w["metric"]
        if "def_duel" in m:
            parts.append("dominant 1v1 defender")
        elif "aerial" in m:
            parts.append("aerial presence and strength in the air")
        elif "goals_conceded" in m:
            parts.append("defensive solidity and organisation")
        elif "possession" in m:
            parts.append("composed ball-carrier under pressure")
        elif "pass_acc" in m:
            parts.append("reliable passer who retains possession")
        elif "goals_scored" in m:
            parts.append("goal threat and attacking output")

    press = club_profile.get("press_intensity", "")
    if press == "High press":
        parts.append("high work rate and press triggers")
    elif press == "Low block":
        parts.append("defensive discipline and positional awareness")

    style = club_profile.get("play_style", "")
    if style == "Direct":
        parts.append("can hold up play and compete for long balls")
    elif style == "Possession-based":
        parts.append("comfortable on the ball in tight spaces")

    # Deduplicate preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for p in parts:
        if p not in seen:
            seen.add(p)
            unique.append(p)

    return ", ".join(unique)


# ── Squad comparison ──────────────────────────────────────────────────────────

# Columns to display in squad comparison — named as they appear in Wyscout
# position files. Subset chosen to work across all positions.
_SQUAD_DISPLAY_COLS = [
    ("Player",                  "Player"),
    ("Minutes played",          "Mins"),
    ("Passes per 90",           "Pass p90"),
    ("Accurate passes, %",      "Pass%"),
    ("Duels per 90",            "Duels p90"),
    ("Duels won, %",            "Duel%"),
    ("Aerial duels per 90",     "Aerial p90"),
    ("Aerial duels won, %",     "Aerial%"),
    ("Defensive duels per 90",  "Def duel p90"),
    ("Defensive duels won, %",  "Def%"),
    ("Interceptions per 90",    "Int p90"),
]


def get_club_squad_at_position(
    club_name: str,
    pos_key: str,
    ws_files: dict[str, dict[str, str]],
    min_mins: int = 450,
) -> pd.DataFrame | None:
    """
    Find the target club's players at the given position in Wyscout league files.

    Tries Championship, League One, League Two in order. Returns a filtered
    DataFrame of the club's players at that position with display columns,
    or None if the club is not found in any file.

    Parameters
    ----------
    club_name : str
        Club name as it appears in the Wyscout position file's 'Team' column.
    pos_key : str
        Position key (e.g. 'Central Defender') matching the WS_FILES dict.
    ws_files : dict
        The WS_FILES dict from app.py / pages.
    min_mins : int
        Minimum minutes to include a player in the squad view.
    """
    for league in ["Championship", "League One", "League Two"]:
        path = ws_files.get(league, {}).get(pos_key)
        if not path or not os.path.exists(path):
            continue
        try:
            df = pd.read_excel(path)
        except Exception:
            continue
        if "Team" not in df.columns or "Minutes played" not in df.columns:
            continue
        mask = df["Team"].str.strip().str.lower() == club_name.strip().lower()
        squad = df[mask & (df["Minutes played"] >= min_mins)].copy()
        if not squad.empty:
            # Keep only available display columns
            keep = [src for src, _ in _SQUAD_DISPLAY_COLS if src in squad.columns]
            return squad[keep].reset_index(drop=True)
    return None


# ── Style fit score ───────────────────────────────────────────────────────────

def get_style_fit_score(
    season: dict,
    phys: Optional[dict],
    club_profile: dict,
    ws_peers: dict,
    phys_peers: dict,
    league_medians: dict,
) -> dict:
    """
    Compute a 0-100 style fit score between a player and a club across four
    dimensions. Returns a dict with keys:
        overall, press_fit, buildup_fit, gap_fill, physical_fit
    Any dimension lacking sufficient data returns None for that key.

    Scoring logic:
    - press_fit:   player's defensive intensity vs club's pressing demand
    - buildup_fit: player's passing profile vs club's build-up style
    - gap_fill:    how directly the player addresses the club's statistical weaknesses
    - physical_fit: player's physical output vs peers (proxy for club fit)
    """
    from src.metrics import percentile_rank  # avoid circular at module level

    def pr(key: str, val=None, peers: Optional[dict] = None) -> Optional[float]:
        p = peers if peers is not None else ws_peers
        v = val if val is not None else season.get(key)
        if not p or key not in p or v is None:
            return None
        return percentile_rank(v, p[key])

    scores: dict[str, Optional[float]] = {}

    # ── 1. Press fit ──────────────────────────────────────────────────────────
    ppda = club_profile.get("avg_ppda")
    if ppda is not None and ws_peers:
        if ppda < 8:   # High press — needs energy, recoveries, pressing triggers
            pcts = [pr("interceptions_p90"), pr("recoveries_p90")]
        elif ppda < 12:  # Moderate
            pcts = [pr("def_duel_win"), pr("interceptions_p90")]
        else:            # Low block — needs positional defensive solidity
            pcts = [pr("def_duel_win"), pr("def_duels_p90")]
        valid = [p for p in pcts if p is not None]
        scores["press_fit"] = round(sum(valid) / len(valid)) if valid else None

    # ── 2. Build-up fit ───────────────────────────────────────────────────────
    possession = club_profile.get("avg_possession")
    long_pass  = club_profile.get("avg_long_pass_pct")
    if possession is not None and ws_peers:
        if possession > 55:             # Possession-based — passing quality critical
            pcts = [pr("pass_acc"), pr("passes_p90")]
        elif long_pass and long_pass > 35:  # Direct — aerial & long ball ability
            pcts = [pr("long_passes_p90"), pr("aerial_p90")]
        else:                           # Balanced
            pcts = [pr("pass_acc"), pr("prog_runs_p90")]
        valid = [p for p in pcts if p is not None]
        scores["buildup_fit"] = round(sum(valid) / len(valid)) if valid else None

    # ── 3. Gap fill ───────────────────────────────────────────────────────────
    # How well does the player address this club's specific statistical weaknesses?
    gap_pcts: list[float] = []
    club_def    = club_profile.get("avg_def_duel_win_pct", 100)
    club_aerial = club_profile.get("avg_aerial_win_pct", 100)
    club_conc   = club_profile.get("avg_goals_conceded", 0)
    med_def     = league_medians.get("avg_def_duel_win_pct", 50)
    med_aerial  = league_medians.get("avg_aerial_win_pct", 50)
    med_conc    = league_medians.get("avg_goals_conceded", 1.5)

    if club_def < med_def and ws_peers:
        p = pr("def_duel_win")
        if p is not None: gap_pcts.append(p)
    if club_aerial < med_aerial and ws_peers:
        p = pr("aerial_win")
        if p is not None: gap_pcts.append(p)
    if club_conc > med_conc and ws_peers:
        p = pr("def_duels_p90")
        if p is not None: gap_pcts.append(p)
    scores["gap_fill"] = round(sum(gap_pcts) / len(gap_pcts)) if gap_pcts else None

    # ── 4. Physical fit ───────────────────────────────────────────────────────
    if phys and phys_peers:
        phys_pcts = [pr(k, phys.get(k), phys_peers)
                     for k in ("total_dist_p90", "hsr_dist_p90")]
        valid = [p for p in phys_pcts if p is not None]
        scores["physical_fit"] = round(sum(valid) / len(valid)) if valid else None

    # ── Overall ───────────────────────────────────────────────────────────────
    valid_scores = [v for v in scores.values() if v is not None]
    scores["overall"] = round(sum(valid_scores) / len(valid_scores)) if valid_scores else None

    return scores
