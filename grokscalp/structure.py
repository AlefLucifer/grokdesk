"""Market structure: swings, BOS/CHoCH, order blocks, FVGs, liquidity, OTE.

This is the SMC/ICT half of the engine. Every detector is deliberately plain:
pivots, price relative to pivots, gaps between candles, and where volume sat.
No pattern is called unless a later bar confirms it, so the read never repaints
on the last candle.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .indicators import clamp, mean
from .types import Candle, Level, Structure


@dataclass
class Pivot:
    i: int
    price: float
    kind: str        # "H" | "L"
    ts: int


# --------------------------------------------------------------------------
# swings
# --------------------------------------------------------------------------

def swing_pivots(candles: Sequence[Candle], k: int = 2) -> list[Pivot]:
    """Fractal pivots: a high that is the highest of `k` bars either side."""
    out: list[Pivot] = []
    n = len(candles)
    for i in range(k, n - k):
        win = candles[i - k:i + k + 1]
        hi = candles[i].h
        lo = candles[i].l
        if all(c.h <= hi for c in win) and any(c.h < hi for c in win):
            out.append(Pivot(i, hi, "H", candles[i].ts))
        if all(c.l >= lo for c in win) and any(c.l > lo for c in win):
            out.append(Pivot(i, lo, "L", candles[i].ts))
    return out


def zigzag(candles: Sequence[Candle], k: int = 2, min_move: float = 0.35) -> list[Pivot]:
    """Alternating H/L pivots, each leg at least `min_move` ATRs."""
    pivots = swing_pivots(candles, k)
    if not pivots:
        return []
    from .indicators import atr, last
    a = last(atr(candles, 14)) or (candles[-1].c * 0.005)
    min_gap = a * min_move
    kept: list[Pivot] = []
    for p in pivots:
        if not kept:
            kept.append(p)
            continue
        prev = kept[-1]
        if p.kind == prev.kind:
            better = p.price > prev.price if p.kind == "H" else p.price < prev.price
            if better:
                kept[-1] = p
            continue
        if abs(p.price - prev.price) >= min_gap:
            kept.append(p)
    return kept


# --------------------------------------------------------------------------
# BOS / CHoCH
# --------------------------------------------------------------------------

def break_events(candles: Sequence[Candle], pivots: Sequence[Pivot], k: int = 2) -> list[dict]:
    """Walk forward. A close through the last confirmed swing is a break.

    BOS = break in the direction of the prevailing trend (continuation),
    CHoCH = break against it (character change). The pivot has to be confirmed
    by `k` bars before its level is allowed to break, which is why this does
    not repaint.
    """
    highs = [p for p in pivots if p.kind == "H"]
    lows = [p for p in pivots if p.kind == "L"]
    hi_ptr = lo_ptr = 0
    active_hi: Pivot | None = None
    active_lo: Pivot | None = None
    broken_hi = broken_lo = False
    trend = 0
    events: list[dict] = []
    for i, c in enumerate(candles):
        while hi_ptr < len(highs) and highs[hi_ptr].i + k <= i:
            active_hi, broken_hi = highs[hi_ptr], False
            hi_ptr += 1
        while lo_ptr < len(lows) and lows[lo_ptr].i + k <= i:
            active_lo, broken_lo = lows[lo_ptr], False
            lo_ptr += 1
        if active_hi and not broken_hi and c.c > active_hi.price:
            events.append({
                "ts": c.ts, "i": i, "kind": "BOS" if trend >= 0 else "CHoCH",
                "direction": 1, "price": active_hi.price, "close": c.c,
                "pivot_i": active_hi.i,
            })
            broken_hi = True
            trend = 1
        if active_lo and not broken_lo and c.c < active_lo.price:
            events.append({
                "ts": c.ts, "i": i, "kind": "BOS" if trend <= 0 else "CHoCH",
                "direction": -1, "price": active_lo.price, "close": c.c,
                "pivot_i": active_lo.i,
            })
            broken_lo = True
            trend = -1
    return events


# --------------------------------------------------------------------------
# order blocks & fair value gaps
# --------------------------------------------------------------------------

def order_blocks(candles: Sequence[Candle], atr_v: float, lookback: int = 140) -> tuple[list[Level], list[Level]]:
    """Displacement candles, and the last opposite candle before each.

    A zone is `mitigated` once price trades back into it. Unmitigated zones are
    the ones worth an entry, so they are ordered first.
    """
    bull: list[Level] = []
    bear: list[Level] = []
    n = len(candles)
    start = max(10, n - lookback)
    if atr_v <= 0:
        return bull, bear
    for i in range(start, n):
        c = candles[i]
        if c.body < 1.1 * atr_v:
            continue
        if c.bull:
            for j in range(i - 1, max(start - 1, i - 7), -1):
                z = candles[j]
                if not z.bull and c.c > z.h:
                    lo, hi = z.l, max(z.o, z.c)
                    filled = any(x.l <= hi for x in candles[i + 1:])
                    bull.append(Level("ob", lo, hi, "bullish order block",
                                      strength=clamp(0.35 + c.body / atr_v / 4 + (0.0 if filled else 0.25)),
                                      ts=z.ts))
                    break
        else:
            for j in range(i - 1, max(start - 1, i - 7), -1):
                z = candles[j]
                if z.bull and c.c < z.l:
                    lo, hi = min(z.o, z.c), z.h
                    filled = any(x.h >= lo for x in candles[i + 1:])
                    bear.append(Level("ob", lo, hi, "bearish order block",
                                      strength=clamp(0.35 + c.body / atr_v / 4 + (0.0 if filled else 0.25)),
                                      ts=z.ts))
                    break
    # keep the freshest, unmitigated zones nearest the price
    price = candles[-1].c
    def rank(z: Level) -> tuple:
        return (z.contains(price, atr_v * 8), -z.strength, -z.ts)
    return sorted(bull, key=rank)[:6], sorted(bear, key=rank)[:6]


def fair_value_gaps(candles: Sequence[Candle], lookback: int = 120) -> tuple[list[Level], list[Level]]:
    """Three-candle imbalances with the fill ratio tracked."""
    bull: list[Level] = []
    bear: list[Level] = []
    n = len(candles)
    start = max(2, n - lookback)
    for i in range(start, n):
        a, b, c = candles[i - 2], candles[i - 1], candles[i]
        if c.l > a.h and b.bull:
            lo, hi = a.h, c.l
            fill = min(1.0, max(0.0, (hi - min([x.l for x in candles[i + 1:]] or [hi])) / max(hi - lo, 1e-9)))
            bull.append(Level("fvg", lo, hi, f"bullish FVG ({fill:.0%} filled)",
                              strength=clamp(0.35 + (hi - lo) / max(candles[-1].c * 0.005, 1e-9) / 8) * (1 - fill * 0.7),
                              ts=b.ts))
        if c.h < a.l and not b.bull:
            lo, hi = c.h, a.l
            fill = min(1.0, max(0.0, (max([x.h for x in candles[i + 1:]] or [lo]) - lo) / max(hi - lo, 1e-9)))
            bear.append(Level("fvg", lo, hi, f"bearish FVG ({fill:.0%} filled)",
                              strength=clamp(0.35 + (hi - lo) / max(candles[-1].c * 0.005, 1e-9) / 8) * (1 - fill * 0.7),
                              ts=b.ts))
    return bull[-6:], bear[-6:]


# --------------------------------------------------------------------------
# liquidity: equal highs/lows, sweeps, range
# --------------------------------------------------------------------------

def _cluster(prices: Sequence[float], tol: float) -> list[list[float]]:
    groups: list[list[float]] = []
    for p in sorted(prices):
        if groups and p - groups[-1][-1] <= tol:
            groups[-1].append(p)
        else:
            groups.append([p])
    return groups


def liquidity_pools(candles: Sequence[Candle], pivots: Sequence[Pivot],
                    atr_v: float, tol_mult: float = 0.22) -> list[Level]:
    tol = max(atr_v * tol_mult, candles[-1].c * 0.0004)
    pools: list[Level] = []
    for kind, side in (("H", "BSL"), ("L", "SSL")):
        prices = [p.price for p in pivots if p.kind == kind]
        for grp in _cluster(prices, tol):
            if len(grp) < 2:
                continue
            mid = mean(grp)
            pools.append(Level("liq", mid - tol / 2, mid + tol / 2,
                               f"{side} — {len(grp)} equal {'highs' if kind == 'H' else 'lows'}",
                               strength=clamp(0.25 + 0.15 * len(grp)), ts=candles[-1].ts))
    # extremes of the visible range are pools too, even with one touch
    hi = max(c.h for c in candles[-90:])
    lo = min(c.l for c in candles[-90:])
    pools.append(Level("liq", hi * 0.9995, hi * 1.0005, "range high (BSL)", strength=0.55))
    pools.append(Level("liq", lo * 0.9995, lo * 1.0005, "range low (SSL)", strength=0.55))
    return sorted(pools, key=lambda z: -z.strength)


def detect_sweep(candles: Sequence[Candle], pools: Sequence[Level],
                 atr_v: float, lookback: int = 14) -> dict:
    """A wick through a pool that closes back inside = stop run."""
    best: dict = {}
    n = len(candles)
    for i in range(max(1, n - lookback), n):
        c = candles[i]
        for p in pools:
            if "BSL" not in p.note and "highs" not in p.note:
                continue
            if c.h > p.hi and c.c < p.mid:
                wick = c.h - max(c.o, c.c)
                if wick < atr_v * 0.15:
                    continue
                score = clamp(0.35 + wick / max(atr_v, 1e-9) / 3)
                if score > best.get("score", 0):
                    best = {"direction": -1, "score": score, "level": p.hi,
                            "price": c.c, "wick_atr": wick / max(atr_v, 1e-9),
                            "side": "BSL", "bars_ago": n - 1 - i,
                            "volume_z": c.v / max(mean([x.v for x in candles[-20:]]), 1e-9)}
            if "SSL" not in p.note and "lows" not in p.note:
                continue
            if c.l < p.lo and c.c > p.mid:
                wick = min(c.o, c.c) - c.l
                if wick < atr_v * 0.15:
                    continue
                score = clamp(0.35 + wick / max(atr_v, 1e-9) / 3)
                if score > best.get("score", 0):
                    best = {"direction": 1, "score": score, "level": p.lo,
                            "price": c.c, "wick_atr": wick / max(atr_v, 1e-9),
                            "side": "SSL", "bars_ago": n - 1 - i,
                            "volume_z": c.v / max(mean([x.v for x in candles[-20:]]), 1e-9)}
    return best


# --------------------------------------------------------------------------
# OTE, S/R, trendlines
# --------------------------------------------------------------------------

def ote_zone(candles: Sequence[Candle], zz: Sequence[Pivot]) -> Level | None:
    """Optimal trade entry: 61.8%–79% retracement of the last impulse leg."""
    if len(zz) < 2:
        return None
    a, b = zz[-2], zz[-1]
    leg = abs(b.price - a.price)
    if leg <= 0:
        return None
    if b.kind == "H":                      # up leg, discount zone below
        lo = b.price - leg * 0.79
        hi = b.price - leg * 0.618
        return Level("ote", lo, hi, "OTE 61.8–79% of the last up leg", strength=0.7, ts=b.ts)
    lo = b.price + leg * 0.618
    hi = b.price + leg * 0.79
    return Level("ote", lo, hi, "OTE 61.8–79% of the last down leg", strength=0.7, ts=b.ts)


def support_resistance(pivots: Sequence[Pivot], atr_v: float, price: float,
                       tol_mult: float = 0.30) -> list[Level]:
    tol = max(atr_v * tol_mult, price * 0.0005)
    out: list[Level] = []
    for kind in ("H", "L"):
        prices = [p.price for p in pivots if p.kind == kind]
        for grp in _cluster(prices, tol):
            mid = mean(grp)
            touches = len(grp)
            if touches < 2:
                continue
            out.append(Level("sr", mid - tol / 2, mid + tol / 2,
                             f"{'resistance' if mid > price else 'support'} · {touches} touches",
                             strength=clamp(0.2 + 0.15 * touches)))
    return sorted(out, key=lambda z: abs(z.mid - price))[:6]


def trendline(candles: Sequence[Candle], pivots: Sequence[Pivot], price: float,
              atr_v: float) -> dict:
    """Fit the last three swing highs / lows and report slope + whether it broke."""
    n = len(candles)
    out: dict = {}
    for kind, name in (("H", "resistance"), ("L", "support")):
        pts = [p for p in pivots if p.kind == kind][-3:]
        if len(pts) < 2:
            continue
        xm = mean([p.i for p in pts])
        ym = mean([p.price for p in pts])
        denom = sum((p.i - xm) ** 2 for p in pts)
        if denom == 0:
            continue
        slope = sum((p.i - xm) * (p.price - ym) for p in pts) / denom
        now = ym + slope * (n - 1 - xm)
        pad = atr_v * 0.25
        broke = price > now + pad if kind == "H" else price < now - pad
        out[name] = {
            "slope_atr": slope * 10 / max(atr_v, 1e-9),
            "value": now,
            "touches": len(pts),
            "broken": broke,
            "direction": "down" if slope < 0 else "up",
        }
    return out


# --------------------------------------------------------------------------
# the full read
# --------------------------------------------------------------------------

def analyse_structure(candles: Sequence[Candle], atr_v: float, k: int = 2) -> Structure:
    st = Structure()
    if len(candles) < 20 or atr_v <= 0:
        return st
    price = candles[-1].c
    pivots = swing_pivots(candles, k)
    zz = zigzag(candles, k)
    events = break_events(candles, pivots, k)
    st.events = events
    if events:
        last_ev = events[-1]
        st.trend = last_ev["direction"]
        st.label = "bullish" if st.trend > 0 else "bearish"
        # a break older than 25 bars with price back through it is stale
        if len(candles) - 1 - last_ev["i"] > 25:
            st.label += " (stale)"
    else:
        # fall back on higher highs / lower lows
        if len(zz) >= 3:
            st.trend = 1 if zz[-1].price > zz[-3].price and zz[-1].kind == "H" else \
                       -1 if zz[-1].price < zz[-3].price and zz[-1].kind == "L" else 0
            st.label = {1: "bullish", -1: "bearish", 0: "unclear"}[st.trend]
    highs = [p.price for p in pivots if p.kind == "H"]
    lows = [p.price for p in pivots if p.kind == "L"]
    st.swing_highs, st.swing_lows = highs[-12:], lows[-12:]
    st.last_high = highs[-1] if highs else max(c.h for c in candles[-20:])
    st.last_low = lows[-1] if lows else min(c.l for c in candles[-20:])

    st.order_blocks = [z for pair in order_blocks(candles, atr_v) for z in pair]
    st.fvgs = [z for pair in fair_value_gaps(candles) for z in pair]
    st.pools = liquidity_pools(candles, pivots, atr_v)
    st.sweep = detect_sweep(candles, st.pools, atr_v)
    st.ote = ote_zone(candles, zz)
    st.sr = support_resistance(pivots, atr_v, price)
    window = candles[-61:-1] or candles[-60:]
    st.range_high = max(c.h for c in window)
    st.range_low = min(c.l for c in window)
    span = st.range_high - st.range_low
    st.premium_discount = clamp((price - st.range_low) / span) if span > 0 else 0.5
    return st
