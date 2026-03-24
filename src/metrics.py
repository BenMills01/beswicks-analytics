"""
src/metrics.py
Beswicks Sports Analytics — shared calculation module.

Single source of truth for all metric calculations. No Streamlit imports;
importable by both app.py and generate_report.py.
"""

from __future__ import annotations

import os
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

# ── Constants ─────────────────────────────────────────────────────────────────

MIN_PEER_N = 5                 # minimum peer group size before showing percentiles
MIN_MATCH_MINS = 20            # minimum minutes per match to include in match-level data
MIN_SEASON_MINS_PHYSICAL = 450 # minimum season minutes for physical peer inclusion
CONF_THRESHOLD = 0.85          # minimum fuzzy match score to accept without override

METRIC_DESC: Dict[str, str] = {
    "Total dist p90":              "Total metres covered per 90 minutes. Measures overall work rate and engine.",
    "HSR dist p90":                "High-speed running distance (above ~20km/h) per 90 mins.",
    "Sprint dist p90":             "Distance covered at sprint pace (above ~25km/h) per 90 mins.",
    "PSV99 avg":                   "Peak Sprint Velocity — average of the player's top speed across matches.",
    "COD count p90":               "Changes of direction per 90 mins. Reflects agility and positional movement.",
    "Goals p90":                   "Goals scored per 90 minutes played.",
    "Assists p90":                 "Assists (final pass before a goal) per 90 minutes.",
    "xG p90":                      "Expected goals per 90 mins.",
    "xA p90":                      "Expected assists per 90 mins.",
    "Shot asts p90":               "Passes that directly led to a shot, per 90 mins.",
    "Touches in box":              "Times the player received the ball inside the opposition penalty area per 90 mins.",
    "Dribbles p90":                "Dribble attempts per 90 mins.",
    "Prog runs p90":               "Ball carries that advance the team significantly up the pitch, per 90 mins.",
    "Passes p90":                  "Total pass attempts per 90 mins.",
    "Long pass p90":               "Long pass attempts per 90 mins.",
    "Crosses p90":                 "Cross attempts per 90 mins from wide areas.",
    "Duels p90":                   "Total physical contests per 90 mins.",
    "Aerial p90":                  "Aerial duels contested per 90 mins.",
    "Def duels p90":               "Defensive duel attempts per 90 mins.",
    "Interceptions":               "Times the player intercepts an opposition pass per 90 mins.",
    "Recoveries p90":              "Times the player wins possession from a loose ball, per 90 mins.",
    "Losses p90":                  "Times the player loses the ball per 90 mins. Lower is better.",
    "Pass acc %":                  "Percentage of passes that reach a teammate.",
    "Duel win %":                  "Percentage of all duels won.",
    "Aerial win %":                "Percentage of aerial duels won.",
    "Def duel win %":              "Percentage of defensive duels won.",
    "Dribble success %":           "Percentage of dribble attempts completed successfully.",
    "Pressures received p90":      "Times the player was pressed by an opponent per 90 mins.",
    "Ball retention under press":  "Percentage of times the player kept the ball when under pressure.",
    "Pass completion under press": "Pass accuracy when under immediate pressure.",
    "Runs per match":              "Off-ball runs made per match.",
    "Dangerous runs":              "Runs made into high-threat areas per match.",
    "Runs targeted":               "Times teammates attempted to play the ball to the player's runs.",
    "Runs received":               "Times the player actually received the ball after making a run.",
}


# ── Core helpers ──────────────────────────────────────────────────────────────

def p90(value: float, minutes: float) -> float:
    """Return value expressed per 90 minutes. Returns 0.0 if minutes is zero."""
    if minutes == 0:
        return 0.0
    return round((value / minutes) * 90, 2)


def pct(num: float, denom: float) -> Optional[float]:
    """Return (num / denom) * 100, rounded to 1 dp. Returns None if denom is zero or None."""
    if denom is None or denom == 0:
        return None
    if num is None:
        return None
    return round((num / denom) * 100, 1)


def percentile_rank(
    value: float,
    series: pd.Series,
    inverse: bool = False,
) -> Optional[float]:
    """
    Return the percentile rank of *value* within *series*.

    Uses scipy percentileofscore with kind='rank'. Returns None if the value is
    missing or the cleaned series has fewer than MIN_PEER_N entries.
    Set inverse=True for metrics where lower is better (e.g. losses).
    """
    clean = series.dropna()
    if len(clean) < MIN_PEER_N or pd.isna(value) or value is None:
        return None
    rank = scipy_stats.percentileofscore(clean, value, kind='rank')
    return round(100 - rank if inverse else rank, 1)


