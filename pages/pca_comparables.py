"""
pages/pca_comparables.py
Beswicks Sports Analytics — PCA Comparable Players Experiment

Experimental test page comparing three player-similarity methods side-by-side:
  1. Current   — position-weighted Euclidean on 16 curated metrics (baseline)
  2. PCA-16    — PCA on same 16 metrics, no position weights (isolates decorrelation effect)
  3. PCA-all   — PCA on all per-90/% columns (~50-70 cols), client imputed at mean for unknowns
  4. Hybrid    — current top-8 annotated with PCA confirmation ranks + PCA-only discoveries

No changes are made to src/metrics.py — this is a self-contained experiment.
"""
import os
import glob
from typing import Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.metrics import (
    get_season_totals,
    get_physical_totals,
    build_physical_season_averages,
    find_comparable_players,
    MIN_PEER_N,
    _COMPARABLE_FEATURE_MAP,   # peer col → client key (16 curated metrics)
    _COMPARABLE_DISPLAY_COLS,  # peer col → display label
)

st.set_page_config(
    page_title="Beswicks | PCA Experiment",
    page_icon="🔬",
    layout="wide",
)

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 1.5rem; padding-bottom: 2rem; }
[data-testid="stSidebar"] { background: #0f0f0f; }
[data-testid="stSidebar"] * { color: #e0e0e0 !important; }
.section-header {
    font-size: 0.7rem; font-weight: 700; letter-spacing: 0.1em;
    text-transform: uppercase; color: #c8a45a; margin: 20px 0 10px;
    padding-bottom: 6px; border-bottom: 1px solid #2a2a2a;
}
.col-label {
    font-size: 0.7rem; font-weight: 700; color: #c8a45a;
    text-transform: uppercase; letter-spacing: 0.08em;
    padding: 6px 0 4px; border-bottom: 1px solid #2a2a2a; margin-bottom: 8px;
}
.stat-card {
    background: #161616; border: 1px solid #2a2a2a; border-radius: 8px;
    padding: 14px 12px; text-align: center;
}
.stat-card .label { font-size: 0.65rem; color: #888; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 4px; }
.stat-card .value { font-size: 1.4rem; font-weight: 700; }
.stat-card .sub   { font-size: 0.65rem; color: #555; margin-top: 2px; }
</style>
""", unsafe_allow_html=True)

GOLD    = '#c8a45a'
PLOT_BG = '#0f0f0f'

DATA_DIR     = "data"
PLAYERS_DIR  = os.path.join(DATA_DIR, "players")
PHYSICAL_CSV = os.path.join(DATA_DIR, "physical_all_2526.csv")

WS_FILES = {
    'Championship': {
        'Central Defender': os.path.join(DATA_DIR, "Championship Central Defenders.xlsx"),
        'Full Back':        os.path.join(DATA_DIR, "Championship Full Back:Wing Back.xlsx"),
        'Central Mid':      os.path.join(DATA_DIR, "Championship Central Midfielders.xlsx"),
        'Att Mid':          os.path.join(DATA_DIR, "Championship Attacking Midfielders.xlsx"),
        'Wide Mid':         os.path.join(DATA_DIR, "Championship Wide Midfielders.xlsx"),
        'Center Forward':   os.path.join(DATA_DIR, "Championship CF's.xlsx"),
        'Goalkeeper':       os.path.join(DATA_DIR, "Championship GKs.xlsx"),
    },
    'League One': {
        'Central Defender': os.path.join(DATA_DIR, "League One Central Defenders.xlsx"),
        'Full Back':        os.path.join(DATA_DIR, "League One Full Back:Wing Back.xlsx"),
        'Central Mid':      os.path.join(DATA_DIR, "League One Central Midfielders.xlsx"),
        'Att Mid':          os.path.join(DATA_DIR, "League One Attacking Midfielders.xlsx"),
        'Wide Mid':         os.path.join(DATA_DIR, "League One Wide Midfielders.xlsx"),
        'Center Forward':   os.path.join(DATA_DIR, "League One CF's.xlsx"),
        'Goalkeeper':       os.path.join(DATA_DIR, "League One GKs.xlsx"),
    },
    'League Two': {
        'Central Defender': os.path.join(DATA_DIR, "League Two Central Defenders.xlsx"),
        'Full Back':        os.path.join(DATA_DIR, "League Two FB:WB.xlsx"),
        'Central Mid':      os.path.join(DATA_DIR, "League Two Central Midfielders.xlsx"),
        'Att Mid':          os.path.join(DATA_DIR, "League Two Attacking Midfielders.xlsx"),
        'Wide Mid':         os.path.join(DATA_DIR, "League Two Wide Midfielders.xlsx"),
        'Center Forward':   os.path.join(DATA_DIR, "League Two CFs.xlsx"),
        'Goalkeeper':       os.path.join(DATA_DIR, "League Two GKs.xlsx"),
    },
}

POSITION_KEYS = ['Central Defender', 'Full Back', 'Central Mid',
                 'Att Mid', 'Wide Mid', 'Center Forward', 'Goalkeeper']

# ── Data loaders ───────────────────────────────────────────────────────────────

def get_player_list():
    pattern = os.path.join(os.path.abspath(PLAYERS_DIR), "*_master.xlsx")
    files   = sorted(glob.glob(pattern))
    return [(os.path.basename(f).replace("_master.xlsx", "").replace("_", " "), f) for f in files]


@st.cache_data
def _load_master(filepath: str) -> dict:
    xls = pd.ExcelFile(filepath)
    return {s: pd.read_excel(xls, sheet_name=s)
            for s in ['Wyscout', 'Physical', 'Pressing', 'Off_Ball_Runs', 'Match_by_Match']
            if s in xls.sheet_names}


@st.cache_data
def _load_physical_csv() -> Optional[pd.DataFrame]:
    if not os.path.exists(PHYSICAL_CSV):
        return None
    return pd.read_csv(PHYSICAL_CSV, parse_dates=['match_date'])


@st.cache_data
def _cached_phys_avgs(phys_csv: Optional[pd.DataFrame]) -> Optional[pd.DataFrame]:
    return build_physical_season_averages(phys_csv)


@st.cache_data
def _find_position(player_short_name: str) -> Optional[str]:
    """Scan peer files to auto-detect Wyscout position key."""
    for league in ['Championship', 'League One', 'League Two']:
        for pos_key, path in WS_FILES[league].items():
            if not os.path.exists(path):
                continue
            df = pd.read_excel(path)
            if player_short_name in df['Player'].values:
                return pos_key
    return None


@st.cache_data
def _load_peer_file(path: str) -> pd.DataFrame:
    """Cache individual peer file loads — these are the expensive disk reads."""
    return pd.read_excel(path)


# ── PCA feature selection ──────────────────────────────────────────────────────

_ADMIN_COLS = {
    'Minutes played', 'Matches played', 'Player', 'Team', 'Position', 'Age',
    'Height', 'Weight', 'Foot', 'Birth date', 'Contract expires', 'Passport country',
    'On loan', 'Market value', 'Citizenship', 'League', 'Nation',
}


def _rate_columns(df: pd.DataFrame) -> list:
    """
    Return all per-90 and percentage columns from a Wyscout peer DataFrame.
    Excludes admin/count columns, keeps only columns with at least 50% non-null values.
    """
    cols = []
    for c in df.columns:
        if c in _ADMIN_COLS:
            continue
        cl = c.lower()
        if 'per 90' in cl or cl.endswith('%') or cl.endswith(', %') or 'ratio' in cl:
            non_null = df[c].apply(pd.to_numeric, errors='coerce').notna().mean()
            if non_null >= 0.5:
                cols.append(c)
    return cols


# ── PCA implementation ─────────────────────────────────────────────────────────

def _pca_comparables(
    client_totals: dict,
    pos_key: str,
    league_filter: list,
    min_mins: int,
    top_n: int = 8,
    client_name: str = "",
    n_components: Optional[int] = None,
    use_all_columns: bool = False,
) -> tuple[pd.DataFrame, dict]:
    """
    PCA-based player similarity.

    Parameters
    ----------
    use_all_columns : bool
        False → 16 curated metrics (same as current, no position weights).
        True  → all per-90 / % columns in the peer file; client imputed at peer
                mean for metrics not in season_combined.

    Returns
    -------
    result_df : pd.DataFrame
        top_n rows, columns: Player/Team/League/Minutes/Similarity/_rank + display cols.
        _rank is 1-based across ALL peers — needed for hybrid validation annotation.
    diagnostics : dict
        n_components, variance_explained, var_per_component, loadings_df,
        features_used, n_features, imputed_count, all_ranked (full df with _rank).
    """
    # ── Load and filter peer group ─────────────────────────────────────────
    dfs = []
    for league in league_filter:
        path = WS_FILES.get(league, {}).get(pos_key)
        if path and os.path.exists(path):
            df_l = _load_peer_file(path)
            df_l['_league'] = league
            dfs.append(df_l)

    if not dfs:
        return pd.DataFrame(), {}

    df = pd.concat(dfs, ignore_index=True)
    df = df[pd.to_numeric(df['Minutes played'], errors='coerce') >= min_mins].copy()

    if client_name:
        short = client_name.split()[-1]
        df = df[~df['Player'].str.lower().str.contains(short.lower(), na=False)]

    if len(df) < MIN_PEER_N:
        return pd.DataFrame(), {}

    df = df.reset_index(drop=True)

    # ── Select features ────────────────────────────────────────────────────
    if use_all_columns:
        feat_cols = _rate_columns(df)
    else:
        feat_cols = [c for c in _COMPARABLE_FEATURE_MAP if c in df.columns]

    if len(feat_cols) < 4:
        return pd.DataFrame(), {}

    # ── Build peer feature matrix ──────────────────────────────────────────
    peer_feats = df[feat_cols].apply(pd.to_numeric, errors='coerce')
    thresh = max(4, int(len(feat_cols) * 0.7))
    peer_feats = peer_feats.dropna(thresh=thresh)
    df = df.loc[peer_feats.index].reset_index(drop=True)
    peer_feats = peer_feats.reset_index(drop=True)

    col_means = peer_feats.mean()
    peer_feats = peer_feats.fillna(col_means)

    # ── Build client vector ────────────────────────────────────────────────
    client_arr  = []
    imputed_cols = []
    for c in feat_cols:
        client_key = _COMPARABLE_FEATURE_MAP.get(c)
        val = client_totals.get(client_key) if client_key else None
        if val is not None and not pd.isna(float(val)):
            client_arr.append(float(val))
        else:
            client_arr.append(float(col_means[c]))
            imputed_cols.append(c)
    client_arr = np.array(client_arr, dtype=float)

    # ── Z-score normalise ──────────────────────────────────────────────────
    X     = peer_feats.values.astype(float)
    means = X.mean(axis=0)
    stds  = X.std(axis=0)
    stds[stds == 0] = 1.0
    X_z   = (X - means) / stds
    c_z   = (client_arr - means) / stds

    # ── PCA via numpy SVD ──────────────────────────────────────────────────
    # SVD of X_z: X_z = U @ diag(S) @ Vt
    # Principal components = rows of Vt
    # Variance explained by each component = S_i^2 / sum(S^2)
    try:
        U, S, Vt = np.linalg.svd(X_z, full_matrices=False)
    except np.linalg.LinAlgError:
        return pd.DataFrame(), {}

    var_ratio = (S ** 2) / (S ** 2).sum()
    cumvar    = np.cumsum(var_ratio)

    if n_components is None:
        n_comp = int(np.searchsorted(cumvar, 0.95)) + 1
    else:
        n_comp = int(n_components)
    n_comp = min(n_comp, len(S), len(feat_cols), len(df))

    components = Vt[:n_comp]         # (n_comp, n_features)
    X_pca      = X_z @ components.T  # (n_peers, n_comp)
    c_pca      = c_z @ components.T  # (n_comp,)

    # ── Euclidean distance in PCA space ────────────────────────────────────
    diff      = X_pca - c_pca
    distances = np.sqrt((diff ** 2).sum(axis=1))

    df['_dist'] = distances
    df['_mins'] = pd.to_numeric(df['Minutes played'], errors='coerce')
    df = df.sort_values('_dist').reset_index(drop=True)
    df['_rank'] = range(1, len(df) + 1)

    max_d = float(df['_dist'].max())
    df['Similarity'] = (
        ((1 - df['_dist'] / max_d) * 100).clip(0, 100).round(1)
        if max_d > 0 else 100.0
    )

    # ── Build output DataFrame ─────────────────────────────────────────────
    display_cols = {c: lbl for c, lbl in _COMPARABLE_DISPLAY_COLS.items() if c in df.columns}
    keep = ['Player', 'Team', '_league', '_mins', 'Similarity', '_rank'] + list(display_cols.keys())
    keep = [c for c in keep if c in df.columns]

    all_ranked = df[keep].copy()
    all_ranked = all_ranked.rename(columns={'_league': 'League', '_mins': 'Minutes'})
    all_ranked = all_ranked.rename(columns=display_cols)
    if 'Minutes' in all_ranked.columns:
        all_ranked['Minutes'] = all_ranked['Minutes'].astype(int)

    result = all_ranked.head(top_n).copy()

    diagnostics = {
        'n_components':       n_comp,
        'variance_explained': float(var_ratio[:n_comp].sum() * 100),
        'var_per_component':  var_ratio.tolist(),   # full list for scree plot
        'loadings_df':        pd.DataFrame(Vt[:n_comp], columns=feat_cols),
        'features_used':      feat_cols,
        'n_features':         len(feat_cols),
        'imputed_count':      len(imputed_cols),
        'imputed_cols':       imputed_cols,
        'all_ranked':         all_ranked,
    }

    return result, diagnostics


# ── Chart helpers ──────────────────────────────────────────────────────────────

def _scree_plot(var_per_comp_full: list, n_comp: int, title: str = '') -> go.Figure:
    """Dark-theme bar chart of variance explained per PCA component."""
    n   = min(len(var_per_comp_full), 20)   # cap display at 20 components
    x   = [f"PC{i+1}" for i in range(n)]
    pct = [v * 100 for v in var_per_comp_full[:n]]
    cum = list(np.cumsum(pct))
    bar_cols = [GOLD if i < n_comp else '#2a2a2a' for i in range(n)]

    fig = go.Figure()
    fig.add_bar(x=x, y=pct, marker_color=bar_cols, name='% variance', opacity=0.9)
    fig.add_scatter(
        x=x, y=cum, mode='lines+markers',
        line=dict(color=GOLD, width=2, dash='dot'),
        marker=dict(size=4, color=GOLD),
        name='Cumulative %',
    )
    fig.add_hline(y=95, line_color='#444', line_dash='dot', line_width=1,
                  annotation_text='95%', annotation_font_color='#555')
    if n_comp <= n:
        fig.add_vline(x=n_comp - 0.5, line_color='#555', line_width=1, line_dash='dash')

    fig.update_layout(
        title=dict(text=title, font=dict(color='#888', size=10), x=0),
        height=220, plot_bgcolor=PLOT_BG, paper_bgcolor=PLOT_BG,
        font=dict(color='#aaa', size=9),
        margin=dict(l=40, r=10, t=36, b=40),
        xaxis=dict(showgrid=False, tickfont=dict(size=8, color='#666')),
        yaxis=dict(gridcolor='#222', showgrid=True, tickfont=dict(size=8, color='#666'),
                   zeroline=False, ticksuffix='%'),
        legend=dict(bgcolor='rgba(0,0,0,0)', font=dict(size=8, color='#888'),
                    orientation='h', y=1.1),
    )
    return fig


def _render_loadings(loadings_df: pd.DataFrame, n_show: int = 3, top_feats: int = 5):
    """Render top N component loadings as coloured mini-tables."""
    n_comp = min(n_show, len(loadings_df))
    cols   = st.columns(n_comp)
    for i in range(n_comp):
        row     = loadings_df.iloc[i]
        top_idx = row.abs().nlargest(top_feats).index
        with cols[i]:
            st.markdown(f"**Component {i+1}**")
            rows = []
            for feat in top_idx:
                loading = row[feat]
                colour  = '#4ade80' if loading > 0 else '#f87171'
                label   = feat.replace(' per 90', ' p90').replace('Successful defensive actions', 'Def actions')
                rows.append(
                    f'<span style="color:{colour};font-size:0.78rem">'
                    f'{loading:+.3f}</span> '
                    f'<span style="color:#aaa;font-size:0.78rem">{label}</span>'
                )
            st.markdown("<br>".join(rows), unsafe_allow_html=True)


def _sim_colour(val) -> str:
    """Pandas Styler: colour Similarity cells."""
    try:
        v = float(val)
    except (TypeError, ValueError):
        return ""
    if v >= 85:
        return "background-color: #166534; color: #86efac"
    elif v >= 70:
        return "background-color: #854d0e; color: #fde68a"
    return "background-color: #1e3a5f; color: #93c5fd"


def _rank_colour(val) -> str:
    """Pandas Styler: colour rank cells — low rank = more similar = greener."""
    try:
        v = int(val)
    except (TypeError, ValueError):
        return "color: #555"
    if v <= 8:
        return "color: #4ade80; font-weight: 700"
    elif v <= 16:
        return "color: #facc15"
    return "color: #666"


def _signal_colour(val) -> str:
    """Pandas Styler: colour signal cells."""
    if "Confirmed" in str(val):
        return "color: #4ade80; font-weight: 700"
    elif "Partial" in str(val):
        return "color: #facc15"
    return "color: #f87171"


def _show_comparables(df: pd.DataFrame, label: str, caption: str = ""):
    """Render a comparables table with the standard styling."""
    st.markdown(f'<div class="col-label">{label}</div>', unsafe_allow_html=True)
    if df.empty:
        st.caption("Not enough data to compute.")
        return
    display = df.drop(columns=['_rank'], errors='ignore')
    st.dataframe(
        display.style
            .format(precision=1, na_rep="–")
            .applymap(_sim_colour, subset=['Similarity']),
        use_container_width=True,
        hide_index=True,
    )
    if caption:
        st.caption(caption)


def _stat_card(label: str, value: str, sub: str, colour: str) -> str:
    return (
        f'<div class="stat-card">'
        f'<div class="label">{label}</div>'
        f'<div class="value" style="color:{colour}">{value}</div>'
        f'<div class="sub">{sub}</div>'
        f'</div>'
    )


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🔬 PCA Experiment")
    st.markdown(
        "<small style='color:#666'>Compare 3 similarity methods side-by-side. "
        "No changes to production code.</small>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    player_list = get_player_list()
    if not player_list:
        st.warning("No player master files found.")
        st.stop()

    player_names  = [p[0] for p in player_list]
    selected_name = st.selectbox("Player", player_names)
    selected_path = next(p[1] for p in player_list if p[0] == selected_name)

    st.markdown("---")
    st.markdown("### Peer group")
    min_mins = st.slider("Min minutes", 450, 1800, 900, 90)
    peer_leagues = st.multiselect(
        "Leagues",
        ["Championship", "League One", "League Two"],
        default=["Championship", "League One", "League Two"],
    )
    if not peer_leagues:
        peer_leagues = ["Championship", "League One", "League Two"]

    top_n = st.slider("Top N to compare", 5, 15, 8)

    st.markdown("---")
    st.markdown("### PCA settings")
    _auto_n = st.checkbox("Auto n_components (95% variance)", value=True)
    _manual_n = None
    if not _auto_n:
        _manual_n = st.slider("n_components", 2, 16, 6)
    n_components = None if _auto_n else _manual_n

    show_diagnostics = st.toggle("Show diagnostics", value=True)

    st.markdown("---")
    st.caption("Similarities computed fresh on each filter change.")


# ── Load player data ──────────────────────────────────────────────────────────

with st.spinner(f"Loading {selected_name}..."):
    sheets   = _load_master(selected_path)
    phys_csv = _load_physical_csv()

ws_raw = sheets.get('Wyscout')
ph_raw = sheets.get('Physical')

if ws_raw is None:
    st.error(f"No Wyscout sheet found for {selected_name}.")
    st.stop()

ws = ws_raw[ws_raw['Minutes played'] >= 20].copy().sort_values('Date').reset_index(drop=True)
ph = (ph_raw[ph_raw['minutes_full_all'] >= 20].copy()
      .sort_values('match_date').reset_index(drop=True)
      if ph_raw is not None else None)

season = get_season_totals(ws)
phys   = get_physical_totals(ph) if ph is not None else None
season_combined = {**season, **(phys or {})}

short = (ph_raw['player_short_name'].iloc[0]
         if ph_raw is not None and 'player_short_name' in ph_raw.columns
         else selected_name)

# Auto-detect position from peer files; fall back to manual selectbox
with st.spinner("Detecting position..."):
    ws_pos_key = _find_position(short) if short else None

if ws_pos_key is None:
    ws_pos_key = st.selectbox(
        "Position not auto-detected — select manually",
        POSITION_KEYS,
        index=0,
    )

pos_str  = ws_pos_key or "–"
mins_str = f"{int(season.get('mins', 0)):,}"
club_str = (ph_raw['team_name'].iloc[0]
            if ph_raw is not None and 'team_name' in ph_raw.columns else "")

# ── Page header ───────────────────────────────────────────────────────────────

st.markdown(
    f"## 🔬 PCA Comparable Players — Experiment &nbsp;"
    f"<span style='font-size:0.8rem;color:#888'>"
    f"{selected_name} · {pos_str} · {club_str} · {mins_str} mins</span>",
    unsafe_allow_html=True,
)
st.caption(
    "Experimental comparison only. Production comparable players (in the Club Report) "
    "continue to use the current position-weighted approach until you decide otherwise."
)

if not ws_pos_key:
    st.warning("No position detected — cannot compute comparables.")
    st.stop()

# ── Compute all three methods ─────────────────────────────────────────────────

with st.spinner("Computing comparables (3 methods)..."):
    # 1. Current approach (production)
    _phys_avgs = _cached_phys_avgs(phys_csv)
    try:
        current_df = find_comparable_players(
            client_totals=season_combined,
            pos_key=ws_pos_key,
            league_filter=peer_leagues,
            min_mins=min_mins,
            ws_files=WS_FILES,
            top_n=top_n,
            client_name=selected_name,
            client_phys=phys,
            phys_season_avgs=_phys_avgs,
        )
        # Drop the _phys_matched helper column — not needed here
        current_df = current_df.drop(columns=['_phys_matched'], errors='ignore')
    except Exception as _e:
        st.warning(f"Current approach failed: {_e}")
        current_df = pd.DataFrame()

    # 2. PCA — 16 curated metrics (no position weights)
    try:
        pca16_df, pca16_diag = _pca_comparables(
            client_totals=season_combined,
            pos_key=ws_pos_key,
            league_filter=peer_leagues,
            min_mins=min_mins,
            top_n=top_n,
            client_name=selected_name,
            n_components=n_components,
            use_all_columns=False,
        )
    except Exception as _e:
        st.warning(f"PCA-16 failed: {_e}")
        pca16_df, pca16_diag = pd.DataFrame(), {}

    # 3. PCA — all per-90/% columns (client imputed at peer mean)
    try:
        pcaall_df, pcaall_diag = _pca_comparables(
            client_totals=season_combined,
            pos_key=ws_pos_key,
            league_filter=peer_leagues,
            min_mins=min_mins,
            top_n=top_n,
            client_name=selected_name,
            n_components=n_components,
            use_all_columns=True,
        )
    except Exception as _e:
        st.warning(f"PCA-all failed: {_e}")
        pcaall_df, pcaall_diag = pd.DataFrame(), {}

# ── Build hybrid validation table ─────────────────────────────────────────────

pca16_full  = pca16_diag.get('all_ranked',  pd.DataFrame())
pcaall_full = pcaall_diag.get('all_ranked', pd.DataFrame())

hybrid_rows = []
confirmed_both = confirmed_one = unconfirmed = 0

if not current_df.empty:
    for _, row in current_df.iterrows():
        name = row['Player']

        pca16_match  = pca16_full[pca16_full['Player']  == name] if not pca16_full.empty  else pd.DataFrame()
        pcaall_match = pcaall_full[pcaall_full['Player'] == name] if not pcaall_full.empty else pd.DataFrame()

        rank16  = int(pca16_match['_rank'].iloc[0])  if not pca16_match.empty  else None
        rankall = int(pcaall_match['_rank'].iloc[0]) if not pcaall_match.empty else None

        in16  = rank16  is not None and rank16  <= top_n
        inall = rankall is not None and rankall <= top_n

        if in16 and inall:
            signal = "✓ Confirmed"
            confirmed_both += 1
        elif in16 or inall:
            signal = "~ Partial"
            confirmed_one += 1
        else:
            signal = "? Unconfirmed"
            unconfirmed += 1

        hybrid_rows.append({
            'Player':       name,
            'Team':         row.get('Team', ''),
            'Current sim':  row.get('Similarity'),
            'PCA-16 rank':  rank16  if rank16  is not None else '–',
            'PCA-all rank': rankall if rankall is not None else '–',
            'Signal':       signal,
        })

hybrid_df = pd.DataFrame(hybrid_rows)

# PCA-only discoveries: top_n in BOTH PCA lists but absent from current
current_names  = set(current_df['Player'].tolist()) if not current_df.empty else set()
pca16_names    = set(pca16_full.head(top_n)['Player'].tolist())  if not pca16_full.empty  else set()
pcaall_names   = set(pcaall_full.head(top_n)['Player'].tolist()) if not pcaall_full.empty else set()
discovery_names = (pca16_names & pcaall_names) - current_names

discovery_rows = []
for name in discovery_names:
    r16  = pca16_full[pca16_full['Player']  == name]
    rall = pcaall_full[pcaall_full['Player'] == name]
    rank16  = int(r16['_rank'].iloc[0])  if not r16.empty  else 999
    rankall = int(rall['_rank'].iloc[0]) if not rall.empty else 999
    team = r16['Team'].iloc[0] if not r16.empty else (rall['Team'].iloc[0] if not rall.empty else '')
    discovery_rows.append({
        'Player': name, 'Team': team,
        'PCA-16 rank': rank16, 'PCA-all rank': rankall,
        'Avg PCA rank': round((rank16 + rankall) / 2, 1),
    })
discovery_rows.sort(key=lambda x: x['Avg PCA rank'])

# ── Four-column comparison display ────────────────────────────────────────────

st.markdown('<div class="section-header">Method comparison — top {}</div>'.format(top_n),
            unsafe_allow_html=True)

col1, col2, col3, col4 = st.columns(4)

with col1:
    n_feat_cur = len(_COMPARABLE_FEATURE_MAP)
    _show_comparables(
        current_df,
        label="Current — position-weighted",
        caption=f"16 features · position weights active",
    )

with col2:
    if pca16_diag:
        n16  = pca16_diag['n_components']
        var16 = pca16_diag['variance_explained']
        _show_comparables(
            pca16_df,
            label=f"PCA — 16 metrics",
            caption=f"{n16} components · {var16:.0f}% variance · no position weights",
        )
    else:
        st.markdown('<div class="col-label">PCA — 16 metrics</div>', unsafe_allow_html=True)
        st.caption("Not enough data.")

with col3:
    if pcaall_diag:
        nall  = pcaall_diag['n_components']
        varall = pcaall_diag['variance_explained']
        nfeat = pcaall_diag['n_features']
        nimp  = pcaall_diag['imputed_count']
        _show_comparables(
            pcaall_df,
            label=f"PCA — all columns",
            caption=(
                f"{nall} components · {varall:.0f}% variance · "
                f"{nfeat} features · {nimp} client metrics imputed at peer mean"
            ),
        )
    else:
        st.markdown('<div class="col-label">PCA — all columns</div>', unsafe_allow_html=True)
        st.caption("Not enough data.")

with col4:
    st.markdown('<div class="col-label">Hybrid validation</div>', unsafe_allow_html=True)
    if not hybrid_df.empty:
        num_cols = ['Current sim']
        rank_cols = ['PCA-16 rank', 'PCA-all rank']
        styler = hybrid_df.style.format(
            {c: '{:.1f}' for c in num_cols if c in hybrid_df.columns},
            na_rep='–',
        )
        if 'Similarity' in hybrid_df.columns:
            styler = styler.applymap(_sim_colour, subset=['Current sim'])
        for rc in rank_cols:
            if rc in hybrid_df.columns:
                styler = styler.applymap(_rank_colour, subset=[rc])
        if 'Signal' in hybrid_df.columns:
            styler = styler.applymap(_signal_colour, subset=['Signal'])
        st.dataframe(styler, use_container_width=True, hide_index=True)

        if discovery_rows:
            st.markdown("**PCA-only discoveries** ↓")
            st.caption(
                f"{len(discovery_rows)} player(s) in both PCA top-{top_n} lists "
                f"but not in current approach — worth reviewing manually."
            )
            st.dataframe(
                pd.DataFrame(discovery_rows).style.format(precision=1),
                use_container_width=True,
                hide_index=True,
            )
    else:
        st.caption("No current results to annotate.")

# ── Agreement summary bar ──────────────────────────────────────────────────────

st.markdown('<div class="section-header">Agreement summary</div>', unsafe_allow_html=True)
_total = max(len(hybrid_rows), 1)
_disc  = len(discovery_rows)

c_green  = '#4ade80' if confirmed_both >= (_total * 0.6)   else ('#facc15' if confirmed_both >= (_total * 0.375) else '#f87171')
c_amber  = '#facc15'
c_disc   = '#facc15' if _disc > 0 else '#4ade80'

scards = st.columns(4)
with scards[0]:
    st.markdown(
        _stat_card("Confirmed by both PCA", f"{confirmed_both}/{_total}",
                   "In top-N for PCA-16 and PCA-all", c_green),
        unsafe_allow_html=True,
    )
with scards[1]:
    st.markdown(
        _stat_card("Partial — one PCA only", f"{confirmed_one}/{_total}",
                   "In top-N for exactly one PCA method", c_amber),
        unsafe_allow_html=True,
    )
with scards[2]:
    st.markdown(
        _stat_card("Unconfirmed by either PCA", f"{unconfirmed}/{_total}",
                   "Not in either PCA top-N", "#f87171"),
        unsafe_allow_html=True,
    )
with scards[3]:
    st.markdown(
        _stat_card("PCA-only discoveries", str(_disc),
                   "Missed by current, found by both PCA", c_disc),
        unsafe_allow_html=True,
    )

# ── Diagnostics ───────────────────────────────────────────────────────────────

if show_diagnostics and (pca16_diag or pcaall_diag):
    st.markdown('<div class="section-header">PCA diagnostics</div>', unsafe_allow_html=True)
    with st.expander("Scree plots & component loadings", expanded=True):
        diag_tabs = []
        if pca16_diag:
            diag_tabs.append("PCA — 16 metrics")
        if pcaall_diag:
            diag_tabs.append("PCA — all columns")

        if diag_tabs:
            tabs = st.tabs(diag_tabs)
            tab_idx = 0

            if pca16_diag:
                with tabs[tab_idx]:
                    tab_idx += 1
                    _dc = pca16_diag
                    d1, d2 = st.columns([1, 2])
                    with d1:
                        st.plotly_chart(
                            _scree_plot(
                                _dc['var_per_component'],
                                _dc['n_components'],
                                f"Variance explained — {_dc['n_components']} components selected",
                            ),
                            use_container_width=True,
                        )
                        st.caption(
                            f"{_dc['n_components']} components explain "
                            f"{_dc['variance_explained']:.1f}% of variance. "
                            f"Features: {_dc['n_features']}."
                        )
                    with d2:
                        st.markdown("**Top component loadings** (green = positive, red = negative)")
                        _render_loadings(_dc['loadings_df'], n_show=min(3, _dc['n_components']))
                    with st.expander(f"All {_dc['n_features']} features used"):
                        st.write(", ".join(_dc['features_used']))

            if pcaall_diag:
                with tabs[tab_idx]:
                    _dc = pcaall_diag
                    d1, d2 = st.columns([1, 2])
                    with d1:
                        st.plotly_chart(
                            _scree_plot(
                                _dc['var_per_component'],
                                _dc['n_components'],
                                f"Variance explained — {_dc['n_components']} components selected",
                            ),
                            use_container_width=True,
                        )
                        st.caption(
                            f"{_dc['n_components']} components explain "
                            f"{_dc['variance_explained']:.1f}% of variance. "
                            f"Features: {_dc['n_features']}. "
                            f"Client imputed on {_dc['imputed_count']} features."
                        )
                        if _dc['imputed_cols']:
                            with st.expander(f"{_dc['imputed_count']} imputed features"):
                                st.caption(
                                    "Client placed at peer mean for these metrics (not in season_combined):"
                                )
                                st.write(", ".join(_dc['imputed_cols']))
                    with d2:
                        st.markdown("**Top component loadings** (green = positive, red = negative)")
                        _render_loadings(_dc['loadings_df'], n_show=min(3, _dc['n_components']))
                    with st.expander(f"All {_dc['n_features']} features used"):
                        st.write(", ".join(_dc['features_used']))
