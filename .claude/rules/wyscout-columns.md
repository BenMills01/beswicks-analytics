# Rule: Wyscout column access

Wyscout exports from the master XLSX files use a mix of named column access
and integer index access. This is intentional — some columns have non-obvious
or duplicated names in the export format.

## Do not change these

The following integer index positions are used throughout `app.py` and
`generate_report.py`. Do not rename, reorder, or insert columns in Wyscout
source files without updating every iloc reference.

| iloc index | What it contains              | Used in                            |
|------------|-------------------------------|------------------------------------|
| 10         | Shots on target               | shots_on_tgt_pct                   |
| 13         | Accurate passes               | pass_acc, pass_acc_pct             |
| 15         | Accurate long passes          | lp_acc                             |
| 17         | Accurate crosses              | cross_acc_pct                      |
| 19         | Successful dribbles           | drib_pct, Drb% match log           |
| 21         | Duels won                     | duel_win, duel_win_pct             |
| 23         | Aerial duels won              | aerial_win                         |
| 31         | Defensive duels               | def_duels_p90, DefDuel log         |
| 32         | Defensive duels won           | def_duel_win, DefD% log            |
| 33         | Loose ball duels              | loose_duels_p90                    |
| 34         | Loose ball duels won          | loose_duel_win                     |
| 35         | Sliding tackles               | slide_tackles_p90                  |
| 36         | Successful sliding tackles    | slide_tackle_pct                   |
| 39         | Yellow cards                  | season totals                      |
| 40         | Red cards                     | season totals                      |
| 42         | Offensive duels               | off_duels_p90                      |
| 43         | Offensive duels won           | off_duel_win                       |
| 48         | Through passes                | through_passes_p90                 |
| 49         | Accurate through passes       | through_pass_acc                   |
| 51         | Second assists                | second_asts_p90                    |
| 53         | Accurate passes to final third| ptf3_acc_pct                       |
| 54         | Passes to penalty area        | ppa_p90                            |
| 55         | Accurate passes to pen. area  | ppa_acc_pct                        |
| 56         | Received passes               | recv_passes_p90                    |
| 57         | Forward passes                | fwd_passes_p90                     |
| 58         | Accurate forward passes       | fwd_pass_acc                       |
| 59         | Back passes                   | back_passes_p90                    |
| 60         | Accurate back passes          | back_pass_acc                      |

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
- `Passes to final third`, `Fouls`, `Fouls suffered`
- `own half`, `opp. half` (loss/recovery location breakdowns)
