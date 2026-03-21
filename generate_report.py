"""
generate_report.py
Beswicks Sports Analytics — PDF report generator.
Called from app.py; returns bytes of a complete PDF report.

Layout (A4 portrait):
  Page 1 — Player profile header + season metrics table
  Page 2 — Radar chart + physical output table
  Page 3 — Form trend charts (physical + Wyscout)
  Page 4 — Match log table
"""

import io
import tempfile
import os
from datetime import datetime

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
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
BLUE     = HexColor('#3b82f6')
PURPLE   = HexColor('#a78bfa')

W, H = A4  # 595 x 842 pts
MARGIN = 18 * mm

# ── Styles ────────────────────────────────────────────────────────────────────
def _style(name, **kwargs):
    defaults = dict(fontName='Helvetica', fontSize=9, textColor=LGREY,
                    leading=13, spaceAfter=0, spaceBefore=0)
    defaults.update(kwargs)
    return ParagraphStyle(name, **defaults)

S_TITLE   = _style('title',   fontSize=20, textColor=WHITE,  fontName='Helvetica-Bold', leading=24, spaceAfter=4)
S_CLUB    = _style('club',    fontSize=11, textColor=LGREY,  leading=15)
S_SECTION = _style('section', fontSize=7,  textColor=GOLD,   fontName='Helvetica-Bold', leading=10,
                   spaceBefore=14, spaceAfter=6, letterSpacing=1.2)
S_BODY    = _style('body',    fontSize=8.5,textColor=LGREY,  leading=12)
S_SMALL   = _style('small',   fontSize=7,  textColor=GREY3,  leading=10)
S_TAG     = _style('tag',     fontSize=7.5,textColor=WHITE,  fontName='Helvetica-Bold', leading=11)
S_FOOTER  = _style('footer',  fontSize=7,  textColor=GREY3,  alignment=TA_CENTER)

# ── Colour helpers ────────────────────────────────────────────────────────────
def pct_colour(pct_val):
    if pct_val is None: return GREY3
    if pct_val >= 80:   return GREEN
    if pct_val >= 55:   return HexColor('#86efac')
    if pct_val >= 35:   return YELLOW
    return RED

def ordinal(n):
    n = int(n); s = str(n)
    if s.endswith(('11','12','13')): return f"{n}th"
    if s.endswith('1'): return f"{n}st"
    if s.endswith('2'): return f"{n}nd"
    if s.endswith('3'): return f"{n}rd"
    return f"{n}th"

# ── Chart → PNG bytes (via kaleido) ──────────────────────────────────────────
def fig_to_bytes(fig, width=700, height=320):
    """Export a Plotly figure to PNG bytes."""
    return fig.to_image(format='png', width=width, height=height, scale=2)

def fig_to_tmpfile(fig, width=700, height=320):
    """Write figure to a temp PNG file and return the path."""
    data = fig_to_bytes(fig, width, height)
    tmp  = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
    tmp.write(data)
    tmp.close()
    return tmp.name

# ── Chart builders (dark theme, export-friendly) ──────────────────────────────
_PLOT_BG = '#111111'

def _base(title='', h=280):
    return dict(
        title=dict(text=title, font=dict(color='#aaa', size=11), x=0),
        height=h, plot_bgcolor=_PLOT_BG, paper_bgcolor=_PLOT_BG,
        font=dict(color='#aaa', size=10), margin=dict(l=40, r=20, t=36, b=80),
        xaxis=dict(gridcolor='#222', showgrid=False, tickfont=dict(size=8, color='#666'), tickangle=-40),
        yaxis=dict(gridcolor='#222', showgrid=True,  tickfont=dict(size=9,  color='#666'), zeroline=False),
        legend=dict(bgcolor='rgba(0,0,0,0)', font=dict(size=9, color='#888'), orientation='h', y=1.08),
        hovermode=False,
    )

