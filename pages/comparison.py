"""
pages/comparison.py
Beswicks Sports Analytics — Player Comparison

Two modes:
  1. vs League player — compare a Beswicks client against any player in the
     combined League One / League Two Wyscout files.
  2. vs Another client — compare two Beswicks clients head-to-head.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
import glob
from datetime import datetime

from src.metrics import (
    p90, pct, percentile_rank, pct_colour,
    get_season_totals, get_physical_totals,
    build_physical_peers, build_wyscout_peers, build_physical_season_averages,
    MIN_PEER_N,
)

st.set_page_config(
    page_title="Beswicks | Comparison",
    page_icon="⚖️",
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
.pbar-track { background: #2a2a2a; border-radius: 3px; height: 4px; margin-top: 6px; overflow: hidden; }
.pbar-fill  { height: 4px; border-radius: 3px; }
.peer-banner      { background: #111a11; border: 1px solid #1e3a1e; border-radius: 8px; padding: 10px 16px; margin: 8px 0 16px; font-size: 0.75rem; color: #4ade80; }
.peer-banner-warn { background: #1a1500; border: 1px solid #3a3000; color: #facc15; }
.section-header   { font-size: 0.7rem; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: #c8a45a; margin: 24px 0 12px; padding-bottom: 6px; border-bottom: 1px solid #2a2a2a; }
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────────────────
PLOT_BG  = '#0f0f0f'
PAPER_BG = '#0f0f0f'
GRID_COL = '#222222'
TEXT_COL = '#aaaaaa'
GOLD     = '#c8a45a'
BLUE     = '#3b82f6'

DATA_DIR    = "data"
PLAYERS_DIR = os.path.join(DATA_DIR, "players")
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

COMP_METRICS = [
    # Physical
    ("Total dist p90",    'total_dist_p90',    False),
    ("HSR dist p90",      'hsr_dist_p90',      False),
    ("Sprint dist p90",   'sprint_dist_p90',   False),
    ("PSV99 avg",         'psv99_avg',         False),
    # Attacking
    ("Goals p90",         'goals_p90',         False),
    ("Assists p90",       'assists_p90',        False),
    ("xG p90",            'xg_p90',            False),
    ("xA p90",            'xa_p90',            False),
    ("Shot asts p90",     'shot_asts_p90',      False),
    ("Shots on tgt %",    'shots_on_tgt_pct',   False),
    ("Goal conv %",       'goal_conv_pct',      False),
    ("Touches box p90",   'touches_box_p90',    False),
    ("Dribbles p90",      'dribbles_p90',       False),
    ("Dribble succ %",    'drib_pct',           False),
    ("Prog runs p90",     'prog_runs_p90',      False),
    ("Off duels p90",     'off_duels_p90',      False),
    ("Off duel win %",    'off_duel_win',       False),
    ("Fouls suffered p90",'fouls_suffered_p90', False),
    # Passing
    ("Passes p90",        'passes_p90',         False),
    ("Pass acc %",        'pass_acc',           False),
    ("Fwd passes p90",    'fwd_passes_p90',     False),
    ("Fwd pass acc %",    'fwd_pass_acc',       False),
    ("Back passes p90",   'back_passes_p90',    False),
    ("Back pass acc %",   'back_pass_acc',      False),
    ("Recv passes p90",   'recv_passes_p90',    False),
    ("Long passes p90",   'long_passes_p90',    False),
    ("Long pass acc %",   'lp_acc',             False),
    ("Avg pass length",   'avg_pass_length',    False),
    ("Crosses p90",       'crosses_p90',        False),
    ("Cross acc %",       'cross_acc_pct',      False),
    # Key passing
    ("Through passes p90",'through_passes_p90', False),
    ("Through pass acc %",'through_pass_acc',   False),
    ("PTF3 p90",          'ptf3_p90',           False),
    ("PTF3 acc %",        'ptf3_acc_pct',       False),
    ("PPA p90",           'ppa_p90',            False),
    ("PPA acc %",         'ppa_acc_pct',        False),
    ("2nd assists p90",   'second_asts_p90',    False),
    # Duels & defensive
    ("Duels p90",         'duels_p90',          False),
    ("Duel win %",        'duel_win',           False),
    ("Aerial p90",        'aerial_p90',         False),
    ("Aerial win %",      'aerial_win',         False),
    ("Def duels p90",     'def_duels_p90',      False),
    ("Def duel win %",    'def_duel_win',       False),
    ("Loose ball p90",    'loose_duels_p90',    False),
    ("Loose ball win %",  'loose_duel_win',     False),
    ("Slide tackles p90", 'slide_tackles_p90',  False),
    ("Slide tackle succ %",'slide_tackle_pct',  False),
    ("Interceptions",     'interceptions_p90',  False),
    ("Recoveries p90",    'recoveries_p90',     False),
    ("Clearances p90",    'clearances_p90',     False),
    ("Fouls p90",         'fouls_p90',          True),
]

CHART_METRICS = [
    ("Goals p90",         'goals_p90',          False),
    ("xG p90",            'xg_p90',             False),
    ("Shot asts p90",     'shot_asts_p90',       False),
    ("Dribbles p90",      'dribbles_p90',        False),
    ("Prog runs p90",     'prog_runs_p90',       False),
    ("Off duel win %",    'off_duel_win',        False),
    ("Crosses p90",       'crosses_p90',         False),
    ("Through passes p90",'through_passes_p90',  False),
    ("Duels p90",         'duels_p90',           False),
    ("Duel win %",        'duel_win',            False),
    ("Aerial p90",        'aerial_p90',          False),
    ("Aerial win %",      'aerial_win',          False),
    ("Def duels p90",     'def_duels_p90',       False),
    ("Def duel win %",    'def_duel_win',        False),
    ("Interceptions",     'interceptions_p90',   False),
    ("Recoveries p90",    'recoveries_p90',      False),
    ("Pass acc %",        'pass_acc',            False),
    ("Ball security",     'losses_p90',          True),
]


# ── Loaders ───────────────────────────────────────────────────────────────────
def get_player_list():
    """Scan data/players/ for master Excel files."""
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
def _cached_physical_season_avgs(phys_csv):
    return build_physical_season_averages(phys_csv)


@st.cache_data
def load_league_file():
    """Load combined all-player League One + Two files for vs-League-player mode."""
    dfs = []
    for league, files in WS_FILES.items():
        p = files['all']
        if os.path.exists(p):
            df = pd.read_excel(p)
            df['_league'] = league
            dfs.append(df)
    return pd.concat(dfs, ignore_index=True) if dfs else None


@st.cache_data
def find_player_position_file(player_short_name):
    """Return position key (e.g. 'Central Defender') by scanning position files."""
    for league in ['League One', 'League Two']:
        for pos_key, path in WS_FILES[league].items():
            if pos_key == 'all':
                continue
            if not os.path.exists(path):
                continue
            df = pd.read_excel(path)
            if player_short_name in df['Player'].values:
                return pos_key
    return None


# ── HTML helpers ──────────────────────────────────────────────────────────────
def delta_html(c_val, x_val, inverse=False):
    if c_val is None or x_val is None:
        return "<span style='color:#555;font-size:0.7rem'>–</span>"
    diff = (c_val - x_val) if not inverse else (x_val - c_val)
    if abs(diff) < 0.005:
        return "<span style='color:#888;font-size:0.7rem'>=</span>"
    col = '#4ade80' if diff > 0 else '#f87171'
    ar  = '▲' if diff > 0 else '▼'
    return f"<span style='color:{col};font-size:0.7rem;font-weight:600'>{ar} {abs(diff):.2f}</span>"


def bar_html(pv):
    if pv is None:
        return ''
    c = pct_colour(pv)
    return f"<div class='pbar-track'><div class='pbar-fill' style='width:{pv:.0f}%;background:{c};'></div></div>"


def comp_card(label, c_val, x_val, c_pct=None, x_pct=None, inverse=False):
    fmt = lambda v: f"{v:.2f}" if v is not None else "–"
    if c_val is not None and x_val is not None:
        a_bold = "font-weight:700;color:#fff;" if (c_val > x_val) != inverse else "color:#aaa;"
        b_bold = "font-weight:700;color:#fff;" if (x_val > c_val) != inverse else "color:#aaa;"
    else:
        a_bold = b_bold = "color:#aaa;"
    return f"""<div style='background:#1a1a1a;border:1px solid #2a2a2a;border-radius:8px;padding:10px 12px;margin:4px 0'>
  <div style='font-size:0.65rem;color:#666;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:6px'>{label}</div>
  <div style='display:flex;align-items:center;justify-content:space-between'>
    <div style='{a_bold}font-size:1.1rem;line-height:1'>{fmt(c_val)}</div>
    <div style='text-align:center'>{delta_html(c_val, x_val, inverse)}</div>
    <div style='{b_bold}font-size:1.1rem;line-height:1;text-align:right'>{fmt(x_val)}</div>
  </div>
  <div style='display:flex;gap:8px;margin-top:5px'>
    <div style='flex:1'>{bar_html(c_pct)}</div>
    <div style='flex:1;transform:scaleX(-1)'>{bar_html(x_pct)}</div>
  </div>