def ordinal(n: int) -> str:
    """Convert an integer to its ordinal string (1 → '1st', 2 → '2nd', etc.)."""
    n = int(n)
    s = str(n)
    if s.endswith(('11', '12', '13')):
        return f"{n}th"
    if s.endswith('1'):
        return f"{n}st"
    if s.endswith('2'):
        return f"{n}nd"
    if s.endswith('3'):
        return f"{n}rd"
    return f"{n}th"


def pct_colour(pct_val: Optional[float]) -> str:
    """
    Return a hex colour string based on percentile bucket.

    >= 80  → green  (#4ade80)
    >= 55  → light green (#86efac)
    >= 35  → yellow (#facc15)
    <  35  → red    (#f87171)
    None   → grey   (#666)
    """
    if pct_val is None:
        return '#666'
    if pct_val >= 80:
        return '#4ade80'
    if pct_val >= 55:
        return '#86efac'
    if pct_val >= 35:
        return '#facc15'
    return '#f87171'


def rolling_avg(series: pd.Series, window: int = 5) -> pd.Series:
    """Return a rolling mean with min_periods=3."""
    return pd.Series(series).rolling(window=window, min_periods=3).mean()


def mins_to_opacity(
    minutes_series: pd.Series,
    lo: float = 0.3,
    hi: float = 1.0,
    min_mins: int = 20,
    max_mins: int = 90,
) -> list:
    """
    Map a series of minutes values to opacity floats in [lo, hi].

    Values below min_mins are clamped to lo; values above max_mins are clamped to hi.
    """
    clipped = pd.Series(minutes_series).clip(lower=min_mins, upper=max_mins)
    normed  = (clipped - min_mins) / (max_mins - min_mins)
    return (lo + normed * (hi - lo)).tolist()


def rgba(hex_col: str, opacity: float) -> str:
    """Convert a hex colour string and opacity float to an rgba() CSS string."""
    h = hex_col.lstrip('#')
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{opacity:.2f})"


def colour_list(hex_col: str, opacities: list) -> list:
    """Return a list of rgba strings for a given hex colour and list of opacities."""
    return [rgba(hex_col, o) for o in opacities]


# ── Match label parsers ───────────────────────────────────────────────────────

def parse_wyscout_label(match_str: str, team_name: str) -> str:
    """
    Parse a Wyscout match string to 'Opponent (H/A)' format.

    Example: 'Wycombe Wanderers - Wigan Athletic 2:0' → 'Wigan Athletic (H)'
    """
    try:
        parts = str(match_str).split(' - ', 1)
        if len(parts) != 2:
            return str(match_str)
        home = parts[0].strip()
        away_score = parts[1].strip()
        tokens = away_score.rsplit(' ', 1)
        away = tokens[0].strip() if len(tokens) == 2 and ':' in tokens[1] else away_score
        is_home = (home == team_name)
        opponent = away if is_home else home
        return f"{opponent} ({'H' if is_home else 'A'})"
    except Exception:
        return str(match_str)


def parse_physical_label(match_name: str, team_name: str) -> str:
    """
    Parse a SkillCorner match name to 'Opponent (H/A)' format.

    Example: 'Wycombe Wanderers v Stockport County FC' → 'Stockport (H)'
    Strips common suffixes (FC, AFC, United, etc.) from the opponent name.
    """
    try:
        parts = str(match_name).split(' v ', 1)
        if len(parts) != 2:
            return str(match_name)
        home, away = parts[0].strip(), parts[1].strip()
        is_home = (home == team_name)
        opponent = away if is_home else home
        for sfx in [' FC', ' AFC', ' United', ' City', ' Town', ' County',
                    ' Wanderers', ' Rovers', ' Athletic']:
            opponent = opponent.replace(sfx, '')
        return f"{opponent.strip()} ({'H' if is_home else 'A'})"
    except Exception:
        return str(match_name)


# ── Season aggregation ────────────────────────────────────────────────────────

