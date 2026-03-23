# Skill: data-pipeline

Auto-invoked when: adding new data files, updating player master files,
modifying matching logic, or handling SkillCorner/Wyscout data imports.

## What this skill covers

The data pipeline for the Beswicks platform has two sources that must be
linked together per player: Wyscout (technical) and SkillCorner (physical).

## File conventions

### Player master files
Location: `data/players/{First}_{Last}_master.xlsx`
Required sheets (exact names):
- `Wyscout` — match-by-match, min 20 mins per match to be included
- `Physical` — SkillCorner match-level, min 20 mins per match
- `Pressing` — SkillCorner under-pressure passing, min 20 mins
- `Off_Ball_Runs` — SkillCorner off-ball runs, min 20 mins
- `Match_by_Match` — aggregated season totals (reference only)

### League peer files
Location: `data/`
Two naming conventions in use:
- `League One Full Back:Wing Back.xlsx` (colon separator)
- `League Two FB:WB.xlsx` (abbreviated)
Always verify the exact filename before referencing in `WS_FILES`.

## SkillCorner↔Wyscout matching

### Matching file
`data/player_matching_l1_l2_2526.csv` contains fuzzy-matched player names.
Confidence threshold: 0.85 (`CONF_THRESHOLD`).
Below 0.85, the match is ignored unless overridden.

### Override file
`data/matching_overrides.csv` — manual corrections.
Columns: `sc_player_id`, `skillcorner_name`, `wyscout_name`, `wyscout_team`, `notes`, `updated_at`

To add an override:
1. Find the player's `sc_player_id` from the physical CSV or matching file
2. Add a row to `matching_overrides.csv` with the correct `wyscout_name`
3. The admin page (`pages/admin_matching.py`) provides a UI for this

### Not cached
`load_overrides()` is deliberately not cached — changes apply immediately
without an app restart.

## Physical CSV structure (`physical_l1_l2_2526.csv`)

Key columns used:
- `player_name` — SkillCorner full name
- `player_short_name` — abbreviated name used for Wyscout matching
- `sc_player_id` — SkillCorner unique player ID
- `team_name` — club name
- `competition_name` — league (used for L1/L2 filtering)
- `match_date` — parsed as datetime
- `match_name` — "Home FC v Away FC" format
- `quality_check` — boolean; only `True` rows used in peer building
- `position_group` — SkillCorner position classification
- `group` — position group used for peer filtering
- `minutes_played_per_match` — filter threshold: min 20 for individual, min 450 for season peers

Physical metrics used:
- `dist_per_match`, `hsr_dist_per_match`, `sprint_dist_per_match`
- `count_hsr_per_match`, `count_sprint_per_match`, `count_high_accel_per_match`
- `top_speed_per_match` (PSV99)
- `total_distance_full_all`, `hsr_distance_full_all`, `sprint_distance_full_all`
- `hsr_count_full_all`, `sprint_count_full_all`, `cod_count_full_all`
- `highaccel_count_full_all`, `psv99`, `minutes_full_all`

## Adding a new season's data

1. Replace or supplement the physical CSV with the new season's file
2. Update all file references in `app.py` (`PHYSICAL_CSV`, `WS_FILES`, `MATCHING_CSV`)
3. Re-run the matching process and update `player_matching_l1_l2_2526.csv`
4. Review `matching_overrides.csv` — previous overrides may still be valid
5. Update `CLAUDE.md` with the new season reference
