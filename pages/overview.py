"""
pages/overview.py
Beswicks Sports Analytics — Client Overview

Shows all clients in a summary grid — name, club, position, spotlight
metrics, form trajectory, and physical output.
"""

import streamlit as st
import pandas as pd
import os
import glob
from datetime import datetime

from src.metrics import get_season_totals, get_physical_totals, compute_trajectory

st.set_page_config(
    page_title="Beswicks | Client Overview",
    page_icon="📋",
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
</style>
""", unsafe_allow_html=True)

# ── Paths ──────────────────────────────────────────────────────────────────────
DATA_DIR    = "data"
PLAYERS_DIR = os.path.join(DATA_DIR, "players")

GOLD   = '#c8a45a'
GREEN  = '#4ade80'
YELLOW = '#facc15'
RED    = '#f87171'
GREY   = '#555'

# ── Position spotlight metrics ─────────────────────────────────────────────────
# Maps position_group → list of (season_key, display_label, format_str) tuples
_POS_SPOTLIGHT = {
    'Central Defender': [
        ('def_duel_win',        'DefDuel%', '.1f'),
        ('aerial_win',          'Aerial%',  '.1f'),
        ('interceptions_p90',   'Int p90',  '.2f'),
    ],
    'Full Back': [
        ('crosses_p90',         'Cross p90','.2f'),
        ('prog_runs_p90',       'Prog p90', '.2f'),
        ('def_duel_win',        'DefDuel%', '.1f'),
    ],
    'Central Mid': [
        ('passes_p90',          'Pass p90', '.1f'),
        ('pass_acc',            'Pass%',    '.1f'),
        ('recoveries_p90',      'Rec p90',  '.2f'),
    ],
    'Att Mid': [
        ('xg_p90',              'xG p90',   '.2f'),
        ('xa_p90',              'xA p90',   '.2f'),
        ('prog_runs_p90',       'Prog p90', '.2f'),
    ],
    'Wide Mid': [
        ('crosses_p90',         'Cross p90','.2f'),
        ('xa_p90',              'xA p90',   '.2f'),
        ('dribbles_p90',        'Drb p90',  '.2f'),
    ],
    'Center Forward': [
        ('xg_p90',              'xG p90',   '.2f'),
        ('goals_p90',           'G p90',    '.2f'),
        ('aerial_win',          'Aerial%',  '.1f'),
    ],
    'Goalkeeper': [
        ('pass_acc',            'Pass%',    '.1f'),
        ('passes_p90',          'Pass p90', '.1f'),
        ('losses_p90',          'Loss p90', '.2f'),
    ],
}
_DEFAULT_SPOTLIGHT = [
    ('xg_p90',   'xG p90',  '.2f'),
    ('pass_acc', 'Pass%',   '.1f'),
    ('def_duel_win', 'DefDuel%', '.1f'),
]

# ── Form trajectory column per position (Wyscout column name) ──────────────────
_POS_TRAJ_COL = {
    'Central Defender': 'Duels',
    'Full Back':        'Passes',
    'Central Mid':      'Passes',
    'Att Mid':          'xG',
    'Wide Mid':         'xG',
    'Center Forward':   'Goals',
    'Goalkeeper':       'Passes',
}


# ── Data loaders ───────────────────────────────────────────────────────────────
@st.cache_data
def load_master(filepath):
    xls = pd.ExcelFile(filepath)
    return {s: pd.read_excel(xls, sheet_name=s)
            for s in ['Wyscout', 'Physical', 'Pressing', 'Off_Ball_Runs', 'Match_by_Match']
            if s in xls.sheet_names}


def get_player_list():
    """Scan data/players/ for master Excel files."""
    pattern = os.path.join(os.path.abspath(PLAYERS_DIR), "*_master.xlsx")
    files   = sorted(glob.glob(pattern))
    return [(os.path.basename(f).replace("_master.xlsx", "").replace("_", " "), f) for f in files]


def _fmt(val, fmt='.2f', fallback='–'):
    """Format a numeric value, returning fallback on None/error."""
    if val is None:
        return fallback
    try:
        return format(float(val), fmt)
    except Exception:
        return fallback


def _spotlight_html(season: dict, pos: str) -> str:
    """Render a row of 2-3 position-relevant spotlight metrics."""
    metrics = _POS_SPOTLIGHT.get(pos, _DEFAULT_SPOTLIGHT)
    parts   = []
    for key, label, fmt in metrics:
        raw = season.get(key)
        val = _fmt(raw, fmt)
        if val != '–':
            suffix = '%' if '%' in label else ''
            parts.append(
                f"<span style='color:#aaa'>{label}: "
                f"<span style='color:#e0e0e0;font-weight:600'>{val}{suffix}</span></span>"
            )
    return '  ·  '.join(parts) if parts else ''


def _form_html(traj: dict | None, label: str) -> str:
    """Render a compact form trend line."""
    if not traj:
        return ''
    col  = GREEN if traj['direction'] == 'up' else (RED if traj['direction'] == 'down' else GREY)
    sign = '+' if traj['pct_change'] > 0 else ''
    return (
        f"<div style='font-size:0.72rem;margin-top:5px;color:{col}'>"
        f"{traj['symbol']} {label} {sign}{traj['pct_change']:.0f}% · L8 vs P8"
        f"</div>"
    )


def player_card_html(
    display_name: str,
    season: dict,
    phys: dict | None,
    club: str,
    pos: str,
    updated_str: str,
    traj: dict | None,
    traj_label: str,
    form_dip: bool,
) -> str:
    """Render an enhanced dark summary card for one client."""
    mins    = int(season.get('mins', 0))
    matches = int(season.get('matches', 0))
    goals   = int(season.get('goals_raw', 0))
    assists = int(season.get('assists_raw', 0))

    border_col = RED if form_dip else GOLD

    spotlight = _spotlight_html(season, pos)
    spotlight_div = (
        f"<div style='font-size:0.75rem;margin-bottom:5px;line-height:1.6'>{spotlight}</div>"
        if spotlight else ''
    )

    phys_line = ''
    if phys:
        td  = _fmt(phys.get('total_dist_p90'), '.1f')
        psv = _fmt(phys.get('psv99_avg'), '.2f')
        phys_line = (
            f"<div style='font-size:0.72rem;color:#888;margin-top:4px'>"
            f"📏 {td} km/90  ·  ⚡ PSV99 {psv}</div>"
        )

    form_div  = _form_html(traj, traj_label)
    dip_badge = (
        "<span style='background:#f87171;color:#0f0f0f;font-size:0.62rem;"
        "font-weight:700;padding:2px 6px;border-radius:3px;margin-left:6px'>FORM DIP</span>"
        if form_dip else ''
    )

    return f"""
<div style='background:#0f0f0f;border-radius:10px;padding:18px 20px;
            border-left:4px solid {border_col};margin-bottom:4px;height:100%;'>
  <div style='font-size:1.05rem;font-weight:700;color:#fff;margin-bottom:2px'>
    {display_name}{dip_badge}
  </div>
  <div style='font-size:0.75rem;color:#888;margin-bottom:8px'>{club or '—'}  ·  {pos or '—'}</div>
  <div style='display:flex;gap:18px;font-size:0.8rem;margin-bottom:6px'>
    <span><span style='color:{GOLD};font-weight:700'>{goals}</span><span style='color:#666'> G</span></span>
    <span><span style='color:{GOLD};font-weight:700'>{assists}</span><span style='color:#666'> A</span></span>
    <span style='color:#aaa'>{matches} apps · {mins:,} mins</span>
  </div>
  {spotlight_div}
  {form_div}
  {phys_line}
  <div style='font-size:0.65rem;color:#444;margin-top:8px;border-top:1px solid #1e1e1e;padding-top:6px'>
    Updated: {updated_str}
  </div>
</div>"""


# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="header-bar">
  <div><h1>Client Overview</h1><div class="sub">All clients · Season 2025/26</div></div>
  <div class="beswicks-badge">Beswicks Sports</div>
</div>
""", unsafe_allow_html=True)