def get_season_totals(ws: pd.DataFrame) -> Dict[str, object]:
    """
    Extract season-level totals and per-90 rates from a Wyscout match DataFrame.

    Columns are accessed by both name and integer index. The iloc positions
    below must not be changed without updating every reference in app.py and
    generate_report.py.

    Parameters
    ----------
    ws : pd.DataFrame
        Wyscout sheet filtered to qualifying appearances (≥20 mins).

    Returns
    -------
    dict
        Season metrics keyed by metric name.
    """
    mins: float = ws['Minutes played'].sum()
    s = ws.sum(numeric_only=True)

    return {
        'mins':    mins,
        'matches': len(ws),
        'goals_raw':   int(s['Goals']),
        'assists_raw': int(s['Assists']),
        'yellow': int(ws.iloc[:, 39].sum()),  # yellow cards
        'red':    int(ws.iloc[:, 40].sum()),  # red cards

        # Attacking
        'goals_p90':       p90(s['Goals'],  mins),
        'assists_p90':     p90(s['Assists'], mins),
        'xg_p90':          p90(s['xG'],     mins),
        'xa_p90':          p90(s['xA'],     mins),
        'shots_p90':       p90(s['Shots'],  mins),
        'shot_asts_p90':   p90(ws['Shot assists'].sum(),           mins),
        'touches_box_p90': p90(ws['Touches in penalty area'].sum(), mins),
        'dribbles_p90':    p90(s['Dribbles'], mins),
        'drib_pct':        pct(ws.iloc[:, 19].sum(), s['Dribbles']),  # successful dribbles
        'prog_runs_p90':   p90(ws['Progressive runs'].sum(), mins),
        'ptf3_p90':        p90(ws['Passes to final third'].sum(), mins),

        # Passing
        'passes_p90':      p90(s['Passes'],      mins),
        'pass_acc':        pct(ws.iloc[:, 13].sum(), s['Passes']),       # accurate passes
        'long_passes_p90': p90(s['Long passes'], mins),
        'lp_acc':          pct(ws.iloc[:, 15].sum(), s['Long passes']),  # accurate long passes
        'crosses_p90':     p90(s['Crosses'], mins),

        # Duels
        'duels_p90':       p90(s['Duels'], mins),
        'duel_win':        pct(ws.iloc[:, 21].sum(), s['Duels']),         # duels won
        'aerial_p90':      p90(s['Aerial duels'], mins),
        'aerial_win':      pct(ws.iloc[:, 23].sum(), s['Aerial duels']), # aerial duels won
        'def_duels_p90':   p90(ws.iloc[:, 31].sum(), mins),              # defensive duels
        'def_duel_win':    pct(ws.iloc[:, 32].sum(), ws.iloc[:, 31].sum()),  # def duels won

        # Defensive
        'interceptions_p90': p90(s['Interceptions'], mins),
        'recoveries_p90':    p90(s['Recoveries'], mins),  # raw recoveries from master
        'rec_opp_p90':       p90(ws['opp. half'].sum(), mins),
        'clearances_p90':    p90(s['Clearances'], mins),
        'losses_p90':        p90(s['Losses'],     mins),
        'losses_oh_p90':     p90(ws['own half'].sum(), mins),
        'fouls_p90':         p90(ws['Fouls'].sum(), mins),
    }


def get_physical_totals(ph: pd.DataFrame) -> Dict[str, float]:
    """
    Extract season-level physical totals and per-90 rates from the Physical sheet.

    Parameters
    ----------
    ph : pd.DataFrame
        Physical sheet filtered to qualifying appearances (≥20 mins).

    Returns
    -------
    dict
        Physical metrics keyed by metric name.
    """
    mins: float = ph['minutes_full_all'].sum()
    s = ph.sum(numeric_only=True)
    return {
        'total_dist_p90':   p90(s['total_distance_full_all'],  mins),
        'hsr_dist_p90':     p90(s['hsr_distance_full_all'],    mins),
        'hsr_count_p90':    p90(s['hsr_count_full_all'],       mins),
        'sprint_dist_p90':  p90(s['sprint_distance_full_all'], mins),
        'sprint_count_p90': p90(s['sprint_count_full_all'],    mins),
        'psv99_avg':        round(ph['psv99'].mean(), 2),
        'psv99_max':        round(ph['psv99'].max(),  2),
        'cod_p90':          p90(s['cod_count_full_all'],        mins),
        'hi_accel_p90':     p90(s['highaccel_count_full_all'], mins),
    }


