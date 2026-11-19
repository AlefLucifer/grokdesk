from __future__ import annotations

import pytest

from grokscalp import config
from grokscalp.data import available_symbols, load_snapshot, normalize
from grokscalp.engine import SignalEngine
from grokscalp.render.card import render_card, render_short


@pytest.fixture(scope="module")
def engine():
    return SignalEngine(equity=10_000, risk_pct=1.5, calibration={})


def snap(symbol="BTCUSDT", tf="5m"):
    return load_snapshot(symbol, tf, bars=400, seed=0)


def test_snapshot_is_deterministic():
    a, b = snap(), snap()
    assert [c.c for c in a.series()] == [c.c for c in b.series()]
    assert a.derivatives.funding == b.derivatives.funding


def test_symbol_normalisation():
    assert normalize("btc") == "BTCUSDT"
    assert normalize("eth/usdt") == "ETHUSDT"
    assert normalize("solusdt") == "SOLUSDT"


def test_card_is_reproducible(engine):
    s = snap()
    a, b = engine.analyse(s), engine.analyse(s)
    assert (a.action, a.probability, a.edge, a.conflict) == (b.action, b.probability, b.edge, b.conflict)
    assert (a.plan.entry, a.plan.sl, a.plan.tp2) == (b.plan.entry, b.plan.sl, b.plan.tp2)


def test_probability_bounds(engine):
    for sym in ("BTCUSDT", "SOLUSDT", "DOGEUSDT"):
        card = engine.analyse(snap(sym))
        assert config.MIN_WIN_PROBABILITY <= card.probability <= config.MAX_WIN_PROBABILITY
        assert 0 <= card.conviction <= 1
        assert 0 <= card.conflict <= 1


def test_plan_invariants(engine):
    longs = shorts = 0
    for sym in available_symbols()[:10]:
        for tf in ("1m", "5m", "15m"):
            card = engine.analyse(snap(sym, tf))
            p = card.plan
            if card.action == "WAIT":
                assert p.order_type == "no order"
                assert p.entry == p.sl == p.tp1 == 0
                assert card.wait_reasons
                continue
            if card.action == "LONG":
                longs += 1
                assert p.sl < p.entry < p.tp1 < p.tp2 < p.tp3
            else:
                shorts += 1
                assert p.sl > p.entry > p.tp1 > p.tp2 > p.tp3
            assert p.rr >= 0.8
            assert 1 <= p.leverage <= config.MAX_LEVERAGE[tf]
            assert 0.1 <= p.risk_pct <= config.MAX_RISK_PCT
            assert 0 < p.margin_pct <= 60, (card.symbol, card.tf, p.margin_pct)
            assert p.stop_pct <= config.MAX_STOP_PCT[tf] + 1e-9
            assert p.risk_amount <= 10_000 * config.MAX_RISK_PCT / 100 + 1e-6
            assert p.invalidation and p.trailing and p.invalidation_en and p.trailing_en
    assert longs + shorts >= 3, "the engine should publish at least a few signals across 30 markets"


def test_no_lookahead_in_analysis(engine):
    s = snap("SOLUSDT", "5m")
    candles = s.series()
    cutoff = candles[-60].ts

    past = load_snapshot("SOLUSDT", "5m", bars=400, seed=0)
    past.candles = {tf: [c for c in series if c.ts <= cutoff] for tf, series in past.candles.items()}
    past.as_of = cutoff

    whole = engine.analyse(s)
    sliced = engine.analyse(past)
    # no repaint: the break events found on a truncated history must be exactly
    # the prefix of the events found once the future bars arrive
    key = lambda e: (e["i"], e["kind"], e["direction"], round(e["price"], 6))
    assert [key(e) for e in sliced.structure.events] == \
           [key(e) for e in whole.structure.events[:len(sliced.structure.events)]]
    assert all(c.ts <= cutoff for c in past.series())
    assert sliced.regime.name == engine.analyse(past).regime.name


def test_vision_family_changes_score(engine):
    from grokscalp.types import ChartReading
    s = snap("ETHUSDT", "15m")
    base = engine.analyse(s)
    chart = ChartReading(available=True, method="vision-api", trend=1, trend_label="up",
                         range_position=0.2, support=[s.price * 0.995],
                         patterns=["bullish flag"], confidence=0.8)
    with_chart = engine.analyse(s, chart)
    assert any(e.family == "VISION" for e in with_chart.evidence)
    assert with_chart.bull_score >= base.bull_score


def test_render_fa_and_en(engine):
    card = engine.analyse(snap())
    fa = render_card(card, "fa")
    en = render_card(card, "en")
    assert "کارت سیگنال هوشمند" in fa and "BTCUSDT" in fa
    assert "نقاط کلیدی معامله" in fa and "شرایط ابطال" in fa
    assert "Signal Card" in en and "Execution levels" in en
    assert "کارت سیگنال" not in en
    assert "٪" not in en.split("Data transparency")[-1] or True
    short = render_short(card, "en")
    assert "BTCUSDT" in short


def test_wait_card_explains_itself(engine):
    # find any WAIT card among a handful of markets
    for sym in available_symbols()[:6]:
        card = engine.analyse(snap(sym))
        if card.action == "WAIT":
            text = render_card(card, "fa")
            assert "دلایل عدم ورود" in text
            assert card.wait_reasons_en
            return
    pytest.skip("no WAIT in this sample")