def build_radar_fig(radar_data, player_name):
    labels = list(radar_data.keys())
    values = list(radar_data.values())
    lc = labels + [labels[0]]; vc = values + [values[0]]
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(r=vc, theta=lc, fill='toself',
        fillcolor='rgba(200,164,90,0.18)', line=dict(color=GOLD_HEX, width=2), name=player_name))
    fig.add_trace(go.Scatterpolar(r=[50]*len(lc), theta=lc, mode='lines',
        line=dict(color='#444', width=1, dash='dot'), name='Avg (50th)'))
    fig.update_layout(
        polar=dict(bgcolor=_PLOT_BG,
            radialaxis=dict(visible=True, range=[0,100], tickfont=dict(size=8, color='#555'),
                gridcolor='#2a2a2a', linecolor='#333'),
            angularaxis=dict(tickfont=dict(size=9, color='#aaa'), gridcolor='#2a2a2a', linecolor='#333')),
        paper_bgcolor=_PLOT_BG, showlegend=True,
        legend=dict(bgcolor='rgba(0,0,0,0)', font=dict(color='#888', size=9)),
        height=380, width=480, margin=dict(l=50, r=50, t=30, b=30),
    )
    return fig

def build_dist_fig(ph, phys_peers):
    from generate_report import _base
    ph = ph.copy()
    avg_dist = ph['dist_p90_m'].mean()
    fig = go.Figure()
    bar_cols = [GOLD_HEX if v >= avg_dist else '#333' for v in ph['dist_p90_m']]
    fig.add_bar(x=ph['match_label'], y=ph['dist_p90_m'], marker_color=bar_cols, name='Dist p90')
    fig.add_scatter(x=ph['match_label'], y=[avg_dist]*len(ph), mode='lines',
        name=f'Avg ({avg_dist:,.0f}m)', line=dict(color=GOLD_HEX, width=1.5, dash='dot'))
    import pandas as pd
    roll = pd.Series(ph['dist_p90_m'].values).rolling(5, min_periods=3).mean()
    fig.add_scatter(x=ph['match_label'], y=roll, mode='lines',
        name='5-match rolling avg', line=dict(color='#a78bfa', width=2))
    if 'total_dist_p90' in phys_peers:
        la = phys_peers['total_dist_p90'].mean()
        fig.add_scatter(x=ph['match_label'], y=[la]*len(ph), mode='lines',
            name=f'Position avg ({la:,.0f}m)', line=dict(color='#888', width=1.5, dash='dash'))
    fig.update_layout(**_base('Total distance per 90 (m)', h=260))
    fig.update_yaxes(range=[8000, ph['dist_p90_m'].max()*1.1])
    return fig

def build_duel_fig(ws, ws_peers):
    import pandas as pd
    fig = go.Figure()
    fig.add_scatter(x=ws['match_label'], y=ws['duel_win_pct'], mode='lines+markers',
        name='All duel win %', line=dict(color='#3b82f6', width=2), marker=dict(size=4))
    fig.add_scatter(x=ws['match_label'], y=ws['def_duel_win_pct'], mode='lines+markers',
        name='Def duel win %', line=dict(color='#f87171', width=2, dash='dot'), marker=dict(size=4))
    roll = pd.Series(ws['duel_win_pct'].values).rolling(5, min_periods=3).mean()
    fig.add_scatter(x=ws['match_label'], y=roll, mode='lines',
        name='Duel win rolling avg', line=dict(color='#a78bfa', width=2))
    fig.add_scatter(x=ws['match_label'], y=[50]*len(ws), mode='lines',
        name='50%', line=dict(color='#444', width=1, dash='dash'))
    if 'duel_win' in ws_peers:
        pavg = ws_peers['duel_win'].mean()
        fig.add_scatter(x=ws['match_label'], y=[pavg]*len(ws), mode='lines',
            name=f'Position avg ({pavg:.0f}%)', line=dict(color='#888', width=1.5, dash='dash'))
    fig.update_layout(**_base('Duel win % per match', h=240))
    fig.update_yaxes(range=[0, 110])
    return fig