# ── Match log ─────────────────────────────────────────────────────────────────

def build_match_log(ws: pd.DataFrame, team_name: str) -> pd.DataFrame:
    """
    Build a per-match log DataFrame from the Wyscout sheet.

    Uses both named column access and integer iloc positions. The iloc positions
    must not be reordered in source files without updating all references here
    and in app.py / generate_report.py.

    Parameters
    ----------
    ws : pd.DataFrame
        Wyscout sheet filtered to qualifying appearances.
    team_name : str
        The player's team name, used to derive H/A from the match string.

    Returns
    -------
    pd.DataFrame
        One row per match with derived columns.
    """
    rows = []

    def safe_int(v: object) -> int:
        try:
            return int(v) if pd.notna(v) else 0
        except Exception:
            return 0

    def safe_round(v: object, d: int = 2) -> float:
        try:
            return round(float(v), d) if pd.notna(v) else 0.0
        except Exception:
            return 0.0

    def sp(n: object, d: object) -> str:
        try:
            return (
                f"{int(round(float(n) / float(d) * 100))}%"
                if pd.notna(n) and pd.notna(d) and float(d) > 0
                else "-"
            )
        except Exception:
            return "-"

    for _, r in ws.iterrows():
        rows.append({
            'Match':   parse_wyscout_label(r['Match'], team_name),
            'Date':    pd.to_datetime(r['Date']).strftime('%d %b') if pd.notna(r['Date']) else '',
            'Pos':     str(r['Position']),
            'Min':     safe_int(r['Minutes played']),
            'G':       safe_int(r['Goals']),
            'A':       safe_int(r['Assists']),
            'xG':      safe_round(r['xG']),
            'xA':      safe_round(r['xA']),
            'ShAst':   safe_int(r['Shot assists']),
            'TouBox':  safe_int(r['Touches in penalty area']),
            'Drb':     safe_int(r['Dribbles']),
            'Drb%':    sp(r.iloc[19], r['Dribbles']),     # successful dribbles / dribbles
            'Pass':    safe_int(r['Passes']),
            'Pass%':   sp(r.iloc[13], r['Passes']),        # accurate passes / passes
            'Cross':   safe_int(r['Crosses']),
            'PTF3':    safe_int(r['Passes to final third']),
            'Duels':   safe_int(r['Duels']),
            'Duel%':   sp(r.iloc[21], r['Duels']),         # duels won / duels
            'AerDuel': safe_int(r['Aerial duels']),
            'Aer%':    sp(r.iloc[23], r['Aerial duels']),  # aerial duels won / aerial duels
            'DefDuel': safe_int(r.iloc[31]),                # defensive duels
            'DefD%':   sp(r.iloc[32], r.iloc[31]),          # defensive duels won / defensive duels
            'Int':     safe_int(r['Interceptions']),
            'Rec':     safe_int(r['Recoveries']),
            'Clr':     safe_int(r['Clearances']),
            'Loss':    safe_int(r['Losses']),
            'LossOH':  safe_int(r['own half']),
            'Foul':    safe_int(r['Fouls']),
        })
    return pd.DataFrame(rows)


# ── Peer group builders ───────────────────────────────────────────────────────

