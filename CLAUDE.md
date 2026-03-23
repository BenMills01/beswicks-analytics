# Beswicks Sports Analytics — Claude Instructions

## What this project is

A Streamlit-based football performance analysis platform for Beswicks Sports, a
professional football agency. It ingests Wyscout CSV/XLSX exports and SkillCorner
physical data to produce interactive dashboards and PDF reports for internal
analysts, players, and clubs.

## Stack

- **Framework**: Streamlit (multi-page app — `app.py` is the main page, `pages/` holds extras)
- **Data**: Wyscout XLSX exports + SkillCorner CSV (`data/physical_l1_l2_2526.csv`)
- **Visualisation**: Plotly (dark theme — `PLOT_BG = '#0f0f0f'`)
- **PDF export**: ReportLab (`generate_report.py`) — A4 portrait, dark-branded
- **Numeric**: pandas, numpy, scipy (percentile scoring via `scipy_stats.percentileofscore`)
- **Python**: 3.11+, dependencies in `requirements.txt`

## Project structure

```
beswicks-analytics/
├── app.py                        # Main Streamlit page — all core dashboard logic
├── generate_report.py            # PDF report generator (ReportLab)
├── pages/
│   └── admin_matching.py         # SkillCorner↔Wyscout name matching admin UI
├── data/
│   ├── players/                  # Per-client master XLSX files (*_master.xlsx)
│   │   └── {Name}_master.xlsx    # Sheets: Wyscout, Physical, Pressing, Off_Ball_Runs, Match_by_Match
│   ├── League One *.xlsx         # Position-specific peer group files
│   ├── League Two *.xlsx         # Position-specific peer group files
│   ├── physical_l1_l2_2526.csv   # SkillCorner physical data (all players)
│   ├── player_matching_l1_l2_2526.csv  # SkillCorner↔Wyscout name matching
│   └── matching_overrides.csv    # Manual override file for low-confidence matches
└── .claude/                      # This folder
```

## Key architecture decisions

### Player master files
Each client has a `data/players/{First}_{Last}_master.xlsx` with these sheets:
- `Wyscout` — match-by-match Wyscout export (columns accessed by name AND index — be careful)
- `Physical` — SkillCorner match-level physical data
- `Pressing` — SkillCorner under-pressure passing data
- `Off_Ball_Runs` — SkillCorner off-ball run data
- `Match_by_Match` — aggregated match log

### Column access — critical gotcha
Some Wyscout columns are accessed by **integer index** (not name) because Wyscout
exports use duplicate or non-obvious column names. Examples from `get_season_totals()`:
- `ws.iloc[:,13]` = accurate passes
- `ws.iloc[:,15]` = accurate long passes
- `ws.iloc[:,19]` = successful dribbles
- `ws.iloc[:,21]` = duels won
- `ws.iloc[:,23]` = aerial duels won
- `ws.iloc[:,31]` = defensive duels
- `ws.iloc[:,32]` = defensive duels won
- `ws.iloc[:,39]` = yellow cards
- `ws.iloc[:,40]` = red cards

**Never rename these columns or change their order in source files.**

### Player name resolution
SkillCorner and Wyscout use different name formats. Resolution priority:
1. Manual override in `matching_overrides.csv`
2. High-confidence fuzzy match (score >= 0.85) from `player_matching_l1_l2_2526.csv`
3. Fallback to SkillCorner short name

The `resolve_wyscout_name()` function handles this. `CONF_THRESHOLD = 0.85`.

### Peer group logic
- Physical peers: built from `physical_l1_l2_2526.csv`, filtered by `position_group` column
- Wyscout peers: built from position-specific XLSX files (e.g. `League One Central Defenders.xlsx`)
- Position file is auto-detected by scanning files for the player's Wyscout short name
- Minimum 5 peers required before percentile ranking is shown
- Peer league filter (Both / L1 / L2) and minimum minutes set in sidebar

### Metric expression
- All rate stats expressed per 90 minutes
- Raw totals used only for goals, assists, appearances, cards
- Percentile ranks via `scipy_stats.percentileofscore` (kind='rank')
- Minimum 450 mins for physical peer inclusion; configurable for Wyscout

### Caching
- `@st.cache_data` on all data loaders EXCEPT `load_overrides()` (intentionally
  not cached so admin edits apply immediately without restarting)
- If adding new loaders, always apply `@st.cache_data`

### Plotting conventions
- All charts dark theme: `PLOT_BG = PAPER_BG = '#0f0f0f'`
- Bar opacity encodes minutes played (`mins_to_opacity()`, lo=0.3, hi=1.0)
- Rolling average always purple (`PURPLE = '#a78bfa'`), window=5, min_periods=3
- Player season average shown as dashed gold line
- Position peer average shown as dashed grey line
- Never add gridlines on x-axis (`showgrid=False` on xaxis)

### PDF report (`generate_report.py`)
- A4 portrait, dark background (#0f0f0f), gold (#c8a45a) brand colour
- ReportLab `SimpleDocTemplate` with 18mm margins
- Page 1: profile header + season metrics table
- Page 2: radar chart + physical output table
- Page 3: form trend charts
- Page 4: match log table
- Plotly charts exported to PNG via Kaleido before embedding

## Domain rules

### Audiences — always confirm before generating any report text
- `internal` — candid, full analytical depth, can flag concerns directly
- `player` — honest but constructive, development-focused, accessible language
- `club` — polished, confident, structured fit argument

### Comparisons
- Never compare across positions
- Default same-league; cross-league requires a manually provided difficulty multiplier
- Never estimate a multiplier — always ask

### Clients (as of initial setup)
Seven client master files exist in `data/players/`:
- Connor Taylor
- Devon Matthews
- James Plant
- Jordan Willis
- Lasse Sorensen
- Lewis Macari
- Will Goodwin

New clients: create `data/players/{First}_{Last}_master.xlsx` with the five sheets above.

## Code standards

- Type hints and docstrings on all new functions
- No hardcoded player names or file paths in logic — always derive from config or input
- Multipliers passed explicitly, never inferred
- New Streamlit pages go in `pages/` with `st.set_page_config()` at the top
- Use `st.cache_data` on all data loaders
- Metric calculations must be consistent with `get_season_totals()` and `get_physical_totals()`
- Never use `print()` — Streamlit surfaces these oddly; use `st.write()` for debug or remove
- Do not change column index positions in Wyscout sheets without updating all iloc references
