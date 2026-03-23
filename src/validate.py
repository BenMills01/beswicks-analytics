"""
src/validate.py
Beswicks Sports Analytics — startup data validation module.

Validates player master files, league peer files, and the SkillCorner↔Wyscout
matching table on startup. Core functions are Streamlit-free; only
display_validation_results() imports streamlit.
"""

from __future__ import annotations

import os
import glob
from typing import Any, Dict, List, Optional

import pandas as pd

# ── Constants matching CLAUDE.md & metrics.py ────────────────────────────────

_REQUIRED_SHEETS = ['Wyscout', 'Physical', 'Pressing', 'Off_Ball_Runs', 'Match_by_Match']

_WYSCOUT_REQUIRED_COLS = [
    'Minutes played', 'Date', 'Match', 'Competition', 'Position',
    'Goals', 'Assists', 'xG', 'xA', 'Shots',
    'Passes', 'Long passes', 'Crosses', 'Dribbles', 'Aerial duels', 'Duels',
    'Interceptions', 'Recoveries', 'Clearances', 'Losses',
    'Shot assists', 'Touches in penalty area', 'Progressive runs',
    'Passes to final third', 'Fouls', 'own half', 'opp. half',
]

# iloc position → keywords that should appear (case-insensitive) in the column header.
# Wyscout exports use multi-level headers; pandas deduplicates repeated names as
# 'won', 'won.1', 'successful.1' etc. — accepted keywords reflect both the full
# column name and the deduplicated short form that actually appears in the header row.
_ILOC_CHECKS: Dict[int, List[str]] = {
    13: ['pass', 'accurate'],            # accurate passes
    19: ['dribble', 'successful'],       # successful dribbles (may appear as 'successful.1')
    21: ['duel', 'won'],                 # duels won (may appear as 'won')
    23: ['aerial', 'won'],               # aerial duels won (may appear as 'won.1')
    31: ['def', 'defensive', 'won'],     # defensive duels (may appear as 'won.2' or 'defensive')
    39: ['yellow', 'card'],              # yellow cards
    40: ['red', 'card'],                 # red cards
}

_PHYSICAL_REQUIRED_COLS = [
    'minutes_full_all', 'total_distance_full_all', 'hsr_distance_full_all',
    'sprint_distance_full_all', 'psv99', 'match_date', 'match_name',
    'team_name', 'player_name',
]

_PRESSING_REQUIRED_COLS = [
    'minutes_played_per_match', 'ball_retention_ratio_under_pressure',
    'pass_completion_ratio_under_pressure', 'count_pressures_received_per_match',
]

_OFF_BALL_REQUIRED_COLS = [
    'minutes_played_per_match', 'count_runs_per_match',
    'count_dangerous_runs_per_match', 'count_runs_targeted_per_match',
    'count_runs_received_per_match',
]

_MIN_SEASON_MINS_WARN = 500   # warn if total Wyscout minutes below this
_MIN_MATCHES_WARN     = 5     # warn if fewer than this many qualifying matches


# ── Internal helpers ──────────────────────────────────────────────────────────

def _player_name_from_path(filepath: str) -> str:
    """Derive a human-readable player name from a master file path."""
    base = os.path.basename(filepath)
    return base.replace('_master.xlsx', '').replace('_', ' ')


def _check_columns(
    df: pd.DataFrame,
    required: List[str],
    sheet_name: str,
    errors: List[str],
) -> None:
    """Append an error for each required column missing from df."""
    for col in required:
        if col not in df.columns:
            errors.append(f"{sheet_name} sheet missing column: '{col}'")


# ── 1. Player master file validation ─────────────────────────────────────────

