"""
pages/overview.py
Beswicks Sports Analytics — Client Overview

Shows all clients in a summary grid — name, club, position, key stats, freshness.
"""

import streamlit as st
import pandas as pd
import os
import glob
from datetime import datetime

from src.metrics import get_season_totals, get_physical_totals

st.set_page_config(
    page_title="Beswicks | Client Overview",
    page_icon="📋",
    layout="wide",
)

# ── Dark CSS (same block as app.py) ───────────────────────────────────────────
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

# ── Paths ─────────────────────────────────────────────────────────────────────
DATA_DIR    = "data"
PLAYERS_DIR = os.path.join(DATA_DIR, "players")

GOLD   = '#c8a45a'
GREEN  = '#4ade80'
YELLOW = '#facc15'
RED    = '#f87171'


# ── Data loaders ──────────────────────────────────────────────────────────────
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


def _stat(val, fmt=".2f", fallback="–"):
    if val is None:
        return fallback
    try:
        return format(float(val), fmt)
    except Exception:
        return fallback


def player_card_html(display_name, season, phys, club, pos, updated_str):
    """Render a dark summary card for one client."""
    mins    = int(season.get('mins', 0))
    matches = int(season.get('matches', 0))
    goals   = int(season.get('goals_raw', 0))
    assists = int(season.get('assists_raw', 0))

    phys_line = ""
    if phys:
        td  = _stat(phys.get('total_dist_p90'), ".1f")
        psv = _stat(phys.get('psv99_avg'), ".2f")
        phys_line = f"<div style='font-size:0.72rem;color:#888;margin-top:4px'>📏 {td} km/90 · ⚡ PSV99 {psv}</div>"

    return f"""
<div style='background:#0f0f0f;border-radius:10px;padding:18px 20px;
            border-left:4px solid {GOLD};margin-bottom:4px;height:100%;'>
  <div style='font-size:1.05rem;font-weight:700;color:#fff;margin-bottom:2px'>{display_name}</div>
  <div style='font-size:0.75rem;color:#888;margin-bottom:8px'>{club or "—"} · {pos or "—"}</div>
  <div style='display:flex;gap:18px;font-size:0.8rem;margin-bottom:6px'>
    <span><span style='color:{GOLD};font-weight:700'>{goals}</span><span style='color:#666'> G</span></span>
    <span><span style='color:{GOLD};font-weight:700'>{assists}</span><span style='color:#666'> A</span></span>
    <span style='color:#aaa'>{matches} apps · {mins} mins</span>
  </div>
  {phys_line}
  <div style='font-size:0.65rem;color:#444;margin-top:8px;border-top:1px solid #1e1e1e;padding-top:6px'>
    Updated: {updated_str}
  </div>
</div>"""


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="header-bar">
  <div><h1>Client Overview</h1><div class="sub">All clients · Season 2025/26</div></div>
  <div class="beswicks-badge">Beswicks Sports</div>
</div>
""", unsafe_allow_html=True)

st.caption("Select a player from the sidebar on any page to view full analysis.")

# ── Load and render ───────────────────────────────────────────────────────────
player_list = get_player_list()

if not player_list:
    st.warning(f"No player files found in `{PLAYERS_DIR}`.")
    st.stop()

# Build cards in rows of 3
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
                season = get_season_totals(ws)

                ph   = ph_raw[ph_raw['minutes_full_all'] >= 20].copy() if ph_raw is not None else None
                phys = get_physical_totals(ph) if ph is not None else None

                # Metadata from Physical sheet
                club = ""
                pos  = ""
                if ph_raw is not None:
                    if 'team_name'      in ph_raw.columns: club = ph_raw['team_name'].iloc[0]
                    if 'position_group' in ph_raw.columns: pos  = ph_raw['position_group'].iloc[0]

                updated_str = datetime.fromtimestamp(os.path.getmtime(filepath)).strftime('%d %b %Y')

                st.markdown(
                    player_card_html(display_name, season, phys, club, pos, updated_str),
                    unsafe_allow_html=True,
                )
            except Exception as e:
                st.error(f"{display_name}: {e}")
