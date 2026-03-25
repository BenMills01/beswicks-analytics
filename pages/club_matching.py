"""
pages/club_matching.py
Beswicks Sports Analytics — Reverse Club Matching

Given a client, ranks all clubs in data/clubs/ by how well the player
fits their tactical profile. Uses the same fit-score engine as the club
report, applied in reverse (player → clubs rather than club → player).
"""

import streamlit as st
import pandas as pd
import os
import glob

from src.metrics import (
    get_season_totals, get_physical_totals,
    build_wyscout_peers, build_physical_peers,
    percentile_rank,
)
from src.clubs import (
    get_all_club_profiles, get_league_medians,
    get_club_weaknesses, filter_weaknesses_by_position,
    get_style_fit_score,
)

st.set_page_config(
    page_title="Beswicks | Club Matching",
    page_icon="🎯",
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
.header-bar h1 { color: #fff; font-size: 1.35rem; font-weight: 700; margin: 0; }
.header-bar .sub { color: #888; font-size: 0.78rem; margin-top: 2px; }
.beswicks-badge {
    background: #c8a45a; color: #0f0f0f; font-size: 0.7rem;
    font-weight: 700; letter-spacing: 0.08em; padding: 4px 10px;
    border-radius: 4px; text-transform: uppercase;
}
.fit-card {
    background: #0f0f0f; border-radius: 10px; padding: 16px 20px;
    border-left: 4px solid #c8a45a; margin-bottom: 8px;
}
.fit-card-top { background: #0f0f0f; border-left-color: #4ade80; }
.section-header {
    font-size: 0.7rem; font-weight: 700; letter-spacing: 0.1em;
    text-transform: uppercase; color: #c8a45a; margin: 20px 0 10px;
    padding-bottom: 6px; border-bottom: 1px solid #2a2a2a;
}
</style>
""", unsafe_allow_html=True)

# ── Paths (mirror app.py) ──────────────────────────────────────────────────────
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

GOLD  = '#c8a45a'
GREEN = '#4ade80'
AMBER = '#facc15'
RED   = '#f87171'
GREY  = '#888888'


# ── Helpers ────────────────────────────────────────────────────────────────────
def _score_colour(v: int | None) -> str:
    if v is None: return GREY
    if v >= 70:   return GREEN
    if v >= 50:   return AMBER
    return RED


def _score_bar(v: int | None, label: str) -> str:
    """Compact coloured score pill."""
    if v is None:
        return f"<span style='color:#444;font-size:0.72rem'>{label} –</span>"
    col = _score_colour(v)
    return (
        f"<span style='font-size:0.72rem;color:#666'>{label} </span>"
        f"<span style='color:{col};font-weight:700;font-size:0.82rem'>{v}</span>"
    )


def _weakness_sentence(w: dict, player_name: str) -> str:
    """One-line fit rationale from a weakness dict."""
    return f"{w['interpretation']} — {player_name} is a direct candidate to address this gap."


# ── Data loaders ───────────────────────────────────────────────────────────────
@st.cache_data
def load_master(filepath: str) -> dict:
    xls = pd.ExcelFile(filepath)
    return {s: pd.read_excel(xls, sheet_name=s)
            for s in ['Wyscout', 'Physical']
            if s in xls.sheet_names}


@st.cache_data
def load_physical_csv() -> pd.DataFrame | None:
    if os.path.exists(PHYSICAL_CSV):
        return pd.read_csv(PHYSICAL_CSV)
    return None


@st.cache_data
def cached_all_club_profiles() -> dict:
    return get_all_club_profiles()


def get_player_list() -> list[tuple[str, str]]:
    pattern = os.path.join(os.path.abspath(PLAYERS_DIR), "*_master.xlsx")
    files   = sorted(glob.glob(pattern))
    return [(os.path.basename(f).replace("_master.xlsx", "").replace("_", " "), f)
            for f in files]


# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="header-bar">
  <div><h1>🎯 Reverse Club Matching</h1>
       <div class="sub">Find the best club fits for a client across all profiled clubs</div></div>
  <div class="beswicks-badge">Beswicks Sports</div>
</div>
""", unsafe_allow_html=True)

# ── Sidebar ────────────────────────────────────────────────────────────────────
player_list = get_player_list()
if not player_list:
    st.warning(f"No player files found in `{PLAYERS_DIR}`.")
    st.stop()

with st.sidebar:
    st.markdown("### Player")
    player_names  = [n for n, _ in player_list]
    selected_name = st.selectbox("Select client", player_names)
    selected_path = dict(player_list)[selected_name]

    st.markdown("### Peer group")
    peer_league = st.selectbox(
        "League for peer comparison",
        ["Both", "League One", "League Two", "Championship"],
        help="Used to build the peer group for percentile ranking.",
    )
    min_mins = st.slider("Min minutes (peers)", 450, 1800, 900, step=50)

    st.markdown("### Display")
    top_n_clubs = st.slider("Top N clubs to show", 5, 30, 15)

# ── Load player data ───────────────────────────────────────────────────────────
with st.spinner(f"Loading {selected_name}..."):
    sheets = load_master(selected_path)
    phys_csv = load_physical_csv()

ws_raw = sheets.get('Wyscout')
ph_raw = sheets.get('Physical')

if ws_raw is None:
    st.error("No Wyscout sheet found in this player's file.")
    st.stop()

ws     = ws_raw[ws_raw['Minutes played'] >= 20].copy()
if 'Date' in ws.columns:
    ws = ws.sort_values('Date').reset_index(drop=True)

season = get_season_totals(ws)

ph     = ph_raw[ph_raw['minutes_full_all'] >= 20].copy() if ph_raw is not None else None
phys   = get_physical_totals(ph) if ph is not None else None

# ── Detect position ────────────────────────────────────────────────────────────
pos = ''
if ph_raw is not None and 'position_group' in ph_raw.columns:
    pos = str(ph_raw['position_group'].iloc[0])
if not pos and 'Position' in ws_raw.columns:
    pos = str(ws_raw['Position'].iloc[0])

club_from_file = ''
if ph_raw is not None and 'team_name' in ph_raw.columns:
    club_from_file = str(ph_raw['team_name'].iloc[0])

# ── Build peer groups ─────────────────────────────────────────────────────────
pos_key = pos if pos in WS_FILES.get('League One', {}) else None

ws_peers,   ws_peer_n   = (
    build_wyscout_peers(pos_key, peer_league, min_mins, WS_FILES)
    if pos_key else ({}, 0)
)
phys_peers, phys_peer_n = (
    build_physical_peers(phys_csv, pos, min_mins, peer_league)
    if phys_csv is not None and pos else ({}, 0)
)

if ws_peer_n < 5:
    st.warning(
        f"Peer group too small ({ws_peer_n} players) to compute reliable fit scores. "
        "Try relaxing min minutes or changing the league filter."
    )

# ── Load all club profiles ─────────────────────────────────────────────────────
with st.spinner("Loading club profiles..."):
    all_profiles    = cached_all_club_profiles()
    league_medians  = get_league_medians(all_profiles)

if len(all_profiles) < 3:
    st.error(f"Fewer than 3 club profiles found in `data/clubs/`. Add Team Stats *.xlsx files.")
    st.stop()

# ── Compute fit scores for every club ─────────────────────────────────────────
results = []
for club_name, profile in all_profiles.items():
    if profile.get('matches', 0) == 0:
        continue
    try:
        fit = get_style_fit_score(season, phys, profile, ws_peers, phys_peers, league_medians)
        if fit.get('overall') is None:
            continue

        weaknesses        = get_club_weaknesses(profile, league_medians)
        pos_weaknesses    = filter_weaknesses_by_position(weaknesses, pos_key)
        top_weakness_text = pos_weaknesses[0]['label'] if pos_weaknesses else '–'
        n_gaps_filled     = len(pos_weaknesses)

        results.append({
            'Club':         club_name,
            'League':       profile.get('league') or '–',
            'Formation':    profile.get('primary_formation') or '–',
            'Style':        profile.get('play_style') or '–',
            'Press':        profile.get('press_intensity') or '–',
            'Overall':      fit.get('overall'),
            'Pressing fit': fit.get('out_of_possession'),
            'Build-up fit': fit.get('in_possession'),
            'Gap fill':     fit.get('gap_fill'),
            'Physical fit': fit.get('physical_fit'),
            'Top gap':      top_weakness_text,
            'Gaps':         n_gaps_filled,
            '_profile':     profile,
            '_weaknesses':  pos_weaknesses,
        })
    except Exception:
        continue

if not results:
    st.error("Could not compute fit scores for any club. Check that peer data is available.")
    st.stop()

results_df = (
    pd.DataFrame(results)
    .sort_values('Overall', ascending=False)
    .reset_index(drop=True)
)

# ── Player summary banner ──────────────────────────────────────────────────────
mins  = int(season.get('mins', 0))
goals = int(season.get('goals_raw', 0))
asts  = int(season.get('assists_raw', 0))
st.markdown(
    f"<div style='background:#0f0f0f;border-radius:10px;padding:14px 20px;"
    f"border-left:4px solid {GOLD};margin-bottom:16px'>"
    f"<span style='color:#fff;font-weight:700;font-size:1rem'>{selected_name}</span>"
    f"<span style='color:#888;font-size:0.8rem'> · {pos or '—'} · {club_from_file or '—'} · "
    f"{mins:,} mins · {goals}G {asts}A</span>"
    f"<span style='color:#555;font-size:0.75rem'> · Ranked against {len(results_df)} clubs · "
    f"peer group: {ws_peer_n} {pos or ''} players</span>"
    f"</div>",
    unsafe_allow_html=True,
)

# ── Summary table ──────────────────────────────────────────────────────────────
st.markdown('<div class="section-header">Club fit rankings</div>', unsafe_allow_html=True)

display_df = results_df.head(top_n_clubs)[
    ['Club', 'League', 'Formation', 'Style', 'Press',
     'Overall', 'Pressing fit', 'Build-up fit', 'Gap fill', 'Physical fit', 'Top gap']
].copy()

# Colour the Overall column
def _colour_overall(val):
    if pd.isna(val): return ''
    col = '#4ade80' if val >= 70 else ('#facc15' if val >= 50 else '#f87171')
    return f'color: {col}; font-weight: bold'

st.dataframe(
    display_df.style.applymap(_colour_overall, subset=['Overall']),
    use_container_width=True,
    hide_index=True,
)

# ── Club detail expanders ──────────────────────────────────────────────────────
st.markdown('<div class="section-header">Club detail</div>', unsafe_allow_html=True)
st.caption("Expand a club to see the specific gaps the player addresses and style context.")

for _, row in results_df.head(top_n_clubs).iterrows():
    overall   = row['Overall']
    col_hex   = _score_colour(overall)
    label     = f"**{row['Club']}** — {row['League']} · {row['Formation']} · Overall fit: **{overall}/100**"

    with st.expander(label):
        c1, c2, c3, c4 = st.columns(4)
        for col_widget, key, lbl in [
            (c1, 'Pressing fit',  'PRESSING'),
            (c2, 'Build-up fit',  'BUILD-UP'),
            (c3, 'Gap fill',      'GAP FILL'),
            (c4, 'Physical fit',  'PHYSICAL'),
        ]:
            v = row[key]
            vc = _score_colour(v)
            col_widget.markdown(
                f"<div style='text-align:center'>"
                f"<div style='font-size:0.65rem;color:#666;letter-spacing:0.08em'>{lbl}</div>"
                f"<div style='font-size:1.6rem;font-weight:700;color:{vc}'>{v if v is not None else '–'}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

        st.markdown("")

        # Style context
        style_parts = []
        if row['Press'] and row['Press'] != '–': style_parts.append(row['Press'])
        if row['Style'] and row['Style'] != '–': style_parts.append(row['Style'])
        if style_parts:
            st.markdown(
                f"<span style='color:#888;font-size:0.8rem'>Style: {' · '.join(style_parts)}</span>",
                unsafe_allow_html=True,
            )

        # Position-relevant gaps the player addresses
        pos_weaks = row['_weaknesses']
        if pos_weaks:
            st.markdown(
                "<div style='margin-top:10px;font-size:0.75rem;color:#c8a45a;"
                "font-weight:600;letter-spacing:0.06em'>GAPS THIS PLAYER ADDRESSES</div>",
                unsafe_allow_html=True,
            )
            for w in pos_weaks[:3]:
                gap_col = RED if w['gap_pct'] > 20 else AMBER
                st.markdown(
                    f"<div style='margin-top:4px;font-size:0.78rem'>"
                    f"<span style='color:{gap_col};font-weight:600'>{w['label']}</span>"
                    f" — Club: {w['club_val']:.1f} vs median {w['median_val']:.1f} "
                    f"(<span style='color:{gap_col}'>▼{w['gap_pct']:.0f}%</span>)<br/>"
                    f"<span style='color:#888'>{_weakness_sentence(w, selected_name)}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                "<span style='color:#555;font-size:0.78rem'>No position-relevant gaps identified for this club.</span>",
                unsafe_allow_html=True,
            )