def validate_master_file(filepath: str) -> Dict[str, Any]:
    """
    Validate a single player master XLSX file.

    Checks sheet presence, required columns, iloc positions, row counts,
    and basic data quality. Returns a structured result dict.

    Parameters
    ----------
    filepath : str
        Absolute or relative path to a ``*_master.xlsx`` file.

    Returns
    -------
    dict with keys:
        ``file``     — filepath as supplied
        ``player``   — human-readable player name derived from filename
        ``valid``    — True if zero errors
        ``errors``   — list of strings; each entry will break the app
        ``warnings`` — list of strings; data quality concerns
    """
    player = _player_name_from_path(filepath)
    errors:   List[str] = []
    warnings: List[str] = []

    # ── File existence ────────────────────────────────────────────────────────
    if not os.path.exists(filepath):
        return {
            'file': filepath, 'player': player, 'valid': False,
            'errors': [f"File not found: {filepath}"], 'warnings': [],
        }

    # ── Open workbook ─────────────────────────────────────────────────────────
    try:
        xls = pd.ExcelFile(filepath)
    except Exception as exc:
        return {
            'file': filepath, 'player': player, 'valid': False,
            'errors': [f"Cannot open file: {exc}"], 'warnings': [],
        }

    present_sheets = xls.sheet_names

    # ── Required sheets ───────────────────────────────────────────────────────
    for sheet in _REQUIRED_SHEETS:
        if sheet not in present_sheets:
            errors.append(f"Missing required sheet: '{sheet}'")

    # ── Wyscout sheet ─────────────────────────────────────────────────────────
    if 'Wyscout' in present_sheets:
        try:
            ws = pd.read_excel(xls, sheet_name='Wyscout')

            # Named columns
            _check_columns(ws, _WYSCOUT_REQUIRED_COLS, 'Wyscout', errors)

            # Minimum column count for iloc access (positions 0–40 must exist)
            if ws.shape[1] < 41:
                errors.append(
                    f"Wyscout sheet has only {ws.shape[1]} columns; "
                    f"need >= 41 so iloc positions 13–40 are valid"
                )
            else:
                # Validate iloc positions by keyword match
                cols_lower = [str(c).lower() for c in ws.columns]
                for idx, keywords in _ILOC_CHECKS.items():
                    header = cols_lower[idx] if idx < len(cols_lower) else ''
                    if not any(kw in header for kw in keywords):
                        errors.append(
                            f"Wyscout iloc[{idx}] header is '{ws.columns[idx]}'; "
                            f"expected a column containing {keywords!r}"
                        )

            # Qualifying rows
            try:
                mins_col = pd.to_numeric(ws['Minutes played'], errors='coerce')
                qualifying = int((mins_col >= 20).sum())
                if qualifying == 0:
                    errors.append("Wyscout sheet: no rows with Minutes played >= 20")

                total_mins = mins_col[mins_col >= 20].sum()
                if qualifying > 0 and total_mins < _MIN_SEASON_MINS_WARN:
                    warnings.append(
                        f"Wyscout: only {int(total_mins)} qualifying minutes "
                        f"(threshold for warnings: {_MIN_SEASON_MINS_WARN})"
                    )
                if qualifying < _MIN_MATCHES_WARN:
                    warnings.append(
                        f"Wyscout: only {qualifying} qualifying appearance(s) "
                        f"(fewer than {_MIN_MATCHES_WARN} may affect percentile reliability)"
                    )
            except Exception as exc:
                errors.append(f"Wyscout 'Minutes played' column unreadable: {exc}")

            # Date parseable
            if 'Date' in ws.columns:
                try:
                    pd.to_datetime(ws['Date'], errors='raise')
                except Exception:
                    bad = ws['Date'].dropna().head(3).tolist()
                    warnings.append(
                        f"Wyscout 'Date' column has unparseable values (e.g. {bad})"
                    )

        except Exception as exc:
            errors.append(f"Failed to read Wyscout sheet: {exc}")

    # ── Physical sheet ────────────────────────────────────────────────────────
    if 'Physical' in present_sheets:
        try:
            ph = pd.read_excel(xls, sheet_name='Physical')

            _check_columns(ph, _PHYSICAL_REQUIRED_COLS, 'Physical', errors)

            if 'minutes_full_all' in ph.columns:
                mins_ph = pd.to_numeric(ph['minutes_full_all'], errors='coerce')
                if (mins_ph >= 20).sum() == 0:
                    errors.append("Physical sheet: no rows with minutes_full_all >= 20")
                if len(ph) == 0:
                    warnings.append("Physical sheet: 0 rows total")

        except Exception as exc:
            errors.append(f"Failed to read Physical sheet: {exc}")

    # ── Pressing sheet ────────────────────────────────────────────────────────
    if 'Pressing' in present_sheets:
        try:
            pr = pd.read_excel(xls, sheet_name='Pressing')
            _check_columns(pr, _PRESSING_REQUIRED_COLS, 'Pressing', errors)
            if len(pr) == 0:
                warnings.append("Pressing sheet: 0 rows")
        except Exception as exc:
            errors.append(f"Failed to read Pressing sheet: {exc}")

    # ── Off_Ball_Runs sheet ───────────────────────────────────────────────────
    if 'Off_Ball_Runs' in present_sheets:
        try:
            ob = pd.read_excel(xls, sheet_name='Off_Ball_Runs')
            _check_columns(ob, _OFF_BALL_REQUIRED_COLS, 'Off_Ball_Runs', errors)
            if len(ob) == 0:
                warnings.append("Off_Ball_Runs sheet: 0 rows")
        except Exception as exc:
            errors.append(f"Failed to read Off_Ball_Runs sheet: {exc}")

    return {
        'file':     filepath,
        'player':   player,
        'valid':    len(errors) == 0,
        'errors':   errors,
        'warnings': warnings,
    }


