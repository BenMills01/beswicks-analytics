# /project:new-chart

Add a new Plotly chart to the Beswicks analytics dashboard.

## What to do

1. Confirm which data source the chart uses: Wyscout, Physical, Pressing, or Off_Ball_Runs.
2. Confirm which section of `app.py` it belongs to:
   - Seasonal metrics (top of page)
   - Physical output (match-by-match tabs)
   - Form trends (Wyscout match-by-match tabs)
   - Match log (table section)
3. Build the chart following the conventions below.
4. Wrap it in a new tab if there are already multiple charts in that section.

## Chart conventions — always follow these

- Dark theme: `plot_bgcolor=PLOT_BG`, `paper_bgcolor=PAPER_BG` (`'#0f0f0f'`)
- Use `base_layout()` helper for all layout defaults
- Bar opacity must encode minutes played — use `mins_to_opacity()` and `colour_list()`
- Rolling average line: purple (`PURPLE = '#a78bfa'`), width=2, window=5, min_periods=3
- Player season average: dashed gold line (`GOLD = '#c8a45a'`), width=1.5
- Position peer average: dashed grey line (`'#888'`), width=1.5
- No gridlines on x-axis (`showgrid=False`)
- All hover templates must include minutes played in `customdata`
- Chart height: 320px for standard, 340px for dual-axis, 460px for radar
- Never hardcode a player's name — use `name` variable from sidebar resolution

## Dual-axis charts

Use `make_subplots(specs=[[{"secondary_y": True}]])`.
Right axis should have `showgrid=False` and a short `title_text`.

## Adding to PDF report

If the chart should also appear in PDF exports, add a matching Plotly figure
in `generate_report.py` using the same data and export it via Kaleido.
Keep PDF chart colours consistent with the dashboard (same hex values).
