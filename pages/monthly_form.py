"""
pages/monthly_form.py
Beswicks Sports Analytics — Monthly / Date-Range Form Report

Select a player and a date window to view stats for that period
vs their full season average, with form charts and match log.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
import glob
from datetime import datetime, timedelta, date

from src.metrics import (
    get_season_totals, get_physical_totals, build_match_log,
    p90, pct, rolling_avg, parse_wyscout_label, parse_physical_label,
    percentile_rank,
)

st.set_page_config(
    page_title="Beswicks | Form Report",
    page_icon="📈",
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
.mc { background: #1a1a1a; border-radius: 8px; padding: 12px 14px 10px; border: 1px solid #2a2a2a; }
.mc-label { font-size: 0.68rem; color: #666; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 4px; }
.mc-value { font-size: 1.4rem; font-weight: 700; color: #fff; line-height: 1; }
.mc-sub   { font-size: 0.68rem; color: #555; margin-top: 3px; }
</style>
""", unsafe_allow_html=True)

PLOT_BG  = '#0f0f0f'
PAPER_BG = '#0f0f0f'
GRID_COL = '#222222'
TEXT_COL = '#aaaaaa'
GOLD     = '#c8a45a'
PURPLE   = '#a78bfa'

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


def delta_chip(period_val, season_val, inverse=False, fmt='.2f'):
    if period_val is None or season_val is None:
        return ""
    diff   = period_val - season_val
    better = diff > 0 if not inverse else diff < 0
    if abs(diff) < 0.005:
        return "<span style='color:#888;font-size:0.65rem'>=</span>"
    col = '#4ade80' if better else '#f87171'
    ar  = '▲' if diff > 0 else '▼'
    return f"<span style='color:{col};font-size:0.65rem;font-weight:600'>{ar} {abs(diff):{fmt}}</span>"


def metric_compare(label, period_val, season_val, fmt='.2f', inverse=False, suffix=''):
    pv_str = f'{period_val:{fmt}}{suffix}' if period_val is not None else '–'
    sv_str = f'{season_val:{fmt}}{suffix}' if season_val is not None else '–'
    chip   = delta_chip(period_val, season_val, inverse, fmt)
    return (
        f"<div class='mc'>"
        f"<div class='mc-label'>{label}</div>"
        f"<div class='mc-value'>{pv_str}</div>"
        f"<div class='mc-sub'>{sv_str} season {chip}</div>"
        f"</div>"
    )


def metric_row_html(cards):
    inner = ''.join(cards)
    return f"<div style='display:grid;grid-template-columns:repeat({len(cards)},1fr);gap:10px;margin-bottom:8px'>{inner}</div>"


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="header-bar">
  <div><h1>Form Report</h1><div class="sub">Period stats vs season average</div></div>
  <div class="beswicks-badge">Beswicks Sports</div>
</div>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📈 Form Report")
    st.markdown("---")
    player_list = get_player_list()
    if not player_list:
        st.warning("No player files found.")
        st.stop()

    player_names  = [p[0] for p in player_list]
    selected_name = st.selectbox("Select player", player_names)
    selected_path = next(p[1] for p in player_list if p[0] == selected_name)

    st.markdown("---")
    st.markdown("### Date range")
    today       = date.today()
    default_from = today - timedelta(days=28)
    date_from   = st.date_input("From", value=default_from)
    date_to     = st.date_input("To",   value=today)
    if date_from > date_to:
        st.error("'From' must be before 'To'.")
        st.stop()

# ── Load data ─────────────────────────────────────────────────────────────────
with st.spinner(f"Loading {selected_name}..."):
    sheets = load_master(selected_path)

ws_raw = sheets.get('Wyscout')
ph_raw = sheets.get('Physical')

if ws_raw is None:
    st.error(f"No Wyscout sheet found for {selected_name}.")
    st.stop()

ws_full = ws_raw[ws_raw['Minutes played'] >= 20].copy().sort_values('Date').reset_index(drop=True)
ph_full = ph_raw[ph_raw['minutes_full_all'] >= 20].copy().sort_values('match_date').reset_index(drop=True) if ph_raw is not None else None

club = ph_raw['team_name'].iloc[0]      if ph_raw is not None and 'team_name'      in ph_raw.columns else ""
pos  = ph_raw['position_group'].iloc[0] if ph_raw is not None and 'position_group' in ph_raw.columns else ""

