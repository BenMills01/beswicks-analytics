# Rule: Wyscout column access

Wyscout exports from the master XLSX files use a mix of named column access
and integer index access. This is intentional — some columns have non-obvious
or duplicated names in the export format.

## Do not change these

The following integer index positions are used throughout `app.py` and
`generate_report.py`. Do not rename, reorder, or insert columns in Wyscout
source files without updating every iloc reference.

| iloc index | What it contains          | Used in                      |
|------------|---------------------------|------------------------------|
| 13         | Accurate passes           | pass_acc, pass_acc_pct       |
| 15         | Accurate long passes      | lp_acc                       |
| 19         | Successful dribbles       | drib_pct, Drb% match log     |
| 21         | Duels won                 | duel_win, duel_win_pct       |
| 23         | Aerial duels won          | aerial_win                   |
| 31         | Defensive duels           | def_duels_p90, DefDuel log   |
| 32         | Defensive duels won       | def_duel_win, DefD% log      |
| 39         | Yellow cards              | season totals                |
| 40         | Red cards                 | season totals                |

## When adding a new metric from Wyscout

1. Check if the column has a reliable named header first.
2. If accessing by index, add a comment documenting what the index contains.
3. Verify the index against an actual exported file before shipping.
4. If the column is used in both `get_season_totals()` and `build_match_log()`,
   ensure both use the same access method.

## Named columns that are reliable

These can be accessed by name safely:
- `Minutes played`, `Date`, `Match`, `Competition`, `Position`, `Team`
- `Goals`, `Assists`, `xG`, `xA`, `Shots`
- `Passes`, `Long passes`, `Crosses`, `Dribbles`
- `Aerial duels`, `Duels`, `Interceptions`, `Recoveries`, `Clearances`, `Losses`
- `Shot assists`, `Touches in penalty area`, `Progressive runs`
- `Passes to final third`, `Fouls`
- `own half`, `opp. half` (loss/recovery location breakdowns)
