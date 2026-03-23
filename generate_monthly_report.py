"""
generate_monthly_report.py
Beswicks Sports Analytics — Monthly / date-range form report PDF generator.

Layout (A4 portrait):
  Page 1 — Period header + stat comparison table (period vs season average)
  Page 2 — Form charts (distance p90 bar + duel win % line)
  Page 3 — Match log for the period
"""

import io
import tempfile
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go

from src.metrics import ordinal, p90, pct, build_match_log, rolling_avg

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, Image, PageBreak, KeepTogether,
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


S_TITLE   = _style('mfr_title',   fontSize=18, textColor=WHITE,  fontName='Helvetica-Bold', leading=22)
S_SECTION = _style('mfr_section', fontSize=7,  textColor=GOLD,   fontName='Helvetica-Bold', leading=10,
                   spaceBefore=12, spaceAfter=5, letterSpacing=1.2)
S_BODY    = _style('mfr_body',    fontSize=8.5, textColor=LGREY, leading=12)
S_SMALL   = _style('mfr_small',   fontSize=7,  textColor=GREY3,  leading=10)
S_CENTER  = _style('mfr_center',  fontSize=8,  textColor=LGREY,  leading=12, alignment=TA_CENTER)
S_FOOTER  = _style('mfr_footer',  fontSize=7,  textColor=GREY3,  alignment=TA_CENTER)

_PLOT_BG = '#111111'


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


def _base(title='', h=260):
    return dict(
        title=dict(text=title, font=dict(color='#aaa', size=11), x=0),
        height=h, plot_bgcolor=_PLOT_BG, paper_bgcolor=_PLOT_BG,
        font=dict(color='#aaa', size=10), margin=dict(l=40, r=20, t=36, b=80),
        xaxis=dict(gridcolor='#222', showgrid=False, tickfont=dict(size=8, color='#666'), tickangle=-40),
        yaxis=dict(gridcolor='#222', showgrid=True,  tickfont=dict(size=9,  color='#666'), zeroline=False),
        legend=dict(bgcolor='rgba(0,0,0,0)', font=dict(size=9, color='#888'), orientation='h', y=1.08),
        hovermode=False,
    )


def _fig_to_tmpfile(fig, width=680, height=280):
    data = fig.to_image(format='png', width=width, height=height, scale=2)
    tmp  = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
    tmp.write(data)
    tmp.close()
    return tmp.name


def _build_dist_fig(ph_period):
    """Distance p90 bar chart for the period."""
    ph = ph_period.copy()
    avg = ph['dist_p90_m'].mean()
    fig = go.Figure()
    colours = [GOLD_HEX if v >= avg else '#333333' for v in ph['dist_p90_m']]
    fig.add_bar(x=ph['match_label'], y=ph['dist_p90_m'], marker_color=colours, name='Dist p90')
    fig.add_scatter(x=ph['match_label'], y=[avg] * len(ph), mode='lines',
        name=f'Period avg ({avg:,.0f}m)', line=dict(color=GOLD_HEX, width=1.5, dash='dot'))
    roll = pd.Series(ph['dist_p90_m'].values).rolling(5, min_periods=2).mean()
    fig.add_scatter(x=ph['match_label'], y=roll, mode='lines',
        name='Rolling avg', line=dict(color='#a78bfa', width=2))
    fig.update_layout(**_base('Total distance per 90 — period'))
    return fig


def _build_duel_fig(ws_period):
    """Duel win % line chart for the period."""
    ws = ws_period.copy()
    fig = go.Figure()
    fig.add_scatter(x=ws['match_label'], y=ws['duel_win_pct'], mode='lines+markers',
        name='All duel win %', line=dict(color='#3b82f6', width=2), marker=dict(size=4))
    fig.add_scatter(x=ws['match_label'], y=ws['def_duel_win_pct'], mode='lines+markers',
        name='Def duel win %', line=dict(color='#f87171', width=2, dash='dot'), marker=dict(size=4))
    roll = pd.Series(ws['duel_win_pct'].values).rolling(5, min_periods=2).mean()
    fig.add_scatter(x=ws['match_label'], y=roll, mode='lines',
        name='Rolling avg', line=dict(color='#a78bfa', width=2))
    fig.add_scatter(x=ws['match_label'], y=[50] * len(ws), mode='lines',
        name='50%', line=dict(color='#444', width=1, dash='dash'))
    fig.update_layout(**_base('Duel win % — period'))
    fig.update_yaxes(range=[0, 110])
    return fig


