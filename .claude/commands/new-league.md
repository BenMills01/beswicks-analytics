# /project:new-league

Add a new league's data to the Beswicks platform.

## What to do

1. Confirm the league name (used as the key throughout — must match exactly).
2. Confirm which position-specific XLSX files are available.
3. Follow the steps below to wire everything in.

## Steps

### 1. Add data files to `data/`

Name files consistently:
- `{League Name} min {X} mins.xlsx` — all players with minimum minutes
- `{League Name} Central Defenders.xlsx`
- `{League Name} Full Back:Wing Back.xlsx`
- `{League Name} Central Midfielders.xlsx`
- `{League Name} Attacking Midfielders.xlsx`
- `{League Name} Wide Midfielders.xlsx`
- `{League Name} CFs.xlsx`
- `{League Name} GKs.xlsx`

### 2. Add to `WS_FILES` in `app.py`

```python
WS_FILES = {
    'League One': { ... },
    'League Two': { ... },
    'New League Name': {
        'all':              os.path.join(DATA_DIR, "New League Name min X mins.xlsx"),
        'Central Defender': os.path.join(DATA_DIR, "New League Name Central Defenders.xlsx"),
        ...
    },
}
```

### 3. Update the league filter in the sidebar

Add the new league to the `peer_league` radio options.

### 4. Update physical data filtering

In `build_physical_peers()`, add the new league's competition name string
to the `str.contains()` filter logic.

### 5. Cross-league comparisons

If clients will be compared across leagues, always prompt for a difficulty
multiplier before running any comparison. Never estimate it.
Document the multiplier used in any output.

## Rules

- League name string must be identical everywhere it appears (dict key, file names, filter strings)
- Never assume a cross-league multiplier — always ask
