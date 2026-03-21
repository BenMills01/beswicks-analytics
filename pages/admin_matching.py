"""
pages/admin_matching.py
Beswicks Sports Analytics — Player Matching Admin

Streamlit multi-page app page.
Shows unmatched / low-confidence SkillCorner↔Wyscout player links
and lets you manually set the correct Wyscout name via overrides CSV.
"""

import streamlit as st
import pandas as pd
import os

st.set_page_config(
    page_title="Beswicks | Matching Admin",
    page_icon="🔧",
    layout="wide",
)

# ── Paths ─────────────────────────────────────────────────────────────────────
DATA_DIR       = "data"
MATCHING_CSV    = os.path.join(DATA_DIR, "player_matching_l1_l2_2526.csv")
OVERRIDES_CSV   = os.path.join(DATA_DIR, "matching_overrides.csv")
PHYSICAL_CSV    = os.path.join(DATA_DIR, "physical_l1_l2_2526.csv")
WYSCOUT_FILES  = [
    os.path.join(DATA_DIR, "League One min 874 mins.xlsx"),
    os.path.join(DATA_DIR, "League One Central Defenders.xlsx"),
    os.path.join(DATA_DIR, "League One Full Back:Wing Back.xlsx"),
    os.path.join(DATA_DIR, "League One Central Midfielders.xlsx"),
    os.path.join(DATA_DIR, "League One Attacking Midfielders.xlsx"),
    os.path.join(DATA_DIR, "League One Wide Midfielders.xlsx"),
    os.path.join(DATA_DIR, "League One CF's.xlsx"),
    os.path.join(DATA_DIR, "League One GKs.xlsx"),
    os.path.join(DATA_DIR, "League Two min 874 mins.xlsx"),
    os.path.join(DATA_DIR, "League Two Central Defenders.xlsx"),
    os.path.join(DATA_DIR, "League Two FB:WB.xlsx"),
    os.path.join(DATA_DIR, "League Two Central Midfielders.xlsx"),
    os.path.join(DATA_DIR, "League Two Attacking Midfielders.xlsx"),
    os.path.join(DATA_DIR, "League Two Wide Midfielders.xlsx"),
    os.path.join(DATA_DIR, "League Two CFs.xlsx"),
    os.path.join(DATA_DIR, "League Two GKs.xlsx"),
]