</div>"""


def pct_colours(pcts, opacity=1.0):
    def c(v):
        if v >= 80:   return f'rgba(74,222,128,{opacity})'
        elif v >= 55: return f'rgba(134,239,172,{opacity})'
        elif v >= 35: return f'rgba(250,204,21,{opacity})'
        else:         return f'rgba(248,113,113,{opacity})'
    return [c(v) for v in pcts]


def player_identity_card(display_name, subtitle, accent=GOLD):
    return (
        f"<div style='background:#0f0f0f;border-radius:8px;padding:14px 18px;"
        f"border-left:4px solid {accent};margin:8px 0'>"
        f"<div style='font-size:1.1rem;font-weight:700;color:#fff'>{display_name}</div>"
        f"<div style='font-size:0.75rem;color:#888'>{subtitle}</div></div>"
    )


def render_comparison(
    name_a: str,
    sub_a: str,
    season_a: dict,
    name_b: str,
    sub_b: str,
    season_b: dict,
    ws_peers: dict,
    phys_peers: dict,
    ws_peer_n: int,
):
    """Render metric cards + percentile bar chart for two players."""
    def gp(key, value, inverse=False):
        series = ws_peers.get(key) if key in ws_peers else phys_peers.get(key)
        if series is None or value is None:
            return None
        return percentile_rank(value, series, inverse=inverse)

    # ── Identity strip ────────────────────────────────────────────────────────
    ca, cvs, cb = st.columns([5, 1, 5])
    with ca:
        st.markdown(player_identity_card(name_a, sub_a, GOLD), unsafe_allow_html=True)
    with cvs:
        st.markdown(
            "<div style='text-align:center;padding-top:22px;font-size:1rem;color:#555;font-weight:700'>vs</div>",
            unsafe_allow_html=True,
        )
    with cb:
        st.markdown(player_identity_card(name_b, sub_b, BLUE), unsafe_allow_html=True)

    # ── Metric cards ──────────────────────────────────────────────────────────
    half = len(COMP_METRICS) // 2 + 1
    cl, cr = st.columns(2)
    for col, metrics in [(cl, COMP_METRICS[:half]), (cr, COMP_METRICS[half:])]:
        col.markdown(
            f"<div style='display:flex;justify-content:space-between;margin-bottom:4px;padding:0 4px'>"
            f"<span style='font-size:0.7rem;color:{GOLD};font-weight:600'>{name_a}</span>"
            f"<span style='font-size:0.7rem;color:{BLUE};font-weight:600'>{name_b}</span></div>",
            unsafe_allow_html=True,
        )
        for label, key, inv in metrics:
            c_val = season_a.get(key)
            x_val = season_b.get(key)
            c_pct = gp(key, c_val, inv)
            x_pct = gp(key, x_val, inv)
            col.markdown(comp_card(label, c_val, x_val, c_pct, x_pct, inv), unsafe_allow_html=True)

    # ── Percentile bar chart ──────────────────────────────────────────────────
    if ws_peer_n >= MIN_PEER_N:
        st.markdown(
            f"<div class='section-header' style='margin-top:28px'>Percentile comparison · vs {ws_peer_n} position peers</div>",
            unsafe_allow_html=True,
        )
        chart_labels, pcts_a, pcts_b = [], [], []
        for clabel, key, inv in CHART_METRICS:
            if key not in ws_peers:
                continue
            cp_a = percentile_rank(season_a.get(key), ws_peers[key], inverse=inv) if season_a.get(key) is not None else None
            cp_b = percentile_rank(season_b.get(key), ws_peers[key], inverse=inv) if season_b.get(key) is not None else None
            if cp_a is not None and cp_b is not None:
                chart_labels.append(clabel)
                pcts_a.append(cp_a)
                pcts_b.append(cp_b)

        if len(chart_labels) >= 3:
            fig = go.Figure()
            fig.add_bar(
                name=name_a, x=chart_labels, y=pcts_a,
                marker_color=pct_colours(pcts_a, 1.0),
                hovertemplate='%{x}<br>' + name_a + ': %{y:.0f}th percentile<extra></extra>',
            )
            fig.add_bar(
                name=name_b, x=chart_labels, y=pcts_b,
                marker_color=pct_colours(pcts_b, 0.6),
                hovertemplate='%{x}<br>' + name_b + ': %{y:.0f}th percentile<extra></extra>',
            )
            fig.add_scatter(
                x=chart_labels, y=[50] * len(chart_labels), mode='lines',
                name='50th percentile',
                line=dict(color='#444', width=1.5, dash='dash'),
                hoverinfo='skip',
            )
            fig.update_layout(
                height=400, plot_bgcolor=PLOT_BG, paper_bgcolor=PAPER_BG,
                barmode='group', font=dict(color=TEXT_COL, size=11),
                yaxis=dict(
                    range=[0, 105], tickvals=[0, 25, 50, 75, 100],
                    ticktext=['0', '25th', '50th', '75th', '100th'],
                    gridcolor=GRID_COL, showgrid=True,
                    tickfont=dict(size=10, color='#666'), zeroline=False,
                ),
                xaxis=dict(tickangle=-30, tickfont=dict(size=10, color='#888'), showgrid=False),
                legend=dict(bgcolor='rgba(0,0,0,0)', font=dict(size=11, color='#aaa'), orientation='h', y=1.06),
                margin=dict(l=10, r=10, t=20, b=80),
                hovermode='x unified', hoverlabel=dict(bgcolor='#1a1a1a', font_size=11),
            )
            st.plotly_chart(fig, use_container_width=True)
            st.markdown("""
