# Rule: Metric standards

All metric calculations must follow these standards to ensure consistency
across the dashboard, PDF reports, and any future outputs.

## Per-90 calculation

Always use the `p90(value, minutes)` helper:
```python
def p90(value, minutes):
    if minutes == 0: return 0.0
    return round((value / minutes) * 90, 2)
```

Never calculate per-90 inline with a different rounding approach.

## Percentage calculation

Always use the `pct(num, denom)` helper:
```python
def pct(num, denom):
    if denom == 0: return None
    return round((num / denom) * 100, 1)
```

Returns `None` on zero denominator — handle this in display logic.

## Percentile ranking

Always use `scipy_stats.percentileofscore(series, value, kind='rank')`.
For inverse metrics (lower = better, e.g. losses), pass `inverse=True` to
`percentile_rank()` which computes `100 - rank`.

Minimum peer group size before showing a percentile: **5 players**.

## Sample size

Always state sample size at the top of any analysis section:
- Minutes played (sum across all appearances in the filtered dataset)
- Number of matches included

## What gets per-90 treatment

Rate stats (per-90): passes, dribbles, duels, interceptions, recoveries,
clearances, losses, crosses, shots, shot assists, progressive runs, touches
in box, xG, xA, distances, sprint counts, accelerations.

Raw totals only: goals, assists, appearances, yellow cards, red cards.

Lead with per-90; show raw in brackets where both are relevant.

## Cross-league multipliers

If a multiplier is applied, it must be:
1. Provided explicitly by the user — never estimated
2. Documented clearly in any output that uses adjusted figures
3. Applied consistently to both the client's stats and comparison player's stats

Never silently apply or remove a multiplier.
