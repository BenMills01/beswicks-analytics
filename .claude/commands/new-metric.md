# /project:new-metric

Add a new metric card or percentile ranking to the Beswicks dashboard.

## What to do

1. Confirm the data source: Wyscout sheet, Physical sheet, Pressing sheet, or Off_Ball_Runs sheet.
2. Confirm whether it should appear in the seasonal metrics section, the peer
   comparison section, or the radar chart.
3. Add the metric following the rules below.

## Metric expression rules

- Rate stats: always per 90 minutes using the `p90(value, minutes)` helper
- Percentages: use `pct(numerator, denominator)` helper
- Raw totals: goals, assists, appearances, cards only
- Always include sample size context in the `sub` field of `metric_card()`

## Adding to seasonal totals

Add the calculation to `get_season_totals()` or `get_physical_totals()` in `app.py`.
Follow the existing pattern: `'key': p90(source_column_sum, mins)`.

## Adding to peer comparison

1. Add the peer series to `build_wyscout_peers()` or `build_physical_peers()`.
2. Map the column name from the position-specific XLSX files — check an actual
   file to confirm the exact column header before adding it.
3. Add to the `gp()` or `gpp()` lambda calls in the metrics section.

## Adding to the metric card display

Use `metric_card(label, value, sub, vcls, pct_val, peer_n)`:
- `vcls`: `'mc-good'` (green), `'mc-warn'` (yellow), `'mc-bad'` (red), or `''`
- `pct_val`: percentile (0–100) or None if no peer data
- `peer_n`: number of peers in the comparison group

Wrap cards in `metric_row([...])` and render with `st.markdown(..., unsafe_allow_html=True)`.

## Adding to the radar chart

Add a tuple to `radar_keys` in the radar section:
`('Display Label', 'metric_key', is_inverse_metric)`

Set `is_inverse_metric=True` for metrics where lower is better (e.g. losses).

## Adding a metric description

Add to the `METRIC_DESC` dict at the top of `app.py`:
`"Label": "One sentence explaining what this measures and why it matters."`

## Wyscout column index warning

If the metric uses a Wyscout column accessed by iloc index (not name), document
the index and what it contains in a comment next to the iloc call. Do not change
existing index references.