st.caption("Form trajectory compares last 8 appearances vs previous 8 (per 90). Red border = >15% drop.")

# ── Load and render ────────────────────────────────────────────────────────────
player_list = get_player_list()

if not player_list:
    st.warning(f"No player files found in `{PLAYERS_DIR}`.")
    st.stop()

cols_per_row = 3
rows = [player_list[i:i + cols_per_row] for i in range(0, len(player_list), cols_per_row)]

for row in rows:
    cols = st.columns(cols_per_row)
    for col, (display_name, filepath) in zip(cols, row):
        with col:
            try:
                sheets = load_master(filepath)
                ws_raw = sheets.get('Wyscout')
                ph_raw = sheets.get('Physical')

                if ws_raw is None:
                    st.warning(f"{display_name}: no Wyscout sheet")
                    continue

                ws     = ws_raw[ws_raw['Minutes played'] >= 20].copy()
                # Sort by date for trajectory accuracy
                if 'Date' in ws.columns:
                    ws = ws.sort_values('Date').reset_index(drop=True)

                season = get_season_totals(ws)

                ph   = ph_raw[ph_raw['minutes_full_all'] >= 20].copy() if ph_raw is not None else None
                phys = get_physical_totals(ph) if ph is not None else None

                # Position and club metadata
                club = ''
                pos  = ''
                if ph_raw is not None:
                    if 'team_name'      in ph_raw.columns: club = str(ph_raw['team_name'].iloc[0])
                    if 'position_group' in ph_raw.columns: pos  = str(ph_raw['position_group'].iloc[0])

                # Fallback: read position from Wyscout if Physical sheet missing
                if not pos and 'Position' in ws_raw.columns:
                    pos = str(ws_raw['Position'].iloc[0])

                # Trajectory — pick the most meaningful column per position
                traj_col   = _POS_TRAJ_COL.get(pos, 'xG')
                traj_label = traj_col  # e.g. "xG", "Duels", "Passes"
                traj = compute_trajectory(ws, traj_col)

                # Form dip flag: direction is down AND > 15% relative drop
                form_dip = (
                    traj is not None
                    and traj['direction'] == 'down'
                    and traj['pct_change'] < -15
                )

                updated_str = datetime.fromtimestamp(os.path.getmtime(filepath)).strftime('%d %b %Y')

                st.markdown(
                    player_card_html(
                        display_name, season, phys, club, pos,
                        updated_str, traj, traj_label, form_dip,
                    ),
                    unsafe_allow_html=True,
                )

            except Exception as e:
                st.error(f"{display_name}: {e}")