<div style='display:flex;gap:16px;justify-content:center;margin-top:4px;flex-wrap:wrap'>
  <span style='font-size:0.7rem;color:#4ade80'>■ 80th+ percentile</span>
  <span style='font-size:0.7rem;color:#86efac'>■ 55–79th</span>
  <span style='font-size:0.7rem;color:#facc15'>■ 35–54th</span>
  <span style='font-size:0.7rem;color:#f87171'>■ Below 35th</span>
  <span style='font-size:0.7rem;color:#555'>--- 50th percentile</span>
</div>""", unsafe_allow_html=True)


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="header-bar">
  <div><h1>Player Comparison</h1><div class="sub">Wyscout + SkillCorner · 2025/26 Season</div></div>
  <div class="beswicks-badge">Beswicks Sports</div>
</div>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚖️ Comparison")
    st.markdown("---")

    player_list = get_player_list()
    if not player_list:
        st.warning("No player files found.")
        st.stop()

    player_names = [p[0] for p in player_list]

    st.markdown("### Beswicks client")
    selected_name = st.selectbox("Select client", player_names, key="cmp_client")
    selected_path = next(p[1] for p in player_list if p[0] == selected_name)

    st.markdown("---")
    st.markdown("### Peer group filters")
    min_mins_peer = st.slider("Min minutes", 450, 1800, 900, 90)
    peer_league   = st.radio("League", ["Both", "Championship", "League One", "League Two"], horizontal=True)

# ── Load client A ─────────────────────────────────────────────────────────────
with st.spinner(f"Loading {selected_name}..."):
    sheets_a  = load_master(selected_path)
    phys_csv  = load_physical_csv()
    phys_avgs = _cached_physical_season_avgs(phys_csv)

ws_raw_a = sheets_a.get('Wyscout')
ph_raw_a = sheets_a.get('Physical')
if ws_raw_a is None:
    st.error(f"No Wyscout sheet found for {selected_name}.")
    st.stop()

ws_a     = ws_raw_a.copy()
ph_a     = ph_raw_a[ph_raw_a['minutes_full_all'] >= 20].copy() if ph_raw_a is not None else None
season_a = get_season_totals(ws_a)
phys_a   = get_physical_totals(ph_a) if ph_a is not None else None
if phys_a:
    season_a.update(phys_a)

# Metadata
club_a   = ph_raw_a['team_name'].iloc[0]      if ph_raw_a is not None and 'team_name'      in ph_raw_a.columns else ""
pos_a    = ph_raw_a['position_group'].iloc[0] if ph_raw_a is not None and 'position_group' in ph_raw_a.columns else ""
mins_a   = int(season_a.get('mins', 0))
short_a  = ph_raw_a['player_short_name'].iloc[0] if ph_raw_a is not None and 'player_short_name' in ph_raw_a.columns else selected_name

# Position key for peer group
ws_pos_key = find_player_position_file(short_a) if short_a else None
ws_peers, ws_peer_n = build_wyscout_peers(ws_pos_key, peer_league, min_mins_peer, WS_FILES) if ws_pos_key else ({}, 0)
phys_peers, _       = build_physical_peers(phys_csv, pos_a, min_mins_peer, peer_league) if pos_a else ({}, 0)

sub_a = f"{club_a} · {pos_a} · {mins_a} mins"

# ── Mode selector ─────────────────────────────────────────────────────────────
st.markdown('<div class="section-header">Comparison mode</div>', unsafe_allow_html=True)
mode = st.radio(
    "Compare against",
    ["vs League player", "vs Another client"],
    horizontal=True,
    label_visibility="collapsed",
)

# ── Mode 1: vs League player ──────────────────────────────────────────────────
if mode == "vs League player":
    league_df = load_league_file()
    if league_df is None:
        st.markdown(
            '<div class="peer-banner peer-banner-warn">⚠ League Wyscout file not found in data/</div>',
            unsafe_allow_html=True,
        )
        st.stop()

    search_q = st.text_input("Search for a player to compare", placeholder="Type a name...")
    if not search_q:
        st.stop()

    search_df = league_df if peer_league == 'Both' else league_df[league_df['_league'] == peer_league]
    matches   = search_df[search_df['Player'].str.contains(search_q, case=False, na=False)]

    if len(matches) == 0:
        st.info(f"No players found matching '{search_q}'.")
        st.stop()

    opts    = (matches['Player'] + " · " + matches['Team'] + " · " + matches['Position']).tolist()
    sel_opt = st.selectbox("Select player", opts)
    comp_row = matches.iloc[opts.index(sel_opt)]

    def cv(col):
        v = comp_row.get(col)
        return round(float(v), 3) if pd.notna(v) else None

    season_b = {
        # Attacking
        'goals_p90':          cv('Goals per 90'),
        'assists_p90':        cv('Assists per 90'),
        'xg_p90':             cv('xG per 90'),
        'xa_p90':             cv('xA per 90'),
        'shot_asts_p90':      cv('Shot assists per 90'),
        'shots_on_tgt_pct':   cv('Shots on target, %'),
        'goal_conv_pct':      cv('Goal conversion, %'),
        'touches_box_p90':    cv('Touches in box per 90'),
        'dribbles_p90':       cv('Dribbles per 90'),
        'drib_pct':           cv('Successful dribbles, %'),
        'prog_runs_p90':      cv('Progressive runs per 90'),
        'off_duels_p90':      cv('Offensive duels per 90'),
        'off_duel_win':       cv('Offensive duels won, %'),
        'fouls_suffered_p90': cv('Fouls suffered per 90'),
        # Passing
        'passes_p90':         cv('Passes per 90'),
        'pass_acc':           cv('Accurate passes, %'),
        'fwd_passes_p90':     cv('Forward passes per 90'),
        'fwd_pass_acc':       cv('Accurate forward passes, %'),
        'back_passes_p90':    cv('Back passes per 90'),
        'back_pass_acc':      cv('Accurate back passes, %'),
        'recv_passes_p90':    cv('Received passes per 90'),
        'long_passes_p90':    cv('Long passes per 90'),
        'lp_acc':             cv('Accurate long passes, %'),
        'avg_pass_length':    cv('Average pass length, m'),
        'crosses_p90':        cv('Crosses per 90'),
        'cross_acc_pct':      cv('Accurate crosses, %'),
        # Key passing
        'through_passes_p90': cv('Through passes per 90'),
        'through_pass_acc':   cv('Accurate through passes, %'),
        'ptf3_p90':           cv('Passes to final third per 90'),
        'ptf3_acc_pct':       cv('Accurate passes to final third, %'),
        'ppa_p90':            cv('Passes to penalty area per 90'),
        'ppa_acc_pct':        cv('Accurate passes to penalty area, %'),
        'second_asts_p90':    cv('Second assists per 90'),
        # Duels & defensive
        'duels_p90':          cv('Duels per 90'),
        'duel_win':           cv('Duels won, %'),
        'aerial_p90':         cv('Aerial duels per 90'),
        'aerial_win':         cv('Aerial duels won, %'),
        'interceptions_p90':  cv('Interceptions per 90'),
        'recoveries_p90':     cv('Successful defensive actions per 90'),
        'def_duels_p90':      cv('Defensive duels per 90'),
        'def_duel_win':       cv('Defensive duels won, %'),
        'loose_duels_p90':    cv('Loose ball duels per 90'),
        'loose_duel_win':     cv('Loose ball duels won, %'),
        'slide_tackles_p90':  cv('Sliding tackles per 90'),
        'slide_tackle_pct':   cv('Successful sliding tackles, %'),
        'clearances_p90':     cv('Clearances per 90'),
        'fouls_p90':          cv('Fouls per 90'),
    }

    # Physical lookup for comparison player
    if phys_avgs is not None:
        comp_name  = comp_row.get('Player', '')
        phys_match = phys_avgs[phys_avgs['player_name'] == comp_name]
        if len(phys_match) == 0:
            parts = str(comp_name).split('.')
            if len(parts) > 1:
                surname    = parts[-1].strip()
                phys_match = phys_avgs[phys_avgs['player_name'].str.contains(surname, case=False, na=False)]
        if len(phys_match) > 0:
            pr = phys_match.iloc[0]
            season_b.update({
                'total_dist_p90':  round(float(pr['total_dist_p90']),  1),
                'hsr_dist_p90':    round(float(pr['hsr_dist_p90']),    1),
                'sprint_dist_p90': round(float(pr['sprint_dist_p90']), 1),
                'psv99_avg':       round(float(pr['psv99_avg']),        2),
                'hi_accel_p90':    round(float(pr['hi_accel_p90']),    1),
            })

    comp_mins_str = f"{int(comp_row.get('Minutes played'))} mins" if pd.notna(comp_row.get('Minutes played')) else ""
    name_b = comp_row['Player']
    sub_b  = f"{comp_row.get('Team', '')} · {comp_row.get('Position', '')} · {comp_mins_str}"

    render_comparison(selected_name, sub_a, season_a, name_b, sub_b, season_b, ws_peers, phys_peers, ws_peer_n)

# ── Mode 2: vs Another client ─────────────────────────────────────────────────
else:
    other_options = [n for n in player_names if n != selected_name]
    if not other_options:
        st.warning("Only one client file found — add a second player to use this mode.")
        st.stop()

    other_name = st.selectbox("Select second client", other_options, key="cmp_client2")
    other_path = next(p[1] for p in player_list if p[0] == other_name)

    with st.spinner(f"Loading {other_name}..."):
        sheets_b = load_master(other_path)

    ws_raw_b = sheets_b.get('Wyscout')
    ph_raw_b = sheets_b.get('Physical')
    if ws_raw_b is None:
        st.error(f"No Wyscout sheet found for {other_name}.")
        st.stop()

    ws_b     = ws_raw_b.copy()
    ph_b     = ph_raw_b[ph_raw_b['minutes_full_all'] >= 20].copy() if ph_raw_b is not None else None
    season_b = get_season_totals(ws_b)
    phys_b   = get_physical_totals(ph_b) if ph_b is not None else None
    if phys_b:
        season_b.update(phys_b)

    club_b  = ph_raw_b['team_name'].iloc[0]      if ph_raw_b is not None and 'team_name'      in ph_raw_b.columns else ""
    pos_b   = ph_raw_b['position_group'].iloc[0] if ph_raw_b is not None and 'position_group' in ph_raw_b.columns else ""
    mins_b  = int(season_b.get('mins', 0))
    sub_b   = f"{club_b} · {pos_b} · {mins_b} mins"

    render_comparison(selected_name, sub_a, season_a, other_name, sub_b, season_b, ws_peers, phys_peers, ws_peer_n)
