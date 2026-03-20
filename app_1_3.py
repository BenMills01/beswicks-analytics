import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
from scipy import stats as scipy_stats

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
    [data-testid="stSidebar"] .stFileUploader label { color: #aaa !important; }

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
    .profile-name { font-size: 1.6rem; font-weight: 700; color: #fff; margin: 0 0 4px; }
    .profile-meta { color: #aaa; font-size: 0.82rem; margin: 0; }
    .profile-tags { margin-top: 12px; display: flex; flex-wrap: wrap; gap: 8px; }
    .tag { background: #1e1e1e; border: 1px solid #333; color: #ccc; border-radius: 5px; padding: 4px 10px; font-size: 0.74rem; }
    .tag-gold { background: #2a2218; border: 1px solid #c8a45a; color: #c8a45a; }

    .mc {
        background: #1a1a1a; border-radius: 8px; padding: 12px 14px 10px;
        border: 1px solid #2a2a2a;
    }
    .mc-label { font-size: 0.68rem; color: #666; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 4px; }
    .mc-value { font-size: 1.4rem; font-weight: 700; color: #fff; line-height: 1; }
    .mc-sub { font-size: 0.68rem; color: #555; margin-top: 3px; }
    .pbar-track { background: #2a2a2a; border-radius: 3px; height: 4px; margin-top: 6px; overflow: hidden; }
    .pbar-fill { height: 4px; border-radius: 3px; }
    .mc-pct { font-size: 0.68rem; margin-top: 4px; font-weight: 600; }

    .mc-good .mc-value { color: #4ade80; }
    .mc-warn .mc-value { color: #facc15; }
    .mc-bad  .mc-value { color: #f87171; }

    .peer-banner {
        background: #111a11; border: 1px solid #1e3a1e; border-radius: 8px;
        padding: 10px 16px; margin: 8px 0 16px; font-size: 0.75rem; color: #4ade80;
    }
    .peer-banner-warn {
        background: #1a1500; border: 1px solid #3a3000; color: #facc15;
    }
    .section-header {
        font-size: 0.7rem; font-weight: 700; letter-spacing: 0.1em;
        text-transform: uppercase; color: #c8a45a; margin: 24px 0 12px;
        padding-bottom: 6px; border-bottom: 1px solid #2a2a2a;
    }
    hr { border-color: #2a2a2a; margin: 20px 0; }
    .upload-prompt { text-align: center; padding: 60px 20px; color: #555; }
    .upload-prompt h2 { color: #888; font-size: 1.2rem; }
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

# ── Helpers ───────────────────────────────────────────────────────────────────
def p90(value, minutes):
    if minutes == 0: return 0.0
    return round((value / minutes) * 90, 2)

def pct(num, denom):
    if denom == 0: return None
    return round((num / denom) * 100, 1)

def percentile_rank(value, series, inverse=False):
    clean = series.dropna()
    if len(clean) == 0 or pd.isna(value) or value is None: return None
    rank = scipy_stats.percentileofscore(clean, value, kind='rank')
    return round(100 - rank if inverse else rank, 1)

def pct_colour(pct_val):
    if pct_val is None: return '#666'
    if pct_val >= 80: return '#4ade80'
    if pct_val >= 55: return '#86efac'
    if pct_val >= 35: return '#facc15'
    return '#f87171'

def ordinal(n):
    n = int(n)
    s = str(n)
    if s.endswith('11') or s.endswith('12') or s.endswith('13'): return f"{n}th"
    if s.endswith('1'): return f"{n}st"
    if s.endswith('2'): return f"{n}nd"
    if s.endswith('3'): return f"{n}rd"
    return f"{n}th"

def metric_card(label, value, sub='', vcls='', pct_val=None, peer_n=None):
    pct_section = ''
    if pct_val is not None:
        c = pct_colour(pct_val)
        w = f"{pct_val:.0f}%"
        peer_str = f" · n={peer_n}" if peer_n else ""
        pct_section = f"""
        <div class="pbar-track"><div class="pbar-fill" style="width:{w};background:{c};"></div></div>
        <div class="mc-pct" style="color:{c};">{ordinal(pct_val)} percentile{peer_str}</div>"""
    return f"""
    <div class="mc {vcls}">
        <div class="mc-label">{label}</div>
        <div class="mc-value">{value}</div>
        {'<div class="mc-sub">' + sub + '</div>' if sub else ''}
        {pct_section}
    </div>"""

# ── Data loading ──────────────────────────────────────────────────────────────
def load_data(file):
    xls = pd.ExcelFile(file)
    sheets = {}
    for sheet in ['Wyscout', 'Physical', 'Pressing', 'Off_Ball_Runs', 'Match_by_Match']:
        if sheet in xls.sheet_names:
            sheets[sheet] = pd.read_excel(xls, sheet_name=sheet)
    return sheets

def process_wyscout(df):
    df = df[df['Minutes played'] >= 20].copy()
    return df.sort_values('Date').reset_index(drop=True)

def process_physical(df):
    df = df[df['minutes_full_all'] >= 20].copy()
    return df.sort_values('match_date').reset_index(drop=True)

def load_peer_group(file, min_mins=900):
    try:
        if str(file.name).endswith('.csv'):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)
    except Exception:
        return None
    min_col = next((c for c in ['Minutes played', 'minutes_played', 'Min', 'Mins'] if c in df.columns), None)
    if min_col:
        df = df[df[min_col] >= min_mins].copy()
    return df if len(df) >= 5 else None

def compute_peer_series(peer_df):
    """Return dict of metric_key -> Series of per-90 values for peer group."""
    if peer_df is None: return {}
    cols = list(peer_df.columns)
    mc = next((c for c in ['Minutes played', 'minutes_played', 'Min'] if c in cols), None)
    if not mc: return {}

    def pp90(col):
        if col not in peer_df.columns: return None
        s = (peer_df[col] / peer_df[mc] * 90).replace([np.inf, -np.inf], np.nan).dropna()
        return s if len(s) >= 5 else None

    def ppct(ni, di):
        try:
            n, d = peer_df.iloc[:, ni], peer_df.iloc[:, di]
            s = np.where(d > 0, n / d * 100, np.nan)
            s = pd.Series(s).dropna()
            return s if len(s) >= 5 else None
        except Exception:
            return None

    out = {
        'goals_p90':         pp90('Goals'),
        'assists_p90':       pp90('Assists'),
        'xg_p90':            pp90('xG'),
        'xa_p90':            pp90('xA'),
        'shots_p90':         pp90('Shots'),
        'shot_asts_p90':     pp90('Shot assists'),
        'touches_box_p90':   pp90('Touches in penalty area'),
        'dribbles_p90':      pp90('Dribbles'),
        'prog_runs_p90':     pp90('Progressive runs'),
        'ptf3_p90':          pp90('Passes to final third'),
        'passes_p90':        pp90('Passes'),
        'long_passes_p90':   pp90('Long passes'),
        'crosses_p90':       pp90('Crosses'),
        'duels_p90':         pp90('Duels'),
        'aerial_p90':        pp90('Aerial duels'),
        'interceptions_p90': pp90('Interceptions'),
        'recoveries_p90':    pp90('Recoveries'),
        'clearances_p90':    pp90('Clearances'),
        'losses_p90':        pp90('Losses'),
        'fouls_p90':         pp90('Fouls'),
        'pass_acc':          ppct(13, cols.index('Passes')) if 'Passes' in cols and len(cols) > 13 else None,
        'duel_win':          ppct(21, cols.index('Duels')) if 'Duels' in cols and len(cols) > 21 else None,
        'aerial_win':        ppct(23, cols.index('Aerial duels')) if 'Aerial duels' in cols and len(cols) > 23 else None,
        'def_duel_win':      ppct(32, 31) if len(cols) > 32 else None,
        'drib_pct':          ppct(19, cols.index('Dribbles')) if 'Dribbles' in cols and len(cols) > 19 else None,
    }
    return {k: v for k, v in out.items() if v is not None}

def get_season_totals(ws):
    mins = ws['Minutes played'].sum()
    s = ws.sum(numeric_only=True)
    return {
        'mins': mins, 'matches': len(ws),
        'goals_raw': int(s['Goals']), 'assists_raw': int(s['Assists']),
        'yellow': int(ws.iloc[:, 39].sum()), 'red': int(ws.iloc[:, 40].sum()),
        'goals_p90':         p90(s['Goals'], mins),
        'assists_p90':       p90(s['Assists'], mins),
        'xg_p90':            p90(s['xG'], mins),
        'xa_p90':            p90(s['xA'], mins),
        'shots_p90':         p90(s['Shots'], mins),
        'shot_asts_p90':     p90(ws['Shot assists'].sum(), mins),
        'touches_box_p90':   p90(ws['Touches in penalty area'].sum(), mins),
        'dribbles_p90':      p90(s['Dribbles'], mins),
        'drib_pct':          pct(ws.iloc[:, 19].sum(), s['Dribbles']),
        'prog_runs_p90':     p90(ws['Progressive runs'].sum(), mins),
        'ptf3_p90':          p90(ws['Passes to final third'].sum(), mins),
        'passes_p90':        p90(s['Passes'], mins),
        'pass_acc':          pct(ws.iloc[:, 13].sum(), s['Passes']),
        'long_passes_p90':   p90(s['Long passes'], mins),
        'lp_acc':            pct(ws.iloc[:, 15].sum(), s['Long passes']),
        'crosses_p90':       p90(s['Crosses'], mins),
        'duels_p90':         p90(s['Duels'], mins),
        'duel_win':          pct(ws.iloc[:, 21].sum(), s['Duels']),
        'aerial_p90':        p90(s['Aerial duels'], mins),
        'aerial_win':        pct(ws.iloc[:, 23].sum(), s['Aerial duels']),
        'def_duels_p90':     p90(ws.iloc[:, 31].sum(), mins),
        'def_duel_win':      pct(ws.iloc[:, 32].sum(), ws.iloc[:, 31].sum()),
        'interceptions_p90': p90(s['Interceptions'], mins),
        'recoveries_p90':    p90(s['Recoveries'], mins),
        'rec_opp_p90':       p90(ws['opp. half'].sum(), mins),
        'clearances_p90':    p90(s['Clearances'], mins),
        'losses_p90':        p90(s['Losses'], mins),
        'losses_oh_p90':     p90(ws['own half'].sum(), mins),
        'fouls_p90':         p90(ws['Fouls'].sum(), mins),
    }

def get_physical_totals(ph):
    mins = ph['minutes_full_all'].sum()
    s = ph.sum(numeric_only=True)
    return {
        'total_dist_p90':  p90(s['total_distance_full_all'], mins),
        'hsr_dist_p90':    p90(s['hsr_distance_full_all'], mins),
        'hsr_count_p90':   p90(s['hsr_count_full_all'], mins),
        'sprint_dist_p90': p90(s['sprint_distance_full_all'], mins),
        'sprint_count_p90':p90(s['sprint_count_full_all'], mins),
        'psv99_avg':       round(ph['psv99'].mean(), 2),
        'psv99_max':       round(ph['psv99'].max(), 2),
        'cod_p90':         p90(s['cod_count_full_all'], mins),
        'high_accel_p90':  p90(s['highaccel_count_full_all'], mins),
    }

def build_match_log(ws):
    rows = []
    for _, r in ws.iterrows():
        mins = r['Minutes played']
        def sp(n, d): return f"{int(round(n/d*100))}%" if d > 0 else "-"
        rows.append({
            'Match': r['Match'], 'Date': pd.to_datetime(r['Date']).strftime('%d %b') if pd.notna(r['Date']) else '',
            'Pos': str(r['Position']), 'Min': int(mins),
            'G': int(r['Goals']), 'A': int(r['Assists']),
            'xG': round(r['xG'], 2), 'xA': round(r['xA'], 2),
            'ShAst': int(r['Shot assists']), 'TouBox': int(r['Touches in penalty area']),
            'Drb': int(r['Dribbles']), 'Drb%': sp(r.iloc[19], r['Dribbles']),
            'Pass': int(r['Passes']), 'Pass%': sp(r.iloc[13], r['Passes']),
            'Cross': int(r['Crosses']), 'PTF3': int(r['Passes to final third']),
            'Duels': int(r['Duels']), 'Duel%': sp(r.iloc[21], r['Duels']),
            'AerDuel': int(r['Aerial duels']), 'Aer%': sp(r.iloc[23], r['Aerial duels']),
            'DefDuel': int(r.iloc[31]), 'DefD%': sp(r.iloc[32], r.iloc[31]),
            'Int': int(r['Interceptions']), 'Rec': int(r['Recoveries']),
            'Clr': int(r['Clearances']), 'Loss': int(r['Losses']),
            'LossOH': int(r['own half']), 'Foul': int(r['Fouls']),
        })
    return pd.DataFrame(rows)

def base_layout(title='', height=320):
    return dict(
        title=dict(text=title, font=dict(color=TEXT_COL, size=12), x=0),
        height=height, plot_bgcolor=PLOT_BG, paper_bgcolor=PAPER_BG,
        font=dict(color=TEXT_COL, size=11), margin=dict(l=10, r=10, t=36, b=40),
        xaxis=dict(gridcolor=GRID_COL, showgrid=False, tickfont=dict(size=9, color='#666'), tickangle=-45),
        yaxis=dict(gridcolor=GRID_COL, showgrid=True, tickfont=dict(size=10, color='#666'), zeroline=False),
        legend=dict(bgcolor='rgba(0,0,0,0)', font=dict(size=10, color='#888'), orientation='h', y=1.08),
        hovermode='x unified', hoverlabel=dict(bgcolor='#1a1a1a', font_size=11),
    )

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚽ Beswicks Sports")
    st.markdown("---")
    st.markdown("### Player data")
    uploaded_file = st.file_uploader("Upload master Excel file", type=['xlsx'],
        help="Player master file with Wyscout, Physical, Pressing and Off_Ball_Runs sheets.")
    st.markdown("---")
    st.markdown("### Peer group")
    peer_file = st.file_uploader("Upload peer group file *(optional)*", type=['xlsx', 'csv'],
        help="Wyscout season averages for the position group. One row per player. Unlocks percentile rankings.")
    min_mins_peer = st.slider("Min minutes filter (peer group)", 450, 1800, 900, 90)
    st.markdown("---")
    st.markdown("### Player details")
    player_name   = st.text_input("Full name",  placeholder="e.g. Lasse Sørensen")
    player_club   = st.text_input("Club",        placeholder="e.g. Huddersfield Town")
    player_league = st.text_input("League",      placeholder="e.g. ENG - League One")
    player_pos    = st.text_input("Position",    placeholder="e.g. Right Back / Wing-Back")
    player_age    = st.number_input("Age", min_value=15, max_value=45, value=24)
    st.markdown("---")
    st.caption("Beswicks Sports Analytics · Internal Use Only")

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="header-bar">
    <div><h1>Player Analysis Platform</h1><div class="sub">Wyscout + SkillCorner · 2025/26 Season</div></div>
    <div class="beswicks-badge">Beswicks Sports</div>
</div>
""", unsafe_allow_html=True)

if uploaded_file is None:
    st.markdown("""
    <div class="upload-prompt">
        <h2>Upload a player file to begin</h2>
        <p>Use the sidebar to upload any client's master Excel file.<br>
        Upload a peer group file to unlock percentile rankings.</p>
        <p style="color:#444;margin-top:24px;font-size:0.75rem;">Accepts: Wyscout · SkillCorner Physical · Pressing · Off-Ball Runs</p>
    </div>""", unsafe_allow_html=True)
    st.stop()

# ── Load ──────────────────────────────────────────────────────────────────────
with st.spinner("Loading..."):
    sheets = load_data(uploaded_file)

ws_raw = sheets.get('Wyscout')
ph_raw = sheets.get('Physical')
if ws_raw is None:
    st.error("Could not find a 'Wyscout' sheet. Please check the file format.")
    st.stop()

ws     = process_wyscout(ws_raw)
ph     = process_physical(ph_raw) if ph_raw is not None else None
season = get_season_totals(ws)
phys   = get_physical_totals(ph) if ph is not None else None

peer_df    = load_peer_group(peer_file, min_mins_peer) if peer_file else None
peer_data  = compute_peer_series(peer_df)
peer_n     = len(peer_df) if peer_df is not None else None

def gp(key, value, inverse=False):
    """Get percentile for a metric value against peer group."""
    if key not in peer_data or value is None: return None
    return percentile_rank(value, peer_data[key], inverse=inverse)

name    = player_name   or "Player"
club    = player_club   or "Club"
league  = player_league or "League"
pos     = player_pos    or "Position"
age_val = player_age

try:
    date_start = pd.to_datetime(ws['Date'].min()).strftime('%d %b %Y')
    date_end   = pd.to_datetime(ws['Date'].max()).strftime('%d %b %Y')
except Exception:
    date_start, date_end = "–", "–"

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

# ── Peer status banner ────────────────────────────────────────────────────────
if peer_df is not None:
    st.markdown(f"""<div class="peer-banner">
        ✓ Peer group active — {peer_n} players · {min_mins_peer}+ mins · percentile rankings enabled
    </div>""", unsafe_allow_html=True)
else:
    st.markdown("""<div class="peer-banner peer-banner-warn">
        ⚠ No peer group loaded — upload a position group export in the sidebar to enable percentile rankings
    </div>""", unsafe_allow_html=True)

# ── Seasonal metrics ──────────────────────────────────────────────────────────
st.markdown('<div class="section-header">Seasonal metrics · per 90</div>', unsafe_allow_html=True)

# Physical (no percentile — would need SkillCorner peer export)
if phys:
    st.markdown("**Physical output**")
    c1, c2, c3, c4, c5 = st.columns(5)
    for col, label, val, sub in [
        (c1, "Total dist p90",  f"{int(phys['total_dist_p90']):,}m",  "SkillCorner"),
        (c2, "HSR dist p90",    f"{int(phys['hsr_dist_p90'])}m",      f"{phys['hsr_count_p90']:.0f} reps"),
        (c3, "Sprint dist p90", f"{int(phys['sprint_dist_p90'])}m",   f"{phys['sprint_count_p90']:.0f} sprints"),
        (c4, "PSV99 avg",       str(phys['psv99_avg']),                f"Peak: {phys['psv99_max']}"),
        (c5, "COD count p90",   f"{phys['cod_p90']:.0f}",             "Changes of direction"),
    ]:
        col.markdown(metric_card(label, val, sub, 'mc-good'), unsafe_allow_html=True)

# Attacking
st.markdown("**Attacking output**")
c1, c2, c3, c4, c5, c6 = st.columns(6)
for col, label, val, sub, vcls, key, inv in [
    (c1, "Goals p90",      f"{season['goals_p90']:.2f}",      f"{season['goals_raw']} raw",   "mc-good" if season['goals_raw'] >= 2 else "", 'goals_p90',       False),
    (c2, "Assists p90",    f"{season['assists_p90']:.2f}",    f"{season['assists_raw']} raw", "",                                            'assists_p90',     False),
    (c3, "xG p90",         f"{season['xg_p90']:.2f}",         "",                             "",                                            'xg_p90',          False),
    (c4, "xA p90",         f"{season['xa_p90']:.2f}",         "",                             "",                                            'xa_p90',          False),
    (c5, "Shot asts p90",  f"{season['shot_asts_p90']:.2f}",  "",                             "mc-good" if season['shot_asts_p90'] > 0.5 else "", 'shot_asts_p90', False),
    (c6, "Touches in box", f"{season['touches_box_p90']:.2f}","per 90",                       "",                                            'touches_box_p90', False),
]:
    col.markdown(metric_card(label, val, sub, vcls, gp(key, season.get(key), inv), peer_n), unsafe_allow_html=True)

# Passing
st.markdown("**Passing & ball-carrying**")
c1, c2, c3, c4, c5 = st.columns(5)
pa = season['pass_acc']
for col, label, val, sub, vcls, key, inv in [
    (c1, "Passes p90",    f"{season['passes_p90']:.1f}",      f"{pa:.1f}% accuracy" if pa else "", "mc-good" if pa and pa > 80 else "mc-warn" if pa and pa > 70 else "mc-bad", 'passes_p90', False),
    (c2, "Long pass p90", f"{season['long_passes_p90']:.2f}", f"{season['lp_acc']:.1f}% acc" if season['lp_acc'] else "", "", 'long_passes_p90', False),
    (c3, "Crosses p90",   f"{season['crosses_p90']:.2f}",     "",                                 "",                                            'crosses_p90',     False),
    (c4, "Dribbles p90",  f"{season['dribbles_p90']:.2f}",    f"{season['drib_pct']:.1f}% success" if season['drib_pct'] else "", "mc-good" if season['drib_pct'] and season['drib_pct'] > 60 else "", 'dribbles_p90', False),
    (c5, "Prog runs p90", f"{season['prog_runs_p90']:.2f}",   "",                                 "",                                            'prog_runs_p90',   False),
]:
    col.markdown(metric_card(label, val, sub, vcls, gp(key, season.get(key), inv), peer_n), unsafe_allow_html=True)

# Defensive
st.markdown("**Defensive output**")
c1, c2, c3, c4, c5, c6 = st.columns(6)
for col, label, val, sub, vcls, key, inv in [
    (c1, "Duels p90",      f"{season['duels_p90']:.1f}",        f"{season['duel_win']:.1f}% win rate",   "mc-warn" if season['duel_win'] and season['duel_win'] < 55 else "mc-good", 'duels_p90',         False),
    (c2, "Aerial p90",     f"{season['aerial_p90']:.2f}",       f"{season['aerial_win']:.1f}% win rate" if season['aerial_win'] else "", "", 'aerial_p90', False),
    (c3, "Def duels p90",  f"{season['def_duels_p90']:.2f}",    f"{season['def_duel_win']:.1f}% win rate" if season['def_duel_win'] else "", "mc-warn" if season['def_duel_win'] and season['def_duel_win'] < 60 else "mc-good", 'def_duels_p90', False),
    (c4, "Interceptions",  f"{season['interceptions_p90']:.2f}","per 90",                                 "mc-good" if season['interceptions_p90'] > 4 else "", 'interceptions_p90', False),
    (c5, "Recoveries p90", f"{season['recoveries_p90']:.2f}",   f"Opp half: {season['rec_opp_p90']:.2f}","",                                                   'recoveries_p90',    False),
    (c6, "Losses p90",     f"{season['losses_p90']:.2f}",       f"Own half: {season['losses_oh_p90']:.2f}", "mc-bad" if season['losses_p90'] > 12 else "mc-warn", 'losses_p90',    True),
]:
    col.markdown(metric_card(label, val, sub, vcls, gp(key, season.get(key), inv), peer_n), unsafe_allow_html=True)

# Win rates
st.markdown("**Win rates & accuracy**")
c1, c2, c3, c4, c5 = st.columns(5)
for col, label, val, sub, vcls, key, inv in [
    (c1, "Pass acc %",        f"{season['pass_acc']:.1f}%" if season['pass_acc'] else "–",       f"{season['passes_p90']:.1f} passes p90",     "mc-good" if pa and pa > 80 else "mc-warn", 'pass_acc',     False),
    (c2, "Duel win %",        f"{season['duel_win']:.1f}%" if season['duel_win'] else "–",       f"{season['duels_p90']:.1f} duels p90",        "mc-warn" if season['duel_win'] and season['duel_win'] < 55 else "mc-good", 'duel_win', False),
    (c3, "Aerial win %",      f"{season['aerial_win']:.1f}%" if season['aerial_win'] else "–",   f"{season['aerial_p90']:.1f} aerials p90",     "", 'aerial_win',   False),
    (c4, "Def duel win %",    f"{season['def_duel_win']:.1f}%" if season['def_duel_win'] else "–",f"{season['def_duels_p90']:.1f} def duels",   "mc-warn" if season['def_duel_win'] and season['def_duel_win'] < 60 else "mc-good", 'def_duel_win', False),
    (c5, "Dribble success %", f"{season['drib_pct']:.1f}%" if season['drib_pct'] else "–",       f"{season['dribbles_p90']:.1f} dribbles p90", "mc-good" if season['drib_pct'] and season['drib_pct'] > 60 else "", 'drib_pct', False),
]:
    col.markdown(metric_card(label, val, sub, vcls, gp(key, season.get(key), inv), peer_n), unsafe_allow_html=True)

# Pressing
pressing_raw = sheets.get('Pressing')
if pressing_raw is not None:
    press = pressing_raw[pressing_raw['minutes_played_per_match'] >= 20]
    if len(press) > 0:
        st.markdown("**Under-pressure passing**")
        c1, c2, c3 = st.columns(3)
        avg_ret  = press['ball_retention_ratio_under_pressure'].mean()
        avg_comp = press['pass_completion_ratio_under_pressure'].mean()
        avg_pres = press['count_pressures_received_per_match'].mean()
        c1.markdown(metric_card("Pressures received p90", f"{avg_pres:.1f}"), unsafe_allow_html=True)
        c2.markdown(metric_card("Ball retention under press", f"{avg_ret:.1f}%", vcls="mc-warn" if avg_ret < 70 else "mc-good"), unsafe_allow_html=True)
        c3.markdown(metric_card("Pass completion under press", f"{avg_comp:.1f}%", vcls="mc-warn" if avg_comp < 70 else "mc-good"), unsafe_allow_html=True)

# Off-ball runs
obr_raw = sheets.get('Off_Ball_Runs')
if obr_raw is not None:
    obr = obr_raw[obr_raw['minutes_played_per_match'] >= 20]
    if len(obr) > 0:
        st.markdown("**Off-ball runs**")
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(metric_card("Runs per match",  f"{obr['count_runs_per_match'].mean():.1f}"), unsafe_allow_html=True)
        c2.markdown(metric_card("Dangerous runs",  f"{obr['count_dangerous_runs_per_match'].mean():.1f}"), unsafe_allow_html=True)
        c3.markdown(metric_card("Runs targeted",   f"{obr['count_runs_targeted_per_match'].mean():.1f}"), unsafe_allow_html=True)
        c4.markdown(metric_card("Runs received",   f"{obr['count_runs_received_per_match'].mean():.1f}"), unsafe_allow_html=True)

# ── Percentile radar (peer data only) ────────────────────────────────────────
if peer_df is not None and len(peer_data) >= 5:
    st.markdown('<div class="section-header">Percentile profile · vs peer group</div>', unsafe_allow_html=True)

    radar_keys = [
        ('Goals p90',       'goals_p90',        False),
        ('xG p90',          'xg_p90',           False),
        ('Shot asts p90',   'shot_asts_p90',     False),
        ('Pass acc %',      'pass_acc',          False),
        ('Dribbles p90',    'dribbles_p90',      False),
        ('Prog runs p90',   'prog_runs_p90',     False),
        ('Crosses p90',     'crosses_p90',       False),
        ('Duels p90',       'duels_p90',         False),
        ('Duel win %',      'duel_win',          False),
        ('Aerial p90',      'aerial_p90',        False),
        ('Interceptions',   'interceptions_p90', False),
        ('Recoveries p90',  'recoveries_p90',    False),
        ('Ball security',   'losses_p90',        True),
    ]
    radar_data = {label: gp(key, season.get(key), inv) for label, key, inv in radar_keys}
    radar_data = {k: v for k, v in radar_data.items() if v is not None}

    if len(radar_data) >= 5:
        labels = list(radar_data.keys())
        values = list(radar_data.values())
        lc = labels + [labels[0]]
        vc = values + [values[0]]

        fig_r = go.Figure()
        fig_r.add_trace(go.Scatterpolar(r=vc, theta=lc, fill='toself',
            fillcolor='rgba(200,164,90,0.15)', line=dict(color=GOLD, width=2), name=name))
        fig_r.add_trace(go.Scatterpolar(r=[50]*len(lc), theta=lc, mode='lines',
            line=dict(color='#444', width=1, dash='dot'), name='League avg (50th)'))
        fig_r.update_layout(
            polar=dict(bgcolor=PLOT_BG,
                radialaxis=dict(visible=True, range=[0, 100], tickfont=dict(size=9, color='#555'),
                                gridcolor='#2a2a2a', linecolor='#333'),
                angularaxis=dict(tickfont=dict(size=10, color=TEXT_COL), gridcolor='#2a2a2a', linecolor='#333')),
            paper_bgcolor=PAPER_BG, showlegend=True,
            legend=dict(bgcolor='rgba(0,0,0,0)', font=dict(color='#888', size=10)),
            height=460, margin=dict(l=60, r=60, t=30, b=30),
        )
        col_r, col_s = st.columns([3, 2])
        with col_r:
            st.plotly_chart(fig_r, use_container_width=True)
        with col_s:
            st.markdown(f"<div style='padding-top:30px'>", unsafe_allow_html=True)
            st.markdown(f"<p style='color:#666;font-size:0.75rem;margin-bottom:16px'>vs {peer_n} {pos} players · {min_mins_peer}+ mins</p>", unsafe_allow_html=True)
            top3    = sorted(radar_data.items(), key=lambda x: x[1], reverse=True)[:3]
            bottom3 = sorted(radar_data.items(), key=lambda x: x[1])[:3]
            st.markdown("<p style='color:#4ade80;font-size:0.72rem;font-weight:700;letter-spacing:0.06em;margin:0 0 6px'>STRENGTHS</p>", unsafe_allow_html=True)
            for lbl, val in top3:
                st.markdown(f"<p style='color:#ccc;font-size:0.82rem;margin:4px 0'>{lbl} &nbsp;<span style='color:#4ade80;font-weight:600'>{ordinal(val)}</span></p>", unsafe_allow_html=True)
            st.markdown("<p style='color:#f87171;font-size:0.72rem;font-weight:700;letter-spacing:0.06em;margin:16px 0 6px'>BELOW AVERAGE</p>", unsafe_allow_html=True)
            for lbl, val in bottom3:
                st.markdown(f"<p style='color:#ccc;font-size:0.82rem;margin:4px 0'>{lbl} &nbsp;<span style='color:#f87171;font-weight:600'>{ordinal(val)}</span></p>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

# ── Physical charts ───────────────────────────────────────────────────────────
if ph is not None and len(ph) > 0:
    st.markdown('<div class="section-header">Physical output · match by match</div>', unsafe_allow_html=True)
    ph['match_label'] = ph['match_date'].apply(lambda x: pd.to_datetime(x).strftime('%d %b') if pd.notna(x) else '')
    ph['dist_p90']    = ph.apply(lambda r: p90(r['total_distance_full_all'],  r['minutes_full_all']), axis=1)
    ph['hsr_p90']     = ph.apply(lambda r: p90(r['hsr_distance_full_all'],    r['minutes_full_all']), axis=1)
    ph['sprint_p90']  = ph.apply(lambda r: p90(r['sprint_distance_full_all'], r['minutes_full_all']), axis=1)
    avg_dist = ph['dist_p90'].mean()
    avg_hsr  = ph['hsr_p90'].mean()

    tab1, tab2, tab3 = st.tabs(["Distance", "HSR & Sprint", "PSV99 & Accelerations"])
    with tab1:
        fig = go.Figure()
        fig.add_bar(x=ph['match_label'], y=ph['dist_p90'],
                    marker_color=[GOLD if v >= avg_dist else '#333' for v in ph['dist_p90']],
                    name='Total dist p90', hovertemplate='%{y:,.0f}m<extra></extra>')
        fig.add_scatter(x=ph['match_label'], y=[avg_dist]*len(ph), mode='lines',
                        name=f'Avg ({avg_dist:,.0f}m)', line=dict(color=RED, width=1.5, dash='dot'), hoverinfo='skip')
        fig.update_layout(**base_layout('Total distance per 90 (m)', height=300))
        fig.update_yaxes(range=[8000, ph['dist_p90'].max() * 1.05])
        st.plotly_chart(fig, use_container_width=True)
    with tab2:
        fig2 = go.Figure()
        fig2.add_bar(x=ph['match_label'], y=ph['hsr_p90'],    name='HSR dist p90',    marker_color=BLUE, hovertemplate='HSR: %{y:.0f}m<extra></extra>')
        fig2.add_bar(x=ph['match_label'], y=ph['sprint_p90'], name='Sprint dist p90', marker_color='rgba(200,164,90,0.53)', hovertemplate='Sprint: %{y:.0f}m<extra></extra>')
        fig2.add_scatter(x=ph['match_label'], y=[avg_hsr]*len(ph), mode='lines',
                         name=f'HSR avg ({avg_hsr:.0f}m)', line=dict(color=BLUE, width=1.5, dash='dot'), hoverinfo='skip')
        fig2.update_layout(**base_layout('HSR & sprint distance per 90 (m)', height=300), barmode='group')
        st.plotly_chart(fig2, use_container_width=True)
    with tab3:
        fig3 = make_subplots(specs=[[{"secondary_y": True}]])
        avg_psv = ph['psv99'].mean()
        fig3.add_scatter(x=ph['match_label'], y=ph['psv99'], mode='lines+markers', name='PSV99',
                         line=dict(color=GREEN, width=2), marker=dict(size=5, color=GREEN),
                         hovertemplate='PSV99: %{y:.2f}<extra></extra>', secondary_y=False)
        fig3.add_scatter(x=ph['match_label'], y=[avg_psv]*len(ph), mode='lines', name=f'Avg ({avg_psv:.2f})',
                         line=dict(color='#555', width=1, dash='dot'), hoverinfo='skip', secondary_y=False)
        fig3.add_bar(x=ph['match_label'],
                     y=ph.apply(lambda r: p90(r['highaccel_count_full_all'], r['minutes_full_all']), axis=1),
                     name='High accel p90', marker_color='rgba(200,164,90,0.40)',
                     hovertemplate='High accel: %{y:.1f}<extra></extra>', secondary_y=True)
        fig3.update_layout(**base_layout('PSV99 & high accelerations per 90', height=300))
        fig3.update_yaxes(range=[7.0, ph['psv99'].max() + 0.3], secondary_y=False,
                          title_text='PSV99', title_font=dict(size=10, color='#555'))
        fig3.update_yaxes(secondary_y=True, title_text='High accel p90',
                          title_font=dict(size=10, color='#555'), showgrid=False)
        st.plotly_chart(fig3, use_container_width=True)

# ── Form trends ───────────────────────────────────────────────────────────────
st.markdown('<div class="section-header">Form trends · match by match</div>', unsafe_allow_html=True)
ws['match_label']      = ws['Date'].apply(lambda x: pd.to_datetime(x).strftime('%d %b') if pd.notna(x) else '')
ws['duel_win_pct']     = ws.apply(lambda r: pct(r.iloc[21], r['Duels']),   axis=1)
ws['def_duel_win_pct'] = ws.apply(lambda r: pct(r.iloc[32], r.iloc[31]), axis=1)
ws['losses_p90_m']     = ws.apply(lambda r: p90(r['Losses'],                r['Minutes played']), axis=1)
ws['ptf3_p90_m']       = ws.apply(lambda r: p90(r['Passes to final third'], r['Minutes played']), axis=1)
ws['shot_ast_p90_m']   = ws.apply(lambda r: p90(r['Shot assists'],           r['Minutes played']), axis=1)
ws['pass_acc_pct']     = ws.apply(lambda r: pct(r.iloc[13], r['Passes']),   axis=1)

ftab1, ftab2, ftab3 = st.tabs(["Duels", "Attacking output", "Losses & passing"])
with ftab1:
    fig_d = go.Figure()
    fig_d.add_scatter(x=ws['match_label'], y=ws['duel_win_pct'], mode='lines+markers',
                      name='All duel win %', line=dict(color=BLUE, width=2), marker=dict(size=5), connectgaps=True,
                      hovertemplate='Duel win: %{y:.0f}%<extra></extra>')
    fig_d.add_scatter(x=ws['match_label'], y=ws['def_duel_win_pct'], mode='lines+markers',
                      name='Def duel win %', line=dict(color=RED, width=2, dash='dot'), marker=dict(size=5), connectgaps=True,
                      hovertemplate='Def duel win: %{y:.0f}%<extra></extra>')
    fig_d.add_scatter(x=ws['match_label'], y=[50]*len(ws), mode='lines', name='50% line',
                      line=dict(color='#444', width=1, dash='dash'), hoverinfo='skip')
    if 'duel_win' in peer_data:
        pavg = peer_data['duel_win'].mean()
        fig_d.add_scatter(x=ws['match_label'], y=[pavg]*len(ws), mode='lines',
                          name=f'Peer avg ({pavg:.0f}%)', line=dict(color=GOLD, width=1.5, dash='dot'), hoverinfo='skip')
    fig_d.update_layout(**base_layout('Duel win % (all & defensive)', height=320))
    fig_d.update_yaxes(range=[0, 115])
    st.plotly_chart(fig_d, use_container_width=True)

with ftab2:
    fig_a = go.Figure()
    fig_a.add_bar(x=ws['match_label'], y=ws['ptf3_p90_m'],     name='PTF3 p90',      marker_color='rgba(59,130,246,0.60)', hovertemplate='PTF3 p90: %{y:.1f}<extra></extra>')
    fig_a.add_bar(x=ws['match_label'], y=ws['shot_ast_p90_m'], name='Shot asts p90', marker_color=GREEN, hovertemplate='Shot asts p90: %{y:.1f}<extra></extra>')
    goal_games = ws[ws['Goals'] > 0]
    if len(goal_games) > 0:
        fig_a.add_scatter(x=goal_games['match_label'], y=[ws['ptf3_p90_m'].max() * 1.1]*len(goal_games),
                          mode='markers+text', name='Goal', marker=dict(symbol='star', size=12, color=GOLD),
                          text=['⭐']*len(goal_games), textposition='top center', hovertemplate='Goal<extra></extra>')
    fig_a.update_layout(**base_layout('Attacking output per 90', height=320), barmode='group')
    st.plotly_chart(fig_a, use_container_width=True)

with ftab3:
    avg_loss = ws['losses_p90_m'].mean()
    fig_l = make_subplots(specs=[[{"secondary_y": True}]])
    fig_l.add_bar(x=ws['match_label'], y=ws['losses_p90_m'], name='Losses p90',
                  marker_color=[RED if v >= 18 else 'rgba(200,164,90,0.53)' if v >= 14 else '#333' for v in ws['losses_p90_m']],
                  hovertemplate='Losses p90: %{y:.1f}<extra></extra>', secondary_y=False)
    fig_l.add_scatter(x=ws['match_label'], y=[avg_loss]*len(ws), mode='lines', name=f'Avg ({avg_loss:.1f})',
                      line=dict(color='#555', width=1.5, dash='dot'), hoverinfo='skip', secondary_y=False)
    fig_l.add_scatter(x=ws['match_label'], y=ws['pass_acc_pct'], mode='lines+markers', name='Pass acc %',
                      line=dict(color=GREEN, width=1.5), marker=dict(size=4), connectgaps=True,
                      hovertemplate='Pass acc: %{y:.0f}%<extra></extra>', secondary_y=True)
    fig_l.update_layout(**base_layout('Losses per 90 & passing accuracy', height=320))
    fig_l.update_yaxes(secondary_y=True, title_text='Pass acc %', showgrid=False,
                       range=[40, 105], title_font=dict(size=10, color='#555'))
    st.plotly_chart(fig_l, use_container_width=True)

# ── Match log ─────────────────────────────────────────────────────────────────
st.markdown('<div class="section-header">Match log · full game-by-game</div>', unsafe_allow_html=True)
match_log = build_match_log(ws)
search = st.text_input("Filter by opponent or position", placeholder="e.g. Barnsley, RWB, Jan...")
display_log = match_log[match_log.apply(lambda r: r.astype(str).str.contains(search, case=False).any(), axis=1)] if search else match_log
st.dataframe(display_log, use_container_width=True, hide_index=True, height=520,
    column_config={
        "Match": st.column_config.TextColumn("Match", width="large"),
        "Date":  st.column_config.TextColumn("Date",  width="small"),
        "Pos":   st.column_config.TextColumn("Pos",   width="small"),
        "Min":   st.column_config.NumberColumn("Min",  format="%d"),
        "G":     st.column_config.NumberColumn("G",    format="%d"),
        "A":     st.column_config.NumberColumn("A",    format="%d"),
        "xG":    st.column_config.NumberColumn("xG",   format="%.2f"),
        "xA":    st.column_config.NumberColumn("xA",   format="%.2f"),
    })

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    f"<div style='text-align:center;color:#444;font-size:0.72rem;padding:8px 0'>"
    f"Beswicks Sports Analytics · Internal Use Only · Generated {datetime.now().strftime('%d %b %Y')}"
    f"</div>", unsafe_allow_html=True)

# ── Player comparison ─────────────────────────────────────────────────────────
st.markdown('<div class="section-header">Player comparison</div>', unsafe_allow_html=True)

if peer_df is None:
    st.markdown("""<div class="peer-banner peer-banner-warn">
        ⚠ Upload a peer group file in the sidebar to enable player comparison
    </div>""", unsafe_allow_html=True)
else:
    # ── Player search ─────────────────────────────────────────────────────────
    name_col = next((c for c in ['Player', 'player_name', 'Name', 'Player name', 'Player Name'] if c in peer_df.columns), None)

    if name_col is None:
        st.warning("Could not find a player name column in the peer group file. Expected 'Player' or 'player_name'.")
    else:
        search_q = st.text_input("Search for a player to compare", placeholder="Type a name...")

        if search_q:
            matches = peer_df[peer_df[name_col].str.contains(search_q, case=False, na=False)]
            if len(matches) == 0:
                st.info(f"No players found matching '{search_q}'.")
            else:
                player_options = matches[name_col].tolist()
                selected_name = st.selectbox("Select player", player_options)
                comp_row = matches[matches[name_col] == selected_name].iloc[0]

                # ── Compute comparison player stats ───────────────────────────
                cols_p = list(peer_df.columns)
                mc_p   = next((c for c in ['Minutes played', 'minutes_played', 'Min'] if c in cols_p), None)

                def cp90(col):
                    if col not in cols_p or mc_p not in cols_p: return None
                    mins = comp_row[mc_p]
                    if mins == 0: return None
                    return round((comp_row[col] / mins) * 90, 2)

                def cpct(ni, di):
                    try:
                        n, d = comp_row.iloc[ni], comp_row.iloc[di]
                        return round(n / d * 100, 1) if d > 0 else None
                    except Exception:
                        return None

                comp = {
                    'goals_p90':         cp90('Goals'),
                    'assists_p90':       cp90('Assists'),
                    'xg_p90':            cp90('xG'),
                    'xa_p90':            cp90('xA'),
                    'shots_p90':         cp90('Shots'),
                    'shot_asts_p90':     cp90('Shot assists'),
                    'touches_box_p90':   cp90('Touches in penalty area'),
                    'dribbles_p90':      cp90('Dribbles'),
                    'prog_runs_p90':     cp90('Progressive runs'),
                    'ptf3_p90':          cp90('Passes to final third'),
                    'passes_p90':        cp90('Passes'),
                    'long_passes_p90':   cp90('Long passes'),
                    'crosses_p90':       cp90('Crosses'),
                    'duels_p90':         cp90('Duels'),
                    'aerial_p90':        cp90('Aerial duels'),
                    'interceptions_p90': cp90('Interceptions'),
                    'recoveries_p90':    cp90('Recoveries'),
                    'clearances_p90':    cp90('Clearances'),
                    'losses_p90':        cp90('Losses'),
                    'pass_acc':          cpct(13, cols_p.index('Passes')) if 'Passes' in cols_p and len(cols_p) > 13 else None,
                    'duel_win':          cpct(21, cols_p.index('Duels')) if 'Duels' in cols_p and len(cols_p) > 21 else None,
                    'aerial_win':        cpct(23, cols_p.index('Aerial duels')) if 'Aerial duels' in cols_p and len(cols_p) > 23 else None,
                    'drib_pct':          cpct(19, cols_p.index('Dribbles')) if 'Dribbles' in cols_p and len(cols_p) > 19 else None,
                    'def_duel_win':      cpct(32, 31) if len(cols_p) > 32 else None,
                    'def_duels_p90':     cp90('Defensive duels') if 'Defensive duels' in cols_p else None,
                }

                comp_mins = comp_row[mc_p] if mc_p else None
                comp_mins_str = f"{int(comp_mins)} mins" if comp_mins else ""

                # ── Comparison header ─────────────────────────────────────────
                col_a, col_vs, col_b = st.columns([5, 1, 5])
                with col_a:
                    st.markdown(f"""
                    <div style='background:#0f0f0f;border-radius:8px;padding:14px 18px;border-left:4px solid {GOLD};margin:8px 0'>
                        <div style='font-size:1.1rem;font-weight:700;color:#fff'>{name}</div>
                        <div style='font-size:0.75rem;color:#888'>{club} · {pos} · {int(season['mins'])} mins</div>
                    </div>""", unsafe_allow_html=True)
                with col_vs:
                    st.markdown("<div style='text-align:center;padding-top:22px;font-size:1rem;color:#555;font-weight:700'>vs</div>", unsafe_allow_html=True)
                with col_b:
                    st.markdown(f"""
                    <div style='background:#0f0f0f;border-radius:8px;padding:14px 18px;border-left:4px solid #3b82f6;margin:8px 0'>
                        <div style='font-size:1.1rem;font-weight:700;color:#fff'>{selected_name}</div>
                        <div style='font-size:0.75rem;color:#888'>{comp_mins_str}</div>
                    </div>""", unsafe_allow_html=True)

                # ── Side-by-side metric cards ─────────────────────────────────
                COMP_METRICS = [
                    # (label, client_key, inverse)
                    ("Goals p90",        'goals_p90',         False),
                    ("Assists p90",      'assists_p90',       False),
                    ("xG p90",           'xg_p90',            False),
                    ("xA p90",           'xa_p90',            False),
                    ("Shot asts p90",    'shot_asts_p90',     False),
                    ("Touches box p90",  'touches_box_p90',   False),
                    ("Dribbles p90",     'dribbles_p90',      False),
                    ("Prog runs p90",    'prog_runs_p90',     False),
                    ("Passes p90",       'passes_p90',        False),
                    ("Pass acc %",       'pass_acc',          False),
                    ("Crosses p90",      'crosses_p90',       False),
                    ("PTF3 p90",         'ptf3_p90',          False),
                    ("Duels p90",        'duels_p90',         False),
                    ("Duel win %",       'duel_win',          False),
                    ("Aerial p90",       'aerial_p90',        False),
                    ("Aerial win %",     'aerial_win',        False),
                    ("Interceptions",    'interceptions_p90', False),
                    ("Recoveries p90",   'recoveries_p90',    False),
                    ("Clearances p90",   'clearances_p90',    False),
                    ("Losses p90",       'losses_p90',        True),
                ]

                def delta_html(client_val, comp_val, inverse=False):
                    if client_val is None or comp_val is None:
                        return "<span style='color:#555;font-size:0.7rem'>–</span>"
                    diff = client_val - comp_val
                    if inverse:
                        diff = -diff
                    if abs(diff) < 0.005:
                        return "<span style='color:#888;font-size:0.7rem'>=</span>"
                    colour = '#4ade80' if diff > 0 else '#f87171'
                    arrow  = '▲' if diff > 0 else '▼'
                    return f"<span style='color:{colour};font-size:0.7rem;font-weight:600'>{arrow} {abs(diff):.2f}</span>"

                def comp_card(label, client_val, comp_val, client_pct=None, comp_pct=None, inverse=False):
                    fmt = lambda v: f"{v:.2f}" if v is not None else "–"

                    def bar(pv):
                        if pv is None: return ''
                        c = pct_colour(pv)
                        return f"<div class='pbar-track'><div class='pbar-fill' style='width:{pv:.0f}%;background:{c};'></div></div>"

                    # Determine which player leads
                    if client_val is not None and comp_val is not None:
                        client_leads = (client_val > comp_val) if not inverse else (client_val < comp_val)
                        a_bold = "font-weight:700;color:#fff;" if client_leads else "color:#aaa;"
                        b_bold = "font-weight:700;color:#fff;" if not client_leads else "color:#aaa;"
                    else:
                        a_bold = b_bold = "color:#aaa;"

                    return f"""
                    <div style='background:#1a1a1a;border:1px solid #2a2a2a;border-radius:8px;padding:10px 12px;margin:4px 0'>
                        <div style='font-size:0.65rem;color:#666;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:6px'>{label}</div>
                        <div style='display:flex;align-items:center;justify-content:space-between'>
                            <div style='{a_bold}font-size:1.1rem;line-height:1'>{fmt(client_val)}</div>
                            <div style='text-align:center'>{delta_html(client_val, comp_val, inverse)}</div>
                            <div style='{b_bold}font-size:1.1rem;line-height:1;text-align:right'>{fmt(comp_val)}</div>
                        </div>
                        <div style='display:flex;gap:8px;margin-top:5px'>
                            <div style='flex:1'>{bar(client_pct)}</div>
                            <div style='flex:1;transform:scaleX(-1)'>{bar(comp_pct)}</div>
                        </div>
                    </div>"""

                # Split into two column groups for layout
                st.markdown("<div style='margin-top:16px'>", unsafe_allow_html=True)
                n_metrics = len(COMP_METRICS)
                half = (n_metrics + 1) // 2

                col_left, col_right = st.columns(2)

                # Column headers
                with col_left:
                    st.markdown(f"<div style='display:flex;justify-content:space-between;margin-bottom:4px;padding:0 4px'><span style='font-size:0.7rem;color:{GOLD};font-weight:600'>{name}</span><span style='font-size:0.7rem;color:#3b82f6;font-weight:600'>{selected_name}</span></div>", unsafe_allow_html=True)
                    for label, key, inv in COMP_METRICS[:half]:
                        c_val = season.get(key)
                        x_val = comp.get(key)
                        c_pct = gp(key, c_val, inv)
                        x_pct = percentile_rank(x_val, peer_data[key], inverse=inv) if key in peer_data and x_val is not None else None
                        col_left.markdown(comp_card(label, c_val, x_val, c_pct, x_pct, inv), unsafe_allow_html=True)

                with col_right:
                    st.markdown(f"<div style='display:flex;justify-content:space-between;margin-bottom:4px;padding:0 4px'><span style='font-size:0.7rem;color:{GOLD};font-weight:600'>{name}</span><span style='font-size:0.7rem;color:#3b82f6;font-weight:600'>{selected_name}</span></div>", unsafe_allow_html=True)
                    for label, key, inv in COMP_METRICS[half:]:
                        c_val = season.get(key)
                        x_val = comp.get(key)
                        c_pct = gp(key, c_val, inv)
                        x_pct = percentile_rank(x_val, peer_data[key], inverse=inv) if key in peer_data and x_val is not None else None
                        col_right.markdown(comp_card(label, c_val, x_val, c_pct, x_pct, inv), unsafe_allow_html=True)

                st.markdown("</div>", unsafe_allow_html=True)

                # ── Comparison bar chart ───────────────────────────────────────
                st.markdown("<div style='margin-top:24px'>", unsafe_allow_html=True)

                CHART_METRICS = [
                    ("Goals p90",       'goals_p90',        False),
                    ("xG p90",          'xg_p90',           False),
                    ("Shot asts p90",   'shot_asts_p90',     False),
                    ("Dribbles p90",    'dribbles_p90',      False),
                    ("Prog runs p90",   'prog_runs_p90',     False),
                    ("Crosses p90",     'crosses_p90',       False),
                    ("Duels p90",       'duels_p90',         False),
                    ("Duel win %",      'duel_win',          False),
                    ("Aerial p90",      'aerial_p90',        False),
                    ("Interceptions",   'interceptions_p90', False),
                    ("Recoveries p90",  'recoveries_p90',    False),
                    ("Pass acc %",      'pass_acc',          False),
                    ("Ball security",   'losses_p90',        True),
                ]

                chart_labels, client_pcts, comp_pcts = [], [], []
                for label, key, inv in CHART_METRICS:
                    if key not in peer_data: continue
                    cv = season.get(key)
                    xv = comp.get(key)
                    cp_c = percentile_rank(cv, peer_data[key], inverse=inv) if cv is not None else None
                    cp_x = percentile_rank(xv, peer_data[key], inverse=inv) if xv is not None else None
                    if cp_c is not None and cp_x is not None:
                        chart_labels.append(label)
                        client_pcts.append(cp_c)
                        comp_pcts.append(cp_x)

                if len(chart_labels) >= 3:
                    fig_cmp = go.Figure()
                    fig_cmp.add_bar(
                        y=chart_labels, x=client_pcts, name=name,
                        orientation='h', marker_color=GOLD,
                        hovertemplate='%{y}: %{x:.0f}th pct<extra>' + name + '</extra>'
                    )
                    fig_cmp.add_bar(
                        y=chart_labels, x=comp_pcts, name=selected_name,
                        orientation='h', marker_color='#3b82f6',
                        hovertemplate='%{y}: %{x:.0f}th pct<extra>' + selected_name + '</extra>'
                    )
                    fig_cmp.add_vline(x=50, line_color='#444', line_dash='dot', line_width=1)
                    fig_cmp.update_layout(
                        **base_layout(f'Percentile comparison · {name} vs {selected_name}',
                                      height=max(320, len(chart_labels) * 32 + 80)),
                        barmode='group',
                        xaxis=dict(range=[0, 100], ticksuffix='th', gridcolor=GRID_COL,
                                   showgrid=True, tickfont=dict(size=10, color='#666')),
                        yaxis=dict(tickfont=dict(size=10, color=TEXT_COL), gridcolor=GRID_COL,
                                   showgrid=False, autorange='reversed'),
                        margin=dict(l=130, r=20, t=50, b=40),
                    )
                    st.plotly_chart(fig_cmp, use_container_width=True)
                elif peer_df is not None:
                    st.info("Upload a peer group file with matching columns to enable the percentile comparison chart.")

                st.markdown("</div>", unsafe_allow_html=True)