# Season-wide stats (for comparison column)
season_stats = get_season_totals(ws_full)
season_phys  = get_physical_totals(ph_full) if ph_full is not None else None

# Period filter
ws_period = ws_full[
    (pd.to_datetime(ws_full['Date']).dt.date >= date_from) &
    (pd.to_datetime(ws_full['Date']).dt.date <= date_to)
].copy()

ph_period = None
if ph_full is not None:
    ph_period = ph_full[
        (pd.to_datetime(ph_full['match_date']).dt.date >= date_from) &
        (pd.to_datetime(ph_full['match_date']).dt.date <= date_to)
    ].copy()

n_matches = len(ws_period)

# ── Warning if too few matches ────────────────────────────────────────────────
if n_matches == 0:
    st.warning(f"No qualifying matches found between {date_from.strftime('%d %b %Y')} and {date_to.strftime('%d %b %Y')}.")
    st.stop()

if n_matches < 3:
    st.warning(f"Only {n_matches} match(es) in this window — stats may not be representative.")

# Period stats
period_stats = get_season_totals(ws_period)
period_phys  = get_physical_totals(ph_period) if ph_period is not None and len(ph_period) > 0 else None

# ── Period profile card ────────────────────────────────────────────────────────
date_from_str = date_from.strftime('%d %b %Y')
date_to_str   = date_to.strftime('%d %b %Y')
n_mins        = int(period_stats.get('mins', 0))
goals_r       = int(period_stats.get('goals_raw', 0))
assists_r     = int(period_stats.get('assists_raw', 0))

st.markdown(
    f"<div style='background:#0f0f0f;border-radius:10px;padding:18px 24px;border-left:4px solid {GOLD};margin-bottom:20px'>"
    f"<div style='font-size:1.3rem;font-weight:700;color:#fff;margin-bottom:4px'>{selected_name}</div>"
    f"<div style='font-size:0.78rem;color:#888;margin-bottom:10px'>{club} · {pos}</div>"
    f"<div style='display:flex;flex-wrap:wrap;gap:8px'>"
    f"<span style='background:#2a2010;border:1px solid {GOLD};color:{GOLD};border-radius:5px;padding:4px 10px;font-size:0.74rem;font-weight:700'>"
    f"{date_from_str} → {date_to_str}</span>"
    f"<span style='background:#1e1e1e;border:1px solid #333;color:#ccc;border-radius:5px;padding:4px 10px;font-size:0.74rem'>{n_matches} matches</span>"
    f"<span style='background:#1e1e1e;border:1px solid #333;color:#ccc;border-radius:5px;padding:4px 10px;font-size:0.74rem'>{n_mins:,} mins</span>"
    f"<span style='background:#1e1e1e;border:1px solid #333;color:#ccc;border-radius:5px;padding:4px 10px;font-size:0.74rem'>{goals_r}G · {assists_r}A</span>"
    f"</div></div>",
    unsafe_allow_html=True,
)

# ── Period stats vs season average ────────────────────────────────────────────
st.markdown('<div class="section-header">Period stats vs season average · per 90</div>', unsafe_allow_html=True)
st.caption("Value shown is the period figure. 'Season' shows the full-season average. ▲▼ shows change from season average.")

st.markdown("**Attacking**")
st.markdown(metric_row_html([
    metric_compare("Goals p90",     period_stats.get('goals_p90'),     season_stats.get('goals_p90')),
    metric_compare("Assists p90",   period_stats.get('assists_p90'),   season_stats.get('assists_p90')),
    metric_compare("xG p90",        period_stats.get('xg_p90'),        season_stats.get('xg_p90')),
    metric_compare("xA p90",        period_stats.get('xa_p90'),        season_stats.get('xa_p90')),
    metric_compare("Shot asts p90", period_stats.get('shot_asts_p90'), season_stats.get('shot_asts_p90')),
]), unsafe_allow_html=True)

st.markdown("**Passing & ball-carrying**")
st.markdown(metric_row_html([
    metric_compare("Passes p90",    period_stats.get('passes_p90'),    season_stats.get('passes_p90'),   '.1f'),
    metric_compare("Pass acc %",    period_stats.get('pass_acc'),      season_stats.get('pass_acc'),     '.1f', suffix='%'),
    metric_compare("Dribbles p90",  period_stats.get('dribbles_p90'),  season_stats.get('dribbles_p90')),
    metric_compare("Prog runs p90", period_stats.get('prog_runs_p90'), season_stats.get('prog_runs_p90')),
    metric_compare("Crosses p90",   period_stats.get('crosses_p90'),   season_stats.get('crosses_p90')),
]), unsafe_allow_html=True)