# ── 2. All players validation ─────────────────────────────────────────────────

def validate_all_players(players_dir: str) -> List[Dict[str, Any]]:
    """
    Scan ``players_dir`` for all ``*_master.xlsx`` files and validate each one.

    Parameters
    ----------
    players_dir : str
        Path to the directory containing player master files (e.g. ``data/players``).

    Returns
    -------
    list of result dicts, one per file found (each has the same structure as
    ``validate_master_file`` output). Returns an empty list if the directory
    does not exist or contains no master files.
    """
    pattern = os.path.join(players_dir, '*_master.xlsx')
    files   = sorted(glob.glob(pattern))

    if not files:
        return []

    return [validate_master_file(f) for f in files]


# ── 3. League file validation ─────────────────────────────────────────────────

def validate_league_files(
    ws_files_dict: Dict[str, Dict[str, str]],
) -> List[Dict[str, str]]:
    """
    Check that every file referenced in the WS_FILES dict exists on disk.

    Parameters
    ----------
    ws_files_dict : dict
        Nested ``{league: {pos_key: filepath}}`` dict, matching the ``WS_FILES``
        structure in ``app.py``.

    Returns
    -------
    list of dicts, one per missing file, each with keys
    ``league``, ``pos_key``, and ``path``.
    """
    missing: List[Dict[str, str]] = []
    for league, positions in ws_files_dict.items():
        for pos_key, path in positions.items():
            if not os.path.exists(path):
                missing.append({'league': league, 'pos_key': pos_key, 'path': path})
    return missing


# ── 4. Matching file validation ───────────────────────────────────────────────

def validate_matching(
    matching_csv: str,
    overrides_csv: str,
    conf_threshold: float = 0.85,
) -> List[Dict[str, Any]]:
    """
    Flag SkillCorner↔Wyscout matching entries that may need attention.

    Flags:
    - Players whose match score is below ``conf_threshold`` and have no manual override
    - Players whose match score is missing entirely (NaN) with no override

    Parameters
    ----------
    matching_csv : str
        Path to ``player_matching_l1_l2_2526.csv``.
    overrides_csv : str
        Path to ``matching_overrides.csv``.
    conf_threshold : float
        Minimum acceptable match score (default 0.85, matching CONF_THRESHOLD).

    Returns
    -------
    list of dicts with keys:
        ``sc_player_id``, ``name``, ``score``, ``reason``
    Empty list if no issues or if the matching CSV is absent.
    """
    if not os.path.exists(matching_csv):
        return []

    try:
        matching = pd.read_csv(matching_csv)
    except Exception:
        return []

    # Load overrides to exclude manually resolved players
    overridden_ids: set = set()
    if os.path.exists(overrides_csv):
        try:
            overrides = pd.read_csv(overrides_csv)
            if 'sc_player_id' in overrides.columns:
                overridden_ids = set(overrides['sc_player_id'].dropna().astype(int))
        except Exception:
            pass

    # Deduplicate to one row per player (highest score first)
    if 'wyscout_match_score' in matching.columns:
        matching = (
            matching
            .sort_values('wyscout_match_score', ascending=False)
            .drop_duplicates(subset='sc_player_id')
            .reset_index(drop=True)
        )

    flags: List[Dict[str, Any]] = []
    for _, row in matching.iterrows():
        try:
            sc_id = int(row['sc_player_id'])
        except Exception:
            continue

        if sc_id in overridden_ids:
            continue

        score = row.get('wyscout_match_score')
        name  = row.get('sc_player_name', row.get('player_name', str(sc_id)))

        if pd.isna(score):
            flags.append({
                'sc_player_id': sc_id,
                'name':         name,
                'score':        None,
                'reason':       'No match found in Wyscout data',
            })
        elif float(score) < conf_threshold:
            flags.append({
                'sc_player_id': sc_id,
                'name':         name,
                'score':        round(float(score), 3),
                'reason':       f"Low confidence match (score {score:.3f} < {conf_threshold})",
            })

    return flags