def build_physical_peers(
    phys_csv: Optional[pd.DataFrame],
    position_group: Optional[str],
    min_mins: int,
    league_filter: str,
) -> Tuple[Dict[str, pd.Series], int]:
    """
    Build physical peer group series from the SkillCorner physical CSV.

    Parameters
    ----------
    phys_csv : pd.DataFrame or None
        The full physical CSV loaded from disk.
    position_group : str or None
        SkillCorner position group to filter by (e.g. 'Central Defender').
    min_mins : int
        Minimum season minutes required for a player to be included as a peer.
    league_filter : str
        'Both', 'Championship', 'League One', or 'League Two'.

    Returns
    -------
    (dict of pd.Series, int)
        Peer series keyed by metric name, and the number of peers found.
        Returns ({}, 0) if there are fewer than MIN_PEER_N qualifying peers.
    """
    if phys_csv is None or not position_group:
        return {}, 0

    df = phys_csv[phys_csv['quality_check'] == True].copy()

    if isinstance(league_filter, list):
        _selected = league_filter
    elif league_filter == 'Both':
        _selected = ['League One', 'League Two']
    elif league_filter == 'All':
        _selected = ['Championship', 'League One', 'League Two']
    elif league_filter in ('Championship', 'League One', 'League Two'):
        _selected = [league_filter]
    else:
        _selected = []

    if _selected:
        _pattern = '|'.join(_selected)
        df = df[df['competition_name'].str.contains(_pattern, na=False)]

    df = df[df['group'] == position_group]

    agg = df.groupby('player_name').agg(
        mins         = ('minutes_played_per_match', 'sum'),
        total_dist   = ('dist_per_match',            'sum'),
        hsr_dist     = ('hsr_dist_per_match',         'sum'),
        sprint_dist  = ('sprint_dist_per_match',      'sum'),
        hsr_count    = ('count_hsr_per_match',         'sum'),
        sprint_count = ('count_sprint_per_match',      'sum'),
        hi_accel     = ('count_high_accel_per_match',  'sum'),
        psv99        = ('top_speed_per_match',         'mean'),
    ).reset_index()

    agg = agg[agg['mins'] >= min_mins]
    if len(agg) < MIN_PEER_N:
        return {}, 0

    def pp90(col: str) -> pd.Series:
        return (agg[col] / agg['mins'] * 90).replace([np.inf, -np.inf], np.nan).dropna()

    out = {
        'total_dist_p90':   pp90('total_dist'),
        'hsr_dist_p90':     pp90('hsr_dist'),
        'sprint_dist_p90':  pp90('sprint_dist'),
        'hsr_count_p90':    pp90('hsr_count'),
        'sprint_count_p90': pp90('sprint_count'),
        'hi_accel_p90':     pp90('hi_accel'),
        'psv99_avg':        agg['psv99'].dropna(),
    }
    return {k: v for k, v in out.items() if len(v) >= MIN_PEER_N}, len(agg)


def build_wyscout_peers(
    pos_key: Optional[str],
    league_filter: str,
    min_mins: int,
    ws_files: Dict[str, Dict[str, str]],
) -> Tuple[Dict[str, pd.Series], int]:
    """
    Build Wyscout peer group series from position-specific files.

    Parameters
    ----------
    pos_key : str or None
        Position key (e.g. 'Central Defender') used to look up the correct file.
    league_filter : str
        'Both', 'Championship', 'League One', or 'League Two'.
    min_mins : int
        Minimum minutes for a player to be included as a peer.
    ws_files : dict
        Nested dict of {league: {pos_key: file_path}} — passed explicitly so
        this function has no dependency on global state.

    Returns
    -------
    (dict of pd.Series, int)
        Peer series keyed by metric name, and the number of peers found.
        Returns ({}, 0) if fewer than MIN_PEER_N qualifying peers exist.
    """
    if not pos_key:
        return {}, 0

    if isinstance(league_filter, list):
        leagues = league_filter
    elif league_filter == 'Both':
        leagues = ['League One', 'League Two']
    elif league_filter == 'All':
        leagues = ['Championship', 'League One', 'League Two']
    else:
        leagues = [league_filter]
    dfs = []
    for league in leagues:
        path = ws_files.get(league, {}).get(pos_key)
        if path and os.path.exists(path):
            df = pd.read_excel(path)
            df['_league'] = league
            dfs.append(df)

    if not dfs:
        return {}, 0

    df = pd.concat(dfs, ignore_index=True)
    df = df[pd.to_numeric(df['Minutes played'], errors='coerce') >= min_mins]
    if len(df) < MIN_PEER_N:
        return {}, 0

    def ser(col: str) -> Optional[pd.Series]:
        s = pd.to_numeric(df[col], errors='coerce').dropna()
        return s if len(s) >= MIN_PEER_N else None

    out = {
        'goals_p90':         ser('Goals per 90'),
        'assists_p90':       ser('Assists per 90'),
        'xg_p90':            ser('xG per 90'),
        'xa_p90':            ser('xA per 90'),
        'shot_asts_p90':     ser('Shot assists per 90'),
        'touches_box_p90':   ser('Touches in box per 90'),
        'dribbles_p90':      ser('Dribbles per 90'),
        'drib_pct':          ser('Successful dribbles, %'),
        'prog_runs_p90':     ser('Progressive runs per 90'),
        'passes_p90':        ser('Passes per 90'),
        'pass_acc':          ser('Accurate passes, %'),
        'long_passes_p90':   ser('Long passes per 90'),
        'crosses_p90':       ser('Crosses per 90'),
        'duels_p90':         ser('Duels per 90'),
        'duel_win':          ser('Duels won, %'),
        'aerial_p90':        ser('Aerial duels per 90'),
        'aerial_win':        ser('Aerial duels won, %'),
        'def_duels_p90':     ser('Defensive duels per 90'),
        'def_duel_win':      ser('Defensive duels won, %'),
        'interceptions_p90': ser('Interceptions per 90'),
        # Wyscout composite: won def duels + interceptions + recoveries
        'recoveries_p90':    ser('Successful defensive actions per 90'),
    }
    return {k: v for k, v in out.items() if v is not None}, len(df)