st.markdown("**Duels & defensive**")
st.markdown(metric_row_html([
    metric_compare("Duels p90",     period_stats.get('duels_p90'),     season_stats.get('duels_p90'),     '.1f'),
    metric_compare("Duel win %",    period_stats.get('duel_win'),      season_stats.get('duel_win'),      '.1f', suffix='%'),
    metric_compare("Def duels p90", period_stats.get('def_duels_p90'), season_stats.get('def_duels_p90')),
    metric_compare("Interceptions", period_stats.get('interceptions_p90'), season_stats.get('interceptions_p90')),
    metric_compare("Losses p90",    period_stats.get('losses_p90'),    season_stats.get('losses_p90'),    inverse=True),
]), unsafe_allow_html=True)

if period_phys and season_phys:
    st.markdown("**Physical output**")
    st.markdown(metric_row_html([
        metric_compare("Total dist p90",  period_phys.get('total_dist_p90'),  season_phys.get('total_dist_p90'),  '.0f', suffix='m'),
        metric_compare("HSR dist p90",    period_phys.get('hsr_dist_p90'),    season_phys.get('hsr_dist_p90'),    '.0f', suffix='m'),
        metric_compare("Sprint dist p90", period_phys.get('sprint_dist_p90'), season_phys.get('sprint_dist_p90'), '.0f', suffix='m'),
        metric_compare("PSV99 avg",       period_phys.get('psv99_avg'),       season_phys.get('psv99_avg')),
    ]), unsafe_allow_html=True)

