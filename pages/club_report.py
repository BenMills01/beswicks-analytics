"""
pages/club_report.py
Beswicks Sports Analytics — Club Analysis Report

Generate a transfer pitch for a specific club. Uses the Anthropic API
to write a data-backed narrative, then exports a club-audience PDF with
the narrative appended as the final page.
"""

import streamlit as st
import pandas as pd
import os
import glob
from datetime import datetime

import anthropic

from src.clubs import (
    get_club_list, get_club_profile, fuzzy_match_club, format_club_context,
    get_all_club_profiles, get_league_medians, get_club_weaknesses,
    suggest_club_need, get_club_squad_at_position, get_style_fit_score,
)
from src.metrics import (
    get_season_totals, get_physical_totals, build_match_log,
    build_physical_peers, build_wyscout_peers, build_physical_season_averages,
    p90, pct, percentile_rank, parse_wyscout_label, parse_physical_label,
    MIN_PEER_N, CONF_THRESHOLD,
)

st.set_page_config(
    page_title="Beswicks | Club Report",
    page_icon="🏟️",
    layout="wide",
)

# ── Dark CSS ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 1.5rem; padding-bottom: 2rem; }
[data-testid="stSidebar"] { background: #0f0f0f; }
[data-testid="stSidebar"] * { color: #e0e0e0 !important; }
.header-bar {
    background: #0f0f0f; padding: 18px 28px; border-radius: 10px;
    margin-bottom: 20px; display: flex; align-items: center;
    justify-content: space-between;
}
.header-bar h1 { color: #fff; font-size: 1.35rem; font-weight: 700; margin: 0; letter-spacing: -0.02em; }
.header-bar .sub { color: #888; font-size: 0.78rem; margin-top: 2px; }
.beswicks-badge {
    background: #c8a45a; color: #0f0f0f; font-size: 0.7rem;
    font-weight: 700; letter-spacing: 0.08em; padding: 4px 10px;
    border-radius: 4px; text-transform: uppercase;
}
.section-header { font-size: 0.7rem; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: #c8a45a; margin: 20px 0 10px; padding-bottom: 6px; border-bottom: 1px solid #2a2a2a; }
.narrative-box { background: #0f0f0f; border-left: 4px solid #c8a45a; border-radius: 0 8px 8px 0; padding: 20px 24px; margin: 12px 0; line-height: 1.7; color: #ccc; font-size: 0.9rem; }
</style>
""", unsafe_allow_html=True)

GOLD = '#c8a45a'

DATA_DIR     = "data"
PLAYERS_DIR  = os.path.join(DATA_DIR, "players")
PHYSICAL_CSV = os.path.join(DATA_DIR, "physical_all_2526.csv")
WS_FILES = {
    'Championship': {
        'all':              os.path.join(DATA_DIR, "Championship 886 mins.xlsx"),
        'Central Defender': os.path.join(DATA_DIR, "Championship Central Defenders.xlsx"),
        'Full Back':        os.path.join(DATA_DIR, "Championship Full Back:Wing Back.xlsx"),
        'Central Mid':      os.path.join(DATA_DIR, "Championship Central Midfielders.xlsx"),
        'Att Mid':          os.path.join(DATA_DIR, "Championship Attacking Midfielders.xlsx"),
        'Wide Mid':         os.path.join(DATA_DIR, "Championship Wide Midfielders.xlsx"),
        'Center Forward':   os.path.join(DATA_DIR, "Championship CF's.xlsx"),
        'Goalkeeper':       os.path.join(DATA_DIR, "Championship GKs.xlsx"),
    },
    'League One': {
        'all':              os.path.join(DATA_DIR, "League One min 874 mins.xlsx"),
        'Central Defender': os.path.join(DATA_DIR, "League One Central Defenders.xlsx"),
        'Full Back':        os.path.join(DATA_DIR, "League One Full Back:Wing Back.xlsx"),
        'Central Mid':      os.path.join(DATA_DIR, "League One Central Midfielders.xlsx"),
        'Att Mid':          os.path.join(DATA_DIR, "League One Attacking Midfielders.xlsx"),
        'Wide Mid':         os.path.join(DATA_DIR, "League One Wide Midfielders.xlsx"),
        'Center Forward':   os.path.join(DATA_DIR, "League One CF's.xlsx"),
        'Goalkeeper':       os.path.join(DATA_DIR, "League One GKs.xlsx"),
    },
    'League Two': {
        'all':              os.path.join(DATA_DIR, "League Two min 874 mins.xlsx"),
        'Central Defender': os.path.join(DATA_DIR, "League Two Central Defenders.xlsx"),
        'Full Back':        os.path.join(DATA_DIR, "League Two FB:WB.xlsx"),
        'Central Mid':      os.path.join(DATA_DIR, "League Two Central Midfielders.xlsx"),
        'Att Mid':          os.path.join(DATA_DIR, "League Two Attacking Midfielders.xlsx"),
        'Wide Mid':         os.path.join(DATA_DIR, "League Two Wide Midfielders.xlsx"),
        'Center Forward':   os.path.join(DATA_DIR, "League Two CFs.xlsx"),
        'Goalkeeper':       os.path.join(DATA_DIR, "League Two GKs.xlsx"),
    },
}


@st.cache_data
def _cached_club_list() -> dict[str, str]:
    return get_club_list()


def get_player_list():
    pattern = os.path.join(os.path.abspath(PLAYERS_DIR), "*_master.xlsx")
    files   = sorted(glob.glob(pattern))
    return [(os.path.basename(f).replace("_master.xlsx", "").replace("_", " "), f) for f in files]


@st.cache_data
def load_master(filepath):
    xls = pd.ExcelFile(filepath)
    return {s: pd.read_excel(xls, sheet_name=s)
            for s in ['Wyscout', 'Physical', 'Pressing', 'Off_Ball_Runs', 'Match_by_Match']
            if s in xls.sheet_names}


@st.cache_data
def load_physical_csv():
    if not os.path.exists(PHYSICAL_CSV):
        return None
    return pd.read_csv(PHYSICAL_CSV, parse_dates=['match_date'])


@st.cache_data
def _cached_phys_avgs(phys_csv):
    return build_physical_season_averages(phys_csv)


@st.cache_data
def _cached_all_profiles_and_medians():
    """Load all 72 club profiles and compute league medians once — cached."""
    profiles = get_all_club_profiles()
    medians  = get_league_medians(profiles)
    return profiles, medians


@st.cache_data
def find_player_position_file(player_short_name):
    for league in ['Championship', 'League One', 'League Two']:
        for pos_key, path in WS_FILES[league].items():
            if pos_key == 'all' or not os.path.exists(path):
                continue
            df = pd.read_excel(path)
            if player_short_name in df['Player'].values:
                return pos_key
    return None


def _ordinal(n: int) -> str:
    """Return integer with correct ordinal suffix: 1st, 2nd, 3rd, 4th…"""
    n = int(n)
    if 11 <= (n % 100) <= 13:
        return f"{n}th"
    return f"{n}{['th', 'st', 'nd', 'rd', 'th'][min(n % 10, 4)]}"


def _fmt(v, d=2, fallback='–'):
    if v is None:
        return fallback
    return f"{v:.{d}f}"


def _build_data_summary(
    name, club, pos, age, matches, mins, goals, assists,
    season, phys, ws_peers, phys_peers, ws_peer_n, phys_peer_n,
    target_club, target_league, club_need, extra_notes,
    club_profile_context: str = "",
    weaknesses: list = None,
    squad_context: str = "",
    fit_score: dict = None,
) -> str:
    """
    Build a structured plain-text data summary without AI prose.
    Suitable for analysts who want the numbers without a generated narrative.
    """

    def pr(key, val, inverse=False, peers=None):
        p = peers or ws_peers
        if key not in p or val is None:
            return ""
        r = percentile_rank(val, p[key], inverse=inverse)
        return f"  ({_ordinal(r)} pct)" if r is not None else ""

    lines = [
        f"CLUB REPORT — DATA SUMMARY",
        f"{'=' * 52}",
        f"Player:    {name}",
        f"Position:  {pos}",
        f"Club:      {club}",
        f"Target:    {target_club}" + (f"  ({target_league})" if target_league else ""),
        f"Sample:    {matches} apps · {mins:,} mins · {goals}G · {assists}A",
        f"Peers:     {ws_peer_n} Wyscout · {phys_peer_n} physical",
        "",
    ]

    if club_profile_context:
        lines += [
            "CLUB PROFILE (Wyscout data)",
            f"  {club_profile_context}",
            "",
        ]

    if club_need.strip():
        lines += [f"What they need: {club_need.strip()}", ""]
    if extra_notes.strip():
        lines += [f"Context: {extra_notes.strip()}", ""]

    lines += [
        "ATTACKING",
        f"  Goals p90:         {season.get('goals_p90', 0):.2f}{pr('goals_p90', season.get('goals_p90'))}",
        f"  xG p90:            {season.get('xg_p90', 0):.2f}{pr('xg_p90', season.get('xg_p90'))}",
        f"  Assists p90:       {season.get('assists_p90', 0):.2f}{pr('assists_p90', season.get('assists_p90'))}",
        f"  xA p90:            {season.get('xa_p90', 0):.2f}{pr('xa_p90', season.get('xa_p90'))}",
        f"  Shot assists p90:  {season.get('shot_asts_p90', 0):.2f}{pr('shot_asts_p90', season.get('shot_asts_p90'))}",
        f"  Dribbles p90:      {season.get('dribbles_p90', 0):.2f}{pr('dribbles_p90', season.get('dribbles_p90'))}",
        f"  Prog runs p90:     {season.get('prog_runs_p90', 0):.2f}{pr('prog_runs_p90', season.get('prog_runs_p90'))}",
        "",
        "PASSING",
        f"  Passes p90:        {season.get('passes_p90', 0):.1f}{pr('passes_p90', season.get('passes_p90'))}",
        f"  Pass accuracy:     {season.get('pass_acc', 0):.1f}%{pr('pass_acc', season.get('pass_acc'))}",
        f"  Long passes p90:   {season.get('long_passes_p90', 0):.2f}{pr('long_passes_p90', season.get('long_passes_p90'))}",
        f"  Crosses p90:       {season.get('crosses_p90', 0):.2f}{pr('crosses_p90', season.get('crosses_p90'))}",
        "",
        "DUELS & DEFENDING",
        f"  Duels p90:         {season.get('duels_p90', 0):.1f}{pr('duels_p90', season.get('duels_p90'))}",
        f"  Duel win %:        {season.get('duel_win', 0):.1f}%{pr('duel_win', season.get('duel_win'))}",
        f"  Aerial p90:        {season.get('aerial_p90', 0):.2f}{pr('aerial_p90', season.get('aerial_p90'))}",
        f"  Aerial win %:      {season.get('aerial_win', 0):.1f}%{pr('aerial_win', season.get('aerial_win'))}",
        f"  Def duels p90:     {season.get('def_duels_p90', 0):.2f}{pr('def_duels_p90', season.get('def_duels_p90'))}",
        f"  Def duel win %:    {season.get('def_duel_win', 0):.1f}%{pr('def_duel_win', season.get('def_duel_win'))}",
        f"  Interceptions p90: {season.get('interceptions_p90', 0):.2f}{pr('interceptions_p90', season.get('interceptions_p90'))}",
        f"  Recoveries p90:    {season.get('recoveries_p90', 0):.2f}{pr('recoveries_p90', season.get('recoveries_p90'))}",
        f"  Ball losses p90:   {season.get('losses_p90', 0):.2f}{pr('losses_p90', season.get('losses_p90'), inverse=True)}",
        "",
    ]

    if phys and phys_peer_n >= MIN_PEER_N:
        lines += [
            f"PHYSICAL  (vs {phys_peer_n} position peers)",
            f"  Total dist p90:    {phys.get('total_dist_p90', 0):.1f} m{pr('total_dist_p90', phys.get('total_dist_p90'), peers=phys_peers)}",
            f"  HSR dist p90:      {phys.get('hsr_dist_p90', 0):.1f} m{pr('hsr_dist_p90', phys.get('hsr_dist_p90'), peers=phys_peers)}",
            f"  Sprint dist p90:   {phys.get('sprint_dist_p90', 0):.1f} m{pr('sprint_dist_p90', phys.get('sprint_dist_p90'), peers=phys_peers)}",
            f"  PSV99 avg:         {phys.get('psv99_avg', 0):.1f}{pr('psv99_avg', phys.get('psv99_avg'), peers=phys_peers)}",
            f"  Hi-accel p90:      {phys.get('hi_accel_p90', 0):.2f}{pr('hi_accel_p90', phys.get('hi_accel_p90'), peers=phys_peers)}",
            "",
        ]
    elif phys:
        lines += [
            "PHYSICAL  (insufficient peers for percentile ranking)",
            f"  Total dist p90:    {phys.get('total_dist_p90', 0):.1f} m",
            f"  HSR dist p90:      {phys.get('hsr_dist_p90', 0):.1f} m",
            f"  Sprint dist p90:   {phys.get('sprint_dist_p90', 0):.1f} m",
            f"  PSV99 avg:         {phys.get('psv99_avg', 0):.1f}",
            "",
        ]

    if weaknesses:
        lines.append("CLUB WEAKNESS PROFILE (vs league median)")
        for w in weaknesses[:4]:
            direction = "above" if w["inverse"] else "below"
            lines.append(
                f"  {w['label']}: {w['club_val']:.1f} vs median {w['median_val']:.1f} "
                f"({w['gap_pct']:.1f}% {direction} median)"
            )
        lines.append("")

    if squad_context:
        lines += ["SQUAD COMPARISON", squad_context, ""]

    if fit_score:
        lines.append("STYLE FIT SCORE")
        overall = fit_score.get("overall")
        if overall is not None:
            lines.append(f"  Overall: {overall}/100")
        for dim, label in [
            ("press_fit",    "Press fit"),
            ("buildup_fit",  "Build-up fit"),
            ("gap_fill",     "Gap fill"),
            ("physical_fit", "Physical fit"),
        ]:
            v = fit_score.get(dim)
            if v is not None:
                lines.append(f"  {label}: {v}")
        lines.append("")

    lines.append("Generated by Beswicks Sports Analytics")

    return "\n".join(lines)


def _build_prompt(
    name, club, pos, age, matches, mins, goals, assists,
    season, phys, ws_peers, phys_peers, ws_peer_n, phys_peer_n,
    target_club, target_league, club_need, extra_notes,
    club_profile_context: str = "",
    weaknesses: list = None,
    squad_context: str = "",
    fit_score: dict = None,
) -> str:
    """Build the Anthropic prompt for the transfer pitch narrative."""

    def pr(key, val, inverse=False, peers=None):
        p = peers or ws_peers
        if key not in p or val is None:
            return ''
        r = percentile_rank(val, p[key], inverse=inverse)
        return f" ({_ordinal(r)} pct)" if r is not None else ''

    lines = [
        "You are an elite football analyst writing a transfer pitch for Beswicks Sports Management.\n",
        f"PLAYER: {name} | {pos} | {club} | Age {age}",
        f"SEASON 2025/26: {matches} apps · {mins:,} mins · {goals}G · {assists}A",
        f"PEER GROUP: {ws_peer_n} position peers (League One/Two)\n",
        "KEY STATISTICS (value — percentile vs position peers):",
    ]

    stat_lines = []
    def add(label, key, val, inverse=False, fmt='.2f', suffix='', peers=None):
        if val is not None:
            stat_lines.append(f"  {label}: {val:{fmt}}{suffix}{pr(key, val, inverse, peers)}")

    add("Goals p90",          'goals_p90',        season.get('goals_p90'))
    add("xG p90",             'xg_p90',           season.get('xg_p90'))
    add("Assists p90",        'assists_p90',       season.get('assists_p90'))
    add("xA p90",             'xa_p90',            season.get('xa_p90'))
    add("Shot assists p90",   'shot_asts_p90',     season.get('shot_asts_p90'))
    add("Dribbles p90",       'dribbles_p90',      season.get('dribbles_p90'))
    add("Prog runs p90",      'prog_runs_p90',     season.get('prog_runs_p90'))
    add("Passes p90",         'passes_p90',        season.get('passes_p90'),  fmt='.1f')
    add("Pass accuracy",      'pass_acc',          season.get('pass_acc'),    fmt='.1f', suffix='%')
    add("Crosses p90",        'crosses_p90',       season.get('crosses_p90'))
    add("Duels p90",          'duels_p90',         season.get('duels_p90'),   fmt='.1f')
    add("Duel win %",         'duel_win',          season.get('duel_win'),    fmt='.1f', suffix='%')
    add("Aerial p90",         'aerial_p90',        season.get('aerial_p90'))
    add("Aerial win %",       'aerial_win',        season.get('aerial_win'),  fmt='.1f', suffix='%')
    add("Def duels p90",      'def_duels_p90',     season.get('def_duels_p90'))
    add("Def duel win %",     'def_duel_win',      season.get('def_duel_win'), fmt='.1f', suffix='%')
    add("Interceptions p90",  'interceptions_p90', season.get('interceptions_p90'))
    add("Recoveries p90",     'recoveries_p90',    season.get('recoveries_p90'))
    add("Ball losses p90",    'losses_p90',        season.get('losses_p90'),  inverse=True)

    lines += stat_lines

    if phys and phys_peer_n >= MIN_PEER_N:
        lines.append(f"\nPHYSICAL PROFILE (vs {phys_peer_n} position peers):")
        for label, key in [
            ("Total dist p90", 'total_dist_p90'), ("HSR dist p90", 'hsr_dist_p90'),
            ("Sprint dist p90", 'sprint_dist_p90'), ("PSV99 avg", 'psv99_avg'),
            ("Hi-accel p90", 'hi_accel_p90'),
        ]:
            val = phys.get(key)
            if val is not None:
                lines.append(f"  {label}: {val:.1f}{pr(key, val, peers=phys_peers)}")

    lines += [
        f"\nTARGET CLUB: {target_club}",
        f"DIVISION: {target_league}",
    ]
    if club_profile_context:
        lines.append(f"CLUB PROFILE (Wyscout data): {club_profile_context}")
    lines.append(f"WHAT THEY NEED: {club_need}")
    if extra_notes.strip():
        lines.append(f"ADDITIONAL CONTEXT: {extra_notes}")

    if weaknesses:
        lines.append("\nCLUB WEAKNESS PROFILE (vs league median — use these to anchor the fit argument):")
        for w in weaknesses[:4]:
            direction = "above" if w["inverse"] else "below"
            lines.append(
                f"  {w['label']}: {w['club_val']:.1f} vs median {w['median_val']:.1f} "
                f"({w['gap_pct']:.1f}% {direction} median) — {w['interpretation']}"
            )

    if squad_context:
        lines.append(f"\nSQUAD COMPARISON AT POSITION:\n{squad_context}")

    if fit_score:
        overall = fit_score.get("overall")
        dims = {
            "press_fit":   "Press fit",
            "buildup_fit": "Build-up fit",
            "gap_fill":    "Gap fill (addresses club weaknesses)",
            "physical_fit":"Physical fit",
        }
        dim_parts = ", ".join(
            f"{label} {fit_score[k]}"
            for k, label in dims.items()
            if fit_score.get(k) is not None
        )
        lines.append(f"\nSTYLE FIT SCORE: {overall}/100 ({dim_parts})")
        lines.append("Reference this score and its dimensions in paragraph 4.")

    lines += [
        "\n---",
        "Write a concise, confident transfer pitch (4 paragraphs, approximately 280–320 words total).",
        "Structure:",
        "  1. Player overview and headline offer — what type of player and what they provide",
        "  2. Statistical case — lead with the 3-4 metrics most relevant to what the club needs, all backed by data and percentile context",
        "  3. Physical and pressing profile — concrete numbers, what they mean for this club's style",
        "  4. Summary recommendation and fit argument — why this player suits this specific club",
        "",
        "Rules:",
        "- Every claim must be backed by a specific figure from the data above",
        "- Include percentile ranks in prose where relevant: e.g. '78th percentile among League One central defenders'",
        "- Club-audience tone: confident, professional, no hedging",
        "- Do not mention weaknesses or below-average metrics",
        "- No vague praise ('dynamic presence', 'hard worker', 'quality player')",
        "- No em dashes",
        "- No bullet points — narrative paragraphs only",
        "- Write in third person",
    ]

    return '\n'.join(lines)


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="header-bar">
  <div><h1>Club Analysis Report</h1><div class="sub">AI-generated transfer pitch · Club audience</div></div>
  <div class="beswicks-badge">Beswicks Sports</div>
</div>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🏟️ Club Report")
    st.markdown("---")
    player_list = get_player_list()
    if not player_list:
        st.warning("No player files found.")
        st.stop()

    player_names  = [p[0] for p in player_list]
    selected_name = st.selectbox("Select player", player_names)
    selected_path = next(p[1] for p in player_list if p[0] == selected_name)

    st.markdown("---")
    st.markdown("### Peer group filters")
    min_mins_peer = st.slider("Min minutes", 450, 1800, 900, 90)
    peer_leagues  = st.multiselect(
        "Leagues",
        ["Championship", "League One", "League Two"],
        default=["Championship", "League One", "League Two"],
    )
    if not peer_leagues:
        peer_leagues = ["Championship", "League One", "League Two"]
    peer_league = peer_leagues  # list — peer builders accept list or str

# ── Load data ─────────────────────────────────────────────────────────────────
with st.spinner(f"Loading {selected_name}..."):
    sheets   = load_master(selected_path)
    phys_csv = load_physical_csv()

ws_raw = sheets.get('Wyscout')
ph_raw = sheets.get('Physical')

if ws_raw is None:
    st.error(f"No Wyscout sheet found for {selected_name}.")
    st.stop()

ws = ws_raw[ws_raw['Minutes played'] >= 20].copy().sort_values('Date').reset_index(drop=True)
ph = ph_raw[ph_raw['minutes_full_all'] >= 20].copy().sort_values('match_date').reset_index(drop=True) if ph_raw is not None else None

club   = ph_raw['team_name'].iloc[0]      if ph_raw is not None and 'team_name'      in ph_raw.columns else ""
pos    = ph_raw['position_group'].iloc[0] if ph_raw is not None and 'position_group' in ph_raw.columns else ""

# Derive player's own league from Physical sheet competition_name (e.g. "ENG - League Two" → "League Two")
player_league = ""
if ph_raw is not None and 'competition_name' in ph_raw.columns:
    _comp = ph_raw['competition_name'].dropna().mode()
    if not _comp.empty:
        player_league = _comp.iloc[0].replace("ENG - ", "").strip()
short  = ph_raw['player_short_name'].iloc[0] if ph_raw is not None and 'player_short_name' in ph_raw.columns else selected_name

season = get_season_totals(ws)
phys   = get_physical_totals(ph) if ph is not None else None

try:
    date_start = pd.to_datetime(ws['Date'].min()).strftime('%d %b %Y')
    date_end   = pd.to_datetime(ws['Date'].max()).strftime('%d %b %Y')
except Exception:
    date_start, date_end = '–', '–'

ws_pos_key = find_player_position_file(short) if short else None
ws_peers, ws_peer_n     = build_wyscout_peers(ws_pos_key, peer_league, min_mins_peer, WS_FILES) if ws_pos_key else ({}, 0)
phys_peers, phys_peer_n = build_physical_peers(phys_csv, pos, min_mins_peer, peer_league)

# Merge phys into season for easy lookup
if phys:
    season_combined = {**season, **phys}
else:
    season_combined = season

# ── Club fit rankings ─────────────────────────────────────────────────────────
st.markdown('<div class="section-header">Club fit rankings</div>', unsafe_allow_html=True)

_all_profiles_rank, _all_medians_rank = _cached_all_profiles_and_medians()
_club_scores: list[dict] = []
for _cn, _cp in _all_profiles_rank.items():
    if _cp.get("matches", 0) == 0:
        continue
    try:
        _fs = get_style_fit_score(
            season=season_combined,
            phys=phys,
            club_profile=_cp,
            ws_peers=ws_peers,
            phys_peers=phys_peers,
            league_medians=_all_medians_rank,
        )
        if _fs.get("overall") is not None:
            _club_scores.append({
                "Club":      _cn,
                "League":    _cp.get("league", ""),
                "Formation": _cp.get("primary_formation", ""),
                "Style":     " · ".join(filter(None, [_cp.get("press_intensity"), _cp.get("play_style")])),
                "Overall":   _fs["overall"],
                "Press":     _fs.get("press_fit"),
                "Build-up":  _fs.get("buildup_fit"),
                "Gap fill":  _fs.get("gap_fill"),
                "Physical":  _fs.get("physical_fit"),
            })
    except Exception:
        pass

# Filter to clubs whose league matches the selected peer leagues
_club_scores = [
    s for s in _club_scores
    if _all_profiles_rank.get(s["Club"], {}).get("league") in peer_leagues
    or _all_profiles_rank.get(s["Club"], {}).get("league") is None  # keep if league unknown
]
_club_scores.sort(key=lambda x: x["Overall"], reverse=True)

if _club_scores:
    _rank_df = pd.DataFrame(_club_scores[:10])
    _rank_df.insert(0, "#", range(1, len(_rank_df) + 1))
    def _score_colour(val):
        try:
            v = int(val)
        except (TypeError, ValueError):
            return ""
        if v >= 70:
            return "background-color: #166534; color: #86efac"
        elif v >= 55:
            return "background-color: #854d0e; color: #fde68a"
        else:
            return "background-color: #7f1d1d; color: #fca5a5"

    st.dataframe(
        _rank_df.style.format(
            {c: lambda v: f"{int(v)}" if pd.notna(v) else "–"
             for c in ["Overall", "Press", "Build-up", "Gap fill", "Physical"]}
        ).applymap(_score_colour, subset=["Overall"]),
        use_container_width=True,
        hide_index=True,
    )
    _league_label = " + ".join(peer_leagues)
    st.caption(f"Scored across {len(_club_scores)} clubs · peer filter: {_league_label} · {min_mins_peer}+ mins")

    # Quick-select: clicking a club from the top-10 pre-fills the target input
    if "target_club_input" not in st.session_state:
        st.session_state["target_club_input"] = ""
    _top_names = [r["Club"] for r in _club_scores[:10]]
    _qs_col, _btn_col = st.columns([3, 1])
    with _qs_col:
        _quick_pick = st.selectbox(
            "Quick select from top 10",
            options=[""] + _top_names,
            label_visibility="collapsed",
        )
    with _btn_col:
        if st.button("Use this club", use_container_width=True, disabled=not _quick_pick):
            st.session_state["target_club_input"] = _quick_pick
            st.rerun()
else:
    st.caption("No club profiles available — add Wyscout team stats files to data/clubs/")

# ── Club context inputs ────────────────────────────────────────────────────────
st.markdown('<div class="section-header">Target club</div>', unsafe_allow_html=True)

available_clubs = _cached_club_list()
_n_clubs = len(available_clubs)

if "target_club_input" not in st.session_state:
    st.session_state["target_club_input"] = ""

col_a, col_b = st.columns(2)
with col_a:
    target_club = st.text_input(
        "Club name",
        key="target_club_input",
        placeholder="e.g. Bristol City",
        help=f"{_n_clubs} club files available — start typing to auto-match" if _n_clubs else "No club files found in data/clubs/",
    )

if not target_club:
    st.info("Select a club from the rankings above or type a name to generate a report.")
    st.stop()

# ── Auto-match club file ───────────────────────────────────────────────────────
_club_profile: dict = {}
_club_profile_context: str = ""
_matched_name: str = ""
_weaknesses: list = []
_auto_club_need: str = ""
_squad_df = None
_squad_context: str = ""
_fit_score: dict = {}

if available_clubs:
    _match = fuzzy_match_club(target_club, available_clubs)
    if _match:
        _matched_name, _matched_path = _match
        try:
            _club_profile = get_club_profile(_matched_name, _matched_path)
            _club_profile_context = format_club_context(_club_profile)
        except Exception as _e:
            st.warning(f"Could not load club file for {_matched_name}: {_e}")

        if _club_profile.get("matches", 0) > 0:
            _p = _club_profile
            _wdl = f"W{_p.get('wins',0)}/D{_p.get('draws',0)}/L{_p.get('losses',0)}"

            # ── Profile card ──────────────────────────────────────────────────
            st.markdown(
                f"""<div style="background:#161616;border:1px solid #2a2a2a;border-left:4px solid {GOLD};
                border-radius:0 8px 8px 0;padding:14px 18px;margin:8px 0 12px;font-size:0.82rem;color:#ccc;">
                <span style="color:{GOLD};font-weight:700;text-transform:uppercase;
                letter-spacing:0.08em;font-size:0.7rem;">Club profile matched — {_matched_name}</span><br>
                <span style="color:#999;margin-top:6px;display:block;">
                {"Formation: <b style='color:#e0e0e0'>" + str(_p.get("primary_formation","")) + "</b> &nbsp;·&nbsp;" if _p.get("primary_formation","Unknown") != "Unknown" else ""}
                {"<b style='color:#e0e0e0'>" + str(_p.get("press_intensity","")) + "</b> &nbsp;·&nbsp;" if _p.get("press_intensity") else ""}
                {"<b style='color:#e0e0e0'>" + str(_p.get("play_style","")) + "</b> &nbsp;·&nbsp;" if _p.get("play_style") else ""}
                {"PPDA <b style='color:#e0e0e0'>" + f"{_p['avg_ppda']:.1f}" + "</b> &nbsp;·&nbsp;" if _p.get("avg_ppda") else ""}
                {"Possession <b style='color:#e0e0e0'>" + f"{_p['avg_possession']:.0f}%" + "</b> &nbsp;·&nbsp;" if _p.get("avg_possession") else ""}
                {"Def duel win <b style='color:#e0e0e0'>" + f"{_p['avg_def_duel_win_pct']:.0f}%" + "</b> &nbsp;·&nbsp;" if _p.get("avg_def_duel_win_pct") else ""}
                {"Aerial win <b style='color:#e0e0e0'>" + f"{_p['avg_aerial_win_pct']:.0f}%" + "</b> &nbsp;·&nbsp;" if _p.get("avg_aerial_win_pct") else ""}
                <b style='color:#e0e0e0'>{_wdl}</b> from {_p.get("matches",0)} games
                </span></div>""",
                unsafe_allow_html=True,
            )

            # ── Weakness diagnosis ────────────────────────────────────────────
            _, _medians = _cached_all_profiles_and_medians()
            _weaknesses = get_club_weaknesses(_club_profile, _medians)
            _auto_club_need = suggest_club_need(_weaknesses, _club_profile)

            if _weaknesses:
                with st.expander("Club weakness profile (auto-diagnosed vs league median)", expanded=True):
                    _wcols = st.columns([2, 1, 1, 1, 3])
                    _wcols[0].markdown("**Metric**")
                    _wcols[1].markdown("**Club**")
                    _wcols[2].markdown("**Median**")
                    _wcols[3].markdown("**Gap**")
                    _wcols[4].markdown("**Signal**")
                    for _w in _weaknesses[:5]:
                        _wcols[0].write(_w["label"])
                        _wcols[1].write(f"{_w['club_val']:.1f}")
                        _wcols[2].write(f"{_w['median_val']:.1f}")
                        _direction = "▲" if _w["inverse"] else "▼"
                        _wcols[3].write(f"{_direction} {_w['gap_pct']:.1f}%")
                        _wcols[4].write(_w["interpretation"])

    else:
        st.caption(f"No file match for '{target_club}' in {_n_clubs} available clubs — using manual context only.")

# ── League / division (auto-populated from club profile) ──────────────────────
_auto_league = _club_profile.get("league", "") or ""
target_league = st.text_input(
    "League / division",
    value=_auto_league,
    placeholder="e.g. Championship",
    help="Auto-populated from matched club file. Edit if needed.",
)

# ── What they need + extra context ────────────────────────────────────────────
col_need, col_extra = st.columns(2)
with col_need:
    club_need = st.text_area(
        "What the club needs",
        value=_auto_club_need,
        height=80,
        placeholder="e.g. Ball-playing centre-back, aggressive press, can step out with the ball",
        help="Auto-populated from weakness diagnosis. Edit freely.",
    )
with col_extra:
    extra_notes = st.text_area(
        "Additional context (optional)",
        height=80,
        placeholder="e.g. New manager rebuilding defensively, lost their first-choice CB to injury",
    )

# ── Squad comparison ───────────────────────────────────────────────────────────
if _matched_name and ws_pos_key:
    _squad_df = get_club_squad_at_position(_matched_name, ws_pos_key, WS_FILES, min_mins=min_mins_peer)
    if _squad_df is not None and not _squad_df.empty:
        # Build plain-text squad context for prompt injection
        _squad_lines = [f"  {row.get('Player','?')}: " + ", ".join(
            f"{col} {row[col]:.1f}" if pd.api.types.is_float(row.get(col)) or pd.api.types.is_integer(row.get(col)) else str(row.get(col, ""))
            for col in _squad_df.columns if col != "Player" and row.get(col) is not None
        ) for _, row in _squad_df.iterrows()]
        _squad_context = "\n".join(_squad_lines)

        st.markdown('<div class="section-header">Squad comparison — existing players at this position</div>', unsafe_allow_html=True)
        _display_squad = _squad_df.copy()
        # Rename columns to short labels
        _col_renames = {
            "Minutes played": "Mins", "Passes per 90": "Pass p90", "Accurate passes, %": "Pass%",
            "Duels per 90": "Duels p90", "Duels won, %": "Duel%",
            "Aerial duels per 90": "Aerial p90", "Aerial duels won, %": "Aerial%",
            "Defensive duels per 90": "Def p90", "Defensive duels won, %": "Def%",
            "Interceptions per 90": "Int p90",
        }
        _display_squad = _display_squad.rename(columns=_col_renames)
        st.dataframe(
            _display_squad.style.format(precision=1, na_rep="–"),
            use_container_width=True,
            hide_index=True,
        )
        st.caption(f"{len(_squad_df)} player(s) from {_matched_name} at {ws_pos_key} · {min_mins_peer}+ mins")

# ── Style fit score ────────────────────────────────────────────────────────────
if _club_profile.get("matches", 0) > 0 and (ws_peers or phys_peers):
    try:
        _, _medians_for_fit = _cached_all_profiles_and_medians()
        _fit_score = get_style_fit_score(
            season=season_combined,
            phys=phys,
            club_profile=_club_profile,
            ws_peers=ws_peers,
            phys_peers=phys_peers,
            league_medians=_medians_for_fit,
        )
    except Exception as _fe:
        _fit_score = {}

    if _fit_score.get("overall") is not None:
        st.markdown('<div class="section-header">Style fit score</div>', unsafe_allow_html=True)
        _fit_dims = [
            ("Overall", "overall"),
            ("Press fit", "press_fit"),
            ("Build-up fit", "buildup_fit"),
            ("Gap fill", "gap_fill"),
            ("Physical fit", "physical_fit"),
        ]
        _fit_cols = st.columns(len(_fit_dims))
        for _fc, (_label, _key) in zip(_fit_cols, _fit_dims):
            _v = _fit_score.get(_key)
            if _v is not None:
                _colour = "#4ade80" if _v >= 70 else ("#facc15" if _v >= 50 else "#f87171")
                _fc.markdown(
                    f"""<div style="background:#161616;border:1px solid #2a2a2a;border-radius:8px;
                    padding:12px 10px;text-align:center;">
                    <div style="font-size:0.65rem;color:#888;text-transform:uppercase;
                    letter-spacing:0.08em;margin-bottom:4px;">{_label}</div>
                    <div style="font-size:1.6rem;font-weight:700;color:{_colour};">{_v}</div>
                    <div style="font-size:0.65rem;color:#555;">/100</div></div>""",
                    unsafe_allow_html=True,
                )
            else:
                _fc.markdown(
                    f"""<div style="background:#161616;border:1px solid #2a2a2a;border-radius:8px;
                    padding:12px 10px;text-align:center;">
                    <div style="font-size:0.65rem;color:#888;text-transform:uppercase;
                    letter-spacing:0.08em;margin-bottom:4px;">{_label}</div>
                    <div style="font-size:1rem;color:#444;">–</div></div>""",
                    unsafe_allow_html=True,
                )

# ── Report mode toggle ────────────────────────────────────────────────────────
st.markdown('<div class="section-header">Report mode</div>', unsafe_allow_html=True)
report_mode = st.radio(
    "report_mode",
    ["AI narrative", "Data only"],
    horizontal=True,
    label_visibility="collapsed",
    help="AI narrative calls Claude to write a transfer pitch. Data only formats the raw stats and club profile without AI.",
)

# ── Generate ──────────────────────────────────────────────────────────────────
if "narrative" not in st.session_state:
    st.session_state.narrative = None
if "narrative_player" not in st.session_state:
    st.session_state.narrative_player = None
if "narrative_club" not in st.session_state:
    st.session_state.narrative_club = None
if "narrative_mode" not in st.session_state:
    st.session_state.narrative_mode = None

_shared_args = dict(
    name=selected_name, club=club, pos=pos, age=24,
    matches=int(season.get('matches', 0)),
    mins=int(season.get('mins', 0)),
    goals=int(season.get('goals_raw', 0)),
    assists=int(season.get('assists_raw', 0)),
    season=season_combined, phys=phys,
    ws_peers=ws_peers, phys_peers=phys_peers,
    ws_peer_n=ws_peer_n, phys_peer_n=phys_peer_n,
    target_club=target_club, target_league=target_league,
    club_need=club_need, extra_notes=extra_notes,
    club_profile_context=_club_profile_context,
    weaknesses=_weaknesses or None,
    squad_context=_squad_context,
    fit_score=_fit_score or None,
)

_stale = (
    st.session_state.narrative is None or
    st.session_state.narrative_player != selected_name or
    st.session_state.narrative_club   != target_club or
    st.session_state.narrative_mode   != report_mode
)

_btn_label = "✨ Generate AI report" if report_mode == "AI narrative" else "📊 Generate data summary"
col_gen, col_regen = st.columns([3, 1])
with col_gen:
    generate_btn = st.button(_btn_label, use_container_width=True, type="primary")
with col_regen:
    regen_btn = st.button("↺ Regenerate", use_container_width=True, disabled=_stale)

if generate_btn or regen_btn:
    if report_mode == "Data only":
        # Instant — no API call needed
        st.session_state.narrative        = _build_data_summary(**_shared_args)
        st.session_state.narrative_player = selected_name
        st.session_state.narrative_club   = target_club
        st.session_state.narrative_mode   = report_mode
    else:
        with st.spinner("Generating transfer pitch narrative..."):
            try:
                prompt = _build_prompt(**_shared_args)
                client = anthropic.Anthropic()
                msg    = client.messages.create(
                    model='claude-opus-4-6',
                    max_tokens=700,
                    messages=[{"role": "user", "content": prompt}],
                )
                st.session_state.narrative        = msg.content[0].text
                st.session_state.narrative_player = selected_name
                st.session_state.narrative_club   = target_club
                st.session_state.narrative_mode   = report_mode
            except anthropic.APIConnectionError:
                st.error("Could not connect to the Anthropic API. Check your ANTHROPIC_API_KEY environment variable.")
            except Exception as e:
                st.error(f"Narrative generation failed: {e}")
                st.exception(e)

# ── Preview ───────────────────────────────────────────────────────────────────
if (st.session_state.narrative and
        st.session_state.narrative_player == selected_name and
        st.session_state.narrative_club   == target_club):

    _is_data_mode = st.session_state.narrative_mode == "Data only"
    _section_label = "Data summary" if _is_data_mode else "Transfer pitch narrative"
    st.markdown(f'<div class="section-header">{_section_label}</div>', unsafe_allow_html=True)

    if _is_data_mode:
        st.code(st.session_state.narrative, language=None)
    else:
        st.markdown(
            f"<div class='narrative-box'>{st.session_state.narrative.replace(chr(10), '<br><br>')}</div>",
            unsafe_allow_html=True,
        )

    # ── PDF export ────────────────────────────────────────────────────────────
    st.markdown("---")
    try:
        from generate_report import generate_pdf
        PDF_OK = True
    except Exception:
        PDF_OK = False

    if PDF_OK:
        if st.button("📄 Export club report PDF", use_container_width=True):
            with st.spinner("Building PDF — this may take a few seconds..."):
                try:
                    # Prepare ws/ph with derived columns for form charts
                    ws_pdf = ws.copy()
                    if 'match_label' not in ws_pdf.columns:
                        ws_pdf['match_label']      = ws_pdf.apply(lambda r: parse_wyscout_label(r['Match'], club), axis=1)
                    if 'duel_win_pct' not in ws_pdf.columns:
                        ws_pdf['duel_win_pct']     = ws_pdf.apply(lambda r: pct(r.iloc[21], r['Duels']), axis=1)
                        ws_pdf['def_duel_win_pct'] = ws_pdf.apply(lambda r: pct(r.iloc[32], r.iloc[31]), axis=1)

                    ph_pdf = None
                    if ph is not None:
                        ph_pdf = ph.copy()
                        if 'match_label' not in ph_pdf.columns:
                            ph_pdf['match_label']  = ph_pdf.apply(lambda r: parse_physical_label(r['match_name'], r['team_name']), axis=1)
                            ph_pdf['dist_p90_m']   = ph_pdf.apply(lambda r: p90(r['total_distance_full_all'],  r['minutes_full_all']), axis=1)
                            ph_pdf['hsr_p90_m']    = ph_pdf.apply(lambda r: p90(r['hsr_distance_full_all'],    r['minutes_full_all']), axis=1)
                            ph_pdf['sprint_p90_m'] = ph_pdf.apply(lambda r: p90(r['sprint_distance_full_all'], r['minutes_full_all']), axis=1)

                    # Build radar data
                    radar_keys = [
                        ('Goals p90','goals_p90',False), ('xG p90','xg_p90',False),
                        ('Shot asts p90','shot_asts_p90',False), ('Pass acc %','pass_acc',False),
                        ('Dribbles p90','dribbles_p90',False), ('Prog runs p90','prog_runs_p90',False),
                        ('Crosses p90','crosses_p90',False), ('Duels p90','duels_p90',False),
                        ('Duel win %','duel_win',False), ('Aerial p90','aerial_p90',False),
                        ('Interceptions','interceptions_p90',False), ('Recoveries p90','recoveries_p90',False),
                    ]
                    if phys and phys_peer_n >= MIN_PEER_N:
                        radar_keys += [('HSR dist p90','hsr_dist_p90',False), ('Sprint dist p90','sprint_dist_p90',False)]

                    radar_data = {}
                    for label, key, inv in radar_keys:
                        val = season_combined.get(key)
                        if val is None:
                            continue
                        p_src = phys_peers if key in phys_peers else ws_peers
                        pct_v = percentile_rank(val, p_src.get(key), inverse=inv) if key in p_src else None
                        if pct_v is not None:
                            radar_data[label] = pct_v

                    # Only pass AI narrative prose to PDF — skip data-only dumps
                    _pdf_narrative = st.session_state.narrative
                    if _pdf_narrative and '=====' in _pdf_narrative:
                        _pdf_narrative = None

                    pdf_bytes = generate_pdf(
                        name=selected_name, club=club, league=player_league or target_league or "", pos=pos,
                        age_val=24,
                        date_start=date_start, date_end=date_end,
                        season=season, phys=phys,
                        ws=ws_pdf, ph=ph_pdf,
                        radar_data=radar_data,
                        ws_peers=ws_peers, phys_peers=phys_peers,
                        ws_peer_n=ws_peer_n, phys_peer_n=phys_peer_n,
                        peer_desc=f"{' + '.join(peer_leagues)} · {min_mins_peer}+ mins",
                        audience='club',
                        narrative_text=_pdf_narrative,
                        club_name=target_club,
                        weaknesses=_weaknesses or None,
                        squad_df=_squad_df,
                        fit_score=_fit_score or None,
                    )

                    safe_name = selected_name.replace(' ', '_')
                    safe_club = target_club.replace(' ', '_')
                    filename  = f"Beswicks_{safe_name}_{safe_club}_club_report.pdf"
                    st.download_button(
                        "⬇ Download PDF",
                        data=pdf_bytes,
                        file_name=filename,
                        mime="application/pdf",
                        use_container_width=True,
                    )
                except Exception as e:
                    st.error(f"PDF generation failed: {e}")
                    st.exception(e)
    else:
        st.info("PDF export requires `kaleido` and `reportlab`.")