def build_physical_season_averages(phys_csv: Optional[pd.DataFrame]) -> Optional[pd.DataFrame]:
    """
    Aggregate the physical CSV to per-player season averages.

    Only includes players with at least MIN_SEASON_MINS_PHYSICAL minutes.
    Used for comparison lookups across the squad.

    Parameters
    ----------
    phys_csv : pd.DataFrame or None
        Full SkillCorner physical CSV.

    Returns
    -------
    pd.DataFrame or None
        One row per player with per-90 physical columns, or None if input is None.
    """
    if phys_csv is None:
        return None

    df = phys_csv[phys_csv['quality_check'] == True].copy()
    agg = df.groupby(['player_name', 'team_name', 'competition_name']).agg(
        mins         = ('minutes_played_per_match', 'sum'),
        total_dist   = ('dist_per_match',            'sum'),
        hsr_dist     = ('hsr_dist_per_match',         'sum'),
        sprint_dist  = ('sprint_dist_per_match',      'sum'),
        hsr_count    = ('count_hsr_per_match',         'sum'),
        sprint_count = ('count_sprint_per_match',      'sum'),
        hi_accel     = ('count_high_accel_per_match',  'sum'),
        psv99        = ('top_speed_per_match',         'mean'),
    ).reset_index()

    agg = agg[agg['mins'] >= MIN_SEASON_MINS_PHYSICAL].copy()

    agg['total_dist_p90']   = agg['total_dist']   / agg['mins'] * 90
    agg['hsr_dist_p90']     = agg['hsr_dist']     / agg['mins'] * 90
    agg['sprint_dist_p90']  = agg['sprint_dist']  / agg['mins'] * 90
    agg['hsr_count_p90']    = agg['hsr_count']    / agg['mins'] * 90
    agg['sprint_count_p90'] = agg['sprint_count'] / agg['mins'] * 90
    agg['hi_accel_p90']     = agg['hi_accel']     / agg['mins'] * 90
    agg['psv99_avg']        = agg['psv99']
    return agg


# ── Comparable players ────────────────────────────────────────────────────────

# Mapping: Wyscout peer file column → client season_totals key
_COMPARABLE_FEATURE_MAP: Dict[str, str] = {
    'Goals per 90':                       'goals_p90',
    'Assists per 90':                     'assists_p90',
    'xG per 90':                          'xg_p90',
    'xA per 90':                          'xa_p90',
    'Passes per 90':                      'passes_p90',
    'Accurate passes, %':                 'pass_acc',
    'Dribbles per 90':                    'dribbles_p90',
    'Progressive runs per 90':            'prog_runs_p90',
    'Duels per 90':                       'duels_p90',
    'Duels won, %':                       'duel_win',
    'Aerial duels per 90':                'aerial_p90',
    'Aerial duels won, %':                'aerial_win',
    'Defensive duels per 90':             'def_duels_p90',
    'Defensive duels won, %':             'def_duel_win',
    'Interceptions per 90':               'interceptions_p90',
    'Successful defensive actions per 90':'recoveries_p90',
}

# Columns shown in the output table (peer file names → display label)
_COMPARABLE_DISPLAY_COLS: Dict[str, str] = {
    'Passes per 90':         'Pass p90',
    'Accurate passes, %':    'Pass%',
    'Duels won, %':          'Duel%',
    'Aerial duels per 90':   'Aerial p90',
    'Aerial duels won, %':   'Aerial%',
    'Interceptions per 90':  'Int p90',
    'Goals per 90':          'Goals p90',
}


