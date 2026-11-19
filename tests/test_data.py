from __future__ import annotations

import pytest

from grokscalp.data import load_snapshot
from grokscalp.data.synthetic import gen_candles, gen_derivatives


def test_multitimeframe_last_price_matches():
    snap = load_snapshot("BTCUSDT", "5m", bars=300, seed=7)
    base = snap.series()[-1].c
    for tf, series in snap.candles.items():
        assert series, tf
        assert abs(series[-1].c / base - 1) < 0.02, tf


def test_candles_are_valid_ohlc():
    candles = gen_candles("ETHUSDT", "1m", 300, seed=3)
    assert len(candles) == 300
    for c in candles:
        assert c.l <= min(c.o, c.c) <= max(c.o, c.c) <= c.h
        assert c.v > 0 and 0 <= c.tb <= c.v * 1.0000001
        assert c.ts > 0


def test_derivatives_follow_the_tape():
    candles = gen_candles("SOLUSDT", "5m", 400, seed=1)
    d = gen_derivatives(candles, "SOLUSDT", seed=1)
    assert len(d.oi_history) == 30 and d.oi > 0
    assert len(d.funding_history) == 30
    assert d.orderbook.bids and d.orderbook.asks
    assert d.orderbook.best_bid < d.orderbook.best_ask
    assert d.liquidations and all(b.notional > 0 for b in d.liquidations)
    assert len(d.cvd) == len(candles)
    assert -1 <= d.obi <= 1
    assert d.whales and all(w.notional > 0 and w.side in ("buy", "sell") for w in d.whales)


def test_sentiment_and_macro_present():
    snap = load_snapshot("XRPUSDT", "15m", seed=2)
    s, m = snap.sentiment, snap.macro
    assert 0 <= s.fear_greed <= 100
    assert s.fear_greed_label
    assert s.headlines
    assert s.events and s.events[0].minutes_away >= 0
    assert -1 <= m.btc_trend <= 1
    assert m.btc_dominance > 0 and m.usdt_dominance > 0
    assert m.dxy is not None


def test_unknown_symbol_gets_a_price():
    snap = load_snapshot("WIFUSDT", "5m", bars=300)
    assert snap.price > 0
    assert snap.symbol == "WIFUSDT"


def test_live_falls_back_instead_of_raising(monkeypatch):
    # no network in tests: the loader must degrade to synthetic, not explode
    from grokscalp.data import binance

    def boom(*a, **k):
        raise binance.DataError("offline")

    monkeypatch.setattr(binance, "_klines", boom)
    snap = load_snapshot("BTCUSDT", "5m", live=True, bars=300)
    assert "synthetic" in snap.source


@pytest.mark.parametrize("tf", ["1m", "3m", "5m", "15m", "30m", "1h", "4h"])
def test_every_timeframe_generates(tf):
    snap = load_snapshot("BTCUSDT", tf, bars=300)
    assert len(snap.series()) == 300
    assert snap.series()[-1].c > 0


def test_fixture_roundtrip(tmp_path):
    from grokscalp.data import fixture

    snap = load_snapshot("SOLUSDT", "5m", bars=260, seed=5)
    path = fixture.dump(snap, tmp_path / "snap.json")
    again = fixture.load(path)
    assert again.symbol == snap.symbol and again.tf == snap.tf
    assert len(again.series()) == len(snap.series())
    assert again.series()[-1].c == pytest.approx(snap.series()[-1].c)
    assert again.derivatives.funding == pytest.approx(snap.derivatives.funding)
    assert again.sentiment.fear_greed == snap.sentiment.fear_greed
    assert again.macro.btc_dominance == pytest.approx(snap.macro.btc_dominance)


def test_fixture_from_raw_api_payloads():
    from grokscalp.data.fixture import from_api

    rows = [[1795000000000 + i * 300000, 100 + i * 0.1, 100.4 + i * 0.1,
             99.8 + i * 0.1, 100.2 + i * 0.1, 10 + i, 0, 0, 10, 5 + i * 0.5, 0, 0]
            for i in range(100)]
    snap = from_api(symbol="btcusdt", tf="5m", klines=rows,
                    funding={"lastFundingRate": "0.00012"},
                    open_interest={"openInterest": "12345"},
                    depth={"bids": [["99.9", "2"]], "asks": [["100.0", "1"]]},
                    fng={"data": [{"value": "23", "value_classification": "Fear"}]},
                    glob={"data": {"market_cap_percentage": {"btc": 57.1, "usdt": 4.9}}})
    assert snap.symbol == "BTCUSDT"
    assert snap.derivatives.funding == pytest.approx(0.00012)
    assert snap.derivatives.orderbook.best_bid == pytest.approx(99.9)
    assert snap.sentiment.fear_greed == 23
    assert snap.macro.btc_dominance == pytest.approx(57.1)
    assert snap.derivatives.cvd