# ── Form charts ───────────────────────────────────────────────────────────────
if n_matches >= 2:
    st.markdown('<div class="section-header">Form charts — period</div>', unsafe_allow_html=True)

    # Derive match labels + percentages for charts
    ws_chart = ws_period.copy()
    ws_chart['match_label'] = ws_chart.apply(
        lambda r: parse_wyscout_label(r.get('Match', ''), club), axis=1
    )
    ws_chart['duel_win_pct'] = ws_chart.apply(
        lambda r: pct(float(r.iloc[21]), float(r['Duels'])) if r['Duels'] and float(r['Duels']) > 0 else None, axis=1
    )
    ws_chart['def_duel_win_pct'] = ws_chart.apply(
        lambda r: pct(float(r.iloc[32]), float(r.iloc[31])) if r.iloc[31] and float(r.iloc[31]) > 0 else None, axis=1
    )

    c1, c2 = st.columns(2)

    with c1:
        # Duel win % form chart
        fig_d = go.Figure()
        fig_d.add_scatter(x=ws_chart['match_label'], y=ws_chart['duel_win_pct'],
            mode='lines+markers', name='Duel win %',
            line=dict(color='#3b82f6', width=2), marker=dict(size=5))
        fig_d.add_scatter(x=ws_chart['match_label'], y=ws_chart['def_duel_win_pct'],
            mode='lines+markers', name='Def duel win %',
            line=dict(color='#f87171', width=2, dash='dot'), marker=dict(size=5))
        roll_d = pd.Series(ws_chart['duel_win_pct'].values).rolling(5, min_periods=2).mean()
        fig_d.add_scatter(x=ws_chart['match_label'], y=roll_d, mode='lines',
            name='Rolling avg', line=dict(color=PURPLE, width=2))
        fig_d.add_scatter(x=ws_chart['match_label'], y=[50] * len(ws_chart), mode='lines',
            name='50%', line=dict(color='#444', width=1, dash='dash'))
        fig_d.update_layout(
            height=300, plot_bgcolor=PLOT_BG, paper_bgcolor=PAPER_BG,
            title=dict(text='Duel win % — period', font=dict(color=TEXT_COL, size=11), x=0),
            font=dict(color=TEXT_COL, size=10),
            margin=dict(l=10, r=10, t=36, b=80),
            xaxis=dict(showgrid=False, tickfont=dict(size=9, color='#666'), tickangle=-40),
            yaxis=dict(range=[0, 110], gridcolor=GRID_COL, showgrid=True, tickfont=dict(size=9, color='#666'), zeroline=False),
            legend=dict(bgcolor='rgba(0,0,0,0)', font=dict(size=9, color='#888'), orientation='h', y=1.08),
            hovermode='x unified', hoverlabel=dict(bgcolor='#1a1a1a', font_size=11),
        )
        st.plotly_chart(fig_d, use_container_width=True)

    with c2:
        # Distance p90 chart (physical)
        if ph_period is not None and len(ph_period) >= 2:
            ph_chart = ph_period.copy()
            ph_chart['match_label'] = ph_chart.apply(
                lambda r: parse_physical_label(r.get('match_name', ''), r.get('team_name', club)), axis=1
            )
            ph_chart['dist_p90_m'] = ph_chart.apply(
                lambda r: p90(r['total_distance_full_all'], r['minutes_full_all']) if r['minutes_full_all'] > 0 else None, axis=1
            )
            avg_dist = ph_chart['dist_p90_m'].mean()
            fig_ph   = go.Figure()
            bar_cols = [GOLD if v and v >= avg_dist else '#333' for v in ph_chart['dist_p90_m']]
            fig_ph.add_bar(x=ph_chart['match_label'], y=ph_chart['dist_p90_m'],
                marker_color=bar_cols, name='Dist p90')
            fig_ph.add_scatter(x=ph_chart['match_label'], y=[avg_dist] * len(ph_chart), mode='lines',
                name=f'Period avg ({avg_dist:,.0f}m)', line=dict(color=GOLD, width=1.5, dash='dot'))
            roll_ph = pd.Series(ph_chart['dist_p90_m'].values).rolling(5, min_periods=2).mean()
            fig_ph.add_scatter(x=ph_chart['match_label'], y=roll_ph, mode='lines',
                name='Rolling avg', line=dict(color=PURPLE, width=2))
            fig_ph.update_layout(
                height=300, plot_bgcolor=PLOT_BG, paper_bgcolor=PAPER_BG,
                title=dict(text='Total distance per 90 — period', font=dict(color=TEXT_COL, size=11), x=0),
                font=dict(color=TEXT_COL, size=10),
                margin=dict(l=10, r=10, t=36, b=80),
                xaxis=dict(showgrid=False, tickfont=dict(size=9, color='#666'), tickangle=-40),
                yaxis=dict(gridcolor=GRID_COL, showgrid=True, tickfont=dict(size=9, color='#666'), zeroline=False),
                legend=dict(bgcolor='rgba(0,0,0,0)', font=dict(size=9, color='#888'), orientation='h', y=1.08),
                hovermode='x unified', hoverlabel=dict(bgcolor='#1a1a1a', font_size=11),
            )
            st.plotly_chart(fig_ph, use_container_width=True)
        else:
            st.info("Physical data not available for this period.")

# ── Match log ─────────────────────────────────────────────────────────────────
st.markdown('<div class="section-header">Match log — period</div>', unsafe_allow_html=True)
match_log = build_match_log(ws_period, club)
if len(match_log) == 0:
    st.info("No matches in this period.")
else:
    st.dataframe(
        match_log.iloc[::-1].reset_index(drop=True),
        use_container_width=True,
        hide_index=True,
        height=min(38 * len(match_log) + 40, 500),
    )

# ── PDF export ────────────────────────────────────────────────────────────────
st.markdown("---")
try:
    from generate_monthly_report import generate_monthly_report
    PDF_OK = True
except Exception:
    PDF_OK = False

if PDF_OK:
    if st.button("📄 Generate form report PDF", use_container_width=True):
        with st.spinner("Generating PDF — this may take a few seconds..."):
            try:
                pdf_bytes = generate_monthly_report(
                    player_name=selected_name,
                    club=club,
                    pos=pos,
                    date_from=date_from_str,
                    date_to=date_to_str,
                    ws_period=ws_period,
                    ph_period=ph_period,
                    period_stats=period_stats,
                    period_phys=period_phys,
                    season_stats=season_stats,
                    season_phys=season_phys,
                    team_name=club,
                )
                safe_name = selected_name.replace(' ', '_')
                filename  = f"{safe_name}_form_{date_from.strftime('%Y%m%d')}_{date_to.strftime('%Y%m%d')}.pdf"
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
