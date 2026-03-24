"""
generate_match_report.py
Beswicks Sports Analytics — Single-match PDF report generator.

Layout (A4 portrait):
  Page 1 — Match header + two-column stat breakdown (Wyscout left, Physical right)
            Each stat shown with match value vs season average (▲▼ delta)
"""

import io
from datetime import datetime

from src.metrics import ordinal, p90, pct

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak,
)
from reportlab.lib.colors import HexColor

# ── Brand colours ─────────────────────────────────────────────────────────────
BG       = HexColor('#0f0f0f')
GOLD     = HexColor('#c8a45a')
GOLD_HEX = '#c8a45a'
WHITE    = HexColor('#ffffff')
GREY1    = HexColor('#1a1a1a')
GREY2    = HexColor('#2a2a2a')
GREY3    = HexColor('#666666')
LGREY    = HexColor('#aaaaaa')
GREEN    = HexColor('#4ade80')
YELLOW   = HexColor('#facc15')
RED      = HexColor('#f87171')

W, H   = A4
MARGIN = 18 * mm


def _style(name, **kwargs):
    defaults = dict(fontName='Helvetica', fontSize=9, textColor=LGREY,
                    leading=13, spaceAfter=0, spaceBefore=0)
    defaults.update(kwargs)
    return ParagraphStyle(name, **defaults)


S_TITLE   = _style('mr_title',   fontSize=18, textColor=WHITE, fontName='Helvetica-Bold', leading=22)
S_SECTION = _style('mr_section', fontSize=7,  textColor=GOLD,  fontName='Helvetica-Bold', leading=10,
                   spaceBefore=10, spaceAfter=4, letterSpacing=1.2)
S_BODY    = _style('mr_body',    fontSize=8.5, textColor=LGREY, leading=12)
S_SMALL   = _style('mr_small',   fontSize=7,  textColor=GREY3, leading=10)
S_FOOTER  = _style('mr_footer',  fontSize=7,  textColor=GREY3, alignment=TA_CENTER)


def _draw_background(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(BG)
    canvas.rect(0, 0, W, H, fill=1, stroke=0)
    canvas.setFillColor(GOLD)
    canvas.rect(0, H - 8, W, 8, fill=1, stroke=0)
    canvas.setFillColor(GREY3)
    canvas.setFont('Helvetica', 6.5)
    canvas.drawCentredString(W / 2, 12,
        f"Beswicks Sports Analytics · Internal Use Only · {datetime.now().strftime('%d %b %Y')}")
    canvas.restoreState()


def _delta_para(match_val, season_val, inverse=False):
    """Return a coloured ▲▼ delta Paragraph or '–'."""
    if match_val is None or season_val is None or season_val == 0:
        return Paragraph('–', S_SMALL)
    diff  = match_val - season_val
    better = diff > 0 if not inverse else diff < 0
    if abs(diff) < 0.005:
        col, ar = '#888888', '='
    elif better:
        col, ar = '#4ade80', f'▲ {abs(diff):.2f}'
    else:
        col, ar = '#f87171', f'▼ {abs(diff):.2f}'
    return Paragraph(f'<font color="{col}">{ar}</font>', S_SMALL)


def _stat_table(rows, col_widths):
    """
    Build a dark two-column stat table.
    rows: list of (label, match_val_str, season_val_str, delta_para)
    """
    header = [
        Paragraph('Metric', _style('h', fontSize=7, textColor=GOLD, fontName='Helvetica-Bold', leading=10)),
        Paragraph('Match',  _style('h', fontSize=7, textColor=GOLD, fontName='Helvetica-Bold', leading=10, alignment=TA_CENTER)),
        Paragraph('Season', _style('h', fontSize=7, textColor=GOLD, fontName='Helvetica-Bold', leading=10, alignment=TA_CENTER)),
        Paragraph('Δ',      _style('h', fontSize=7, textColor=GOLD, fontName='Helvetica-Bold', leading=10, alignment=TA_CENTER)),
    ]
    data = [header]
    for label, m_val, s_val, delta in rows:
        data.append([
            Paragraph(label, S_SMALL),
            Paragraph(str(m_val) if m_val is not None else '–', _style('cv', fontSize=8.5, textColor=WHITE, fontName='Helvetica-Bold', leading=12, alignment=TA_CENTER)),
            Paragraph(str(s_val) if s_val is not None else '–', _style('sv', fontSize=8,   textColor=LGREY, leading=12, alignment=TA_CENTER)),
            delta,
        ])
    tbl = Table(data, colWidths=col_widths)
    tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1,  0), GREY1),
        ('ROWBACKGROUNDS',(0, 1), (-1, -1), [GREY1, BG]),
        ('GRID',          (0, 0), (-1, -1), 0.3, GREY2),
        ('LEFTPADDING',   (0, 0), (-1, -1), 5),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 5),
        ('TOPPADDING',    (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN',         (1, 0), (-1, -1), 'CENTER'),
    ]))
    return tbl