def find_comparable_players(
    client_totals: Dict[str, float],
    pos_key: Optional[str],
    league_filter,
    min_mins: int,
    ws_files: Dict[str, Dict[str, str]],
    top_n: int = 8,
    client_name: str = "",
) -> pd.DataFrame:
    """
    Find the most statistically similar players to a client from the Wyscout peer group.

    Uses z-score normalised Euclidean distance across a core set of per-90 metrics.
    Only features where both the peer file column and the client's totals value
    are available are included in the distance calculation.

    Parameters
    ----------
    client_totals : dict
        Season totals dict from get_season_totals() (or season_combined).
    pos_key : str or None
        Position key, e.g. 'Central Defender'.
    league_filter : str or list
        League selection — same format as build_wyscout_peers().
    min_mins : int
        Minimum season minutes for a peer player to be included.
    ws_files : dict
        Nested {league: {pos_key: path}} dict.
    top_n : int
        Number of most similar players to return.
    client_name : str
        Client's display name — excluded from the results.

    Returns
    -------
    pd.DataFrame
        Columns: Player, Team, League, Minutes, Similarity, + key display cols.
        Empty DataFrame if not enough data.
    """
    if not pos_key:
        return pd.DataFrame()

    if isinstance(league_filter, list):
        leagues = league_filter
    elif league_filter == 'Both':
        leagues = ['League One', 'League Two']
    elif league_filter == 'All':
        leagues = ['Championship', 'League One', 'League Two']
    else:
        leagues = [league_filter]

    dfs = []
    for league in leagues:
        path = ws_files.get(league, {}).get(pos_key)
        if path and os.path.exists(path):
            df = pd.read_excel(path)
            df['_league'] = league
            dfs.append(df)

    if not dfs:
        return pd.DataFrame()

    df = pd.concat(dfs, ignore_index=True)
    df = df[pd.to_numeric(df['Minutes played'], errors='coerce') >= min_mins].copy()

    # Exclude the client player
    if client_name:
        # Try short name match (peer files use Wyscout short names)
        client_short = client_name.split()[-1]  # last word as rough short name
        df = df[~df['Player'].str.lower().str.contains(client_short.lower(), na=False)]

    if len(df) < MIN_PEER_N:
        return pd.DataFrame()

    # Filter feature map to columns present in the file and with valid client values
    use_map = {
        peer_col: client_key
        for peer_col, client_key in _COMPARABLE_FEATURE_MAP.items()
        if peer_col in df.columns
        and client_totals.get(client_key) is not None
        and not pd.isna(client_totals.get(client_key, np.nan))
    }

    if len(use_map) < 4:
        return pd.DataFrame()

    feat_cols = list(use_map.keys())
    peer_feats = df[feat_cols].apply(pd.to_numeric, errors='coerce')

    # Drop peers with too many missing features
    peer_feats = peer_feats.dropna(thresh=max(4, len(feat_cols) // 2))
    df = df.loc[peer_feats.index]

    client_vec = np.array([client_totals[use_map[c]] for c in feat_cols], dtype=float)

    # Fill remaining NaNs with column mean before normalising
    col_means = peer_feats.mean()
    peer_feats = peer_feats.fillna(col_means)

    # Z-score normalise using peer distribution
    col_stds = peer_feats.std().replace(0, 1)
    peer_norm   = (peer_feats - col_means) / col_stds
    client_norm = (client_vec - col_means.values) / col_stds.values

    distances = np.sqrt(((peer_norm.values - client_norm) ** 2).sum(axis=1))

    df = df.copy()
    df['_dist']    = distances
    df['_mins']    = pd.to_numeric(df['Minutes played'], errors='coerce')
    df = df.dropna(subset=['_dist']).sort_values('_dist')

    max_d = df['_dist'].max()
    df['Similarity'] = ((1 - df['_dist'] / max_d) * 100).clip(0, 100).round(1) if max_d > 0 else 100.0

    # Build output table
    display_cols = {c: lbl for c, lbl in _COMPARABLE_DISPLAY_COLS.items() if c in df.columns}
    keep = ['Player', 'Team', '_league', '_mins', 'Similarity'] + list(display_cols.keys())
    keep = [c for c in keep if c in df.columns]

    result = df[keep].head(top_n).copy()
    result = result.rename(columns={'_league': 'League', '_mins': 'Minutes'})
    result = result.rename(columns=display_cols)
    result['Minutes'] = result['Minutes'].astype(int)

    return result