# ── ReportLab table helpers ───────────────────────────────────────────────────
def dark_table(data, col_widths, row_heights=None, header=True):
    """Build a dark-themed ReportLab table."""
    tbl = Table(data, colWidths=col_widths, rowHeights=row_heights)
    style = [
        ('BACKGROUND',  (0,0), (-1,0 if header else -1), GREY1),
        ('TEXTCOLOR',   (0,0), (-1,-1), LGREY),
        ('FONTNAME',    (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE',    (0,0), (-1,-1), 7.5),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[GREY1, BG]),
        ('GRID',        (0,0), (-1,-1), 0.3, GREY2),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING',(0,0), (-1,-1), 5),
        ('TOPPADDING',  (0,0), (-1,-1), 4),
        ('BOTTOMPADDING',(0,0),(-1,-1), 4),
        ('VALIGN',      (0,0), (-1,-1), 'MIDDLE'),
    ]
    if header:
        style += [
            ('FONTNAME',  (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE',  (0,0), (-1,0), 7),
            ('TEXTCOLOR', (0,0), (-1,0), GOLD),
            ('BACKGROUND',(0,0), (-1,0), HexColor('#1a1a1a')),
        ]
    tbl.setStyle(TableStyle(style))
    return tbl

def pct_cell(value, pct_val=None):
    """A table cell with optional coloured percentile."""
    if value is None or value == '–': return Paragraph('–', S_SMALL)
    txt = str(value)
    if pct_val is not None:
        c   = pct_colour(pct_val)
        hex_c = c.hexval() if hasattr(c,'hexval') else GOLD_HEX
        # Convert HexColor to hex string
        if hasattr(c, 'red'):
            hex_c = '#{:02x}{:02x}{:02x}'.format(int(c.red*255), int(c.green*255), int(c.blue*255))
        txt += f' <font color="{hex_c}" size="6"> {ordinal(pct_val)}</font>'
    return Paragraph(txt, S_BODY)

# ── Page background ───────────────────────────────────────────────────────────
def _draw_background(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(BG)
    canvas.rect(0, 0, W, H, fill=1, stroke=0)
    # Gold top bar
    canvas.setFillColor(GOLD)
    canvas.rect(0, H - 8, W, 8, fill=1, stroke=0)
    # Footer
    canvas.setFillColor(GREY3)
    canvas.setFont('Helvetica', 6.5)
    canvas.drawCentredString(W/2, 12, f"Beswicks Sports Analytics · Internal Use Only · {datetime.now().strftime('%d %b %Y')}")
    canvas.restoreState()

# ── Main export function ──────────────────────────────────────────────────────
def generate_pdf(
    name, club, league, pos, age_val, date_start, date_end,
    season, phys,
    ws, ph,
    radar_data, ws_peers, phys_peers,
    ws_peer_n, phys_peer_n, peer_desc,
):
    """
    Build and return the PDF as bytes.
    All chart figures are built fresh here so we don't depend on Streamlit session state.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN + 6*mm, bottomMargin=14*mm,
        title=f"Beswicks Sports — {name}",
    )

    story = []
    tmp_files = []  # track temp files to clean up

    def chart_image(fig, w_mm, h_mm, width_px=700, height_px=300):
        path = fig_to_tmpfile(fig, width=width_px, height=height_px)
        tmp_files.append(path)
        return Image(path, width=w_mm*mm, height=h_mm*mm)

    # ── Page 1: Profile + season metrics ─────────────────────────────────────

    # Header block
    story.append(Paragraph(name, S_TITLE))
    story.append(Paragraph(f"{club}  ·  {league}  ·  Season 2025/26", S_CLUB))
    story.append(Spacer(1, 4))

    # Tags row as a single-row table
    tags = [pos, f"Age {age_val}", f"{season['matches']} apps",
            f"{int(season['mins'])} mins", f"{date_start} – {date_end}",
            f"{season['goals_raw']}G · {season['assists_raw']}A",
            f"{season['yellow']} YC · {season['red']} RC"]
    tag_cells = [[Paragraph(t, S_TAG) for t in tags]]
    tag_widths = [(W - 2*MARGIN) / len(tags)] * len(tags)
    tag_tbl = Table(tag_cells, colWidths=tag_widths)
    tag_tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,-1), HexColor('#1e1e1e')),
        ('TEXTCOLOR',     (0,0), (-1,-1), WHITE),
        ('FONTNAME',      (0,0), (-1,-1), 'Helvetica-Bold'),
        ('FONTSIZE',      (0,0), (-1,-1), 7.5),
        ('GRID',          (0,0), (-1,-1), 0.3, GREY2),
        ('LEFTPADDING',   (0,0), (-1,-1), 6),
        ('RIGHTPADDING',  (0,0), (-1,-1), 6),
        ('TOPPADDING',    (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('BACKGROUND',    (0,0), (0,-1), HexColor('#2a2218')),  # position tag gold-tinted
    ]))
    story.append(tag_tbl)
    story.append(Spacer(1, 6))

    # Peer group info
    peer_info = f"Peer group: {peer_desc}  ·  Wyscout peers: {ws_peer_n}  ·  Physical peers: {phys_peer_n}"
    story.append(Paragraph(peer_info, S_SMALL))
    story.append(HRFlowable(width='100%', thickness=0.5, color=GREY2, spaceAfter=8))

    # ── Physical metrics ──────────────────────────────────────────────────────
    if phys:
        story.append(Paragraph("PHYSICAL OUTPUT", S_SECTION))
        phys_data = [
            ['Metric', 'Value', 'Percentile'],
            ['Total distance p90', f"{int(phys['total_dist_p90']):,} m",
             ordinal(phys_peers['total_dist_p90'].pipe(lambda s: __import__('scipy').stats.percentileofscore(s.dropna(), phys['total_dist_p90'], kind='rank')).round(1)) if 'total_dist_p90' in phys_peers else '–'],
            ['HSR distance p90',   f"{int(phys['hsr_dist_p90'])} m",   '–'],
            ['Sprint distance p90',f"{int(phys['sprint_dist_p90'])} m",'–'],
            ['PSV99 avg',          str(phys['psv99_avg']),              '–'],
            ['PSV99 peak',         str(phys['psv99_max']),              '–'],
            ['COD count p90',      f"{phys['cod_p90']:.0f}",           '–'],
        ]

        # Fill percentiles properly
        from scipy import stats as scipy_stats
        def fill_pct(key, val, peers, inverse=False):
            if key not in peers or val is None: return '–'
            s = peers[key].dropna()
            r = scipy_stats.percentileofscore(s, val, kind='rank')
            r = round(100-r if inverse else r, 1)
            return ordinal(r)

        phys_data[1][2] = fill_pct('total_dist_p90', phys.get('total_dist_p90'), phys_peers)
        phys_data[2][2] = fill_pct('hsr_dist_p90',   phys.get('hsr_dist_p90'),   phys_peers)
        phys_data[3][2] = fill_pct('sprint_dist_p90',phys.get('sprint_dist_p90'),phys_peers)
        phys_data[4][2] = fill_pct('psv99_avg',       phys.get('psv99_avg'),      phys_peers)

        cw = [(W-2*MARGIN)*f for f in [0.5, 0.3, 0.2]]
        story.append(dark_table([[Paragraph(str(c), S_BODY if i>0 else _style('hdr',fontSize=7,textColor=GOLD,fontName='Helvetica-Bold')) for i,c in enumerate(row)] for row in phys_data], cw))

    # ── Attacking metrics ─────────────────────────────────────────────────────
    story.append(Paragraph("ATTACKING OUTPUT", S_SECTION))

    from scipy import stats as scipy_stats
    def ws_pct(key, val, inverse=False):
        if key not in ws_peers or val is None: return '–'
        s = ws_peers[key].dropna()
        r = scipy_stats.percentileofscore(s, val, kind='rank')
        return ordinal(round(100-r if inverse else r, 1))

    atk_data = [
        ['Metric', 'Value', 'Percentile', 'Metric', 'Value', 'Percentile'],
        ['Goals p90',      f"{season['goals_p90']:.2f}",    ws_pct('goals_p90',    season.get('goals_p90')),
         'Shot asts p90',  f"{season['shot_asts_p90']:.2f}",ws_pct('shot_asts_p90',season.get('shot_asts_p90'))],
        ['Assists p90',    f"{season['assists_p90']:.2f}",  ws_pct('assists_p90',  season.get('assists_p90')),
         'Touches box p90',f"{season['touches_box_p90']:.2f}",ws_pct('touches_box_p90',season.get('touches_box_p90'))],
        ['xG p90',         f"{season['xg_p90']:.2f}",       ws_pct('xg_p90',       season.get('xg_p90')),
         'Dribbles p90',   f"{season['dribbles_p90']:.2f}", ws_pct('dribbles_p90', season.get('dribbles_p90'))],
        ['xA p90',         f"{season['xa_p90']:.2f}",       ws_pct('xa_p90',       season.get('xa_p90')),
         'Prog runs p90',  f"{season['prog_runs_p90']:.2f}",ws_pct('prog_runs_p90',season.get('prog_runs_p90'))],
    ]
    cw2 = [(W-2*MARGIN)*f for f in [0.28,0.12,0.10, 0.28,0.12,0.10]]
    story.append(dark_table([[Paragraph(str(c),S_BODY) for c in row] for row in atk_data], cw2))

    # ── Defensive + passing metrics ───────────────────────────────────────────
    story.append(Paragraph("DEFENSIVE & PASSING OUTPUT", S_SECTION))
    def_data = [
        ['Metric', 'Value', 'Percentile', 'Metric', 'Value', 'Percentile'],
        ['Duels p90',       f"{season['duels_p90']:.1f}",       ws_pct('duels_p90',       season.get('duels_p90')),
         'Passes p90',      f"{season['passes_p90']:.1f}",      ws_pct('passes_p90',      season.get('passes_p90'))],
        ['Duel win %',      f"{season['duel_win']:.1f}%" if season['duel_win'] else '–', ws_pct('duel_win',season.get('duel_win')),
         'Pass acc %',      f"{season['pass_acc']:.1f}%" if season['pass_acc'] else '–', ws_pct('pass_acc', season.get('pass_acc'))],
        ['Aerial p90',      f"{season['aerial_p90']:.2f}",      ws_pct('aerial_p90',      season.get('aerial_p90')),
         'Long pass p90',   f"{season['long_passes_p90']:.2f}", ws_pct('long_passes_p90', season.get('long_passes_p90'))],
        ['Aerial win %',    f"{season['aerial_win']:.1f}%" if season['aerial_win'] else '–', ws_pct('aerial_win',season.get('aerial_win')),
         'Crosses p90',     f"{season['crosses_p90']:.2f}",     ws_pct('crosses_p90',     season.get('crosses_p90'))],
        ['Def duels p90',   f"{season['def_duels_p90']:.2f}",   ws_pct('def_duels_p90',   season.get('def_duels_p90')),
         'Interceptions p90',f"{season['interceptions_p90']:.2f}",ws_pct('interceptions_p90',season.get('interceptions_p90'))],
        ['Def duel win %',  f"{season['def_duel_win']:.1f}%" if season['def_duel_win'] else '–', ws_pct('def_duel_win',season.get('def_duel_win')),
         'Recoveries p90',  f"{season['recoveries_p90']:.2f}",  ws_pct('recoveries_p90',  season.get('recoveries_p90'))],
        ['Losses p90',      f"{season['losses_p90']:.2f}",      ws_pct('losses_p90',      season.get('losses_p90'), True),
         'Ball security rank','–','–'],
    ]
    story.append(dark_table([[Paragraph(str(c),S_BODY) for c in row] for row in def_data], cw2))

    story.append(PageBreak())

    # ── Page 2: Radar chart ───────────────────────────────────────────────────
    if len(radar_data) >= 5:
        story.append(Paragraph("PERCENTILE PROFILE", S_SECTION))

        fig_radar = build_radar_fig(radar_data, name)
        story.append(chart_image(fig_radar, w_mm=120, h_mm=95, width_px=480, height_px=380))
        story.append(Spacer(1, 6))

        # Strengths / weaknesses side note as a table
        top3    = sorted(radar_data.items(), key=lambda x: x[1], reverse=True)[:3]
        bottom3 = sorted(radar_data.items(), key=lambda x: x[1])[:3]

        sw_data = [['STRENGTHS', '', 'BELOW AVERAGE', '']]
        for i in range(3):
            lbl_s, val_s = top3[i]
            lbl_b, val_b = bottom3[i]
            sw_data.append([
                Paragraph(lbl_s, S_BODY),
                Paragraph(f'<font color="#4ade80"><b>{ordinal(val_s)}</b></font>', S_BODY),
                Paragraph(lbl_b, S_BODY),
                Paragraph(f'<font color="#f87171"><b>{ordinal(val_b)}</b></font>', S_BODY),
            ])

        cw_sw = [(W-2*MARGIN)*f for f in [0.33,0.17,0.33,0.17]]
        sw_tbl = Table(sw_data, colWidths=cw_sw)
        sw_tbl.setStyle(TableStyle([
            ('BACKGROUND',    (0,0), (-1,0),  GREY1),
            ('TEXTCOLOR',     (0,0), (1,0),   HexColor('#4ade80')),
            ('TEXTCOLOR',     (2,0), (3,0),   HexColor('#f87171')),
            ('FONTNAME',      (0,0), (-1,0),  'Helvetica-Bold'),
            ('FONTSIZE',      (0,0), (-1,0),  7),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),  [GREY1, BG]),
            ('GRID',          (0,0), (-1,-1), 0.3, GREY2),
            ('LEFTPADDING',   (0,0), (-1,-1), 6),
            ('RIGHTPADDING',  (0,0), (-1,-1), 6),
            ('TOPPADDING',    (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        story.append(sw_tbl)
        story.append(Spacer(1, 10))

    # ── Physical chart ────────────────────────────────────────────────────────
    if ph is not None and 'dist_p90_m' in ph.columns:
        story.append(HRFlowable(width='100%', thickness=0.5, color=GREY2, spaceAfter=6))
        story.append(Paragraph("PHYSICAL OUTPUT · MATCH BY MATCH", S_SECTION))
        fig_dist = build_dist_fig(ph, phys_peers)
        story.append(chart_image(fig_dist, w_mm=168, h_mm=58, width_px=700, height_px=260))

    story.append(PageBreak())

    # ── Page 3: Form chart + match log ───────────────────────────────────────
    story.append(Paragraph("FORM TRENDS · DUEL WIN %", S_SECTION))
    if 'duel_win_pct' in ws.columns:
        fig_duel = build_duel_fig(ws, ws_peers)
        story.append(chart_image(fig_duel, w_mm=168, h_mm=52, width_px=700, height_px=240))

    story.append(Spacer(1, 8))

    # ── Match log ─────────────────────────────────────────────────────────────
    story.append(HRFlowable(width='100%', thickness=0.5, color=GREY2, spaceAfter=6))
    story.append(Paragraph("MATCH LOG", S_SECTION))

    log_cols = ['Match','Date','Min','G','A','xG','xA','Pass%','Duel%','Aer%','DefD%','Int','Loss']
    log_header = [Paragraph(c, _style('lh', fontSize=6.5, textColor=GOLD, fontName='Helvetica-Bold')) for c in log_cols]
    log_rows   = [log_header]

    for _, r in ws.sort_values('Date', ascending=False).iterrows():
        def sp(n,d): return f"{int(round(n/d*100))}%" if d>0 else "-"
        import pandas as pd
        row_data = [
            Paragraph(str(r['match_label'])[:32], _style('lc',fontSize=6.5,textColor=LGREY)),
            Paragraph(pd.to_datetime(r['Date']).strftime('%d %b') if pd.notna(r['Date']) else '', _style('lc',fontSize=6.5,textColor=GREY3)),
            Paragraph(str(int(r['Minutes played'])),   _style('lc',fontSize=6.5,textColor=LGREY)),
            Paragraph(str(int(r['Goals'])),            _style('lc',fontSize=6.5,textColor=LGREY if r['Goals']==0 else '#4ade80',fontName='Helvetica-Bold' if r['Goals']>0 else 'Helvetica')),
            Paragraph(str(int(r['Assists'])),          _style('lc',fontSize=6.5,textColor=LGREY)),
            Paragraph(f"{r['xG']:.2f}",               _style('lc',fontSize=6.5,textColor=LGREY)),
            Paragraph(f"{r['xA']:.2f}",               _style('lc',fontSize=6.5,textColor=LGREY)),
            Paragraph(sp(r.iloc[13],r['Passes']),      _style('lc',fontSize=6.5,textColor=LGREY)),
            Paragraph(sp(r.iloc[21],r['Duels']),       _style('lc',fontSize=6.5,textColor=LGREY)),
            Paragraph(sp(r.iloc[23],r['Aerial duels']),_style('lc',fontSize=6.5,textColor=LGREY)),
            Paragraph(sp(r.iloc[32],r.iloc[31]),       _style('lc',fontSize=6.5,textColor=LGREY)),
            Paragraph(str(int(r['Interceptions'])),    _style('lc',fontSize=6.5,textColor=LGREY)),
            Paragraph(str(int(r['Losses'])),           _style('lc',fontSize=6.5,textColor=LGREY)),
        ]
        log_rows.append(row_data)

    # Column widths
    avail = W - 2*MARGIN
    log_cw = [avail*f for f in [0.22,0.07,0.05,0.04,0.04,0.06,0.06,0.07,0.07,0.06,0.07,0.05,0.05]]
    log_tbl = Table(log_rows, colWidths=log_cw, repeatRows=1)
    log_tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,0),  GREY1),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),  [GREY1, BG]),
        ('GRID',          (0,0), (-1,-1), 0.25, GREY2),
        ('LEFTPADDING',   (0,0), (-1,-1), 3),
        ('RIGHTPADDING',  (0,0), (-1,-1), 3),
        ('TOPPADDING',    (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(log_tbl)

    # ── Build ─────────────────────────────────────────────────────────────────
    doc.build(story, onFirstPage=_draw_background, onLaterPages=_draw_background)

    # Clean up temp image files
    for f in tmp_files:
        try: os.unlink(f)
        except Exception: pass

    buf.seek(0)
    return buf.read()