def _delta_cell(period_val, season_val, inverse=False, format_spec='.2f'):
    """Return a coloured delta Paragraph."""
    if period_val is None or season_val is None:
        return Paragraph('–', S_SMALL)
    diff   = period_val - season_val
    better = diff > 0 if not inverse else diff < 0
    if abs(diff) < 0.005:
        return Paragraph('<font color="#888888">=</font>', S_SMALL)
    col = '#4ade80' if better else '#f87171'
    ar  = '▲' if diff > 0 else '▼'
    return Paragraph(f'<font color="{col}">{ar} {abs(diff):{format_spec}}</font>', S_SMALL)


def _comparison_table(period: dict, season: dict, period_phys, season_phys, usable_w):
    """Two-section stat comparison table: period vs season average."""
    cw = [usable_w * 0.38, usable_w * 0.18, usable_w * 0.18, usable_w * 0.13, usable_w * 0.13]

    header = [
        Paragraph('Metric',        _style('ch', fontSize=7, textColor=GOLD, fontName='Helvetica-Bold', leading=10)),
        Paragraph('Period',        _style('ch', fontSize=7, textColor=GOLD, fontName='Helvetica-Bold', leading=10, alignment=TA_CENTER)),
        Paragraph('Season avg',    _style('ch', fontSize=7, textColor=GOLD, fontName='Helvetica-Bold', leading=10, alignment=TA_CENTER)),
        Paragraph('Δ',             _style('ch', fontSize=7, textColor=GOLD, fontName='Helvetica-Bold', leading=10, alignment=TA_CENTER)),
        Paragraph('',              S_SMALL),
    ]

    def row(label, p_val, s_val, fmt='.2f', inverse=False, suffix=''):
        p_str = f'{p_val:{fmt}}{suffix}' if p_val is not None else '–'
        s_str = f'{s_val:{fmt}}{suffix}' if s_val is not None else '–'
        return [
            Paragraph(label, S_SMALL),
            Paragraph(p_str, _style('pv', fontSize=8.5, textColor=WHITE, fontName='Helvetica-Bold', leading=12, alignment=TA_CENTER)),
            Paragraph(s_str, _style('sv', fontSize=8,   textColor=LGREY, leading=12, alignment=TA_CENTER)),
            _delta_cell(p_val, s_val, inverse, fmt.replace('%', '.1f')),
            Paragraph('', S_SMALL),
        ]

    def section_row(label):
        return [Paragraph(label, _style('sr', fontSize=7, textColor=GOLD, fontName='Helvetica-Bold',
                          leading=10, letterSpacing=1.0)),
                Paragraph('', S_SMALL), Paragraph('', S_SMALL), Paragraph('', S_SMALL), Paragraph('', S_SMALL)]

    data = [header]

    data.append(section_row('ATTACKING'))
    data.append(row('Goals p90',      period.get('goals_p90'),       season.get('goals_p90')))
    data.append(row('Assists p90',    period.get('assists_p90'),      season.get('assists_p90')))
    data.append(row('xG p90',         period.get('xg_p90'),           season.get('xg_p90')))
    data.append(row('xA p90',         period.get('xa_p90'),           season.get('xa_p90')))
    data.append(row('Shot asts p90',  period.get('shot_asts_p90'),    season.get('shot_asts_p90')))
    data.append(row('Dribbles p90',   period.get('dribbles_p90'),     season.get('dribbles_p90')))
    data.append(row('Prog runs p90',  period.get('prog_runs_p90'),    season.get('prog_runs_p90')))

    data.append(section_row('PASSING'))
    data.append(row('Passes p90',     period.get('passes_p90'),       season.get('passes_p90'),    '.1f'))
    data.append(row('Pass acc %',     period.get('pass_acc'),         season.get('pass_acc'),      '.1f', suffix='%'))
    data.append(row('Long pass p90',  period.get('long_passes_p90'),  season.get('long_passes_p90')))
    data.append(row('Crosses p90',    period.get('crosses_p90'),      season.get('crosses_p90')))

    data.append(section_row('DUELS & DEFENSIVE'))
    data.append(row('Duels p90',      period.get('duels_p90'),        season.get('duels_p90'),     '.1f'))
    data.append(row('Duel win %',     period.get('duel_win'),         season.get('duel_win'),      '.1f', suffix='%'))
    data.append(row('Aerial p90',     period.get('aerial_p90'),       season.get('aerial_p90')))
    data.append(row('Aerial win %',   period.get('aerial_win'),       season.get('aerial_win'),    '.1f', suffix='%'))
    data.append(row('Def duels p90',  period.get('def_duels_p90'),    season.get('def_duels_p90')))
    data.append(row('Def duel win %', period.get('def_duel_win'),     season.get('def_duel_win'),  '.1f', suffix='%'))
    data.append(row('Interceptions',  period.get('interceptions_p90'),season.get('interceptions_p90')))
    data.append(row('Recoveries p90', period.get('recoveries_p90'),   season.get('recoveries_p90')))
    data.append(row('Losses p90',     period.get('losses_p90'),       season.get('losses_p90'),    '.2f', inverse=True))

    if period_phys and season_phys:
        data.append(section_row('PHYSICAL'))
        data.append(row('Total dist p90',  period_phys.get('total_dist_p90'),  season_phys.get('total_dist_p90'),  '.0f', suffix='m'))
        data.append(row('HSR dist p90',    period_phys.get('hsr_dist_p90'),    season_phys.get('hsr_dist_p90'),    '.0f', suffix='m'))
        data.append(row('Sprint dist p90', period_phys.get('sprint_dist_p90'), season_phys.get('sprint_dist_p90'), '.0f', suffix='m'))
        data.append(row('PSV99 avg',       period_phys.get('psv99_avg'),       season_phys.get('psv99_avg')))

    tbl = Table(data, colWidths=cw)
    section_indices = [i for i, r in enumerate(data) if r[1] == Paragraph('', S_SMALL) and i > 0
                       and isinstance(r[0], Paragraph) and r[0].style.name == 'sr']

    style_cmds = [
        ('BACKGROUND',    (0, 0), (-1,  0), GREY1),
        ('ROWBACKGROUNDS',(0, 1), (-1, -1), [GREY1, BG]),
        ('GRID',          (0, 0), (-1, -1), 0.3, GREY2),
        ('LEFTPADDING',   (0, 0), (-1, -1), 5),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 5),
        ('TOPPADDING',    (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('SPAN',          (0, 0), (-1,  0), ),   # header spans all — handled by TableStyle
    ]
    for si in section_indices:
        style_cmds += [
            ('BACKGROUND', (0, si), (-1, si), HexColor('#111111')),
            ('SPAN',       (0, si), (-1, si)),
            ('TOPPADDING', (0, si), (-1, si), 6),
        ]
    tbl.setStyle(TableStyle(style_cmds))
    return tbl


def generate_monthly_report(
    player_name: str,
    club: str,
    pos: str,
    date_from: str,
    date_to: str,
    ws_period,          # filtered Wyscout DataFrame for the period
    ph_period,          # filtered Physical DataFrame for the period (or None)
    period_stats: dict,
    period_phys: dict,
    season_stats: dict,
    season_phys: dict,
    team_name: str,
) -> bytes:
    """
    Build and return a monthly / date-range form report as PDF bytes.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN + 6, bottomMargin=MARGIN,
    )

    usable_w = W - 2 * MARGIN
    story    = []
    tmpfiles = []

    # ── Page 1: Header + comparison table ─────────────────────────────────────
    story.append(Paragraph(player_name, S_TITLE))
    story.append(Spacer(1, 4))
    story.append(Paragraph(f'{club} · {pos} · 2025/26 Season', S_SMALL))
    story.append(Spacer(1, 12))

    # Period tag bar
    n_matches = int(period_stats.get('matches', 0))
    n_mins    = int(period_stats.get('mins', 0))
    goals_r   = int(period_stats.get('goals_raw', 0))
    assists_r = int(period_stats.get('assists_raw', 0))

    tags = [
        (f'Form Report: {date_from} – {date_to}', True),
        (f'{n_matches} matches', False),
        (f'{n_mins:,} mins',    False),
        (f'{goals_r}G · {assists_r}A', False),
    ]
    tag_data = [[Paragraph(t, _style('tag', fontSize=7.5, textColor=(WHITE if gold else LGREY),
                            fontName='Helvetica-Bold' if gold else 'Helvetica', leading=11))
                 for t, gold in tags]]
    tag_tbl = Table(tag_data, colWidths=[usable_w * f for f in [0.38, 0.18, 0.18, 0.26]])
    tag_tbl.setStyle(TableStyle([
        ('BACKGROUND',   (0, 0), (0,  0), HexColor('#2a2010')),
        ('BACKGROUND',   (1, 0), (-1, 0), GREY1),
        ('LEFTPADDING',  (0, 0), (-1, 0), 8),
        ('RIGHTPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING',   (0, 0), (-1, 0), 6),
        ('BOTTOMPADDING',(0, 0), (-1, 0), 6),
        ('LINEBEFORE',   (0, 0), (0,  0), 4, GOLD),
    ]))
    story.append(tag_tbl)
    story.append(Spacer(1, 14))

    story.append(Paragraph('PERIOD vs SEASON AVERAGE', S_SECTION))
    story.append(_comparison_table(period_stats, season_stats, period_phys, season_phys, usable_w))

    # ── Page 2: Form charts ────────────────────────────────────────────────────
    story.append(PageBreak())
    story.append(Paragraph('FORM CHARTS — PERIOD', S_SECTION))

    # Derive match_label + per-match columns needed for charts
    if len(ws_period) >= 2:
        ws_chart = ws_period.copy()
        ws_chart['match_label'] = ws_chart.apply(
            lambda r: f"{str(r.get('Match', r.get('match_label', '?')))[:20]}", axis=1
        )
        ws_chart['duel_win_pct'] = ws_chart.apply(
            lambda r: (float(r.iloc[21]) / float(r['Duels']) * 100
                       if float(r['Duels']) > 0 else None)
            if r['Duels'] and float(r['Duels']) > 0 else None, axis=1
        )
        ws_chart['def_duel_win_pct'] = ws_chart.apply(
            lambda r: (float(r.iloc[32]) / float(r.iloc[31]) * 100
                       if r.iloc[31] and float(r.iloc[31]) > 0 else None), axis=1
        )

        try:
            fig_duel = _build_duel_fig(ws_chart)
            tmp = _fig_to_tmpfile(fig_duel, width=680, height=260)
            tmpfiles.append(tmp)
            story.append(Image(tmp, width=usable_w, height=usable_w * 260 / 680))
            story.append(Spacer(1, 10))
        except Exception:
            pass

    if ph_period is not None and len(ph_period) >= 2:
        ph_chart = ph_period.copy()
        ph_chart['match_label'] = ph_chart.apply(
            lambda r: str(r.get('match_name', ''))[:20], axis=1
        )
        ph_chart['dist_p90_m'] = ph_chart.apply(
            lambda r: (float(r['total_distance_full_all']) / float(r['minutes_full_all']) * 90
                       if r['minutes_full_all'] and float(r['minutes_full_all']) > 0 else None), axis=1
        )

        try:
            fig_dist = _build_dist_fig(ph_chart)
            tmp = _fig_to_tmpfile(fig_dist, width=680, height=260)
            tmpfiles.append(tmp)
            story.append(Image(tmp, width=usable_w, height=usable_w * 260 / 680))
        except Exception:
            pass

    if len(ws_period) < 2 and (ph_period is None or len(ph_period) < 2):
        story.append(Paragraph('Fewer than 2 matches in period — charts not available.', S_SMALL))

    # ── Page 3: Match log ──────────────────────────────────────────────────────
    story.append(PageBreak())
    story.append(Paragraph('MATCH LOG — PERIOD', S_SECTION))

    match_log = build_match_log(ws_period, team_name)
    if len(match_log) == 0:
        story.append(Paragraph('No qualifying matches in this period.', S_SMALL))
    else:
        log_cols  = ['Match', 'Date', 'Min', 'G', 'A', 'xG', 'xA', 'Pass%', 'Duel%', 'Aer%', 'Int', 'Loss']
        log_cols  = [c for c in log_cols if c in match_log.columns]
        log_data  = [[Paragraph(c, _style('lh', fontSize=7, textColor=GOLD, fontName='Helvetica-Bold', leading=10))
                      for c in log_cols]]
        for _, r in match_log.iloc[::-1].iterrows():
            log_data.append([Paragraph(str(r.get(c, '–')), S_SMALL) for c in log_cols])

        cw_log = [usable_w * f for f in [0.24, 0.09, 0.07, 0.05, 0.05, 0.07, 0.07, 0.09, 0.09, 0.09, 0.07, 0.07]]
        cw_log = cw_log[:len(log_cols)]
        total  = sum(cw_log)
        if total > 0:
            cw_log = [w / total * usable_w for w in cw_log]

        log_tbl = Table(log_data, colWidths=cw_log)
        log_tbl.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1,  0), GREY1),
            ('ROWBACKGROUNDS',(0, 1), (-1, -1), [GREY1, BG]),
            ('GRID',          (0, 0), (-1, -1), 0.3, GREY2),
            ('LEFTPADDING',   (0, 0), (-1, -1), 4),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
            ('TOPPADDING',    (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(log_tbl)

    doc.build(story, onFirstPage=_draw_background, onLaterPages=_draw_background)

    # Clean up temp files
    import os
    for t in tmpfiles:
        try:
            os.unlink(t)
        except Exception:
            pass

    return buf.getvalue()
