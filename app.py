import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
from scipy import stats as scipy_stats
import os
import glob

from src.metrics import (
    p90, pct, percentile_rank, ordinal, pct_colour,
    rolling_avg, mins_to_opacity, rgba, colour_list,
    parse_wyscout_label, parse_physical_label,
    get_season_totals, get_physical_totals, build_match_log,
    build_physical_peers, build_wyscout_peers, build_physical_season_averages,
    compute_trajectory, find_comparable_players_pca,
    METRIC_DESC, MIN_PEER_N, CONF_THRESHOLD,
)

# PDF export (graceful fallback if kaleido not installed)
try:
    from generate_report import generate_pdf
    PDF_AVAILABLE = True
except Exception:
    PDF_AVAILABLE = False

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Beswicks Sports | Player Analysis",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
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
.profile-card {
    background: #0f0f0f; border-radius: 10px; padding: 22px 26px;
    margin-bottom: 20px; border-left: 4px solid #c8a45a;
}
.profile-name  { font-size: 1.6rem; font-weight: 700; color: #fff; margin: 0 0 4px; }
.profile-meta  { color: #aaa; font-size: 0.82rem; margin: 0; }
.profile-tags  { margin-top: 12px; display: flex; flex-wrap: wrap; gap: 8px; }
.tag           { background: #1e1e1e; border: 1px solid #333; color: #ccc; border-radius: 5px; padding: 4px 10px; font-size: 0.74rem; }
.tag-gold      { background: #2a2218; border: 1px solid #c8a45a; color: #c8a45a; }
.mc            { background: #1a1a1a; border-radius: 8px; padding: 12px 14px 10px; border: 1px solid #2a2a2a; }
.mc-label      { font-size: 0.68rem; color: #666; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 4px; }
.mc-value      { font-size: 1.4rem; font-weight: 700; color: #fff; line-height: 1; }
.mc-sub        { font-size: 0.68rem; color: #555; margin-top: 3px; }
.pbar-track    { background: #2a2a2a; border-radius: 3px; height: 4px; margin-top: 6px; overflow: hidden; }
.pbar-fill     { height: 4px; border-radius: 3px; }
.mc-pct        { font-size: 0.68rem; margin-top: 4px; font-weight: 600; }
.mc-good .mc-value { color: #4ade80; }
.mc-warn .mc-value { color: #facc15; }
.mc-bad  .mc-value { color: #f87171; }
.peer-banner      { background: #111a11; border: 1px solid #1e3a1e; border-radius: 8px; padding: 10px 16px; margin: 8px 0 16px; font-size: 0.75rem; color: #4ade80; }
.peer-banner-warn { background: #1a1500; border: 1px solid #3a3000; color: #facc15; }
.section-header   { font-size: 0.7rem; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: #c8a45a; margin: 24px 0 12px; padding-bottom: 6px; border-bottom: 1px solid #2a2a2a; }
hr { border-color: #2a2a2a; margin: 20px 0; }
.mc-desc { font-size: 0.65rem; color: #555; cursor: help; padding: 0 2px; position: relative; }
.mc-desc:hover::after {
    content: attr(title); position: absolute; right: 0; top: 18px; z-index: 999;
    background: #222; color: #ccc; font-size: 0.7rem; padding: 6px 10px;
    border-radius: 6px; width: 220px; line-height: 1.5; border: 1px solid #333;
    white-space: normal; pointer-events: none;
}
</style>
""", unsafe_allow_html=True)

PLOT_BG  = '#0f0f0f'
PAPER_BG = '#0f0f0f'
GRID_COL = '#222222'
TEXT_COL = '#aaaaaa'
GOLD     = '#c8a45a'
BLUE     = '#3b82f6'
RED      = '#f87171'
GREEN    = '#4ade80'
PURPLE   = '#a78bfa'

# ── Data paths ────────────────────────────────────────────────────────────────
DATA_DIR        = "data"
PLAYERS_DIR     = os.path.join(DATA_DIR, "players")
PHYSICAL_CSV    = os.path.join(DATA_DIR, "physical_all_2526.csv")
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
MATCHING_CSV    = os.path.join(DATA_DIR, "player_matching_l1_l2_2526.csv")
OVERRIDES_CSV   = os.path.join(DATA_DIR, "matching_overrides.csv")
# CONF_THRESHOLD imported from src.metrics

# ── UI helpers (app.py-only — not shared) ─────────────────────────────────────
def metric_card(label, value, sub='', vcls='', pct_val=None, peer_n=None, trajectory=None):
    pct_section = ''
    if pct_val is not None:
        c  = pct_colour(pct_val)
        w  = f"{pct_val:.0f}%"
        ps = f" · n={peer_n}" if peer_n else ""
        pct_section = (
            f'<div class="pbar-track"><div class="pbar-fill" style="width:{w};background:{c};"></div></div>'
            f'<div class="mc-pct" style="color:{c};">{ordinal(pct_val)} percentile{ps}</div>'
        )
    desc      = METRIC_DESC.get(label, '')
    desc_html = f'<div class="mc-desc" title="{desc}">ⓘ</div>' if desc else ''
    sub_html  = f'<div class="mc-sub">{sub}</div>' if sub else ''
    traj_html = ''
    if trajectory:
        traj_col  = '#4ade80' if trajectory['direction'] == 'up' else ('#f87171' if trajectory['direction'] == 'down' else '#555')
        sign      = '+' if trajectory['pct_change'] > 0 else ''
        traj_html = f'<div class="mc-sub" style="color:{traj_col};font-size:0.68rem">{trajectory["symbol"]} {sign}{trajectory["pct_change"]:.0f}% vs prev 8</div>'
    return (
        f'<div class="mc {vcls}">'
        f'<div style="display:flex;justify-content:space-between;align-items:flex-start">'
        f'<div class="mc-label">{label}</div>{desc_html}</div>'
        f'<div class="mc-value">{value}</div>'
        f'{sub_html}{traj_html}{pct_section}</div>'
    )

def metric_row(cards_html):
    inner = "".join(cards_html)
    return f'<div style="display:grid;grid-template-columns:repeat({len(cards_html)},1fr);gap:10px;margin-bottom:8px">{inner}</div>'

def base_layout(title='', height=320):
    return dict(
        title=dict(text=title, font=dict(color=TEXT_COL, size=12), x=0),
        height=height, plot_bgcolor=PLOT_BG, paper_bgcolor=PAPER_BG,
        font=dict(color=TEXT_COL, size=11), margin=dict(l=10, r=10, t=36, b=90),
        xaxis=dict(gridcolor=GRID_COL, showgrid=False, tickfont=dict(size=9, color='#666'), tickangle=-40),
        yaxis=dict(gridcolor=GRID_COL, showgrid=True, tickfont=dict(size=10, color='#666'), zeroline=False),
        legend=dict(bgcolor='rgba(0,0,0,0)', font=dict(size=10, color='#888'), orientation='h', y=1.08),
        hovermode='x unified', hoverlabel=dict(bgcolor='#1a1a1a', font_size=11),
    )

# ── Player file discovery ─────────────────────────────────────────────────────
def get_player_list():
    """Scan data/players/ for master Excel files. No cache so new files appear immediately."""
    abs_dir = os.path.abspath(PLAYERS_DIR)
    pattern = os.path.join(abs_dir, "*_master.xlsx")
    files   = sorted(glob.glob(pattern))
    return [(os.path.basename(f).replace("_master.xlsx","").replace("_"," "), f) for f in files], abs_dir, pattern

# ── Data loaders ──────────────────────────────────────────────────────────────
@st.cache_data
def load_master(filepath):
    xls = pd.ExcelFile(filepath)
    return {s: pd.read_excel(xls, sheet_name=s)
            for s in ['Wyscout','Physical','Pressing','Off_Ball_Runs','Match_by_Match']
            if s in xls.sheet_names}

@st.cache_data
def load_physical_csv():
    if not os.path.exists(PHYSICAL_CSV): return None
    return pd.read_csv(PHYSICAL_CSV, parse_dates=['match_date'])

@st.cache_data
def load_wyscout_league():
    """Load combined all-player league files for comparison search."""
    dfs = []
    for league, files in WS_FILES.items():
        p = files['all']
        if os.path.exists(p):
            df = pd.read_excel(p)
            df['_league'] = league
            dfs.append(df)
    return pd.concat(dfs, ignore_index=True) if dfs else None

@st.cache_data
def _cached_build_physical_season_averages(phys_csv):
    """Cached wrapper around src.metrics.build_physical_season_averages."""
    return build_physical_season_averages(phys_csv)


@st.cache_data
def find_player_position_file(player_short_name):
    """
    Find which position-specific file a player appears in by name lookup.
    Returns the file key (e.g. 'Central Defender') or None.
    Checks League One first, then League Two.
    """
    for league in ['League One', 'League Two']:
        for pos_key, path in WS_FILES[league].items():
            if pos_key == 'all': continue
            if not os.path.exists(path): continue
            df = pd.read_excel(path)
            if player_short_name in df['Player'].values:
                return pos_key
    return None

@st.cache_data
def load_wyscout_position_file(pos_key, league_filter):
    """Load position-specific file(s) for the given position key and league filter."""
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
        p = WS_FILES.get(league, {}).get(pos_key)
        if p and os.path.exists(p):
            df = pd.read_excel(p)
            df['_league'] = league
            dfs.append(df)
    return pd.concat(dfs, ignore_index=True) if dfs else None

@st.cache_data
def load_matching():
    """Load the SkillCorner↔Wyscout matching file — one row per player (best match score)."""
    if not os.path.exists(MATCHING_CSV): return None
    df = pd.read_csv(MATCHING_CSV)
    return (
        df.sort_values('wyscout_match_score', ascending=False)
        .drop_duplicates(subset='sc_player_id')
        .reset_index(drop=True)
    )

def load_overrides():
    """Load manual overrides CSV — not cached so admin edits apply immediately."""
    if not os.path.exists(OVERRIDES_CSV):
        return pd.DataFrame(columns=['sc_player_id','skillcorner_name','wyscout_name','wyscout_team','notes','updated_at'])
    return pd.read_csv(OVERRIDES_CSV)

# ── Startup validation ────────────────────────────────────────────────────────
from src.validate import run_startup_validation, display_validation_results

@st.cache_data
def get_validation_results():
    return run_startup_validation(PLAYERS_DIR, WS_FILES, MATCHING_CSV, OVERRIDES_CSV)

validation = get_validation_results()
if not validation["all_valid"]:
    display_validation_results(validation)

def resolve_wyscout_name(sc_player_id, fallback_short_name, matching_df, overrides_df):
    """
    Return the correct Wyscout abbreviated name for a SkillCorner player.
    Priority: manual override → high-confidence match (>=0.85) → fallback short name.
    Returns (wyscout_name, source) where source is 'override'|'matching'|'fallback'.
    """
    if overrides_df is not None and len(overrides_df):
        ov = overrides_df[overrides_df['sc_player_id'] == sc_player_id]
        if len(ov):
            return ov.iloc[0]['wyscout_name'], 'override'
    if matching_df is not None:
        row = matching_df[matching_df['sc_player_id'] == sc_player_id]
        if len(row):
            r = row.iloc[0]
            score = r['wyscout_match_score']
            if pd.notna(score) and float(score) >= CONF_THRESHOLD and pd.notna(r['wyscout_name']):
                return r['wyscout_name'], 'matching'
    return fallback_short_name, 'fallback'


def process_wyscout(df):
    return df[df['Minutes played'] >= 20].copy().sort_values('Date').reset_index(drop=True)

def process_physical(df):
    return df[df['minutes_full_all'] >= 20].copy().sort_values('match_date').reset_index(drop=True)

def get_named_ws_peers(pos_key, league_filter, min_mins):
    """Return the full peer DataFrame with Player+Team names (uses position-specific file)."""
    df = load_wyscout_position_file(pos_key, league_filter)
    if df is None: return None
    df = df[pd.to_numeric(df['Minutes played'], errors='coerce') >= min_mins]
    return df.reset_index(drop=True) if len(df) >= 5 else None

def get_named_phys_peers(phys_csv, position_group, min_mins, league_filter):
    """Return aggregated physical peer DataFrame with player names for ranking charts."""
    if phys_csv is None or not position_group: return None
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
        mins         = ('minutes_played_per_match','sum'),
        total_dist   = ('dist_per_match','sum'),
        hsr_dist     = ('hsr_dist_per_match','sum'),
        sprint_dist  = ('sprint_dist_per_match','sum'),
        hsr_count    = ('count_hsr_per_match','sum'),
        sprint_count = ('count_sprint_per_match','sum'),
        hi_accel     = ('count_high_accel_per_match','sum'),
        psv99        = ('top_speed_per_match','mean'),
    ).reset_index()
    agg = agg[agg['mins'] >= min_mins].copy()
    if len(agg) < 5: return None
    agg['total_dist_p90']  = agg['total_dist']  / agg['mins'] * 90
    agg['hsr_dist_p90']    = agg['hsr_dist']    / agg['mins'] * 90
    agg['sprint_dist_p90'] = agg['sprint_dist'] / agg['mins'] * 90
    agg['hi_accel_p90']    = agg['hi_accel']    / agg['mins'] * 90
    agg['psv99_avg']       = agg['psv99']
    return agg


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚽ Beswicks Sports")
    st.markdown("---")
    player_list, _scan_dir, _pattern = get_player_list()
    if not player_list:
        st.warning(f"No player files found.")
        st.code(f"Scanning: {_scan_dir}\nPattern:  {_pattern}\nExists:   {os.path.exists(_scan_dir)}\nContents: {os.listdir(_scan_dir) if os.path.exists(_scan_dir) else 'N/A'}")
        st.stop()
    player_names  = [p[0] for p in player_list]
    selected_name = st.selectbox("Select player", player_names)
    selected_path   = next(p[1] for p in player_list if p[0] == selected_name)
    _player_updated = datetime.fromtimestamp(os.path.getmtime(selected_path)).strftime('%d %b %Y')
    st.caption(f"Updated: {_player_updated}")

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

    st.markdown("---")
    st.markdown("### Override player details")
    st.caption("Leave blank to auto-detect from file.")
    player_club    = st.text_input("Club",     placeholder="e.g. Wycombe Wanderers")
    player_league  = st.text_input("League",   placeholder="e.g. ENG - League One")
    player_pos_ovr = st.text_input("Position", placeholder="e.g. Right Centre-Back")
    player_age     = st.number_input("Age", min_value=15, max_value=45, value=24)

    st.markdown("---")
    st.markdown("### Position file override")
    st.caption("Auto-detected from player name. Override if the wrong file is selected.")
    _pos_file_options = ["Auto-detect"] + list(WS_FILES.get("League One", {}).keys())
    _pos_file_options_display = [o for o in _pos_file_options if o != "all"]
    pos_file_override = st.selectbox(
        "Position file",
        _pos_file_options_display,
        index=0,
        help="Select the correct position group file if auto-detection is wrong."
    )

    st.markdown("---")
    st.markdown("### Export")
    report_audience = st.radio("Report audience", ["Internal", "Player", "Club"], horizontal=True,
                               help="Changes colour treatment, section order, and header label in the PDF.")
    if os.path.exists(PHYSICAL_CSV):
        _phys_updated = datetime.fromtimestamp(os.path.getmtime(PHYSICAL_CSV)).strftime('%d %b %Y')
        st.caption(f"Physical data: {_phys_updated}")
    export_btn = st.button("📄 Generate PDF report", use_container_width=True, help="Exports player profile, metrics, radar chart and match log as a branded PDF.")
    st.caption("Beswicks Sports Analytics · Internal Use Only")

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="header-bar">
  <div><h1>Player Analysis Platform</h1><div class="sub">Wyscout + SkillCorner · 2025/26 Season</div></div>
  <div class="beswicks-badge">Beswicks Sports</div>
</div>
""", unsafe_allow_html=True)

# ── Load ──────────────────────────────────────────────────────────────────────
with st.spinner(f"Loading {selected_name}..."):
    sheets       = load_master(selected_path)
    phys_csv     = load_physical_csv()
    league_df    = load_wyscout_league()
    matching_df  = load_matching()
    overrides_df = load_overrides()
    phys_avgs    = _cached_build_physical_season_averages(phys_csv)

ws_raw = sheets.get('Wyscout')
ph_raw = sheets.get('Physical')
if ws_raw is None:
    st.error("Could not find a 'Wyscout' sheet in this player's file.")
    st.stop()

ws = process_wyscout(ws_raw)
ph = process_physical(ph_raw) if ph_raw is not None else None
season = get_season_totals(ws)
phys   = get_physical_totals(ph) if ph is not None else None

# ── Metadata ──────────────────────────────────────────────────────────────────
if ph_raw is not None and 'player_name' in ph_raw.columns:
    full_name      = ph_raw['player_name'].iloc[0]
    fallback_short = ph_raw['player_short_name'].iloc[0] if 'player_short_name' in ph_raw.columns else selected_name
    sc_player_id   = int(ph_raw['sc_player_id'].iloc[0]) if 'sc_player_id' in ph_raw.columns else None
    position_group = ph_raw['position_group'].iloc[0]    if 'position_group'    in ph_raw.columns else None
    club_from_file = ph_raw['team_name'].iloc[0]         if 'team_name'         in ph_raw.columns else ""
else:
    full_name=selected_name; fallback_short=selected_name
    sc_player_id=None; position_group=None; club_from_file=""

# Resolve correct Wyscout name: override > high-confidence match > fallback
short_name, match_source = resolve_wyscout_name(sc_player_id, fallback_short, matching_df, overrides_df)

name    = full_name
club    = player_club    or club_from_file
league  = player_league  or ""
pos     = player_pos_ovr or (position_group or "")
age_val = player_age

# ── Resolve position file key from player name lookup ─────────────────────────
# Uses the player's Wyscout short name to find which position-specific file
# they appear in — more reliable than mapping from SkillCorner position_group
ws_pos_key = find_player_position_file(short_name) if short_name else None
# Apply manual position file override from sidebar
if pos_file_override and pos_file_override != "Auto-detect":
    ws_pos_key = pos_file_override

# Defaults for peer-file-only metrics (populated below if player is found in league file)
for _k in ('key_passes_p90','smart_passes_p90','smart_pass_acc',
           'third_asts_p90','deep_comp_p90','deep_crosses_p90','prog_passes_p90',
           'prog_pass_acc','lat_passes_p90','lat_pass_acc','avg_pass_length',
           'recv_lp_p90','padj_interceptions','padj_slide_tackles','shots_blocked_p90'):
    season.setdefault(_k, None)

# ── Override season metrics with league file values where more accurate ────────
# Always look up the player's OWN league (not the peer filter) so the stat
# doesn't change when the user toggles the league filter.
if ws_pos_key and short_name:
    # Determine which league the player actually plays in
    player_league_key = None
    for _league in ['League One', 'League Two']:
        _path = WS_FILES.get(_league, {}).get(ws_pos_key)
        if _path and os.path.exists(_path):
            _df = pd.read_excel(_path)
            if short_name in _df['Player'].values:
                player_league_key = _league
                break
    # Load that specific league file (not the peer filter)
    _lookup_league = player_league_key if player_league_key else peer_league
    pos_df = load_wyscout_position_file(ws_pos_key, _lookup_league)
    if pos_df is not None:
        player_row = pos_df[pos_df['Player'] == short_name]
        if len(player_row) > 0:
            r = player_row.iloc[0]
            def _lf(col):
                try: return float(r[col]) if col in pos_df.columns else None
                except: return None
            # Override recoveries_p90 with league file 'Successful defensive actions per 90'
            if _lf('Successful defensive actions per 90') is not None:
                season['recoveries_p90'] = _lf('Successful defensive actions per 90')
            # Supplement season dict with metrics only available in the league-wide file
            season['key_passes_p90']    = _lf('Key passes per 90')
            season['smart_passes_p90']  = _lf('Smart passes per 90')
            season['smart_pass_acc']    = _lf('Accurate smart passes, %')
            season['third_asts_p90']    = _lf('Third assists per 90')
            season['deep_comp_p90']     = _lf('Deep completions per 90')
            season['deep_crosses_p90']  = _lf('Deep completed crosses per 90')
            season['prog_passes_p90']   = _lf('Progressive passes per 90')
            season['prog_pass_acc']     = _lf('Accurate progressive passes, %')
            season['lat_passes_p90']    = _lf('Lateral passes per 90')
            season['lat_pass_acc']      = _lf('Accurate lateral passes, %')
            season['avg_pass_length']   = _lf('Average pass length, m')
            season['recv_lp_p90']       = _lf('Received long passes per 90')
            season['padj_interceptions']= _lf('PAdj Interceptions')
            season['padj_slide_tackles']= _lf('PAdj Sliding tackles')
            season['shots_blocked_p90'] = _lf('Shots blocked per 90')

# ── Peer groups ───────────────────────────────────────────────────────────────
phys_peers, phys_peer_n = build_physical_peers(phys_csv, position_group, min_mins_peer, peer_league)
ws_peers,   ws_peer_n   = build_wyscout_peers(ws_pos_key, peer_league, min_mins_peer, WS_FILES) if ws_pos_key else ({}, 0)
# Named peer dataframes for ranking charts
ws_peers_named   = get_named_ws_peers(ws_pos_key, peer_league, min_mins_peer) if ws_pos_key else None
phys_peers_named = get_named_phys_peers(phys_csv, position_group, min_mins_peer, peer_league)

def gp(key, value, inverse=False):
    series = ws_peers.get(key) if key in ws_peers else phys_peers.get(key)
    if series is None or value is None: return None
    return percentile_rank(value, series, inverse=inverse)

def gpp(key, value, inverse=False):
    series = phys_peers.get(key)
    if series is None or value is None: return None
    return percentile_rank(value, series, inverse=inverse)

try:
    date_start = pd.to_datetime(ws['Date'].min()).strftime('%d %b %Y')
    date_end   = pd.to_datetime(ws['Date'].max()).strftime('%d %b %Y')
except Exception:
    date_start, date_end = "–","–"

peer_desc = f"{' + '.join(peer_league) if isinstance(peer_league, list) else peer_league} · {min_mins_peer}+ mins · position-specific file"

# ── Profile card ──────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="profile-card">
  <div class="profile-name">{name}</div>
  <div class="profile-meta">{club} · {league} · Season 2025/26</div>
  <div class="profile-tags">
    <span class="tag tag-gold">{pos}</span>
    <span class="tag">Age {age_val}</span>
    <span class="tag">{season['matches']} appearances</span>
    <span class="tag">{int(season['mins'])} mins</span>
    <span class="tag">{date_start} → {date_end}</span>
    <span class="tag">{season['goals_raw']}G · {season['assists_raw']}A</span>
    <span class="tag">{season['yellow']} YC · {season['red']} RC</span>
  </div>
</div>""", unsafe_allow_html=True)

# ── Peer banners ──────────────────────────────────────────────────────────────
c1, c2 = st.columns(2)
with c1:
    if phys_peer_n > 0:
        st.markdown(f'<div class="peer-banner">✓ Physical peers · {phys_peer_n} {position_group}s · {peer_desc}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="peer-banner peer-banner-warn">⚠ Physical peer group unavailable — try relaxing filters</div>', unsafe_allow_html=True)
with c2:
    if ws_peer_n > 0:
        source_badge = {'override':'🔧 override','matching':'🔗 matched','fallback':'⚠ fallback'}.get(match_source,'')
        st.markdown(f'<div class="peer-banner">✓ Wyscout peers · {ws_peer_n} players · {peer_desc} · <b>{short_name}</b> {source_badge}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="peer-banner peer-banner-warn">⚠ Wyscout peer group unavailable — try relaxing filters</div>', unsafe_allow_html=True)

# ── Trajectory indicators (last 8 vs previous 8 matches, per-90) ──────────────
_traj_goals   = compute_trajectory(ws, 'Goals')
_traj_xg      = compute_trajectory(ws, 'xG')
_traj_passes  = compute_trajectory(ws, 'Passes')
_traj_duels   = compute_trajectory(ws, 'Duels')

# ── Seasonal metrics ──────────────────────────────────────────────────────────
st.markdown('<div class="section-header">Seasonal metrics · per 90</div>', unsafe_allow_html=True)

_tab_labels = ["Attacking", "Passing", "Key passing", "Defensive"]
if phys:
    _tab_labels.append("Physical")

_tabs = st.tabs(_tab_labels)
_tab = {label: tab for label, tab in zip(_tab_labels, _tabs)}

# ── Attacking tab ──────────────────────────────────────────────────────────────
with _tab["Attacking"]:
    pa = season['pass_acc']
    st.markdown(metric_row([
        metric_card("Goals p90",      f"{season['goals_p90']:.2f}",      f"{season['goals_raw']} raw",   "mc-good" if season['goals_raw']>=2 else "",     gp('goals_p90',      season.get('goals_p90')),      ws_peer_n, trajectory=_traj_goals),
        metric_card("Assists p90",    f"{season['assists_p90']:.2f}",    f"{season['assists_raw']} raw", "",                                               gp('assists_p90',    season.get('assists_p90')),    ws_peer_n),
        metric_card("xG p90",         f"{season['xg_p90']:.2f}",         "",                             "",                                               gp('xg_p90',         season.get('xg_p90')),         ws_peer_n, trajectory=_traj_xg),
        metric_card("Shots p90",      f"{season.get('shots_p90', 0):.2f}", f"{season.get('shots_on_tgt_pct'):.1f}% on tgt" if season.get('shots_on_tgt_pct') else "", "", gp('shots_p90', season.get('shots_p90')), ws_peer_n),
        metric_card("Goal conv %",    f"{season.get('goal_conv_pct'):.1f}%" if season.get('goal_conv_pct') else "–", "",                                   "", gp('goal_conv_pct', season.get('goal_conv_pct')), ws_peer_n),
    ]), unsafe_allow_html=True)
    st.markdown(metric_row([
        metric_card("xA p90",         f"{season['xa_p90']:.2f}",         "",                             "",                                               gp('xa_p90',         season.get('xa_p90')),         ws_peer_n),
        metric_card("Shot asts p90",  f"{season['shot_asts_p90']:.2f}",  "",                             "mc-good" if season['shot_asts_p90']>0.5 else "",  gp('shot_asts_p90',  season.get('shot_asts_p90')),  ws_peer_n),
        metric_card("Touches in box", f"{season['touches_box_p90']:.2f}","per 90",                       "",                                               gp('touches_box_p90',season.get('touches_box_p90')), ws_peer_n),
        metric_card("Off duels p90",  f"{season.get('off_duels_p90', 0):.2f}", f"{season.get('off_duel_win'):.1f}% win" if season.get('off_duel_win') else "", "", gp('off_duels_p90', season.get('off_duels_p90')), ws_peer_n),
        metric_card("Dribbles p90",   f"{season['dribbles_p90']:.2f}",   f"{season['drib_pct']:.1f}% success" if season['drib_pct'] else "", "mc-good" if season['drib_pct'] and season['drib_pct']>60 else "", gp('dribbles_p90', season.get('dribbles_p90')), ws_peer_n),
        metric_card("Prog runs p90",  f"{season['prog_runs_p90']:.2f}",  "",                             "",                                               gp('prog_runs_p90',  season.get('prog_runs_p90')),  ws_peer_n),
        metric_card("Fouls suffered", f"{season.get('fouls_suffered_p90', 0):.2f}", "per 90",            "",                                               gp('fouls_suffered_p90', season.get('fouls_suffered_p90')), ws_peer_n),
    ]), unsafe_allow_html=True)

# ── Passing tab ────────────────────────────────────────────────────────────────
with _tab["Passing"]:
    pa = season['pass_acc']
    st.markdown(metric_row([
        metric_card("Passes p90",     f"{season['passes_p90']:.1f}",     f"{pa:.1f}% accuracy" if pa else "",          "mc-good" if pa and pa>80 else "mc-warn" if pa and pa>70 else "mc-bad", gp('passes_p90',    season.get('passes_p90')),    ws_peer_n, trajectory=_traj_passes),
        metric_card("Fwd passes p90", f"{season.get('fwd_passes_p90', 0):.1f}", f"{season.get('fwd_pass_acc'):.1f}% acc" if season.get('fwd_pass_acc') else "",  "", gp('fwd_passes_p90', season.get('fwd_passes_p90')), ws_peer_n),
        metric_card("Back passes p90",f"{season.get('back_passes_p90', 0):.1f}",f"{season.get('back_pass_acc'):.1f}% acc" if season.get('back_pass_acc') else "", "", gp('back_passes_p90', season.get('back_passes_p90')), ws_peer_n),
        metric_card("Long pass p90",  f"{season['long_passes_p90']:.2f}",f"{season['lp_acc']:.1f}% acc" if season['lp_acc'] else "",             "", gp('long_passes_p90', season.get('long_passes_p90')), ws_peer_n),
        metric_card("Crosses p90",    f"{season['crosses_p90']:.2f}",    f"{season.get('cross_acc_pct'):.1f}% acc" if season.get('cross_acc_pct') else "", "", gp('crosses_p90', season.get('crosses_p90')), ws_peer_n),
    ]), unsafe_allow_html=True)
    st.markdown(metric_row([
        metric_card("Through passes", f"{season.get('through_passes_p90', 0):.2f}", f"{season.get('through_pass_acc'):.1f}% acc" if season.get('through_pass_acc') else "", "", gp('through_passes_p90', season.get('through_passes_p90')), ws_peer_n),
        metric_card("Recv passes p90",f"{season.get('recv_passes_p90', 0):.1f}",   "per 90",                                                                         "", gp('recv_passes_p90', season.get('recv_passes_p90')), ws_peer_n),
    ]), unsafe_allow_html=True)
    _pass_extras = [c for c in [
        metric_card("Lateral passes", f"{season['lat_passes_p90']:.1f}", f"{season['lat_pass_acc']:.1f}% acc" if season['lat_pass_acc'] else "", "", gp('lat_passes_p90', season.get('lat_passes_p90')), ws_peer_n) if season.get('lat_passes_p90') is not None else None,
        metric_card("Recv long passes",f"{season['recv_lp_p90']:.2f}", "per 90", "", gp('recv_lp_p90', season.get('recv_lp_p90')), ws_peer_n) if season.get('recv_lp_p90') is not None else None,
        metric_card("Avg pass length", f"{season['avg_pass_length']:.1f}m", "season avg", "", None, ws_peer_n) if season.get('avg_pass_length') is not None else None,
    ] if c is not None]
    if _pass_extras:
        st.markdown(metric_row(_pass_extras), unsafe_allow_html=True)

# ── Key passing tab ────────────────────────────────────────────────────────────
with _tab["Key passing"]:
    st.markdown(metric_row([
        metric_card("xA p90",         f"{season['xa_p90']:.2f}",         "",                                                                          "", gp('xa_p90',         season.get('xa_p90')),         ws_peer_n),
        metric_card("Shot asts p90",  f"{season['shot_asts_p90']:.2f}",  "",                                                                          "mc-good" if season['shot_asts_p90']>0.5 else "", gp('shot_asts_p90', season.get('shot_asts_p90')), ws_peer_n),
        metric_card("2nd assists p90",f"{season.get('second_asts_p90', 0):.2f}","",                                                                     "", gp('second_asts_p90', season.get('second_asts_p90')), ws_peer_n),
        metric_card("PTF3 p90",       f"{season['ptf3_p90']:.2f}",       f"{season.get('ptf3_acc_pct'):.1f}% acc" if season.get('ptf3_acc_pct') else "", "", gp('ptf3_p90', season.get('ptf3_p90')), ws_peer_n),
        metric_card("Pass to box p90",f"{season.get('ppa_p90', 0):.2f}", f"{season.get('ppa_acc_pct'):.1f}% acc" if season.get('ppa_acc_pct') else "",   "", gp('ppa_p90',  season.get('ppa_p90')),  ws_peer_n),
    ]), unsafe_allow_html=True)
    _kp_extras = [c for c in [
        metric_card("Key passes p90",  f"{season['key_passes_p90']:.2f}",  "per 90",                                                                    "", gp('key_passes_p90',   season.get('key_passes_p90')),  ws_peer_n) if season.get('key_passes_p90')  is not None else None,
        metric_card("Smart passes p90",f"{season['smart_passes_p90']:.2f}",f"{season['smart_pass_acc']:.1f}% acc" if season['smart_pass_acc'] else "",  "", gp('smart_passes_p90', season.get('smart_passes_p90')),ws_peer_n) if season.get('smart_passes_p90') is not None else None,
        metric_card("3rd assists p90", f"{season['third_asts_p90']:.2f}",  "per 90",                                                                    "", gp('third_asts_p90',   season.get('third_asts_p90')),  ws_peer_n) if season.get('third_asts_p90')  is not None else None,
        metric_card("Deep comp p90",   f"{season['deep_comp_p90']:.2f}",   "per 90",                                                                    "", gp('deep_comp_p90',    season.get('deep_comp_p90')),   ws_peer_n) if season.get('deep_comp_p90')   is not None else None,
        metric_card("Deep crosses p90",f"{season['deep_crosses_p90']:.2f}","per 90",                                                                    "", gp('deep_crosses_p90', season.get('deep_crosses_p90')),ws_peer_n) if season.get('deep_crosses_p90') is not None else None,
        metric_card("Prog passes p90", f"{season['prog_passes_p90']:.2f}", f"{season['prog_pass_acc']:.1f}% acc" if season['prog_pass_acc'] else "",    "", gp('prog_passes_p90',  season.get('prog_passes_p90')), ws_peer_n) if season.get('prog_passes_p90') is not None else None,
    ] if c is not None]
    if _kp_extras:
        st.markdown(metric_row(_kp_extras), unsafe_allow_html=True)

# ── Defensive tab ──────────────────────────────────────────────────────────────
with _tab["Defensive"]:
    st.markdown(metric_row([
        metric_card("Duels p90",      f"{season['duels_p90']:.1f}",      f"{season['duel_win']:.1f}% win rate",                                 "mc-warn" if season['duel_win'] and season['duel_win']<55 else "mc-good",       gp('duels_p90',     season.get('duels_p90')),     ws_peer_n, trajectory=_traj_duels),
        metric_card("Aerial p90",     f"{season['aerial_p90']:.2f}",     f"{season['aerial_win']:.1f}% win rate" if season['aerial_win'] else "", "",                                                                            gp('aerial_p90',    season.get('aerial_p90')),    ws_peer_n),
        metric_card("Def duels p90",  f"{season['def_duels_p90']:.2f}",  f"{season['def_duel_win']:.1f}% win rate" if season['def_duel_win'] else "", "mc-warn" if season['def_duel_win'] and season['def_duel_win']<60 else "mc-good", gp('def_duels_p90', season.get('def_duels_p90')), ws_peer_n),
        metric_card("Loose ball p90", f"{season.get('loose_duels_p90', 0):.2f}", f"{season.get('loose_duel_win'):.1f}% win" if season.get('loose_duel_win') else "", "", gp('loose_duels_p90', season.get('loose_duels_p90')), ws_peer_n),
        metric_card("Slide tackles",  f"{season.get('slide_tackles_p90', 0):.2f}", f"{season.get('slide_tackle_pct'):.1f}% success" if season.get('slide_tackle_pct') else "", "", gp('slide_tackles_p90', season.get('slide_tackles_p90')), ws_peer_n),
    ]), unsafe_allow_html=True)
    st.markdown(metric_row([
        metric_card("Interceptions",  f"{season['interceptions_p90']:.2f}","per 90",                                                               "mc-good" if season['interceptions_p90']>4 else "",                           gp('interceptions_p90', season.get('interceptions_p90')), ws_peer_n),
        metric_card("Recoveries p90", f"{season['recoveries_p90']:.2f}",  f"Opp half: {season['rec_opp_p90']:.2f}",                              "",                                                                            gp('recoveries_p90',season.get('recoveries_p90')),    ws_peer_n),
        metric_card("Clearances p90", f"{season['clearances_p90']:.2f}",  "per 90",                                                               "",                                                                            None, ws_peer_n),
        metric_card("Losses p90",     f"{season['losses_p90']:.2f}",      f"Own half: {season['losses_oh_p90']:.2f}",                            "mc-bad" if season['losses_p90']>12 else "mc-warn",                            gp('losses_p90',    season.get('losses_p90'), True), ws_peer_n),
        metric_card("Fouls p90",      f"{season['fouls_p90']:.2f}",       "per 90",                                                               "mc-warn" if season['fouls_p90']>2.5 else "",                                  gp('fouls_p90',     season.get('fouls_p90'), True),  ws_peer_n),
    ]), unsafe_allow_html=True)
    _def_extras = [c for c in [
        metric_card("Shots blocked",    f"{season['shots_blocked_p90']:.2f}",  "per 90", "", gp('shots_blocked_p90',   season.get('shots_blocked_p90')),   ws_peer_n) if season.get('shots_blocked_p90')   is not None else None,
        metric_card("PAdj interceptions",f"{season['padj_interceptions']:.2f}","PAdj",   "", gp('padj_interceptions',  season.get('padj_interceptions')),   ws_peer_n) if season.get('padj_interceptions')  is not None else None,
        metric_card("PAdj slide tackles",f"{season['padj_slide_tackles']:.2f}","PAdj",   "", gp('padj_slide_tackles',  season.get('padj_slide_tackles')),   ws_peer_n) if season.get('padj_slide_tackles')  is not None else None,
    ] if c is not None]
    if _def_extras:
        st.markdown(metric_row(_def_extras), unsafe_allow_html=True)

# ── Physical tab (SkillCorner) ─────────────────────────────────────────────────
if phys:
    with _tab["Physical"]:
        st.markdown("**Output**")
        st.markdown(metric_row([
            metric_card("Total dist p90",  f"{int(phys['total_dist_p90']):,}m", "SkillCorner",                             'mc-good', gpp('total_dist_p90',  phys.get('total_dist_p90')),  phys_peer_n),
            metric_card("HSR dist p90",    f"{int(phys['hsr_dist_p90'])}m",     f"{phys['hsr_count_p90']:.0f} reps",       'mc-good', gpp('hsr_dist_p90',    phys.get('hsr_dist_p90')),    phys_peer_n),
            metric_card("Sprint dist p90", f"{int(phys['sprint_dist_p90'])}m",  f"{phys['sprint_count_p90']:.0f} sprints", 'mc-good', gpp('sprint_dist_p90', phys.get('sprint_dist_p90')), phys_peer_n),
            metric_card("Hi accels p90",   f"{phys['hi_accel_p90']:.0f}",       "SkillCorner",                             'mc-good', gpp('hi_accel_p90',    phys.get('hi_accel_p90')),    phys_peer_n),
            metric_card("PSV99 avg",       str(phys['psv99_avg']),              f"Peak: {phys['psv99_max']}",              'mc-good', gpp('psv99_avg',       phys.get('psv99_avg')),        phys_peer_n),
            metric_card("COD count p90",   f"{phys['cod_p90']:.0f}",            "Changes of direction"),
        ]), unsafe_allow_html=True)

        pressing_raw = sheets.get('Pressing')
        if pressing_raw is not None:
            press = pressing_raw[pressing_raw['minutes_played_per_match'] >= 20]
            if len(press) > 0:
                st.markdown("**Under-pressure passing**")
                avg_ret  = press['ball_retention_ratio_under_pressure'].mean()
                avg_comp = press['pass_completion_ratio_under_pressure'].mean()
                avg_pres = press['count_pressures_received_per_match'].mean()
                c1, c2, c3 = st.columns(3)
                c1.markdown(metric_card("Pressures received p90",   f"{avg_pres:.1f}"),                                                  unsafe_allow_html=True)
                c2.markdown(metric_card("Ball retention under press",f"{avg_ret:.1f}%",  vcls="mc-warn" if avg_ret <70 else "mc-good"),  unsafe_allow_html=True)
                c3.markdown(metric_card("Pass comp under press",     f"{avg_comp:.1f}%", vcls="mc-warn" if avg_comp<70 else "mc-good"),  unsafe_allow_html=True)

        obr_raw = sheets.get('Off_Ball_Runs')
        if obr_raw is not None:
            obr = obr_raw[obr_raw['minutes_played_per_match'] >= 20]
            if len(obr) > 0:
                st.markdown("**Off-ball runs**")
                c1, c2, c3, c4 = st.columns(4)
                c1.markdown(metric_card("Runs per match", f"{obr['count_runs_per_match'].mean():.1f}"),           unsafe_allow_html=True)
                c2.markdown(metric_card("Dangerous runs", f"{obr['count_dangerous_runs_per_match'].mean():.1f}"), unsafe_allow_html=True)
                c3.markdown(metric_card("Runs targeted",  f"{obr['count_runs_targeted_per_match'].mean():.1f}"),  unsafe_allow_html=True)
                c4.markdown(metric_card("Runs received",  f"{obr['count_runs_received_per_match'].mean():.1f}"),  unsafe_allow_html=True)

# ── Percentile radar ──────────────────────────────────────────────────────────
if ws_peer_n >= 5:
    st.markdown('<div class="section-header">Percentile profile · vs peer group</div>', unsafe_allow_html=True)
    radar_keys = [
        ('Goals p90','goals_p90',False),('xG p90','xg_p90',False),
        ('Shot asts p90','shot_asts_p90',False),('Pass acc %','pass_acc',False),
        ('Dribbles p90','dribbles_p90',False),('Prog runs p90','prog_runs_p90',False),
        ('Crosses p90','crosses_p90',False),('Duels p90','duels_p90',False),
        ('Duel win %','duel_win',False),('Aerial p90','aerial_p90',False),
        ('Interceptions','interceptions_p90',False),('Recoveries p90','recoveries_p90',False),
    ]
    if phys and phys_peer_n >= 5:
        radar_keys += [('HSR dist p90','hsr_dist_p90',False),('Sprint dist p90','sprint_dist_p90',False)]

    radar_data = {}
    for label, key, inv in radar_keys:
        val   = season.get(key) or (phys.get(key) if phys else None)
        pct_v = gp(key,val,inv) or gpp(key,val,inv)
        if pct_v is not None: radar_data[label] = pct_v

    if len(radar_data) >= 5:
        labels = list(radar_data.keys()); values = list(radar_data.values())
        lc = labels+[labels[0]]; vc = values+[values[0]]
        fig_r = go.Figure()
        fig_r.add_trace(go.Scatterpolar(r=vc,theta=lc,fill='toself',
            fillcolor='rgba(200,164,90,0.15)',line=dict(color=GOLD,width=2),name=name))
        fig_r.add_trace(go.Scatterpolar(r=[50]*len(lc),theta=lc,mode='lines',
            line=dict(color='#444',width=1,dash='dot'),name='League avg (50th)'))
        fig_r.update_layout(
            polar=dict(bgcolor=PLOT_BG,
                radialaxis=dict(visible=True,range=[0,100],tickfont=dict(size=9,color='#555'),gridcolor='#2a2a2a',linecolor='#333'),
                angularaxis=dict(tickfont=dict(size=10,color=TEXT_COL),gridcolor='#2a2a2a',linecolor='#333')),
            paper_bgcolor=PAPER_BG,showlegend=True,
            legend=dict(bgcolor='rgba(0,0,0,0)',font=dict(color='#888',size=10)),
            height=460,margin=dict(l=60,r=60,t=30,b=30),
        )
        col_r,col_s = st.columns([3,2])
        with col_r: st.plotly_chart(fig_r,use_container_width=True)
        with col_s:
            st.markdown(f"<p style='color:#666;font-size:0.75rem;margin:30px 0 16px'>vs {ws_peer_n} players · {peer_desc}</p>",unsafe_allow_html=True)
            top3    = sorted(radar_data.items(),key=lambda x:x[1],reverse=True)[:3]
            bottom3 = sorted(radar_data.items(),key=lambda x:x[1])[:3]
            st.markdown("<p style='color:#4ade80;font-size:0.72rem;font-weight:700;letter-spacing:0.06em;margin:0 0 6px'>STRENGTHS</p>",unsafe_allow_html=True)
            for lbl,val in top3:
                st.markdown(f"<p style='color:#ccc;font-size:0.82rem;margin:4px 0'>{lbl} &nbsp;<span style='color:#4ade80;font-weight:600'>{ordinal(val)}</span></p>",unsafe_allow_html=True)
            st.markdown("<p style='color:#f87171;font-size:0.72rem;font-weight:700;letter-spacing:0.06em;margin:16px 0 6px'>BELOW AVERAGE</p>",unsafe_allow_html=True)
            for lbl,val in bottom3:
                st.markdown(f"<p style='color:#ccc;font-size:0.82rem;margin:4px 0'>{lbl} &nbsp;<span style='color:#f87171;font-weight:600'>{ordinal(val)}</span></p>",unsafe_allow_html=True)

# ── Physical charts ───────────────────────────────────────────────────────────
if ph is not None and len(ph) > 0:
    st.markdown('<div class="section-header">Physical output · match by match</div>', unsafe_allow_html=True)
    ph['match_label']  = ph.apply(lambda r: parse_physical_label(r['match_name'], r['team_name']), axis=1)
    ph['dist_p90_m']   = ph.apply(lambda r: p90(r['total_distance_full_all'],  r['minutes_full_all']), axis=1)
    ph['hsr_p90_m']    = ph.apply(lambda r: p90(r['hsr_distance_full_all'],    r['minutes_full_all']), axis=1)
    ph['sprint_p90_m'] = ph.apply(lambda r: p90(r['sprint_distance_full_all'], r['minutes_full_all']), axis=1)
    ph_mins = ph['minutes_full_all']
    avg_dist = ph['dist_p90_m'].mean()
    avg_hsr  = ph['hsr_p90_m'].mean()
    opac = mins_to_opacity(ph_mins)

    st.caption("💡 Bar opacity = minutes played (lighter = shorter appearance) · Purple line = 5-match rolling average")

    tab1,tab2,tab3 = st.tabs(["Distance","HSR & Sprint","PSV99 & Accelerations"])

    with tab1:
        bar_cols = [rgba(GOLD,opac[i]) if ph['dist_p90_m'].iloc[i]>=avg_dist else rgba('#333333',opac[i]) for i in range(len(ph))]
        fig = go.Figure()
        fig.add_bar(x=ph['match_label'],y=ph['dist_p90_m'],marker_color=bar_cols,name='Dist p90',
            customdata=ph_mins,hovertemplate='%{x}<br>%{y:,.0f}m · %{customdata:.0f} mins<extra></extra>')
        fig.add_scatter(x=ph['match_label'],y=[avg_dist]*len(ph),mode='lines',
            name=f'Player avg ({avg_dist:,.0f}m)',line=dict(color=GOLD,width=1.5,dash='dot'),hoverinfo='skip')
        fig.add_scatter(x=ph['match_label'],y=rolling_avg(ph['dist_p90_m']),mode='lines',
            name='5-match rolling avg',line=dict(color=PURPLE,width=2),hovertemplate='Rolling avg: %{y:,.0f}m<extra></extra>')
        if 'total_dist_p90' in phys_peers:
            la=phys_peers['total_dist_p90'].mean()
            fig.add_scatter(x=ph['match_label'],y=[la]*len(ph),mode='lines',
                name=f'Position avg ({la:,.0f}m)',line=dict(color='#888',width=1.5,dash='dash'),hoverinfo='skip')
        fig.update_layout(**base_layout('Total distance per 90 (m)',height=320))
        fig.update_yaxes(range=[8000,ph['dist_p90_m'].max()*1.08])
        st.plotly_chart(fig,use_container_width=True)

    with tab2:
        fig2=go.Figure()
        fig2.add_bar(x=ph['match_label'],y=ph['hsr_p90_m'],name='HSR dist p90',
            marker_color=colour_list(BLUE,opac),
            customdata=ph_mins,hovertemplate='%{x}<br>HSR: %{y:.0f}m · %{customdata:.0f} mins<extra></extra>')
        fig2.add_bar(x=ph['match_label'],y=ph['sprint_p90_m'],name='Sprint dist p90',
            marker_color=colour_list(GOLD,opac),
            customdata=ph_mins,hovertemplate='%{x}<br>Sprint: %{y:.0f}m · %{customdata:.0f} mins<extra></extra>')
        fig2.add_scatter(x=ph['match_label'],y=[avg_hsr]*len(ph),mode='lines',
            name=f'Player HSR avg ({avg_hsr:.0f}m)',line=dict(color=BLUE,width=1.5,dash='dot'),hoverinfo='skip')
        fig2.add_scatter(x=ph['match_label'],y=rolling_avg(ph['hsr_p90_m']),mode='lines',
            name='HSR rolling avg',line=dict(color=PURPLE,width=2),hovertemplate='Rolling avg: %{y:.0f}m<extra></extra>')
        if 'hsr_dist_p90' in phys_peers:
            la=phys_peers['hsr_dist_p90'].mean()
            fig2.add_scatter(x=ph['match_label'],y=[la]*len(ph),mode='lines',
                name=f'Position HSR avg ({la:.0f}m)',line=dict(color='#888',width=1.5,dash='dash'),hoverinfo='skip')
        fig2.update_layout(**base_layout('HSR & sprint distance per 90 (m)',height=320),barmode='group')
        st.plotly_chart(fig2,use_container_width=True)

    with tab3:
        fig3=make_subplots(specs=[[{"secondary_y":True}]])
        avg_psv=ph['psv99'].mean()
        fig3.add_scatter(x=ph['match_label'],y=ph['psv99'],mode='lines+markers',name='PSV99',
            line=dict(color=GREEN,width=2),marker=dict(size=5,color=GREEN),
            hovertemplate='%{x}<br>PSV99: %{y:.2f}<extra></extra>',secondary_y=False)
        fig3.add_scatter(x=ph['match_label'],y=[avg_psv]*len(ph),mode='lines',name=f'Avg ({avg_psv:.2f})',
            line=dict(color='#555',width=1,dash='dot'),hoverinfo='skip',secondary_y=False)
        if 'psv99_avg' in phys_peers:
            la=phys_peers['psv99_avg'].mean()
            fig3.add_scatter(x=ph['match_label'],y=[la]*len(ph),mode='lines',
                name=f'Position avg ({la:.2f})',line=dict(color='#888',width=1.5,dash='dash'),hoverinfo='skip',secondary_y=False)
        fig3.add_bar(x=ph['match_label'],
            y=ph.apply(lambda r:p90(r['highaccel_count_full_all'],r['minutes_full_all']),axis=1),
            name='High accel p90',marker_color=colour_list(GOLD,opac),
            customdata=ph_mins,hovertemplate='%{x}<br>High accel: %{y:.1f} · %{customdata:.0f} mins<extra></extra>',
            secondary_y=True)
        fig3.update_layout(**base_layout('PSV99 & high accelerations per 90',height=320))
        fig3.update_yaxes(range=[7.0,ph['psv99'].max()+0.3],secondary_y=False,
            title_text='PSV99',title_font=dict(size=10,color='#555'))
        fig3.update_yaxes(secondary_y=True,title_text='High accel p90',
            title_font=dict(size=10,color='#555'),showgrid=False)
        st.plotly_chart(fig3,use_container_width=True)

# ── Form trends ───────────────────────────────────────────────────────────────
st.markdown('<div class="section-header">Form trends · match by match (last 20 league games)</div>', unsafe_allow_html=True)

# Limit to most recent 20 league matches (League One or League Two) for clarity
ws = ws[ws['Competition'].str.contains('League One|League Two', na=False)].sort_values('Date', ascending=True).tail(20).reset_index(drop=True)

ws['match_label']      = ws.apply(lambda r: parse_wyscout_label(r['Match'], club or club_from_file), axis=1)
ws['duel_win_pct']     = ws.apply(lambda r: pct(r.iloc[21],r['Duels']),          axis=1)
ws['def_duel_win_pct'] = ws.apply(lambda r: pct(r.iloc[32],r.iloc[31]),           axis=1)
ws['losses_raw']       = ws['Losses'].fillna(0)
ws['ptf3_raw']         = ws['Passes to final third'].fillna(0)
ws['shot_ast_raw']     = ws['Shot assists'].fillna(0)
ws['pass_acc_pct']     = ws.apply(lambda r: pct(r.iloc[13],r['Passes']), axis=1)
ws['def_duels_raw']    = ws.iloc[:,31].fillna(0)
ws['aerial_raw']       = ws['Aerial duels'].fillna(0)
ws['int_raw']          = ws['Interceptions'].fillna(0)
ws['rec_raw']          = ws['Recoveries'].fillna(0)
ws_mins = ws['Minutes played']
ws_opac = mins_to_opacity(ws_mins)

st.caption("💡 Bar opacity = minutes played · Purple line = 5-match rolling average")

ftab1,ftab2,ftab3,ftab4 = st.tabs(["Duels","Attacking output","Defensive output","Losses & passing"])

with ftab1:
    fig_d=go.Figure()
    fig_d.add_scatter(x=ws['match_label'],y=ws['duel_win_pct'],mode='lines+markers',name='All duel win %',
        line=dict(color=BLUE,width=2),marker=dict(size=5),connectgaps=True,
        hovertemplate='%{x}<br>Duel win: %{y:.0f}%<extra></extra>')
    fig_d.add_scatter(x=ws['match_label'],y=ws['def_duel_win_pct'],mode='lines+markers',name='Def duel win %',
        line=dict(color=RED,width=2,dash='dot'),marker=dict(size=5),connectgaps=True,
        hovertemplate='%{x}<br>Def duel win: %{y:.0f}%<extra></extra>')
    fig_d.add_scatter(x=ws['match_label'],y=rolling_avg(ws['duel_win_pct']),mode='lines',
        name='Duel win rolling avg',line=dict(color=PURPLE,width=2),connectgaps=True,
        hovertemplate='Rolling avg: %{y:.0f}%<extra></extra>')
    fig_d.add_scatter(x=ws['match_label'],y=[50]*len(ws),mode='lines',name='50% line',
        line=dict(color='#444',width=1,dash='dash'),hoverinfo='skip')
    if 'duel_win' in ws_peers:
        pavg=ws_peers['duel_win'].mean()
        fig_d.add_scatter(x=ws['match_label'],y=[pavg]*len(ws),mode='lines',
            name=f'Position avg ({pavg:.0f}%)',line=dict(color='#888',width=1.5,dash='dash'),hoverinfo='skip')
    fig_d.update_layout(**base_layout('Duel win % (all & defensive)',height=340))
    fig_d.update_yaxes(range=[0,115])
    st.plotly_chart(fig_d,use_container_width=True)

with ftab2:
    fig_a=go.Figure()
    fig_a.add_bar(x=ws['match_label'],y=ws['ptf3_raw'],name='PTF3',
        marker_color=colour_list(BLUE,ws_opac),
        customdata=ws_mins,hovertemplate='%{x}<br>PTF3: %{y:.0f} · %{customdata:.0f} mins<extra></extra>')
    fig_a.add_bar(x=ws['match_label'],y=ws['shot_ast_raw'],name='Shot assists',
        marker_color=colour_list(GREEN,ws_opac),
        customdata=ws_mins,hovertemplate='%{x}<br>Shot asts: %{y:.0f} · %{customdata:.0f} mins<extra></extra>')
    fig_a.add_scatter(x=ws['match_label'],y=rolling_avg(ws['shot_ast_raw']),mode='lines',
        name='Shot asts rolling avg',line=dict(color=PURPLE,width=2),
        hovertemplate='Rolling avg: %{y:.1f}<extra></extra>')
    goal_games=ws[ws['Goals']>0]
    if len(goal_games)>0:
        fig_a.add_scatter(x=goal_games['match_label'],y=[ws['ptf3_raw'].max()*1.1]*len(goal_games),
            mode='markers',name='Goal scored',marker=dict(symbol='star',size=14,color=GOLD),
            hovertemplate='⭐ Goal<extra></extra>')
    fig_a.update_layout(**base_layout('Attacking output · per game',height=340),barmode='group')
    st.plotly_chart(fig_a,use_container_width=True)

with ftab3:
    fig_def = make_subplots(specs=[[{"secondary_y": True}]])
    avg_def  = ws['def_duels_raw'].mean()
    avg_aer  = ws['aerial_raw'].mean()
    fig_def.add_bar(x=ws['match_label'], y=ws['def_duels_raw'], name='Def duels',
        marker_color=colour_list(BLUE, ws_opac),
        customdata=ws_mins, hovertemplate='%{x}<br>Def duels: %{y:.0f} · %{customdata:.0f} mins<extra></extra>',
        secondary_y=False)
    fig_def.add_bar(x=ws['match_label'], y=ws['aerial_raw'], name='Aerial duels',
        marker_color=colour_list(GOLD, ws_opac),
        customdata=ws_mins, hovertemplate='%{x}<br>Aerials: %{y:.0f} · %{customdata:.0f} mins<extra></extra>',
        secondary_y=False)
    fig_def.add_scatter(x=ws['match_label'], y=ws['int_raw'], mode='lines+markers', name='Interceptions',
        line=dict(color=GREEN, width=2), marker=dict(size=5), connectgaps=True,
        hovertemplate='%{x}<br>Int: %{y:.0f}<extra></extra>', secondary_y=True)
    fig_def.add_scatter(x=ws['match_label'], y=rolling_avg(ws['def_duels_raw']), mode='lines',
        name='Def duels rolling avg', line=dict(color=PURPLE, width=2), connectgaps=True,
        hovertemplate='Rolling avg: %{y:.1f}<extra></extra>', secondary_y=False)

    fig_def.update_layout(**base_layout('Defensive output · per game', height=340), barmode='group')
    fig_def.update_yaxes(secondary_y=True, title_text='Interceptions', showgrid=False,
        title_font=dict(size=10, color='#555'))
    st.plotly_chart(fig_def, use_container_width=True)

with ftab4:
    avg_loss=ws['losses_raw'].mean()
    def loss_col(v,o):
        if v>=18:   return rgba(RED,o)
        elif v>=14: return rgba(GOLD,o)
        else:       return rgba('#333333',o)
    loss_cols=[loss_col(ws['losses_raw'].iloc[i],ws_opac[i]) for i in range(len(ws))]
    fig_l=make_subplots(specs=[[{"secondary_y":True}]])
    fig_l.add_bar(x=ws['match_label'],y=ws['losses_raw'],name='Losses',
        marker_color=loss_cols,
        customdata=ws_mins,hovertemplate='%{x}<br>Losses: %{y:.0f} · %{customdata:.0f} mins<extra></extra>',
        secondary_y=False)
    fig_l.add_scatter(x=ws['match_label'],y=[avg_loss]*len(ws),mode='lines',name=f'Avg ({avg_loss:.0f})',
        line=dict(color=GOLD,width=1.5,dash='dot'),hoverinfo='skip',secondary_y=False)
    fig_l.add_scatter(x=ws['match_label'],y=rolling_avg(ws['losses_raw']),mode='lines',
        name='Losses rolling avg',line=dict(color=PURPLE,width=2),connectgaps=True,
        hovertemplate='Rolling avg: %{y:.1f}<extra></extra>',secondary_y=False)
    fig_l.add_scatter(x=ws['match_label'],y=ws['pass_acc_pct'],mode='lines+markers',name='Pass acc %',
        line=dict(color=GREEN,width=1.5),marker=dict(size=4),connectgaps=True,
        hovertemplate='%{x}<br>Pass acc: %{y:.0f}%<extra></extra>',secondary_y=True)
    fig_l.update_layout(**base_layout('Losses per game & passing accuracy',height=340))
    fig_l.update_yaxes(secondary_y=True,title_text='Pass acc %',showgrid=False,
        range=[40,105],title_font=dict(size=10,color='#555'))
    st.plotly_chart(fig_l,use_container_width=True)

# ── Match log ─────────────────────────────────────────────────────────────────
st.markdown('<div class="section-header">Match log · full game-by-game</div>', unsafe_allow_html=True)
# Use full processed Wyscout data (all competitions, all games) not the form-trend filtered slice
ws_all = process_wyscout(ws_raw)
match_log   = build_match_log(ws_all, club or club_from_file)
search      = st.text_input("Filter by opponent or position", placeholder="e.g. Barnsley (A), RWB, Jan...")
display_log = match_log[match_log.apply(lambda r: r.astype(str).str.contains(search,case=False).any(),axis=1)] if search else match_log
st.dataframe(display_log,use_container_width=True,hide_index=True,height=520,
    column_config={
        "Match": st.column_config.TextColumn("Match",width="large"),
        "Date":  st.column_config.TextColumn("Date", width="small"),
        "Pos":   st.column_config.TextColumn("Pos",  width="small"),
        "Min":   st.column_config.NumberColumn("Min",format="%d"),
        "G":     st.column_config.NumberColumn("G",  format="%d"),
        "A":     st.column_config.NumberColumn("A",  format="%d"),
        "xG":    st.column_config.NumberColumn("xG", format="%.2f"),
        "xA":    st.column_config.NumberColumn("xA", format="%.2f"),
    })

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    f"<div style='text-align:center;color:#444;font-size:0.72rem;padding:8px 0'>"
    f"Beswicks Sports Analytics · Internal Use Only · Generated {datetime.now().strftime('%d %b %Y')}"
    f"</div>",unsafe_allow_html=True)

# ── PDF export ────────────────────────────────────────────────────────────────
if 'export_btn' in dir() and export_btn:
    if not PDF_AVAILABLE:
        st.error("PDF export requires `kaleido` and `reportlab`. Add them to requirements.txt and redeploy.")
    else:
        with st.spinner("Generating PDF report — this takes a few seconds..."):
            try:
                # Make sure match_label and per-match columns exist
                if 'match_label' not in ws.columns:
                    ws['match_label'] = ws.apply(lambda r: parse_wyscout_label(r['Match'], club or club_from_file), axis=1)
                if 'duel_win_pct' not in ws.columns:
                    ws['duel_win_pct']     = ws.apply(lambda r: pct(r.iloc[21], r['Duels']), axis=1)
                    ws['def_duel_win_pct'] = ws.apply(lambda r: pct(r.iloc[32], r.iloc[31]), axis=1)

                if ph is not None and 'match_label' not in ph.columns:
                    ph['match_label']  = ph.apply(lambda r: parse_physical_label(r['match_name'], r['team_name']), axis=1)
                    ph['dist_p90_m']   = ph.apply(lambda r: p90(r['total_distance_full_all'],  r['minutes_full_all']), axis=1)
                    ph['hsr_p90_m']    = ph.apply(lambda r: p90(r['hsr_distance_full_all'],    r['minutes_full_all']), axis=1)
                    ph['sprint_p90_m'] = ph.apply(lambda r: p90(r['sprint_distance_full_all'], r['minutes_full_all']), axis=1)

                # Comparable players for PDF (best-effort — non-fatal if it fails)
                try:
                    _comp_df = find_comparable_players_pca(
                        client_totals=season,
                        pos_key=ws_pos_key,
                        league_filter=peer_league,
                        min_mins=min_mins_peer,
                        ws_files=WS_FILES,
                        top_n=8,
                        client_name=short_name or name,
                        client_phys=phys,
                        phys_season_avgs=phys_avgs,
                    )
                except Exception:
                    _comp_df = None

                pdf_bytes = generate_pdf(
                    name=name, club=club, league=league, pos=pos, age_val=age_val,
                    date_start=date_start, date_end=date_end,
                    season=season, phys=phys,
                    ws=ws, ph=ph,
                    radar_data=radar_data if 'radar_data' in dir() else {},
                    ws_peers=ws_peers, phys_peers=phys_peers,
                    ws_peer_n=ws_peer_n, phys_peer_n=phys_peer_n,
                    peer_desc=peer_desc,
                    audience=report_audience.lower(),
                    comparable_df=_comp_df,
                )
                filename = f"Beswicks_{name.replace(' ','_')}_{datetime.now().strftime('%Y%m%d')}.pdf"
                st.download_button(
                    label="⬇️ Download PDF report",
                    data=pdf_bytes,
                    file_name=filename,
                    mime="application/pdf",
                    use_container_width=True,
                )
                st.success(f"Report ready — {filename}")
            except Exception as e:
                st.error(f"PDF generation failed: {e}")
                st.exception(e)
