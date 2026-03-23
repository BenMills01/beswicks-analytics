"""
pages/match_report.py
Beswicks Sports Analytics — Individual Match Report

Select a player and a match to view a full single-match breakdown
(every stat vs the player's season average), then export as PDF.
"""

import streamlit as st
import pandas as pd
import os
import glob
from datetime import datetime

from src.metrics import (
    get_season_totals, get_physical_totals, build_match_log,
    p90, pct, parse_wyscout_label,
)

st.set_page_config(
    page_title="Beswicks | Match Report",
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
.section-header { font-size: 0.7rem; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: #c8a45a; margin: 20px 0 10px; padding-bottom: 6px; border-bottom: 1px solid #2a2a2a; }
</style>
""", unsafe_allow_html=True)

GOLD = '#c8a45a'
DATA_DIR    = "data"
PLAYERS_DIR = os.path.join(DATA_DIR, "players")


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


def delta_html(match_val, season_val, inverse=False, suffix=''):
    if match_val is None or season_val is None or season_val == 0:
        return "<span style='color:#555'>–</span>"
    diff  = match_val - season_val
    better = diff > 0 if not inverse else diff < 0
    if abs(diff) < 0.005:
        return "<span style='color:#888'>=</span>"
    col = '#4ade80' if better else '#f87171'
    ar  = '▲' if diff > 0 else '▼'
    return f"<span style='color:{col};font-weight:600'>{ar} {abs(diff):.2f}{suffix}</span>"


def stat_row_html(label, match_str, season_str, delta_html_str, tooltip=''):
    tt = f' title="{tooltip}"' if tooltip else ''
    return (
        f"<div style='display:grid;grid-template-columns:2fr 1fr 1fr 1fr;gap:4px;"
        f"padding:6px 8px;border-bottom:1px solid #1a1a1a;align-items:center'>"
        f"<span style='font-size:0.72rem;color:#888'{tt}>{label}</span>"
        f"<span style='font-size:0.9rem;font-weight:700;color:#fff;text-align:center'>{match_str}</span>"
        f"<span style='font-size:0.72rem;color:#555;text-align:center'>{season_str}</span>"
        f"<span style='font-size:0.72rem;text-align:right'>{delta_html_str}</span>"
        f"</div>"
    )


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="header-bar">
  <div><h1>Match Report</h1><div class="sub">Single-match breakdown vs season average</div></div>
  <div class="beswicks-badge">Beswicks Sports</div>
</div>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📋 Match Report")
    st.markdown("---")
    player_list = get_player_list()
    if not player_list:
        st.warning("No player files found.")
        st.stop()

    player_names  = [p[0] for p in player_list]
    selected_name = st.selectbox("Select player", player_names)
    selected_path = next(p[1] for p in player_list if p[0] == selected_name)

# ── Load data ─────────────────────────────────────────────────────────────────
with st.spinner(f"Loading {selected_name}..."):
    sheets = load_master(selected_path)

ws_raw = sheets.get('Wyscout')
ph_raw = sheets.get('Physical')

if ws_raw is None:
    st.error(f"No Wyscout sheet found for {selected_name}.")
    st.stop()

ws = ws_raw[ws_raw['Minutes played'] >= 20].copy().sort_values('Date').reset_index(drop=True)
ph = ph_raw[ph_raw['minutes_full_all'] >= 20].copy().sort_values('match_date').reset_index(drop=True) if ph_raw is not None else None

# Metadata
club = ph_raw['team_name'].iloc[0] if ph_raw is not None and 'team_name' in ph_raw.columns else ""
pos  = ph_raw['position_group'].iloc[0] if ph_raw is not None and 'position_group' in ph_raw.columns else ""

season = get_season_totals(ws)
phys   = get_physical_totals(ph) if ph is not None else None

# Build match log for selector labels
match_log = build_match_log(ws, club)

if len(match_log) == 0:
    st.warning("No qualifying matches found (minimum 20 minutes).")
    st.stop()

# Match selector labels: "Wigan (H) · 15 Nov"
match_labels = []
for i, (_, log_row) in enumerate(match_log.iterrows()):
    match_labels.append(f"{log_row['Match']} · {log_row['Date']}")

with st.sidebar:
    st.markdown("---")
    selected_label = st.selectbox("Select match", match_labels, index=len(match_labels) - 1)

selected_idx = match_labels.index(selected_label)
log_row      = match_log.iloc[selected_idx]

# Get the corresponding ws row (same order as match_log — sorted by date)
ws_match = ws.iloc[selected_idx]

# Get physical row by matching date
ph_match = None
if ph is not None:
    match_date_val = pd.to_datetime(ws_match['Date']).date()
    ph_candidates  = ph[pd.to_datetime(ph['match_date']).dt.date == match_date_val]
    if len(ph_candidates) > 0:
        ph_match = ph_candidates.iloc[0]

minutes = int(ws_match['Minutes played'])

# ── Match header ──────────────────────────────────────────────────────────────
st.markdown(
    f"<div style='background:#0f0f0f;border-radius:10px;padding:18px 24px;border-left:4px solid {GOLD};margin-bottom:20px'>"
    f"<div style='font-size:1.4rem;font-weight:700;color:#fff;margin-bottom:4px'>{log_row['Match']}</div>"
    f"<div style='font-size:0.8rem;color:#888'>{log_row['Date']} · {ws_match.get('Competition','–')} · {log_row['Pos']} · {minutes} mins</div>"
    f"</div>",
    unsafe_allow_html=True,
)

# Column header legend
st.markdown(
    "<div style='display:grid;grid-template-columns:2fr 1fr 1fr 1fr;gap:4px;padding:4px 8px;margin-bottom:2px'>"
    "<span style='font-size:0.65rem;color:#555;text-transform:uppercase;letter-spacing:0.06em'>Metric</span>"
    "<span style='font-size:0.65rem;color:#c8a45a;text-transform:uppercase;letter-spacing:0.06em;text-align:center'>This match</span>"
    "<span style='font-size:0.65rem;color:#555;text-transform:uppercase;letter-spacing:0.06em;text-align:center'>Season avg</span>"
    "<span style='font-size:0.65rem;color:#555;text-transform:uppercase;letter-spacing:0.06em;text-align:right'>Δ</span>"
    "</div>",
    unsafe_allow_html=True,
)

# ── Two-column layout ─────────────────────────────────────────────────────────
col_ws, col_ph = st.columns(2)

# ── Helper functions ──────────────────────────────────────────────────────────
def gws(col):
    try:
        v = ws_match[col]
        return None if pd.isna(v) else float(v)
    except Exception:
        return None

def gws_i(idx):
    try:
        v = ws_match.iloc[idx]
        return None if pd.isna(v) else float(v)
    except Exception:
        return None

def gph(col):
    if ph_match is None:
        return None
    try:
        v = ph_match[col]
        return None if pd.isna(v) else float(v)
    except Exception:
        return None

def mp90(raw):
    if raw is None or minutes == 0:
        return None
    return round(raw / minutes * 90, 2)

def fmt(v, d=2):
    return f"{v:.{d}f}" if v is not None else "–"

def fmt_int(v):
    return str(int(v)) if v is not None else "–"

# Derived percentages for this match
passes_m  = gws('Passes')
acc_p_m   = gws_i(13)
acc_pct_m = pct(acc_p_m, passes_m)
duels_m   = gws('Duels')
won_m     = gws_i(21)
duel_w_m  = pct(won_m, duels_m)
aer_m     = gws('Aerial duels')
aer_w_m   = gws_i(23)
aer_pct_m = pct(aer_w_m, aer_m)
def_d_m   = gws_i(31)
def_dw_m  = gws_i(32)
def_dpct_m= pct(def_dw_m, def_d_m)

# ── Wyscout column ────────────────────────────────────────────────────────────
with col_ws:
    st.markdown('<div class="section-header">Wyscout stats</div>', unsafe_allow_html=True)
    rows_html = []

    def add(label, match_str, season_str, match_val=None, season_val=None, inverse=False):
        rows_html.append(stat_row_html(label, match_str, season_str, delta_html(match_val, season_val, inverse)))

    add('Goals',        fmt_int(gws('Goals')),              fmt_int(season.get('goals_raw')),
        gws('Goals'), season.get('goals_raw'))
    add('Assists',      fmt_int(gws('Assists')),             fmt_int(season.get('assists_raw')),
        gws('Assists'), season.get('assists_raw'))
    add('xG',           fmt(gws('xG')),                     fmt(season.get('xg_p90')),
        gws('xG'), season.get('xg_p90'))
    add('xA',           fmt(gws('xA')),                     fmt(season.get('xa_p90')),
        gws('xA'), season.get('xa_p90'))
    add('Shot assists', fmt_int(gws('Shot assists')),        fmt(season.get('shot_asts_p90')),
        mp90(gws('Shot assists')), season.get('shot_asts_p90'))
    add('Passes',       fmt_int(passes_m),                  fmt(season.get('passes_p90'), 1),
        mp90(passes_m), season.get('passes_p90'))
    add('Pass acc %',
        f"{acc_pct_m:.1f}%" if acc_pct_m else '–',
        f"{season['pass_acc']:.1f}%" if season.get('pass_acc') else '–',
        acc_pct_m, season.get('pass_acc'))
    add('Dribbles',     fmt_int(gws('Dribbles')),            fmt(season.get('dribbles_p90')),
        mp90(gws('Dribbles')), season.get('dribbles_p90'))
    add('Prog runs',    fmt_int(gws('Progressive runs')),    fmt(season.get('prog_runs_p90')),
        mp90(gws('Progressive runs')), season.get('prog_runs_p90'))
    add('Touches in box', fmt_int(gws('Touches in penalty area')), fmt(season.get('touches_box_p90')),
        mp90(gws('Touches in penalty area')), season.get('touches_box_p90'))
    add('Duels',        fmt_int(duels_m),                   fmt(season.get('duels_p90'), 1),
        mp90(duels_m), season.get('duels_p90'))
    add('Duel win %',
        f"{duel_w_m:.1f}%" if duel_w_m else '–',
        f"{season['duel_win']:.1f}%" if season.get('duel_win') else '–',
        duel_w_m, season.get('duel_win'))
    add('Aerial duels', fmt_int(aer_m),                     fmt(season.get('aerial_p90')),
        mp90(aer_m), season.get('aerial_p90'))
    add('Aerial win %',
        f"{aer_pct_m:.1f}%" if aer_pct_m else '–',
        f"{season['aerial_win']:.1f}%" if season.get('aerial_win') else '–',
        aer_pct_m, season.get('aerial_win'))
    add('Def duels',    fmt_int(def_d_m),                   fmt(season.get('def_duels_p90')),
        mp90(def_d_m), season.get('def_duels_p90'))
    add('Def duel win %',
        f"{def_dpct_m:.1f}%" if def_dpct_m else '–',
        f"{season['def_duel_win']:.1f}%" if season.get('def_duel_win') else '–',
        def_dpct_m, season.get('def_duel_win'))
    add('Interceptions', fmt_int(gws('Interceptions')),     fmt(season.get('interceptions_p90')),
        mp90(gws('Interceptions')), season.get('interceptions_p90'))
    add('Recoveries',   fmt_int(gws('Recoveries')),         fmt(season.get('recoveries_p90')),
        mp90(gws('Recoveries')), season.get('recoveries_p90'))
    add('Losses',       fmt_int(gws('Losses')),             fmt(season.get('losses_p90')),
        mp90(gws('Losses')), season.get('losses_p90'), inverse=True)

    st.markdown(
        f"<div style='background:#1a1a1a;border-radius:8px;overflow:hidden'>{''.join(rows_html)}</div>",
        unsafe_allow_html=True,
    )

# ── Physical column ───────────────────────────────────────────────────────────
with col_ph:
    st.markdown('<div class="section-header">Physical stats</div>', unsafe_allow_html=True)

    if ph_match is None:
        st.markdown(
            "<div style='background:#1a1a1a;border-radius:8px;padding:16px;color:#555;font-size:0.8rem'>"
            "No physical data found for this match date.</div>",
            unsafe_allow_html=True,
        )
    else:
        ph_mins    = gph('minutes_full_all') or minutes
        raw_dist   = gph('total_distance_full_all')
        raw_hsr    = gph('hsr_distance_full_all')
        raw_spr    = gph('sprint_distance_full_all')
        raw_psv    = gph('psv99')
        raw_accel  = gph('highaccel_count_full_all')
        raw_hsr_n  = gph('hsr_count_full_all')
        raw_spr_n  = gph('sprint_count_full_all')

        def p90ph(raw):
            if raw is None or ph_mins == 0:
                return None
            return round(raw / ph_mins * 90, 1)

        ph_rows_html = []

        def addp(label, match_str, season_str, match_val=None, season_val=None, inverse=False):
            ph_rows_html.append(stat_row_html(label, match_str, season_str, delta_html(match_val, season_val, inverse)))

        addp('Total dist p90',
             f"{int(p90ph(raw_dist)):,}m" if p90ph(raw_dist) else '–',
             f"{int(phys.get('total_dist_p90', 0)):,}m" if phys else '–',
             p90ph(raw_dist), phys.get('total_dist_p90') if phys else None)
        addp('HSR dist p90',
             f"{int(p90ph(raw_hsr)):,}m" if p90ph(raw_hsr) else '–',
             f"{int(phys.get('hsr_dist_p90', 0)):,}m" if phys else '–',
             p90ph(raw_hsr), phys.get('hsr_dist_p90') if phys else None)
        addp('HSR runs p90',
             f"{p90ph(raw_hsr_n):.1f}" if p90ph(raw_hsr_n) else '–',
             f"{phys.get('hsr_count_p90', 0):.1f}" if phys else '–',
             p90ph(raw_hsr_n), phys.get('hsr_count_p90') if phys else None)
        addp('Sprint dist p90',
             f"{int(p90ph(raw_spr)):,}m" if p90ph(raw_spr) else '–',
             f"{int(phys.get('sprint_dist_p90', 0)):,}m" if phys else '–',
             p90ph(raw_spr), phys.get('sprint_dist_p90') if phys else None)
        addp('Sprints p90',
             f"{p90ph(raw_spr_n):.1f}" if p90ph(raw_spr_n) else '–',
             f"{phys.get('sprint_count_p90', 0):.1f}" if phys else '–',
             p90ph(raw_spr_n), phys.get('sprint_count_p90') if phys else None)
        addp('PSV99',
             f"{raw_psv:.2f}" if raw_psv else '–',
             f"{phys.get('psv99_avg', 0):.2f}" if phys else '–',
             raw_psv, phys.get('psv99_avg') if phys else None)
        addp('Hi-accel p90',
             f"{p90ph(raw_accel):.1f}" if p90ph(raw_accel) else '–',
             f"{phys.get('hi_accel_p90', 0):.1f}" if phys else '–',
             p90ph(raw_accel), phys.get('hi_accel_p90') if phys else None)

        st.markdown(
            f"<div style='background:#1a1a1a;border-radius:8px;overflow:hidden'>{''.join(ph_rows_html)}</div>",
            unsafe_allow_html=True,
        )

# ── Season context footer ─────────────────────────────────────────────────────
st.markdown("---")
st.caption(f"Season context: {int(season['matches'])} appearances · {int(season['mins']):,} mins · 2025/26")

# ── PDF export ────────────────────────────────────────────────────────────────
st.markdown("---")
try:
    from generate_match_report import generate_match_report
    PDF_OK = True
except Exception:
    PDF_OK = False

if PDF_OK:
    if st.button("📄 Generate match report PDF", use_container_width=True):
        with st.spinner("Generating PDF..."):
            try:
                opponent  = log_row['Match']
                date_str  = log_row['Date']
                comp      = ws_match.get('Competition', '–')
                pdf_bytes = generate_match_report(
                    player_name=selected_name,
                    club=club,
                    pos=pos,
                    opponent=opponent,
                    match_date=date_str,
                    competition=str(comp),
                    minutes=minutes,
                    ws_row=ws_match,
                    ph_row=ph_match,
                    season=season,
                    phys=phys,
                    total_matches=int(season['matches']),
                    total_mins=int(season['mins']),
                )
                safe_name = selected_name.replace(' ', '_')
                safe_opp  = opponent.replace(' ', '_').replace('(', '').replace(')', '')
                st.download_button(
                    "⬇ Download PDF",
                    data=pdf_bytes,
                    file_name=f"{safe_name}_{safe_opp}_match_report.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            except Exception as e:
                st.error(f"PDF generation failed: {e}")
                st.exception(e)
else:
    st.info("PDF export requires `kaleido` and `reportlab`.")
