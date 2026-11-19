"""Indicators, in plain Python.

Every function returns a list aligned with the input, padded with None where
the indicator is not yet defined. No numpy, no pandas: the engine has to run
on a bare Python 3.10 install, same as the rest of this repo.
"""

from __future__ import annotations

import math
from typing import Sequence

from .types import Candle

Num = float | None


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def last(vals: Sequence[Num], default: float | None = None) -> float | None:
    for v in reversed(vals):
        if v is not None:
            return v
    return default


def value_at(vals: Sequence[Num], i: int) -> float | None:
    """Index from the end: -1 is the latest bar."""
    if not vals:
        return None
    j = len(vals) + i
    if 0 <= j < len(vals):
        return vals[j]
    return None


def mean(vals: Sequence[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0


def stdev(vals: Sequence[float]) -> float:
    if len(vals) < 2:
        return 0.0
    m = mean(vals)
    return math.sqrt(sum((v - m) ** 2 for v in vals) / (len(vals) - 1))


def pct_rank(series: Sequence[float], value: float) -> float:
    if not series:
        return 0.5
    return sum(1 for v in series if v <= value) / len(series)


def zscore(series: Sequence[float], value: float | None = None) -> float:
    if len(series) < 2:
        return 0.0
    v = series[-1] if value is None else value
    sd = stdev(series)
    return 0.0 if sd == 0 else (v - mean(series)) / sd


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def linreg_slope(vals: Sequence[float]) -> float:
    """Least-squares slope per bar. Raw units per bar."""
    n = len(vals)
    if n < 2:
        return 0.0
    xm = (n - 1) / 2.0
    ym = mean(vals)
    denom = sum((i - xm) ** 2 for i in range(n))
    if denom == 0:
        return 0.0
    return sum((i - xm) * (v - ym) for i, v in enumerate(vals)) / denom


# --------------------------------------------------------------------------
# moving averages
# --------------------------------------------------------------------------

def sma(vals: Sequence[float], period: int) -> list[Num]:
    out: list[Num] = [None] * len(vals)
    if period <= 0:
        return out
    run = 0.0
    for i, v in enumerate(vals):
        run += v
        if i >= period:
            run -= vals[i - period]
        if i >= period - 1:
            out[i] = run / period
    return out


def ema(vals: Sequence[float], period: int) -> list[Num]:
    out: list[Num] = [None] * len(vals)
    if period <= 0 or len(vals) < period:
        return out
    k = 2.0 / (period + 1.0)
    prev = mean(vals[:period])
    out[period - 1] = prev
    for i in range(period, len(vals)):
        prev = vals[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def ema_on_gapped(vals: Sequence[Num], period: int) -> list[Num]:
    """EMA over a series that may contain leading/trailing Nones."""
    idx = [i for i, v in enumerate(vals) if v is not None]
    out: list[Num] = [None] * len(vals)
    if len(idx) < period:
        return out
    compact = [float(vals[i]) for i in idx]  # type: ignore[arg-type]
    e = ema(compact, period)
    for k, i in enumerate(idx):
        out[i] = e[k]
    return out


def rma(vals: Sequence[float], period: int) -> list[Num]:
    """Wilder's smoothing (used by RSI and ATR)."""
    out: list[Num] = [None] * len(vals)
    if len(vals) < period:
        return out
    prev = mean(vals[:period])
    out[period - 1] = prev
    for i in range(period, len(vals)):
        prev = (prev * (period - 1) + vals[i]) / period
        out[i] = prev
    return out


# --------------------------------------------------------------------------
# oscillators & volatility
# --------------------------------------------------------------------------

def rsi(vals: Sequence[float], period: int = 14) -> list[Num]:
    out: list[Num] = [None] * len(vals)
    if len(vals) <= period:
        return out
    gains, losses = 0.0, 0.0
    for i in range(1, period + 1):
        d = vals[i] - vals[i - 1]
        gains += max(d, 0.0)
        losses += max(-d, 0.0)
    ag, al = gains / period, losses / period
    out[period] = 100.0 if al == 0 else 100.0 - 100.0 / (1 + ag / al)
    for i in range(period + 1, len(vals)):
        d = vals[i] - vals[i - 1]
        ag = (ag * (period - 1) + max(d, 0.0)) / period
        al = (al * (period - 1) + max(-d, 0.0)) / period
        out[i] = 100.0 if al == 0 else 100.0 - 100.0 / (1 + ag / al)
    return out


def true_range(candles: Sequence[Candle]) -> list[float]:
    out: list[float] = []
    for i, c in enumerate(candles):
        if i == 0:
            out.append(c.h - c.l)
        else:
            p = candles[i - 1].c
            out.append(max(c.h - c.l, abs(c.h - p), abs(c.l - p)))
    return out


def atr(candles: Sequence[Candle], period: int = 14) -> list[Num]:
    return rma(true_range(candles), period)


def atr_pct(candles: Sequence[Candle], period: int = 14) -> float:
    a = last(atr(candles, period))
    return (a / candles[-1].c * 100.0) if a and candles else 0.0


def macd(vals: Sequence[float], fast: int = 12, slow: int = 26, signal: int = 9
         ) -> tuple[list[Num], list[Num], list[Num]]:
    ef, es = ema(vals, fast), ema(vals, slow)
    line: list[Num] = [None] * len(vals)
    for i in range(len(vals)):
        if ef[i] is not None and es[i] is not None:
            line[i] = ef[i] - es[i]  # type: ignore[operator]
    sig = ema_on_gapped(line, signal)
    hist: list[Num] = [None] * len(vals)
    for i in range(len(vals)):
        if line[i] is not None and sig[i] is not None:
            hist[i] = line[i] - sig[i]  # type: ignore[operator]
    return line, sig, hist


def bollinger(vals: Sequence[float], period: int = 20, mult: float = 2.0):
    mid = sma(vals, period)
    up: list[Num] = [None] * len(vals)
    lo: list[Num] = [None] * len(vals)
    width: list[Num] = [None] * len(vals)
    for i in range(len(vals)):
        if i >= period - 1 and mid[i] is not None:
            sd = stdev(vals[i - period + 1:i + 1])
            up[i] = mid[i] + mult * sd  # type: ignore[operator]
            lo[i] = mid[i] - mult * sd  # type: ignore[operator]
            width[i] = (up[i] - lo[i]) / mid[i] * 100.0  # type: ignore[operator]
    return mid, up, lo, width


def stoch(candles: Sequence[Candle], k: int = 14, smooth: int = 3, d: int = 3):
    raw: list[float] = []
    for i in range(len(candles)):
        if i < k - 1:
            continue
        win = candles[i - k + 1:i + 1]
        hi = max(c.h for c in win)
        lo = min(c.l for c in win)
        raw.append(50.0 if hi == lo else (candles[i].c - lo) / (hi - lo) * 100.0)
    kline = sma(raw, smooth)
    kpad: list[Num] = [None] * (len(candles) - len(kline)) + kline
    compact = [float(v) for v in kline if v is not None]
    dline = sma(compact, d)
    dpad: list[Num] = [None] * (len(candles) - len(dline)) + dline
    return kpad, dpad


def adx(candles: Sequence[Candle], period: int = 14):
    n = len(candles)
    if n < period + 1:
        return [None] * n, [None] * n, [None] * n
    plus_dm, minus_dm, tr = [], [], []
    for i in range(1, n):
        up = candles[i].h - candles[i - 1].h
        dn = candles[i - 1].l - candles[i].l
        plus_dm.append(up if up > dn and up > 0 else 0.0)
        minus_dm.append(dn if dn > up and dn > 0 else 0.0)
        p = candles[i - 1].c
        tr.append(max(candles[i].h - candles[i].l,
                      abs(candles[i].h - p), abs(candles[i].l - p)))
    atr_s = rma(tr, period)
    pdm = rma(plus_dm, period)
    mdm = rma(minus_dm, period)
    pdi: list[Num] = [None] * n
    mdi: list[Num] = [None] * n
    dx: list[Num] = [None] * n
    for i in range(n - 1):
        if atr_s[i] and pdm[i] is not None and mdm[i] is not None:
            p = 100.0 * pdm[i] / atr_s[i]  # type: ignore[operator]
            m = 100.0 * mdm[i] / atr_s[i]  # type: ignore[operator]
            pdi[i + 1] = p
            mdi[i + 1] = m
            dx[i + 1] = 100.0 * abs(p - m) / (p + m) if (p + m) else 0.0
    valid = [i for i, v in enumerate(dx) if v is not None]
    adx_out: list[Num] = [None] * n
    if len(valid) >= period:
        compact = [float(dx[i]) for i in valid]  # type: ignore[arg-type]
        sm = rma(compact, period)
        for k, i in enumerate(valid):
            adx_out[i] = sm[k]
    return adx_out, pdi, mdi


def ichimoku(candles: Sequence[Candle]):
    n = len(candles)
    highs = [c.h for c in candles]
    lows = [c.l for c in candles]

    def mid(period: int) -> list[Num]:
        out: list[Num] = [None] * n
        for i in range(period - 1, n):
            out[i] = (max(highs[i - period + 1:i + 1]) + min(lows[i - period + 1:i + 1])) / 2
        return out

    tenkan = mid(9)
    kijun = mid(26)
    span_b = mid(52)
    span_a: list[Num] = [None] * n
    for i in range(n):
        j = i - 26
        if j >= 0 and tenkan[j] is not None and kijun[j] is not None:
            span_a[i] = (tenkan[j] + kijun[j]) / 2  # type: ignore[operator]
    return {
        "tenkan": tenkan,
        "kijun": kijun,
        "span_a": span_a,
        "span_b": span_b,
        "cloud_top": [None if a is None or b is None else max(a, b) for a, b in zip(span_a, span_b)],
        "cloud_bottom": [None if a is None or b is None else min(a, b) for a, b in zip(span_a, span_b)],
        "chikou": [candles[i + 26].c if i + 26 < n else None for i in range(n)],
    }


def vwap(candles: Sequence[Candle], anchor: int | None = None) -> list[float]:
    """Session VWAP from `anchor` (default: start of the series)."""
    start = 0 if anchor is None else max(0, anchor)
    out: list[float] = []
    pv = vol = 0.0
    for i, c in enumerate(candles):
        if i < start:
            out.append(c.c)
            continue
        tp = (c.h + c.l + c.c) / 3.0
        pv += tp * c.v
        vol += c.v
        out.append(pv / vol if vol else c.c)
    return out


def obv(candles: Sequence[Candle]) -> list[float]:
    out = [0.0]
    for i in range(1, len(candles)):
        prev = out[-1]
        if candles[i].c > candles[i - 1].c:
            prev += candles[i].v
        elif candles[i].c < candles[i - 1].c:
            prev -= candles[i].v
        out.append(prev)
    return out


def cvd(candles: Sequence[Candle]) -> list[float]:
    """Cumulative volume delta from taker-buy volume."""
    out: list[float] = []
    run = 0.0
    for c in candles:
        run += c.delta
        out.append(run)
    return out


# --------------------------------------------------------------------------
# volume profile
# --------------------------------------------------------------------------

def volume_profile(candles: Sequence[Candle], bins: int = 24, value_area: float = 0.70):
    """Price-binned traded volume, VAH/VAL/POC.

    Each bar's volume is spread evenly across the bins its range touches, which
    is the usual approximation when you only have OHLCV.
    """
    if not candles:
        return {"poc": 0.0, "vah": 0.0, "val": 0.0, "rows": [], "hvn": [], "lvn": []}
    hi = max(c.h for c in candles)
    lo = min(c.l for c in candles)
    span = max(hi - lo, 1e-9)
    step = span / bins
    rows = [0.0] * bins
    for c in candles:
        first = int((c.l - lo) / step)
        last = int((c.h - lo) / step)
        first = max(0, min(bins - 1, first))
        last = max(first, min(bins - 1, last))
        share = c.v / (last - first + 1)
        for b in range(first, last + 1):
            rows[b] += share
    total = sum(rows)
    poc_i = max(range(bins), key=lambda i: rows[i]) if total else 0
    # grow the value area out from the POC until it holds `value_area` of volume
    inc = rows[poc_i]
    lo_i = hi_i = poc_i
    target = total * value_area
    while inc < target and (lo_i > 0 or hi_i < bins - 1):
        below = rows[lo_i - 1] if lo_i > 0 else -1
        above = rows[hi_i + 1] if hi_i < bins - 1 else -1
        if above >= below:
            hi_i += 1
            inc += max(above, 0)
        else:
            lo_i -= 1
            inc += max(below, 0)
    price_of = lambda i: lo + (i + 0.5) * step  # noqa: E731
    mean_vol = total / bins if bins else 0
    hvn = [price_of(i) for i in range(bins) if rows[i] > mean_vol * 1.6]
    lvn = [price_of(i) for i in range(bins) if 0 < rows[i] < mean_vol * 0.4]
    return {
        "poc": price_of(poc_i),
        "vah": price_of(hi_i),
        "val": price_of(lo_i),
        "rows": [(price_of(i), rows[i]) for i in range(bins)],
        "hvn": hvn,
        "lvn": lvn,
    }


# --------------------------------------------------------------------------
# divergence: price makes a new extreme, the oscillator does not
# --------------------------------------------------------------------------

def divergence(prices: Sequence[float], osc: Sequence[Num], lookback: int = 40,
               pivot: int = 2) -> dict:
    """Compare the last two price swing extremes against the oscillator."""
    n = len(prices)
    start = max(0, n - lookback)
    osc_ok = [(i, osc[i]) for i in range(start, n) if i < len(osc) and osc[i] is not None]
    if len(osc_ok) < 8:
        return {"kind": "none", "strength": 0.0}
    # last two swing lows / highs in price, read the oscillator at the same bars
    def swings(kind: str) -> list[int]:
        out = []
        for i in range(start + pivot, n - pivot):
            win = prices[i - pivot:i + pivot + 1]
            if kind == "low" and prices[i] <= min(win):
                out.append(i)
            if kind == "high" and prices[i] >= max(win):
                out.append(i)
        # keep only alternating, spaced swings
        keep: list[int] = []
        for i in out:
            if not keep or i - keep[-1] > pivot * 2:
                keep.append(i)
        return keep

    osc_map = dict(osc_ok)
    lows, highs = swings("low"), swings("high")
    if len(lows) >= 2:
        a, b = lows[-2], lows[-1]
        if a in osc_map and b in osc_map and prices[b] < prices[a] and osc_map[b] > osc_map[a] + 1.0:
            return {"kind": "bull", "strength": clamp(0.45 + (osc_map[b] - osc_map[a]) / 40),
                    "span": (b - a), "price": prices[b]}
    if len(highs) >= 2:
        a, b = highs[-2], highs[-1]
        if a in osc_map and b in osc_map and prices[b] > prices[a] and osc_map[b] < osc_map[a] - 1.0:
            return {"kind": "bear", "strength": clamp(0.45 + (osc_map[a] - osc_map[b]) / 40),
                    "span": (b - a), "price": prices[b]}
    return {"kind": "none", "strength": 0.0}
