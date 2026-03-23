# /project:add-client

Add a new client to the Beswicks analytics platform.

## What to do

1. Ask for: full name, position, current club, current league, age.
2. Create the master file at `data/players/{First}_{Last}_master.xlsx` with these five sheets:
   - `Wyscout` — match-by-match Wyscout export
   - `Physical` — SkillCorner match-level physical data
   - `Pressing` — SkillCorner under-pressure passing
   - `Off_Ball_Runs` — SkillCorner off-ball run data
   - `Match_by_Match` — aggregated match log
3. Confirm the player's Wyscout short name and check whether they appear in any
   position-specific peer file in `data/`. If not, flag it.
4. Check `data/player_matching_l1_l2_2526.csv` for their SkillCorner ID.
   If match confidence is below 0.85, add a manual override to `data/matching_overrides.csv`.
5. Update the client list in `CLAUDE.md` under the Clients section.

## Rules

- Never proceed without a full profile (name, position, club, league, age).
- Never hardcode the client's name anywhere in app logic — the app discovers
  clients by scanning `data/players/` for `*_master.xlsx` files.
- Sheet names must match exactly: `Wyscout`, `Physical`, `Pressing`, `Off_Ball_Runs`, `Match_by_Match`.