# ── 5. Startup summary ────────────────────────────────────────────────────────

def run_startup_validation(
    players_dir: str,
    ws_files_dict: Dict[str, Dict[str, str]],
    matching_csv: str,
    overrides_csv: str,
) -> Dict[str, Any]:
    """
    Run all four validation checks and return a single summary dict.

    Parameters
    ----------
    players_dir : str
        Path to the ``data/players/`` directory.
    ws_files_dict : dict
        The ``WS_FILES`` nested dict from ``app.py``.
    matching_csv : str
        Path to the SkillCorner↔Wyscout matching CSV.
    overrides_csv : str
        Path to the manual overrides CSV.

    Returns
    -------
    dict with keys:
        ``players``        — list of per-player result dicts
        ``missing_files``  — list of missing league file dicts
        ``matching_flags`` — list of matching issue dicts
        ``all_valid``      — True only if zero errors across everything
        ``error_count``    — total error count
        ``warning_count``  — total warning count
    """
    player_results = validate_all_players(players_dir)
    missing_files  = validate_league_files(ws_files_dict)
    matching_flags = validate_matching(matching_csv, overrides_csv)

    error_count   = sum(len(r['errors']) for r in player_results)
    warning_count = sum(len(r['warnings']) for r in player_results)

    # Missing league files are warnings, not errors (app degrades gracefully)
    warning_count += len(missing_files)

    return {
        'players':        player_results,
        'missing_files':  missing_files,
        'matching_flags': matching_flags,
        'all_valid':      error_count == 0,
        'error_count':    error_count,
        'warning_count':  warning_count,
    }


# ── 6. Streamlit display ──────────────────────────────────────────────────────

def display_validation_results(results: Dict[str, Any]) -> None:
    """
    Render validation results in Streamlit.

    Called from ``app.py`` only when ``results['all_valid']`` is False, so
    this function will always have something to show.

    Parameters
    ----------
    results : dict
        The dict returned by ``run_startup_validation()``.
    """
    import streamlit as st

    player_results  = results.get('players', [])
    missing_files   = results.get('missing_files', [])
    matching_flags  = results.get('matching_flags', [])
    error_count     = results.get('error_count', 0)
    warning_count   = results.get('warning_count', 0)

    if results.get('all_valid'):
        st.success(
            f"Data validation passed — {len(player_results)} player file(s) OK."
        )
        return

    # ── Banner ────────────────────────────────────────────────────────────────
    if error_count > 0:
        st.error(
            f"Data validation found {error_count} error(s) and "
            f"{warning_count} warning(s). "
            "Fix errors before loading player data."
        )
    else:
        st.warning(
            f"Data validation found {warning_count} warning(s). "
            "The app will still run but some data may be incomplete."
        )

    # ── Per-player results ────────────────────────────────────────────────────
    players_with_issues = [r for r in player_results if r['errors'] or r['warnings']]
    if players_with_issues:
        st.markdown("**Player file issues**")
        for r in players_with_issues:
            label = r['player']
            if r['errors']:
                with st.expander(f"❌  {label} — {len(r['errors'])} error(s)", expanded=True):
                    for err in r['errors']:
                        st.markdown(f"- 🔴 {err}")
                    for warn in r['warnings']:
                        st.markdown(f"- 🟡 {warn}")
            elif r['warnings']:
                with st.expander(f"⚠️  {label} — {len(r['warnings'])} warning(s)", expanded=False):
                    for warn in r['warnings']:
                        st.markdown(f"- 🟡 {warn}")

    # ── Missing league files ──────────────────────────────────────────────────
    if missing_files:
        missing_lines = "\n".join(
            f"- {m['league']} / {m['pos_key']}: `{m['path']}`"
            for m in missing_files
        )
        st.warning(
            f"**{len(missing_files)} league peer file(s) missing** "
            f"— peer percentiles will be unavailable for those positions:\n\n"
            + missing_lines
        )

    # ── Matching flags ────────────────────────────────────────────────────────
    if matching_flags:
        flag_lines = "\n".join(
            f"- {f['name']} (id {f['sc_player_id']}): {f['reason']}"
            for f in matching_flags
        )
        st.warning(
            f"**{len(matching_flags)} SkillCorner↔Wyscout matching issue(s)** "
            f"— physical data may use fallback names for these players:\n\n"
            + flag_lines
        )
