from __future__ import annotations

from grokscalp.structure import (analyse_structure, break_events, fair_value_gaps,
                                 liquidity_pools, order_blocks, swing_pivots, zigzag)
from grokscalp.types import Candle


def mk(prices, vol=100.0, start=0):
    out = []
    for i, p in enumerate(prices):
        o = prices[i - 1] if i else p
        out.append(Candle(ts=(start + i) * 60_000, o=o, h=max(o, p) * 1.0005,
                          l=min(o, p) * 0.9995, c=p, v=vol, tb=vol * 0.56))
    return out


def test_swings_on_clean_zigzag():
    prices = [100, 101, 102, 103, 104, 103, 102, 101, 100, 99, 100, 101, 102]
    piv = swing_pivots(mk(prices), k=2)
    highs = [p.price for p in piv if p.kind == "H"]
    lows = [p.price for p in piv if p.kind == "L"]
    assert highs and lows
    assert max(highs) == 104.0012 or abs(max(highs) - 104) < 0.1
    assert min(lows) < 100


def test_break_events_detect_bullish_bos():
    # rally, pullback, then a close through the prior swing high
    prices = [100, 101, 102, 103, 104, 103.2, 102.4, 102.8, 103.5, 104.8, 105.5]
    cs = mk(prices)
    piv = swing_pivots(cs, 2)
    ev = break_events(cs, piv, 2)
    assert any(e["direction"] == 1 for e in ev)


def test_break_events_detect_bearish_choch():
    prices = [100, 101, 102, 103, 104, 105, 104.5, 104, 103.5, 104, 105,
              105.5, 105, 104, 103, 102, 101, 100, 99, 98]
    cs = mk(prices)
    ev = break_events(cs, swing_pivots(cs, 2), 2)
    assert any(e["direction"] == -1 for e in ev)
    assert any(e["kind"] == "CHoCH" for e in ev)


def test_fair_value_gap_is_found():
    # bar 0 high 100, bar 2 low 103 -> bullish imbalance between 100 and 103
    cs = [
        Candle(0, 99, 100.0, 98.9, 99.5, 10, 5),
        Candle(60_000, 99.5, 103.5, 99.4, 103.2, 40, 30),
        Candle(120_000, 103.2, 104.5, 103.0, 104.0, 20, 12),
    ] + [Candle((3 + i) * 60_000, 104 + i * 0.1, 104.2 + i * 0.1, 103.9 + i * 0.1, 104 + i * 0.1, 10, 5)
         for i in range(5)]
    bull, bear = fair_value_gaps(cs)
    assert bull, "expected a bullish FVG"
    assert bull[-1].lo < bull[-1].hi
    assert not bear


def test_order_blocks_need_displacement():
    cs = mk([100.0] * 12)
    ts = 20 * 60_000
    cs.append(Candle(ts, o=101.0, h=101.05, l=100.2, c=100.3, v=20, tb=8))          # last red candle
    cs.append(Candle(ts + 60_000, o=100.3, h=104.0, l=100.25, c=103.8, v=100, tb=72))  # displacement
    bull, _ = order_blocks(cs, atr_v=0.5)
    assert bull, "displacement after a red candle should leave a bullish order block"
    assert bull[0].lo < bull[0].hi


def test_liquidity_pools_have_range_extremes():
    prices = [100 + (i % 7) for i in range(60)]
    cs = mk(prices)
    pools = liquidity_pools(cs, swing_pivots(cs, 2), atr_v=0.4)
    notes = " ".join(p.note for p in pools)
    assert "range high" in notes and "range low" in notes


def test_analyse_structure_smoke():
    import math
    prices = [100 * (1 + 0.002 * i) + math.sin(i / 3) for i in range(150)]
    cs = mk(prices)
    st = analyse_structure(cs, atr_v=0.6, k=2)
    assert st.range_high > st.range_low
    assert 0 <= st.premium_discount <= 1
    assert st.order_blocks or st.fvgs
    assert st.trend in (-1, 0, 1)


def test_zigzag_alternates():
    import math
    prices = [100 + 10 * math.sin(i / 6) for i in range(120)]
    z = zigzag(mk(prices), 2)
    assert len(z) >= 3
    kinds = [p.kind for p in z]
    assert all(kinds[i] != kinds[i + 1] for i in range(len(kinds) - 1))
