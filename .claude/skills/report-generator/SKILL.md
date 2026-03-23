# Skill: report-generator

Auto-invoked when: generating a PDF report, adding a new report type,
or modifying `generate_report.py`.

## What this skill does

Produces or modifies the Beswicks branded PDF report using ReportLab.
The report is dark-themed (matching the dashboard), A4 portrait, and
exported from `generate_report.py` which is called from `app.py`.

## Report structure

Page 1: Player profile header + season metrics table
Page 2: Radar chart (Plotly → Kaleido → PNG) + physical output table
Page 3: Form trend charts (Plotly → Kaleido → PNG)
Page 4: Match log table

## Brand colours (use these hex values exactly)

- Background: `#0f0f0f`
- Gold accent: `#c8a45a`
- White text: `#ffffff`
- Grey text: `#aaaaaa`
- Green highlight: `#4ade80`
- Yellow highlight: `#facc15`
- Red highlight: `#f87171`
- Blue: `#3b82f6`

## Key patterns

### Chart export via Kaleido
```python
import tempfile
fig.write_image(tmp_path, format='png', width=700, height=350, scale=2)
img = Image(tmp_path, width=..., height=...)
```

Always write to a tempfile, not a fixed path — the app may run in read-only environments.

### Table styling
Use ReportLab `TableStyle` with `BACKGROUND`, `TEXTCOLOR`, `FONTNAME`, `FONTSIZE`,
`GRID`, `ROWBACKGROUNDS`. Alternate row colours: `#1a1a1a` and `#141414`.
Header rows: gold background (`#c8a45a`), black text (`#0f0f0f`), Helvetica-Bold.

### Percentile colour coding in tables
Use `pct_colour()` which returns a ReportLab `HexColor`:
- >= 80th: green (`#4ade80`)
- >= 55th: light green (`#86efac`)
- >= 35th: yellow (`#facc15`)
- < 35th: red (`#f87171`)

### Page margins
```python
MARGIN = 18 * mm  # ~51 pts
```
Content width: `W - 2 * MARGIN` (approximately 493 pts for A4)

## Adding a new report page

1. Create a function that returns a list of ReportLab flowables
2. Add it to the main `generate_pdf()` function's story list
3. Insert a `PageBreak()` before the new page
4. Add the corresponding Plotly figure if charts are needed

## Rules

- Never hardcode player data in the report generator — everything comes from
  the `season`, `phys`, `ws`, `ph` arguments passed from `app.py`
- If Kaleido is unavailable, the `generate_pdf` import fails gracefully and
  `PDF_AVAILABLE = False` is set — always handle this in `app.py`
- Keep chart dimensions consistent with the dashboard where possible
- All text in the PDF should match dashboard metric labels exactly
