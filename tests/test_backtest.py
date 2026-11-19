from __future__ import annotations

from grokscalp.backtest import _simulate, calibrate, format_report, run, slice_snapshot
from grokscalp.data import load_snapshot
from grokscalp.engine import SignalEngine
from grokscalp.types import Candle


def mk(o, h, l, c):
    return Candle(ts=0, o=o, h=h, l=l, c=c, v=1, tb=0.5)


def test_simulate_long_hits_tp():
    candles = [mk(100, 100, 100, 100), mk(100, 108, 99, 107)]
    r, win, timeout = _simulate(candles, 0, "LONG", 100, 98, 106, horizon=5)
    assert win and not timeout and r > 0


def test_simulate_long_hits_stop():
    candles = [mk(100, 100, 100, 100), mk(100, 101, 97, 98)]
    r, win, timeout = _simulate(candles, 0, "LONG", 100, 98, 106, horizon=5)
    assert not win and r == -1


def test_simulate_stop_wins_ties():
    candles = [mk(100, 100, 100, 100), mk(100, 108, 97, 100)]
    r, win, _ = _simulate(candles, 0, "LONG", 100, 98, 106, horizon=5)
    assert not win and r == -1


def test_simulate_short_hits_tp():
    candles = [mk(100, 100, 100, 100), mk(100, 100, 93, 94)]
    r, win, _ = _simulate(candles, 0, "SHORT", 100, 102, 94, horizon=5)
    assert win and r > 0


def test_slice_never_sees_the_future():
    snap = load_snapshot("BTCUSDT", "5m", bars=500)
    cutoff = snap.series()[-100].ts
    sliced = slice_snapshot(snap, cutoff, window=200)
    assert sliced.series()[-1].ts == cutoff
    assert all(c.ts <= cutoff for series in sliced.candles.values() for c in series)
    assert len(sliced.series()) <= 200


def test_walk_forward_runs_and_reports():
    snap = load_snapshot("BTCUSDT", "5m", bars=700)
    res = run(snap, SignalEngine(calibration={}), horizon=18, max_steps=70, min_prob=0.55)
    assert res["analysed"] > 0
    assert "by_regime" in res
    text = format_report(res)
    assert "walk-forward" in text
    if res.get("trades"):
        assert 0 <= res["hit_rate"] <= 1
        assert isinstance(calibrate(res["by_regime"]), dict)


def test_calibration_offsets_are_bounded():
    cal = calibrate({"RANGE": {"trades": 100, "hit_rate": 0.20, "mean_p": 0.70},
                     "TREND_UP": {"trades": 4, "hit_rate": 0.9, "mean_p": 0.5}})
    assert cal["offset"]["RANGE"] == -0.08
    assert "TREND_UP" not in cal["offset"]