def generate_match_report(
    player_name: str,
    club: str,
    pos: str,
    opponent: str,
    match_date: str,
    competition: str,
    minutes: int,
    ws_row,       # single-row pandas Series from Wyscout sheet
    ph_row,       # single-row pandas Series from Physical sheet (or None)
    season: dict,
    phys: dict,   # season physical totals (or None)
    total_matches: int,
    total_mins: int,
) -> bytes:
    """
    Build and return a single-match report as PDF bytes.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN + 6, bottomMargin=MARGIN,
    )

    story = []

    # ── Header ────────────────────────────────────────────────────────────────
    story.append(Paragraph(player_name, S_TITLE))
    story.append(Spacer(1, 4))
    story.append(Paragraph(f'{club} · {pos} · Age N/A', S_SMALL))
    story.append(Spacer(1, 10))

    # Match card (gold-left-border table)
    match_card_data = [[
        Paragraph(f'<b><font color="{GOLD_HEX}">vs {opponent}</font></b>  '
                  f'<font color="#aaaaaa">{match_date} · {competition} · {minutes} mins</font>',
                  _style('mc2', fontSize=10, textColor=WHITE, fontName='Helvetica-Bold', leading=14)),
    ]]
    mc_tbl = Table(match_card_data, colWidths=[W - 2 * MARGIN])
    mc_tbl.setStyle(TableStyle([
        ('BACKGROUND',  (0, 0), (-1, -1), GREY1),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING',(0, 0), (-1, -1), 12),
        ('TOPPADDING',  (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING',(0,0), (-1, -1), 10),
        ('LINEBEFORE',  (0, 0), (0,  -1), 4, GOLD),
        ('ROUNDEDCORNERS', [4]),
    ]))
    story.append(mc_tbl)
    story.append(Spacer(1, 14))

    # ── Helper: safe get from ws_row by name ──────────────────────────────────
    def gws(col):
        try:
            v = ws_row[col]
            import pandas as pd
            return None if pd.isna(v) else float(v)
        except Exception:
            return None

    def gws_i(idx):
        try:
            v = ws_row.iloc[idx]
            import pandas as pd
            return None if pd.isna(v) else float(v)
        except Exception:
            return None

    def gph(col):
        if ph_row is None:
            return None
        try:
            v = ph_row[col]
            import pandas as pd
            return None if pd.isna(v) else float(v)
        except Exception:
            return None

    def fmt(v, decimals=2, suffix=''):
        if v is None:
            return '–'
        return f'{v:.{decimals}f}{suffix}'

    def fmt_int(v):
        if v is None:
            return '–'
        return str(int(v))

    mins_m = minutes if minutes else 90

    # Derived match-level values
    passes_m  = gws('Passes')
    acc_p_m   = gws_i(13)
    acc_pct_m = pct(acc_p_m, passes_m)
    duels_m   = gws('Duels')
    won_m     = gws_i(21)
    duel_w_m  = pct(won_m, duels_m)
    aer_m     = gws('Aerial duels')
    aer_w_m   = gws_i(23)
    aer_pct_m = pct(aer_w_m, aer_m)
    def_d_m   = gws_i(31)
    def_dw_m  = gws_i(32)
    def_dpct_m= pct(def_dw_m, def_d_m)

    # p90 for this match
    def mp90(raw):
        if raw is None or mins_m == 0:
            return None
        return round(raw / mins_m * 90, 2)

    # Build Wyscout rows
    ws_rows = [
        ('Goals',             fmt_int(gws('Goals')),          fmt_int(season.get('goals_raw')),           _delta_para(gws('Goals'),   season.get('goals_raw'))),
        ('Assists',           fmt_int(gws('Assists')),         fmt_int(season.get('assists_raw')),         _delta_para(gws('Assists'), season.get('assists_raw'))),
        ('xG',                fmt(gws('xG')),                  fmt(season.get('xg_p90')),                  _delta_para(gws('xG'),      season.get('xg_p90'))),
        ('xA',                fmt(gws('xA')),                  fmt(season.get('xa_p90')),                  _delta_para(gws('xA'),      season.get('xa_p90'))),
        ('Shot assists',      fmt_int(gws('Shot assists')),    fmt(season.get('shot_asts_p90')),            _delta_para(mp90(gws('Shot assists')), season.get('shot_asts_p90'))),
        ('Passes',            fmt_int(passes_m),              fmt(season.get('passes_p90'), 1),            _delta_para(mp90(passes_m), season.get('passes_p90'))),
        ('Pass acc %',        fmt(acc_pct_m, 1, '%') if acc_pct_m else '–',
                              fmt(season.get('pass_acc'), 1, '%') if season.get('pass_acc') else '–',
                              _delta_para(acc_pct_m, season.get('pass_acc'))),
        ('Dribbles',          fmt_int(gws('Dribbles')),        fmt(season.get('dribbles_p90')),            _delta_para(mp90(gws('Dribbles')), season.get('dribbles_p90'))),
        ('Prog runs',         fmt_int(gws('Progressive runs')),fmt(season.get('prog_runs_p90')),           _delta_para(mp90(gws('Progressive runs')), season.get('prog_runs_p90'))),
        ('Touches in box',    fmt_int(gws('Touches in penalty area')), fmt(season.get('touches_box_p90')), _delta_para(mp90(gws('Touches in penalty area')), season.get('touches_box_p90'))),
        ('Duels',             fmt_int(duels_m),               fmt(season.get('duels_p90'), 1),            _delta_para(mp90(duels_m), season.get('duels_p90'))),
        ('Duel win %',        fmt(duel_w_m, 1, '%') if duel_w_m else '–',
                              fmt(season.get('duel_win'), 1, '%') if season.get('duel_win') else '–',
                              _delta_para(duel_w_m, season.get('duel_win'))),
        ('Aerial duels',      fmt_int(aer_m),                 fmt(season.get('aerial_p90')),              _delta_para(mp90(aer_m), season.get('aerial_p90'))),
        ('Aerial win %',      fmt(aer_pct_m, 1, '%') if aer_pct_m else '–',
                              fmt(season.get('aerial_win'), 1, '%') if season.get('aerial_win') else '–',
                              _delta_para(aer_pct_m, season.get('aerial_win'))),
        ('Def duels',         fmt_int(def_d_m),               fmt(season.get('def_duels_p90')),           _delta_para(mp90(def_d_m), season.get('def_duels_p90'))),
        ('Def duel win %',    fmt(def_dpct_m, 1, '%') if def_dpct_m else '–',
                              fmt(season.get('def_duel_win'), 1, '%') if season.get('def_duel_win') else '–',
                              _delta_para(def_dpct_m, season.get('def_duel_win'))),
        ('Interceptions',     fmt_int(gws('Interceptions')),   fmt(season.get('interceptions_p90')),       _delta_para(mp90(gws('Interceptions')), season.get('interceptions_p90'))),
        ('Recoveries',        fmt_int(gws('Recoveries')),      fmt(season.get('recoveries_p90')),          _delta_para(mp90(gws('Recoveries')), season.get('recoveries_p90'))),
        ('Losses',            fmt_int(gws('Losses')),          fmt(season.get('losses_p90')),              _delta_para(mp90(gws('Losses')), season.get('losses_p90'), inverse=True)),
    ]

    # Build Physical rows
    ph_rows = []
    if ph_row is not None and phys:
        ph_mins = gph('minutes_full_all') or mins_m
        raw_dist  = gph('total_distance_full_all')
        raw_hsr   = gph('hsr_distance_full_all')
        raw_spr   = gph('sprint_distance_full_all')
        raw_psv   = gph('psv99')
        raw_accel = gph('highaccel_count_full_all')

        def p90ph(raw):
            if raw is None or ph_mins == 0:
                return None
            return round(raw / ph_mins * 90, 1)

        ph_rows = [
            ('Total dist p90',  f"{int(p90ph(raw_dist)):,}m" if p90ph(raw_dist) else '–',
                                f"{int(phys.get('total_dist_p90', 0)):,}m",
                                _delta_para(p90ph(raw_dist), phys.get('total_dist_p90'))),
            ('HSR dist p90',    f"{int(p90ph(raw_hsr)):,}m" if p90ph(raw_hsr) else '–',
                                f"{int(phys.get('hsr_dist_p90', 0)):,}m",
                                _delta_para(p90ph(raw_hsr), phys.get('hsr_dist_p90'))),
            ('Sprint dist p90', f"{int(p90ph(raw_spr)):,}m" if p90ph(raw_spr) else '–',
                                f"{int(phys.get('sprint_dist_p90', 0)):,}m",
                                _delta_para(p90ph(raw_spr), phys.get('sprint_dist_p90'))),
            ('PSV99',           fmt(raw_psv, 2) if raw_psv else '–',
                                fmt(phys.get('psv99_avg'), 2),
                                _delta_para(raw_psv, phys.get('psv99_avg'))),
            ('Hi-accel p90',    fmt(p90ph(raw_accel), 1) if p90ph(raw_accel) else '–',
                                fmt(phys.get('hi_accel_p90'), 1),
                                _delta_para(p90ph(raw_accel), phys.get('hi_accel_p90'))),
        ]

    # ── Two-column layout ─────────────────────────────────────────────────────
    usable_w = W - 2 * MARGIN
    gap      = 8
    col_w    = (usable_w - gap) / 2

    # Inner column widths: label | match | season | delta
    cw = [col_w * 0.42, col_w * 0.2, col_w * 0.2, col_w * 0.18]

    ws_section_para = Paragraph('WYSCOUT — THIS MATCH vs SEASON AVG', S_SECTION)
    ws_tbl = _stat_table(ws_rows, cw)

    left_story  = [ws_section_para, ws_tbl]

    if ph_rows:
        ph_section_para = Paragraph('PHYSICAL — THIS MATCH vs SEASON AVG', S_SECTION)
        ph_tbl = _stat_table(ph_rows, cw)
        right_story = [ph_section_para, ph_tbl]
    else:
        right_story = [Paragraph('Physical data not available for this match.', S_SMALL)]

    # Pass lists directly so ReportLab can split tall content across pages
    def _cell(items):
        return items

    two_col = Table(
        [[_cell(left_story), Spacer(gap, 1), _cell(right_story)]],
        colWidths=[col_w, gap, col_w],
    )
    two_col.setStyle(TableStyle([
        ('VALIGN',      (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING',(0, 0), (-1, -1), 0),
        ('TOPPADDING',  (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING',(0,0), (-1, -1), 0),
    ]))
    story.append(two_col)

    story.append(Spacer(1, 14))
    story.append(HRFlowable(width='100%', thickness=0.3, color=GREY2))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f'Season context: {total_matches} appearances · {total_mins:,} mins · 2025/26',
        S_FOOTER,
    ))

    doc.build(story, onFirstPage=_draw_background, onLaterPages=_draw_background)
    return buf.getvalue()
