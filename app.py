import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import datetime

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Beswicks Sports | Player Analysis",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Font & base */
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    /* Hide Streamlit chrome */
    #MainMenu, footer, header { visibility: hidden; }
    .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background: #0f0f0f;
    }
    [data-testid="stSidebar"] * { color: #e0e0e0 !important; }
    [data-testid="stSidebar"] .stFileUploader label { color: #aaa !important; }

    /* Header bar */
    .header-bar {
        background: #0f0f0f;
        padding: 18px 28px;
        border-radius: 10px;
        margin-bottom: 20px;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .header-bar h1 {
        color: #ffffff;
        font-size: 1.35rem;
        font-weight: 700;
        margin: 0;
        letter-spacing: -0.02em;
    }
    .header-bar .sub {
        color: #888;
        font-size: 0.78rem;
        margin-top: 2px;
    }
    .beswicks-badge {
        background: #c8a45a;
        color: #0f0f0f;
        font-size: 0.7rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        padding: 4px 10px;
        border-radius: 4px;
        text-transform: uppercase;
    }

    /* Profile card */
    .profile-card {
        background: #0f0f0f;
        border-radius: 10px;
        padding: 22px 26px;
        margin-bottom: 20px;
        border-left: 4px solid #c8a45a;
    }
    .profile-name {
        font-size: 1.6rem;
        font-weight: 700;
        color: #ffffff;
        margin: 0 0 4px;
    }
    .profile-meta {
        color: #aaa;
        font-size: 0.82rem;
        margin: 0;
    }
    .profile-tags {
        margin-top: 12px;
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
    }
    .tag {
        background: #1e1e1e;
        border: 1px solid #333;
        color: #ccc;
        border-radius: 5px;
        padding: 4px 10px;
        font-size: 0.74rem;
    }
    .tag-gold {
        background: #2a2218;
        border: 1px solid #c8a45a;
        color: #c8a45a;
    }

    /* Metric cards */
    .metric-grid {
        display: grid;
        gap: 10px;
    }
    .metric-card {
        background: #1a1a1a;
        border-radius: 8px;
        padding: 14px 16px;
        border: 1px solid #2a2a2a;
    }
    .metric-label {
        font-size: 0.7rem;
        color: #777;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        margin-bottom: 4px;
    }
    .metric-value {
        font-size: 1.5rem;
        font-weight: 700;
        color: #fff;
        margin: 0;
        line-height: 1;
    }
    .metric-sub {
        font-size: 0.7rem;
        color: #555;
        margin-top: 4px;
    }
    .metric-good .metric-value { color: #4ade80; }
    .metric-warn .metric-value { color: #facc15; }
    .metric-bad  .metric-value { color: #f87171; }

    /* Section headers */
    .section-header {
        font-size: 0.7rem;
        font-weight: 700;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: #c8a45a;
        margin: 24px 0 12px;
        padding-bottom: 6px;
        border-bottom: 1px solid #2a2a2a;
    }

    /* Table */
    .match-table { font-size: 0.75rem; }
    .stDataFrame { border-radius: 8px; overflow: hidden; }

    /* Divider */
    hr { border-color: #2a2a2a; margin: 20px 0; }

    /* Upload prompt */
    .upload-prompt {
        text-align: center;
        padding: 60px 20px;
        color: #555;
    }
    .upload-prompt h2 { color: #888; font-size: 1.2rem; }
    .upload-prompt p { font-size: 0.85rem; }
</style>
""", unsafe_allow_html=True)

# ── Helpers ───────────────────────────────────────────────────────────────────
def p90(value, minutes):
    if minutes == 0:
        return 0.0
    return round((value / minutes) * 90, 2)

def pct(num, denom):
    if denom == 0:
        return None
    return round((num / denom) * 100, 1)

def load_data(file):
    """Load all sheets from uploaded Excel file."""
    xls = pd.ExcelFile(file)
    sheets = {}
    for sheet in ['Wyscout', 'Physical', 'Pressing', 'Off_Ball_Runs', 'Match_by_Match']:
        if sheet in xls.sheet_names:
            sheets[sheet] = pd.read_excel(xls, sheet_name=sheet)
    return sheets

def process_wyscout(df):
    """Filter, sort and compute derived cols for Wyscout sheet."""
    df = df[df['Minutes played'] >= 20].copy()
    df = df.sort_values('Date').reset_index(drop=True)
    # Rename ambiguous duplicate cols by position
    cols = list(df.columns)
    df.columns = cols  # keep as-is, access by index where needed
    return df

def process_physical(df):
    df = df[df['minutes_full_all'] >= 20].copy()
    df = df.sort_values('match_date').reset_index(drop=True)
    return df

def get_season_totals(ws):
    """Compute season-level per-90 metrics from Wyscout data."""
    mins = ws['Minutes played'].sum()
    s = ws.sum(numeric_only=True)
    cols = list(ws.columns)

    pass_acc    = pct(ws.iloc[:, 13].sum(), s['Passes'])
    lp_acc      = pct(ws.iloc[:, 15].sum(), s['Long passes'])
    drib_pct    = pct(ws.iloc[:, 19].sum(), s['Dribbles'])
    duel_win    = pct(ws.iloc[:, 21].sum(), s['Duels'])
    aerial_win  = pct(ws.iloc[:, 23].sum(), s['Aerial duels'])
    def_duel_w  = pct(ws.iloc[:, 32].sum(), ws.iloc[:, 31].sum())
    yellow_raw  = int(ws.iloc[:, 39].sum())
    red_raw     = int(ws.iloc[:, 40].sum())

    return {
        'mins': mins,
        'matches': len(ws),
        'goals_raw': int(s['Goals']),
        'assists_raw': int(s['Assists']),
        'yellow': yellow_raw,
        'red': red_raw,
        'goals_p90': p90(s['Goals'], mins),
        'assists_p90': p90(s['Assists'], mins),
        'xg_p90': p90(s['xG'], mins),
        'xa_p90': p90(s['xA'], mins),
        'shots_p90': p90(s['Shots'], mins),
        'shot_asts_p90': p90(ws['Shot assists'].sum(), mins),
        'touches_box_p90': p90(ws['Touches in penalty area'].sum(), mins),
        'dribbles_p90': p90(s['Dribbles'], mins),
        'drib_pct': drib_pct,
        'prog_runs_p90': p90(ws['Progressive runs'].sum(), mins),
        'ptf3_p90': p90(ws['Passes to final third'].sum(), mins),
        'passes_p90': p90(s['Passes'], mins),
        'pass_acc': pass_acc,
        'long_passes_p90': p90(s['Long passes'], mins),
        'lp_acc': lp_acc,
        'crosses_p90': p90(s['Crosses'], mins),
        'duels_p90': p90(s['Duels'], mins),
        'duel_win': duel_win,
        'aerial_p90': p90(s['Aerial duels'], mins),
        'aerial_win': aerial_win,
        'def_duels_p90': p90(ws.iloc[:, 31].sum(), mins),
        'def_duel_win': def_duel_w,
        'interceptions_p90': p90(s['Interceptions'], mins),
        'recoveries_p90': p90(s['Recoveries'], mins),
        'rec_opp_p90': p90(ws['opp. half'].sum(), mins),
        'clearances_p90': p90(s['Clearances'], mins),
        'losses_p90': p90(s['Losses'], mins),
        'losses_oh_p90': p90(ws['own half'].sum(), mins),
        'fouls_p90': p90(ws['Fouls'].sum(), mins),
    }

def get_physical_totals(ph):
    mins = ph['minutes_full_all'].sum()
    s = ph.sum(numeric_only=True)
    return {
        'ph_mins': mins,
        'ph_matches': len(ph),
        'total_dist_p90': p90(s['total_distance_full_all'], mins),
        'hsr_dist_p90': p90(s['hsr_distance_full_all'], mins),
        'hsr_count_p90': p90(s['hsr_count_full_all'], mins),
        'sprint_dist_p90': p90(s['sprint_distance_full_all'], mins),
        'sprint_count_p90': p90(s['sprint_count_full_all'], mins),
        'hi_dist_p90': p90(s['hi_distance_full_all'], mins),
        'psv99_avg': round(ph['psv99'].mean(), 2),
        'psv99_max': round(ph['psv99'].max(), 2),
        'med_accel_p90': p90(s['medaccel_count_full_all'], mins),
        'high_accel_p90': p90(s['highaccel_count_full_all'], mins),
        'med_decel_p90': p90(s['meddecel_count_full_all'], mins),
        'high_decel_p90': p90(s['highdecel_count_full_all'], mins),
        'cod_p90': p90(s['cod_count_full_all'], mins),
    }

def build_match_log(ws):
    """Build the formatted match log dataframe."""
    cols = list(ws.columns)
    rows = []
    for _, r in ws.iterrows():
        mins = r['Minutes played']
        def safe_pct(n, d):
            return f"{int(round(n/d*100))}%" if d > 0 else "-"

        rows.append({
            'Match': r['Match'],
            'Date': pd.to_datetime(r['Date']).strftime('%d %b') if pd.notna(r['Date']) else '',
            'Pos': str(r['Position']),
            'Min': int(mins),
            'G': int(r['Goals']),
            'A': int(r['Assists']),
            'xG': round(r['xG'], 2),
            'xA': round(r['xA'], 2),
            'ShAst': int(r['Shot assists']),
            'TouBox': int(r['Touches in penalty area']),
            'Drb': int(r['Dribbles']),
            'Drb%': safe_pct(r.iloc[19], r['Dribbles']),
            'Pass': int(r['Passes']),
            'Pass%': safe_pct(r.iloc[13], r['Passes']),
            'Cross': int(r['Crosses']),
            'PTF3': int(r['Passes to final third']),
            'Duels': int(r['Duels']),
            'Duel%': safe_pct(r.iloc[21], r['Duels']),
            'AerDuel': int(r['Aerial duels']),
            'Aer%': safe_pct(r.iloc[23], r['Aerial duels']),
            'DefDuel': int(r.iloc[31]),
            'DefD%': safe_pct(r.iloc[32], r.iloc[31]),
            'Int': int(r['Interceptions']),
            'Rec': int(r['Recoveries']),
            'Clr': int(r['Clearances']),
            'Loss': int(r['Losses']),
            'LossOH': int(r['own half']),
            'Foul': int(r['Fouls']),
        })
    return pd.DataFrame(rows)

# ── Plotly theme ──────────────────────────────────────────────────────────────
PLOT_BG  = '#0f0f0f'
PAPER_BG = '#0f0f0f'
GRID_COL = '#222222'
TEXT_COL = '#aaaaaa'
GOLD     = '#c8a45a'
BLUE     = '#3b82f6'
RED      = '#f87171'
GREEN    = '#4ade80'

def base_layout(title='', height=320):
    return dict(
        title=dict(text=title, font=dict(color=TEXT_COL, size=12), x=0),
        height=height,
        plot_bgcolor=PLOT_BG,
        paper_bgcolor=PAPER_BG,
        font=dict(color=TEXT_COL, size=11),
        margin=dict(l=10, r=10, t=36, b=40),
        xaxis=dict(
            gridcolor=GRID_COL, showgrid=False,
            tickfont=dict(size=9, color='#666'),
            tickangle=-45,
        ),
        yaxis=dict(
            gridcolor=GRID_COL, showgrid=True,
            tickfont=dict(size=10, color='#666'),
            zeroline=False,
        ),
        legend=dict(
            bgcolor='rgba(0,0,0,0)',
            font=dict(size=10, color='#888'),
            orientation='h',
            y=1.08,
        ),
        hovermode='x unified',
        hoverlabel=dict(bgcolor='#1a1a1a', font_size=11),
    )

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚽ Beswicks Sports")
    st.markdown("---")
    st.markdown("### Upload player data")
    uploaded_file = st.file_uploader(
        "Upload master Excel file",
        type=['xlsx'],
        help="Upload the player's master .xlsx file containing Wyscout, Physical, Pressing and Off_Ball_Runs sheets."
    )

    st.markdown("---")
    st.markdown("### Player details")
    player_name  = st.text_input("Full name", placeholder="e.g. Lasse Sørensen")
    player_club  = st.text_input("Club", placeholder="e.g. Huddersfield Town")
    player_league = st.text_input("League", placeholder="e.g. ENG - League One")
    player_pos   = st.text_input("Position", placeholder="e.g. Right Back / Wing-Back")
    player_age   = st.number_input("Age", min_value=15, max_value=45, value=24)

    st.markdown("---")
    st.caption("Beswicks Sports Analytics · Internal Use Only")

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="header-bar">
    <div>
        <h1>Player Analysis Platform</h1>
        <div class="sub">Wyscout + SkillCorner · 2025/26 Season</div>
    </div>
    <div class="beswicks-badge">Beswicks Sports</div>
</div>
""", unsafe_allow_html=True)

# ── Main content ──────────────────────────────────────────────────────────────
if uploaded_file is None:
    st.markdown("""
    <div class="upload-prompt">
        <h2>Upload a player file to begin</h2>
        <p>Use the sidebar to upload any client's master Excel file.<br>
        The app will generate their full performance profile automatically.</p>
        <p style="color:#444;margin-top:24px;font-size:0.75rem;">
            Accepts: Wyscout · SkillCorner Physical · Pressing · Off-Ball Runs
        </p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# ── Load & process data ───────────────────────────────────────────────────────
with st.spinner("Loading player data..."):
    sheets = load_data(uploaded_file)

ws_raw = sheets.get('Wyscout')
ph_raw = sheets.get('Physical')

if ws_raw is None:
    st.error("Could not find a 'Wyscout' sheet in this file. Please check the file format.")
    st.stop()

ws = process_wyscout(ws_raw)
season_totals = None  # placeholder, computed below

ph = process_physical(ph_raw) if ph_raw is not None else None

season = get_season_totals(ws)
phys   = get_physical_totals(ph) if ph is not None else None

# Derive display name
name    = player_name  or "Player"
club    = player_club  or "Club"
league  = player_league or "League"
pos     = player_pos   or "Position"
age_val = player_age

# Season dates
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
</div>
""", unsafe_allow_html=True)

# ── Seasonal metrics dashboard ────────────────────────────────────────────────
st.markdown('<div class="section-header">Seasonal metrics · per 90</div>', unsafe_allow_html=True)

def metric_card(label, value, sub='', rating=''):
    cls = f"metric-card metric-{rating}" if rating else "metric-card"
    return f"""
    <div class="{cls}">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{value}</div>
        {'<div class="metric-sub">' + sub + '</div>' if sub else ''}
    </div>"""

# Row 1: Physical (if available)
if phys:
    st.markdown("**Physical output**")
    c1, c2, c3, c4, c5 = st.columns(5)
    cards = [
        (c1, "Total dist p90", f"{int(phys['total_dist_p90']):,}m", "Elite for this tier", "good"),
        (c2, "HSR dist p90",   f"{int(phys['hsr_dist_p90'])}m",    f"{phys['hsr_count_p90']:.0f} reps", "good"),
        (c3, "Sprint dist p90",f"{int(phys['sprint_dist_p90'])}m", f"{phys['sprint_count_p90']:.0f} sprints", "good"),
        (c4, "PSV99 avg",      str(phys['psv99_avg']),              f"Peak: {phys['psv99_max']}", "good"),
        (c5, "COD count p90",  f"{phys['cod_p90']:.0f}",           "Changes of direction", ""),
    ]
    for col, label, val, sub, rating in cards:
        col.markdown(f"""
        <div class="metric-card {'metric-' + rating if rating else ''}">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{val}</div>
            <div class="metric-sub">{sub}</div>
        </div>""", unsafe_allow_html=True)

# Row 2: Attacking
st.markdown("**Attacking output**")
c1, c2, c3, c4, c5, c6 = st.columns(6)
atk_cards = [
    (c1, "Goals p90",      f"{season['goals_p90']:.2f}",       f"{season['goals_raw']} raw", "good" if season['goals_raw'] >= 2 else ""),
    (c2, "Assists p90",    f"{season['assists_p90']:.2f}",      f"{season['assists_raw']} raw", ""),
    (c3, "xG p90",         f"{season['xg_p90']:.2f}",          "", ""),
    (c4, "xA p90",         f"{season['xa_p90']:.2f}",          "", ""),
    (c5, "Shot asts p90",  f"{season['shot_asts_p90']:.2f}",   "", "good" if season['shot_asts_p90'] > 0.5 else ""),
    (c6, "Touches in box", f"{season['touches_box_p90']:.2f}", "per 90", ""),
]
for col, label, val, sub, rating in atk_cards:
    col.markdown(f"""
    <div class="metric-card {'metric-' + rating if rating else ''}">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{val}</div>
        <div class="metric-sub">{sub}</div>
    </div>""", unsafe_allow_html=True)

# Row 3: Passing + carrying
st.markdown("**Passing & ball-carrying**")
c1, c2, c3, c4, c5 = st.columns(5)
pass_cards = [
    (c1, "Passes p90",    f"{season['passes_p90']:.1f}",     f"{season['pass_acc']:.1f}% accuracy", "good" if season['pass_acc'] and season['pass_acc'] > 80 else "warn" if season['pass_acc'] and season['pass_acc'] > 70 else "bad"),
    (c2, "Long pass p90", f"{season['long_passes_p90']:.2f}",f"{season['lp_acc']:.1f}% accuracy" if season['lp_acc'] else "", ""),
    (c3, "Crosses p90",   f"{season['crosses_p90']:.2f}",    "", ""),
    (c4, "Dribbles p90",  f"{season['dribbles_p90']:.2f}",   f"{season['drib_pct']:.1f}% success" if season['drib_pct'] else "", "good" if season['drib_pct'] and season['drib_pct'] > 60 else ""),
    (c5, "Prog runs p90", f"{season['prog_runs_p90']:.2f}",  "", ""),
]
for col, label, val, sub, rating in pass_cards:
    col.markdown(f"""
    <div class="metric-card {'metric-' + rating if rating else ''}">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{val}</div>
        <div class="metric-sub">{sub}</div>
    </div>""", unsafe_allow_html=True)

# Row 4: Defensive
st.markdown("**Defensive output**")
c1, c2, c3, c4, c5, c6 = st.columns(6)
def_cards = [
    (c1, "Duels p90",      f"{season['duels_p90']:.1f}",        f"{season['duel_win']:.1f}% win rate",    "warn" if season['duel_win'] and season['duel_win'] < 55 else "good"),
    (c2, "Aerial p90",     f"{season['aerial_p90']:.2f}",       f"{season['aerial_win']:.1f}% win rate" if season['aerial_win'] else "", ""),
    (c3, "Def duels p90",  f"{season['def_duels_p90']:.2f}",    f"{season['def_duel_win']:.1f}% win rate" if season['def_duel_win'] else "", "warn" if season['def_duel_win'] and season['def_duel_win'] < 60 else "good"),
    (c4, "Interceptions",  f"{season['interceptions_p90']:.2f}","per 90", "good" if season['interceptions_p90'] > 4 else ""),
    (c5, "Recoveries p90", f"{season['recoveries_p90']:.2f}",   f"Opp half: {season['rec_opp_p90']:.2f}", ""),
    (c6, "Losses p90",     f"{season['losses_p90']:.2f}",       f"Own half: {season['losses_oh_p90']:.2f}","bad" if season['losses_p90'] > 12 else "warn"),
]
for col, label, val, sub, rating in def_cards:
    col.markdown(f"""
    <div class="metric-card {'metric-' + rating if rating else ''}">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{val}</div>
        <div class="metric-sub">{sub}</div>
    </div>""", unsafe_allow_html=True)

# ── Pressing (if available) ───────────────────────────────────────────────────
pressing_raw = sheets.get('Pressing')
if pressing_raw is not None:
    press = pressing_raw[pressing_raw['minutes_played_per_match'] >= 20]
    if len(press) > 0:
        st.markdown("**Under-pressure passing**")
        c1, c2, c3 = st.columns(3)
        avg_ret  = press['ball_retention_ratio_under_pressure'].mean()
        avg_comp = press['pass_completion_ratio_under_pressure'].mean()
        avg_pres = press['count_pressures_received_per_match'].mean()
        c1.markdown(f"""<div class="metric-card"><div class="metric-label">Pressures received p90</div><div class="metric-value">{avg_pres:.1f}</div></div>""", unsafe_allow_html=True)
        c2.markdown(f"""<div class="metric-card {'metric-warn' if avg_ret < 70 else 'metric-good'}"><div class="metric-label">Ball retention under press</div><div class="metric-value">{avg_ret:.1f}%</div></div>""", unsafe_allow_html=True)
        c3.markdown(f"""<div class="metric-card {'metric-warn' if avg_comp < 70 else 'metric-good'}"><div class="metric-label">Pass completion under press</div><div class="metric-value">{avg_comp:.1f}%</div></div>""", unsafe_allow_html=True)

# ── Off-ball runs (if available) ──────────────────────────────────────────────
obr_raw = sheets.get('Off_Ball_Runs')
if obr_raw is not None:
    obr = obr_raw[obr_raw['minutes_played_per_match'] >= 20]
    if len(obr) > 0:
        st.markdown("**Off-ball runs**")
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(f"""<div class="metric-card"><div class="metric-label">Runs per match</div><div class="metric-value">{obr['count_runs_per_match'].mean():.1f}</div></div>""", unsafe_allow_html=True)
        c2.markdown(f"""<div class="metric-card"><div class="metric-label">Dangerous runs</div><div class="metric-value">{obr['count_dangerous_runs_per_match'].mean():.1f}</div></div>""", unsafe_allow_html=True)
        c3.markdown(f"""<div class="metric-card"><div class="metric-label">Runs targeted</div><div class="metric-value">{obr['count_runs_targeted_per_match'].mean():.1f}</div></div>""", unsafe_allow_html=True)
        c4.markdown(f"""<div class="metric-card"><div class="metric-label">Runs received</div><div class="metric-value">{obr['count_runs_received_per_match'].mean():.1f}</div></div>""", unsafe_allow_html=True)

# ── Physical charts ───────────────────────────────────────────────────────────
if ph is not None and len(ph) > 0:
    st.markdown('<div class="section-header">Physical output · match by match</div>', unsafe_allow_html=True)

    ph['match_label'] = ph['match_date'].apply(
        lambda x: pd.to_datetime(x).strftime('%d %b') if pd.notna(x) else ''
    )
    ph['dist_p90']   = ph.apply(lambda r: p90(r['total_distance_full_all'],   r['minutes_full_all']), axis=1)
    ph['hsr_p90']    = ph.apply(lambda r: p90(r['hsr_distance_full_all'],     r['minutes_full_all']), axis=1)
    ph['sprint_p90'] = ph.apply(lambda r: p90(r['sprint_distance_full_all'],  r['minutes_full_all']), axis=1)
    avg_dist   = ph['dist_p90'].mean()
    avg_hsr    = ph['hsr_p90'].mean()

    tab1, tab2, tab3 = st.tabs(["Distance", "HSR & Sprint", "PSV99 & Accelerations"])

    with tab1:
        fig = go.Figure()
        fig.add_bar(
            x=ph['match_label'], y=ph['dist_p90'],
            marker_color=[GOLD if v >= avg_dist else '#333' for v in ph['dist_p90']],
            name='Total dist p90', hovertemplate='%{y:,.0f}m<extra></extra>'
        )
        fig.add_scatter(
            x=ph['match_label'], y=[avg_dist]*len(ph),
            mode='lines', name=f'Avg ({avg_dist:,.0f}m)',
            line=dict(color=RED, width=1.5, dash='dot'), hoverinfo='skip'
        )
        fig.update_layout(**base_layout('Total distance per 90 (m)', height=300))
        fig.update_yaxes(range=[8000, ph['dist_p90'].max() * 1.05])
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        fig2 = go.Figure()
        fig2.add_bar(x=ph['match_label'], y=ph['hsr_p90'],    name='HSR dist p90',    marker_color=BLUE,       hovertemplate='HSR: %{y:.0f}m<extra></extra>')
        fig2.add_bar(x=ph['match_label'], y=ph['sprint_p90'], name='Sprint dist p90', marker_color=GOLD+'88',  hovertemplate='Sprint: %{y:.0f}m<extra></extra>')
        fig2.add_scatter(
            x=ph['match_label'], y=[avg_hsr]*len(ph),
            mode='lines', name=f'HSR avg ({avg_hsr:.0f}m)',
            line=dict(color=BLUE, width=1.5, dash='dot'), hoverinfo='skip'
        )
        fig2.update_layout(**base_layout('HSR & sprint distance per 90 (m)', height=300), barmode='group')
        st.plotly_chart(fig2, use_container_width=True)

    with tab3:
        fig3 = make_subplots(specs=[[{"secondary_y": True}]])
        fig3.add_scatter(
            x=ph['match_label'], y=ph['psv99'],
            mode='lines+markers', name='PSV99',
            line=dict(color=GREEN, width=2),
            marker=dict(size=5, color=GREEN),
            hovertemplate='PSV99: %{y:.2f}<extra></extra>',
            secondary_y=False
        )
        avg_psv = ph['psv99'].mean()
        fig3.add_scatter(
            x=ph['match_label'], y=[avg_psv]*len(ph),
            mode='lines', name=f'Avg ({avg_psv:.2f})',
            line=dict(color='#555', width=1, dash='dot'),
            hoverinfo='skip', secondary_y=False
        )
        fig3.add_bar(
            x=ph['match_label'],
            y=ph.apply(lambda r: p90(r['highaccel_count_full_all'], r['minutes_full_all']), axis=1),
            name='High accel p90',
            marker_color=GOLD+'66',
            hovertemplate='High accel: %{y:.1f}<extra></extra>',
            secondary_y=True
        )
        fig3.update_layout(**base_layout('PSV99 & high accelerations per 90', height=300))
        fig3.update_yaxes(range=[7.0, ph['psv99'].max() + 0.3], secondary_y=False, title_text='PSV99', title_font=dict(size=10, color='#555'))
        fig3.update_yaxes(secondary_y=True, title_text='High accel p90', title_font=dict(size=10, color='#555'), showgrid=False)
        st.plotly_chart(fig3, use_container_width=True)

# ── Form trend charts ─────────────────────────────────────────────────────────
st.markdown('<div class="section-header">Form trends · match by match</div>', unsafe_allow_html=True)

ws['match_label'] = ws['Date'].apply(
    lambda x: pd.to_datetime(x).strftime('%d %b') if pd.notna(x) else ''
)
ws_cols = list(ws.columns)

ws['duel_win_pct']     = ws.apply(lambda r: pct(r.iloc[21], r['Duels']), axis=1)
ws['def_duel_win_pct'] = ws.apply(lambda r: pct(r.iloc[32], r.iloc[31]), axis=1)
ws['losses_p90_m']     = ws.apply(lambda r: p90(r['Losses'], r['Minutes played']), axis=1)
ws['ptf3_p90_m']       = ws.apply(lambda r: p90(r['Passes to final third'], r['Minutes played']), axis=1)
ws['shot_ast_p90_m']   = ws.apply(lambda r: p90(r['Shot assists'], r['Minutes played']), axis=1)
ws['pass_acc_pct']     = ws.apply(lambda r: pct(r.iloc[13], r['Passes']), axis=1)

ftab1, ftab2, ftab3 = st.tabs(["Duels", "Attacking output", "Losses & passing"])

with ftab1:
    fig_d = go.Figure()
    fig_d.add_scatter(
        x=ws['match_label'], y=ws['duel_win_pct'],
        mode='lines+markers', name='All duel win %',
        line=dict(color=BLUE, width=2),
        marker=dict(size=5), connectgaps=True,
        hovertemplate='Duel win: %{y:.0f}%<extra></extra>'
    )
    fig_d.add_scatter(
        x=ws['match_label'], y=ws['def_duel_win_pct'],
        mode='lines+markers', name='Def duel win %',
        line=dict(color=RED, width=2, dash='dot'),
        marker=dict(size=5), connectgaps=True,
        hovertemplate='Def duel win: %{y:.0f}%<extra></extra>'
    )
    fig_d.add_scatter(
        x=ws['match_label'], y=[50]*len(ws),
        mode='lines', name='50% line',
        line=dict(color='#444', width=1, dash='dash'), hoverinfo='skip'
    )
    fig_d.update_layout(**base_layout('Duel win % (all & defensive)', height=320))
    fig_d.update_yaxes(range=[0, 115])
    st.plotly_chart(fig_d, use_container_width=True)

with ftab2:
    fig_a = go.Figure()
    fig_a.add_bar(
        x=ws['match_label'], y=ws['ptf3_p90_m'],
        name='PTF3 p90', marker_color=BLUE+'99',
        hovertemplate='PTF3 p90: %{y:.1f}<extra></extra>'
    )
    fig_a.add_bar(
        x=ws['match_label'], y=ws['shot_ast_p90_m'],
        name='Shot asts p90', marker_color=GREEN,
        hovertemplate='Shot asts p90: %{y:.1f}<extra></extra>'
    )
    # Goal markers
    goal_games = ws[ws['Goals'] > 0]
    if len(goal_games) > 0:
        fig_a.add_scatter(
            x=goal_games['match_label'],
            y=[ws['ptf3_p90_m'].max() * 1.1] * len(goal_games),
            mode='markers+text',
            name='Goal',
            marker=dict(symbol='star', size=12, color=GOLD),
            text=['⭐']*len(goal_games),
            textposition='top center',
            hovertemplate='Goal scored<extra></extra>'
        )
    fig_a.update_layout(**base_layout('Attacking output per 90', height=320), barmode='group')
    st.plotly_chart(fig_a, use_container_width=True)

with ftab3:
    avg_loss = ws['losses_p90_m'].mean()
    fig_l = make_subplots(specs=[[{"secondary_y": True}]])
    fig_l.add_bar(
        x=ws['match_label'],
        y=ws['losses_p90_m'],
        name='Losses p90',
        marker_color=[RED if v >= 18 else GOLD+'88' if v >= 14 else '#333' for v in ws['losses_p90_m']],
        hovertemplate='Losses p90: %{y:.1f}<extra></extra>',
        secondary_y=False
    )
    fig_l.add_scatter(
        x=ws['match_label'], y=[avg_loss]*len(ws),
        mode='lines', name=f'Avg ({avg_loss:.1f})',
        line=dict(color='#555', width=1.5, dash='dot'),
        hoverinfo='skip', secondary_y=False
    )
    fig_l.add_scatter(
        x=ws['match_label'], y=ws['pass_acc_pct'],
        mode='lines+markers', name='Pass acc %',
        line=dict(color=GREEN, width=1.5),
        marker=dict(size=4), connectgaps=True,
        hovertemplate='Pass acc: %{y:.0f}%<extra></extra>',
        secondary_y=True
    )
    fig_l.update_layout(**base_layout('Losses per 90 & passing accuracy', height=320))
    fig_l.update_yaxes(secondary_y=True, title_text='Pass acc %', showgrid=False,
                       range=[40, 105], title_font=dict(size=10, color='#555'))
    st.plotly_chart(fig_l, use_container_width=True)

# ── Match log table ───────────────────────────────────────────────────────────
st.markdown('<div class="section-header">Match log · full game-by-game</div>', unsafe_allow_html=True)

match_log = build_match_log(ws)

# Search / filter
search = st.text_input("Filter by opponent or position", placeholder="e.g. Barnsley, RWB, Jan...")
if search:
    mask = match_log.apply(lambda row: row.astype(str).str.contains(search, case=False).any(), axis=1)
    display_log = match_log[mask]
else:
    display_log = match_log

st.dataframe(
    display_log,
    use_container_width=True,
    hide_index=True,
    height=520,
    column_config={
        "Match": st.column_config.TextColumn("Match", width="large"),
        "Date":  st.column_config.TextColumn("Date",  width="small"),
        "Pos":   st.column_config.TextColumn("Pos",   width="small"),
        "Min":   st.column_config.NumberColumn("Min",  format="%d"),
        "G":     st.column_config.NumberColumn("G",    format="%d"),
        "A":     st.column_config.NumberColumn("A",    format="%d"),
        "xG":    st.column_config.NumberColumn("xG",   format="%.2f"),
        "xA":    st.column_config.NumberColumn("xA",   format="%.2f"),
    }
)

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<div style='text-align:center;color:#444;font-size:0.72rem;padding:8px 0'>"
    "Beswicks Sports Analytics · Internal Use Only · "
    f"Generated {datetime.now().strftime('%d %b %Y')}"
    "</div>",
    unsafe_allow_html=True
)
