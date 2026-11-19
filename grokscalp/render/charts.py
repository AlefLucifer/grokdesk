"""Plotly chart for the dashboard: candles, EMAs, zones and the trade plan.

Imported lazily by the UI so the core engine stays dependency-free.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..indicators import ema, vwap
from ..types import SignalCard


def build_figure(card: SignalCard, max_bars: int = 220):
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    snap = card.snapshot
    if snap is None:
        raise ValueError("card has no snapshot")
    candles = snap.series()[-max_bars:]
    x = [datetime.fromtimestamp(c.ts / 1000, tz=timezone.utc) for c in candles]
    closes = [c.c for c in candles]

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.76, 0.24],
                        vertical_spacing=0.03, subplot_titles=("", ""))

    fig.add_trace(go.Candlestick(
        x=x, open=[c.o for c in candles], high=[c.h for c in candles],
        low=[c.l for c in candles], close=closes, name=card.symbol,
        increasing_line_color="#26a69a", decreasing_line_color="#ef5350",
        increasing_fillcolor="#26a69a", decreasing_fillcolor="#ef5350",
        whiskerwidth=0.4,
    ), row=1, col=1)

    for period, color in ((21, "#42a5f5"), (50, "#ab47bc")):
        line = ema(closes, period)
        fig.add_trace(go.Scatter(x=x, y=line, name=f"EMA {period}", mode="lines",
                                 line=dict(color=color, width=1.2)), row=1, col=1)
    vw = vwap(candles)
    fig.add_trace(go.Scatter(x=x, y=vw, name="VWAP", mode="lines",
                             line=dict(color="#ffb74d", width=1, dash="dot")), row=1, col=1)

    colors = ["#26a69a" if c.bull else "#ef5350" for c in candles]
    fig.add_trace(go.Bar(x=x, y=[c.v for c in candles], marker_color=colors,
                         name="volume", opacity=0.55), row=2, col=1)

    # structural zones
    for z in card.structure.order_blocks[:5]:
        fig.add_shape(type="rect", xref="x", yref="y", x0=x[0], x1=x[-1],
                      y0=z.lo, y1=z.hi,
                      fillcolor="rgba(255,167,38,0.16)" if "bull" in z.note else "rgba(120,80,255,0.16)",
                      line=dict(width=0))
    for z in card.structure.fvgs[:4]:
        fig.add_shape(type="rect", xref="x", yref="y", x0=x[0], x1=x[-1],
                      y0=z.lo, y1=z.hi,
                      fillcolor="rgba(38,166,154,0.10)" if "bull" in z.note else "rgba(239,83,80,0.10)",
                      line=dict(width=0))

    # plan levels
    if card.action != "WAIT":
        p = card.plan
        for value, label, color, dash in (
            (p.entry, "entry", "#e0e0e0", "dash"),
            (p.sl, "SL", "#ef5350", "dot"),
            (p.tp1, "TP1", "#66bb6a", "dot"),
            (p.tp2, "TP2", "#4caf50", "dot"),
            (p.tp3, "TP3", "#2e7d32", "dot"),
        ):
            fig.add_hline(y=value, line=dict(color=color, width=1, dash=dash),
                          annotation_text=f"{label} {value:,.6g}",
                          annotation_position="right", annotation_font_color=color)
        fig.add_shape(type="rect", xref="x", yref="y", x0=x[0], x1=x[-1],
                      y0=min(p.entry_lo, p.entry_hi), y1=max(p.entry_lo, p.entry_hi),
                      fillcolor="rgba(255,255,255,0.07)", line=dict(width=0))

    fig.update_layout(
        template="plotly_dark", height=560, margin=dict(l=10, r=10, t=30, b=10),
        showlegend=False, xaxis_rangeslider_visible=False,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(size=11),
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor="rgba(255,255,255,0.06)", side="right")
    return fig