CONF_THRESHOLD = 0.85  # below this → flagged as low confidence

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 1.5rem; }
[data-testid="stSidebar"] { background: #0f0f0f; }
[data-testid="stSidebar"] * { color: #e0e0e0 !important; }
.admin-header {
    background: #0f0f0f; padding: 16px 24px; border-radius: 10px;
    margin-bottom: 20px; border-left: 4px solid #f87171;
}
.admin-header h1 { color: #fff; font-size: 1.2rem; font-weight: 700; margin: 0; }
.admin-header p  { color: #888; font-size: 0.78rem; margin: 4px 0 0; }
.stat-box {
    background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 8px;
    padding: 14px 18px; text-align: center;
}
.stat-val  { font-size: 2rem; font-weight: 700; color: #fff; line-height: 1; }
.stat-lbl  { font-size: 0.7rem; color: #666; text-transform: uppercase; letter-spacing: 0.06em; margin-top: 4px; }
.stat-red  .stat-val { color: #f87171; }
.stat-warn .stat-val { color: #facc15; }
.stat-ok   .stat-val { color: #4ade80; }
.section-header {
    font-size: 0.7rem; font-weight: 700; letter-spacing: 0.1em;
    text-transform: uppercase; color: #c8a45a; margin: 20px 0 10px;
    padding-bottom: 6px; border-bottom: 1px solid #2a2a2a;
}
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="admin-header">
  <h1>🔧 Player Matching Admin</h1>
  <p>Manage SkillCorner ↔ Wyscout player links · Fix unmatched and low-confidence entries</p>
</div>
""", unsafe_allow_html=True)

# ── Load data ─────────────────────────────────────────────────────────────────
@st.cache_data
def load_matching():
    if not os.path.exists(MATCHING_CSV):
        return None
    df = pd.read_csv(MATCHING_CSV)
    # One row per player — keep highest match score
    return (
        df.sort_values('wyscout_match_score', ascending=False)
        .drop_duplicates(subset='sc_player_id')
        .reset_index(drop=True)
    )

@st.cache_data
def load_wyscout_league():
    dfs = []
    for p in WYSCOUT_FILES:
        if os.path.exists(p):
            d = pd.read_excel(p)
            d['_league'] = 'League One' if 'Lge_1' in p else 'League Two'
            dfs.append(d)
    if not dfs:
        return None
    return pd.concat(dfs, ignore_index=True)

def load_overrides():
    if not os.path.exists(OVERRIDES_CSV):
        return pd.DataFrame(columns=['sc_player_id','skillcorner_name','wyscout_name','wyscout_team','notes','updated_at'])
    return pd.read_csv(OVERRIDES_CSV)

def save_overrides(df):
    os.makedirs(DATA_DIR, exist_ok=True)
    df.to_csv(OVERRIDES_CSV, index=False)

def delete_override(sc_player_id):
    ov = load_overrides()
    ov = ov[ov['sc_player_id'] != sc_player_id]
    save_overrides(ov)

def upsert_override(sc_player_id, skillcorner_name, wyscout_name, wyscout_team, notes='manual'):
    ov  = load_overrides()
    now = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')
    new_row = pd.DataFrame([{
        'sc_player_id':    sc_player_id,
        'skillcorner_name':skillcorner_name,
        'wyscout_name':    wyscout_name,
        'wyscout_team':    wyscout_team,
        'notes':           notes,
        'updated_at':      now,
    }])
    # Remove existing entry for this player then append
    ov = ov[ov['sc_player_id'] != sc_player_id]
    ov = pd.concat([ov, new_row], ignore_index=True)
    save_overrides(ov)

matching  = load_matching()
league_df = load_wyscout_league()
overrides = load_overrides()

if matching is None:
    st.error(f"Matching file not found at `{MATCHING_CSV}`. Add it to your `data/` folder.")
    st.stop()

if league_df is None:
    st.error("Wyscout league files not found in `data/`. Cannot show candidate matches.")
    st.stop()

# ── Categorise players ────────────────────────────────────────────────────────
no_match  = matching[matching['wyscout_name'].isna()].copy()
low_conf  = matching[
    matching['wyscout_name'].notna() &
    matching['player_id'].isna() &
    (matching['wyscout_match_score'] < CONF_THRESHOLD)
].copy()
good      = matching[
    matching['player_id'].notna() |
    (matching['wyscout_match_score'] >= CONF_THRESHOLD)
].copy()

# Mark which have overrides
override_ids = set(overrides['sc_player_id'].astype(int).tolist()) if len(overrides) else set()
no_match_remaining  = no_match[~no_match['sc_player_id'].isin(override_ids)]
low_conf_remaining  = low_conf[~low_conf['sc_player_id'].isin(override_ids)]
needs_attention     = len(no_match_remaining) + len(low_conf_remaining)

# ── Stats ─────────────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
stats = [
    (c1, len(matching),        "Total players",    "stat-ok"),
    (c2, len(good),            "Well matched",     "stat-ok"),
    (c3, len(low_conf),        "Low confidence",   "stat-warn"),
    (c4, len(no_match),        "No match found",   "stat-red"),
    (c5, len(overrides),       "Manual overrides", "stat-ok"),
]
for col, val, lbl, cls in stats:
    col.markdown(f"<div class='stat-box {cls}'><div class='stat-val'>{val}</div><div class='stat-lbl'>{lbl}</div></div>", unsafe_allow_html=True)

st.markdown("")

# ── Wyscout player lookup helper ──────────────────────────────────────────────
def find_wyscout_candidates(name_hint, team_hint=None, n=8):
    """Search the Wyscout league file for players matching a name fragment."""
    hits = league_df[league_df['Player'].str.contains(name_hint, case=False, na=False)]
    if team_hint:
        team_hits = hits[hits['Team'].str.contains(team_hint, case=False, na=False)]
        if len(team_hits) > 0:
            hits = team_hits
    return hits[['Player','Team','Position','Minutes played','_league']].drop_duplicates(subset=['Player','Team']).head(n)

# ── Unsaved overrides warning ─────────────────────────────────────────────────
if len(overrides) > 0:
    warning_html = (
        f"<div style='background:#1a0a00;border:1px solid #c8a45a;border-radius:8px;"
        f"padding:12px 16px;margin:0 0 16px;font-size:0.8rem;color:#c8a45a;'>"
        f"<b>Remember to commit your overrides to GitHub.</b><br>"
        f"<span style='color:#888;font-size:0.75rem;'>"
        f"You have {len(overrides)} override(s) saved this session. They will be lost when the app reboots "
        f"unless you download the CSV and commit it to <code>data/matching_overrides.csv</code> in your GitHub repo. "
        f"Go to the Overrides tab to download."
        f"</span></div>"
    )
    st.markdown(warning_html, unsafe_allow_html=True)

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_fix, tab_overrides, tab_all = st.tabs([
    f"⚠️ Needs attention ({needs_attention})",
    f"✅ Overrides ({len(overrides)})",
    f"📋 All players ({len(matching)})",
])

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — Needs attention
# ─────────────────────────────────────────────────────────────────────────────
with tab_fix:

    # ── Filter controls ───────────────────────────────────────────────────────
    col_f1, col_f2, col_f3 = st.columns([2, 2, 1])
    with col_f1:
        show_type = st.radio("Show", ["Both", "No match", "Low confidence"], horizontal=True)
    with col_f2:
        league_filter = st.radio("League", ["Both", "League One", "League Two"], horizontal=True)
    with col_f3:
        hide_fixed = st.checkbox("Hide already overridden", value=True)

    # Build display list
    if show_type == "No match":
        display = no_match.copy()
    elif show_type == "Low confidence":
        display = low_conf.copy()
    else:
        display = pd.concat([no_match, low_conf], ignore_index=True)

    if league_filter != "Both":
        display = display[display['competition'].str.contains(league_filter.split()[-1], na=False)]

    if hide_fixed:
        display = display[~display['sc_player_id'].isin(override_ids)]

    display = display.sort_values(['competition', 'sc_team', 'skillcorner_name'])

    if len(display) == 0:
        st.success("All players in this category have been overridden or are well matched. ✓")
    else:
        st.caption(f"Showing {len(display)} players · Click a row to expand and fix")
        st.markdown("")

        for _, row in display.iterrows():
            sc_id   = int(row['sc_player_id'])
            sc_name = row['skillcorner_name']
            sc_team = row['sc_team']
            ws_name = row['wyscout_name'] if pd.notna(row['wyscout_name']) else "—"
            score   = row['wyscout_match_score'] if pd.notna(row['wyscout_match_score']) else None
            comp    = row['competition']

            # Score badge
            if score is None:
                badge = "🔴 No match"
            elif score >= 0.85:
                badge = f"🟡 {score:.2f}"
            else:
                badge = f"🔴 {score:.2f}"

            already_overridden = sc_id in override_ids
            ovr_label = " ✅ overridden" if already_overridden else ""

            with st.expander(f"**{sc_name}** · {sc_team} · {comp} · {badge}{ovr_label}"):

                col_info, col_fix = st.columns([1, 2])

                with col_info:
                    st.markdown("**SkillCorner record**")
                    st.write(f"SC player ID: `{sc_id}`")
                    st.write(f"Name: **{sc_name}**")
                    st.write(f"Team: {sc_team}")
                    st.write(f"Competition: {comp}")
                    st.markdown("---")
                    st.markdown("**Current match**")
                    st.write(f"Wyscout name: `{ws_name}`")
                    st.write(f"Match score: `{score:.3f}`" if score else "Match score: `—`")

                    if already_overridden:
                        ov_row = overrides[overrides['sc_player_id'] == sc_id].iloc[0]
                        st.markdown("---")
                        st.markdown("**Current override**")
                        st.write(f"→ `{ov_row['wyscout_name']}` ({ov_row['wyscout_team']})")
                        st.caption(f"Set {ov_row['updated_at']}")

                with col_fix:
                    st.markdown("**Find correct Wyscout entry**")

                    # Auto-suggest: derive initials from SC full name
                    parts   = sc_name.strip().split()
                    default_search = f"{parts[0][0]}. {parts[-1]}" if len(parts) >= 2 else sc_name

                    search_hint = st.text_input(
                        "Search Wyscout players",
                        value=default_search,
                        key=f"search_{sc_id}",
                        help="Type part of the abbreviated name e.g. 'C. Taylor' or just a surname",
                    )
                    team_hint = st.text_input(
                        "Filter by team (optional)",
                        value="",
                        key=f"team_{sc_id}",
                        placeholder=sc_team,
                    )

                    if search_hint:
                        candidates = find_wyscout_candidates(search_hint, team_hint or None)

                        if len(candidates) == 0:
                            st.warning("No Wyscout players found matching that search.")
                            st.caption("Try a shorter search — just a surname or first initial.")
                        else:
                            st.markdown("**Candidates:**")
                            for _, cand in candidates.iterrows():
                                mins_str = f"{int(cand['Minutes played'])} mins" if pd.notna(cand['Minutes played']) else "—"
                                label = f"**{cand['Player']}** · {cand['Team']} · {cand['Position']} · {mins_str} · {cand['_league']}"

                                if st.button(f"✓ Use this: {cand['Player']} ({cand['Team']})", key=f"btn_{sc_id}_{cand['Player']}_{cand['Team']}"):
                                    upsert_override(
                                        sc_player_id    = sc_id,
                                        skillcorner_name= sc_name,
                                        wyscout_name    = cand['Player'],
                                        wyscout_team    = cand['Team'],
                                        notes           = 'manual',
                                    )
                                    st.success(f"Saved: {sc_name} → {cand['Player']} ({cand['Team']})")
                                    load_overrides.clear() if hasattr(load_overrides,'clear') else None
                                    st.rerun()

                    st.markdown("---")
                    st.markdown("**Or enter manually**")
                    manual_ws_name = st.text_input("Wyscout name (exact)", value=ws_name if ws_name != "—" else "", key=f"manual_name_{sc_id}", placeholder="e.g. C. Taylor")
                    manual_ws_team = st.text_input("Wyscout team",         value=sc_team,                                                          key=f"manual_team_{sc_id}", placeholder="e.g. Wycombe Wanderers")

                    col_save, col_del = st.columns([1, 1])
                    with col_save:
                        if st.button("💾 Save override", key=f"save_{sc_id}", use_container_width=True):
                            if manual_ws_name.strip():
                                upsert_override(sc_id, sc_name, manual_ws_name.strip(), manual_ws_team.strip())
                                st.success(f"Saved override for {sc_name}")
                                st.rerun()
                            else:
                                st.error("Wyscout name cannot be empty.")

                    with col_del:
                        if already_overridden:
                            if st.button("🗑 Remove override", key=f"del_{sc_id}", use_container_width=True):
                                delete_override(sc_id)
                                st.info(f"Override removed for {sc_name}")
                                st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — Current overrides
# ─────────────────────────────────────────────────────────────────────────────
with tab_overrides:
    overrides_fresh = load_overrides()

    if len(overrides_fresh) == 0:
        st.info("No overrides saved yet. Fix unmatched players in the 'Needs attention' tab.")
    else:
        st.caption(f"{len(overrides_fresh)} overrides · These take priority over the matching file in the main app")
        st.markdown("")

        for _, row in overrides_fresh.iterrows():
            sc_id = int(row['sc_player_id'])
            col_a, col_b, col_c, col_d = st.columns([3, 3, 2, 1])
            col_a.write(f"**{row['skillcorner_name']}**")
            col_b.write(f"→ `{row['wyscout_name']}` · {row['wyscout_team']}")
            col_c.write(f"_{row.get('updated_at','—')}_")
            if col_d.button("🗑", key=f"del_ov_{sc_id}", help="Remove this override"):
                delete_override(sc_id)
                st.rerun()

        st.markdown("---")
        # Download overrides as CSV
        csv_bytes = overrides_fresh.to_csv(index=False).encode()
        st.download_button(
            "⬇️ Download overrides CSV",
            data=csv_bytes,
            file_name="matching_overrides.csv",
            mime="text/csv",
            help="Download to commit to your GitHub repo",
        )

        st.info(
            "**Important:** After saving overrides here, download the CSV above and commit it to "
            "`data/matching_overrides.csv` in your GitHub repo so overrides persist across deploys.",
            icon="ℹ️"
        )

# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — All players
# ─────────────────────────────────────────────────────────────────────────────
with tab_all:
    st.caption(f"{len(matching)} total SkillCorner players · showing match status")

    search_all = st.text_input("Search by name or team", placeholder="e.g. Connor Taylor, Wycombe...")

    display_all = matching.copy()
    display_all['status'] = display_all.apply(lambda r:
        'Override' if r['sc_player_id'] in override_ids else
        'No match' if pd.isna(r['wyscout_name']) else
        'Low confidence' if (pd.isna(r['player_id']) and r['wyscout_match_score'] < CONF_THRESHOLD) else
        'Good',
        axis=1
    )

    if search_all:
        mask = (
            display_all['skillcorner_name'].str.contains(search_all, case=False, na=False) |
            display_all['sc_team'].str.contains(search_all, case=False, na=False)
        )
        display_all = display_all[mask]

    status_colour = {
        'Override':        '✅',
        'Good':            '🟢',
        'Low confidence':  '🟡',
        'No match':        '🔴',
    }
    display_all[''] = display_all['status'].map(status_colour)

    st.dataframe(
        display_all[['','skillcorner_name','sc_team','competition','wyscout_name','wyscout_match_score','status']].rename(columns={
            'skillcorner_name':    'SkillCorner name',
            'sc_team':             'SC team',
            'competition':         'League',
            'wyscout_name':        'Wyscout name',
            'wyscout_match_score': 'Match score',
            'status':              'Status',
        }),
        use_container_width=True,
        hide_index=True,
        height=600,
    )
