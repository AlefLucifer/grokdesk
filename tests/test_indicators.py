from __future__ import annotations

import math

import pytest

from grokscalp import indicators as ind
from grokscalp.types import Candle


def candles_from_closes(closes, vol=100.0):
    out = []
    for i, c in enumerate(closes):
        o = closes[i - 1] if i else c
        out.append(Candle(ts=i * 60_000, o=o, h=max(o, c) * 1.001, l=min(o, c) * 0.999,
                          c=c, v=vol, tb=vol * 0.55))
    return out


def test_sma_ema_alignment():
    vals = [float(i) for i in range(50)]
    s = ind.sma(vals, 5)
    e = ind.ema(vals, 5)
    assert len(s) == len(vals) == len(e)
    assert s[:4] == [None] * 4
    assert s[-1] == pytest.approx(47.0)
    assert e[-1] > 40 and e[-1] < 50


def test_rsi_bounds_and_direction():
    up = [100 + i for i in range(60)]
    down = [200 - i for i in range(60)]
    r_up = ind.rsi(up, 14)
    r_dn = ind.rsi(down, 14)
    assert r_up[-1] == pytest.approx(100.0)
    assert r_dn[-1] == pytest.approx(0.0)
    assert all(0 <= v <= 100 for v in r_up if v is not None)


def test_atr_positive_and_warmup():
    cs = candles_from_closes([100 + math.sin(i / 3) for i in range(40)])
    a = ind.atr(cs, 14)
    assert a[10] is None
    assert a[-1] and a[-1] > 0


def test_macd_shapes():
    cs = candles_from_closes([100 * (1.01 ** (i % 7)) for i in range(120)])
    line, sig, hist = ind.macd([c.c for c in cs])
    assert len(line) == len(sig) == len(hist) == 120
    assert hist[-1] is not None


def test_bollinger_order():
    cs = candles_from_closes([100 + (i % 5) for i in range(60)])
    mid, up, lo, width = ind.bollinger([c.c for c in cs])
    assert lo[-1] < mid[-1] < up[-1]
    assert width[-1] > 0


def test_volume_profile_contains_price():
    cs = candles_from_closes([100 + math.sin(i / 4) * 2 for i in range(120)], vol=50)
    vp = ind.volume_profile(cs, bins=20)
    lo = min(c.l for c in cs)
    hi = max(c.h for c in cs)
    assert lo <= vp["val"] <= vp["poc"] <= vp["vah"] <= hi
    assert len(vp["rows"]) == 20
    assert sum(v for _, v in vp["rows"]) == pytest.approx(sum(c.v for c in cs))


def test_adx_in_range():
    cs = candles_from_closes([100 * (1 + 0.001 * i) for i in range(80)])
    a, pdi, mdi = ind.adx(cs, 14)
    assert a[-1] is not None and 0 <= a[-1] <= 100
    assert pdi[-1] is not None and mdi[-1] is not None


def test_ichimoku_cloud_ordering():
    cs = candles_from_closes([100 + (i % 9) for i in range(120)])
    ich = ind.ichimoku(cs)
    top, bot = ich["cloud_top"], ich["cloud_bottom"]
    assert top[-1] >= bot[-1]
    assert ich["tenkan"][-1] is not None


def test_cvd_matches_delta_sum():
    cs = candles_from_closes([100, 101, 100.5, 102], vol=10)
    series = ind.cvd(cs)
    assert series[-1] == pytest.approx(sum(c.delta for c in cs))


def test_divergence_no_crash_on_flat_series():
    flat = [100.0] * 80
    out = ind.divergence(flat, [50.0] * 80)
    assert out["kind"] in ("none", "bull", "bear")
