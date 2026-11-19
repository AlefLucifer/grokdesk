"""Walk-forward validation.

The win-rate on the card should not be a number a model liked. This replays the
engine bar by bar on the same data source, takes only the signals it would have
published, and measures how often TP1 printed before the stop. The measured hit
rate then calibrates the probability mapping per regime.

Everything is lookahead-safe on price: each analysis only sees candles up to the
decision bar. Derivatives, sentiment and macro are held at their latest values,
which is the honest limit of a snapshot-based engine and is stated in the docs.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from typing import Sequence

from .confluence import calibrate_from_backtest
from .types import Candle, Snapshot


@dataclass
class _Trade:
    ts: int
    symbol: str
    tf: str
    regime: str
    session: str
    family: str
    prob: float
    rr: float
    r: float
    win: bool
    timeout: bool


def slice_snapshot(snap: Snapshot, cutoff_ts: int, window: int = 260) -> Snapshot:
    series: dict[str, list[Candle]] = {}
    for tf, candles in snap.candles.items():
        cut = [c for c in candles if c.ts <= cutoff_ts]
        if not cut:
            continue
        n = window if tf == snap.tf else max(120, window // 3)
        series[tf] = cut[-n:]
    return Snapshot(symbol=snap.symbol, tf=snap.tf, candles=series,
                    derivatives=snap.derivatives, sentiment=snap.sentiment,
                    macro=snap.macro, source=snap.source, as_of=cutoff_ts)


def _simulate(candles: Sequence[Candle], i: int, action: str, entry: float, sl: float,
              tp1: float, horizon: int) -> tuple[float, bool, bool]:
    """Returns (R at TP1-or-stop, won, timed out). Conservative: if a single bar
    touches both levels, the stop is assumed first."""
    side = 1 if action == "LONG" else -1
    R = abs(entry - sl)
    if R <= 0:
        return 0.0, False, True
    end = min(len(candles) - 1, i + horizon)
    for j in range(i + 1, end + 1):
        c = candles[j]
        hit_sl = c.l <= sl if side > 0 else c.h >= sl
        hit_tp = c.h >= tp1 if side > 0 else c.l <= tp1
        if hit_sl and hit_tp:
            return -1.0, False, False
        if hit_sl:
            return -1.0, False, False
        if hit_tp:
            return abs(tp1 - entry) / R, True, False
    exit_px = candles[end].c
    return (exit_px - entry) * side / R, False, True


def _top_family(card) -> str:
    if not card.evidence:
        return "n/a"
    side = 1 if card.action == "LONG" else -1
    fams: dict[str, float] = {}
    for e in card.evidence:
        if e.direction == side:
            fams[e.family] = fams.get(e.family, 0.0) + abs(e.signed)
    return max(fams, key=fams.get) if fams else "n/a"


def run(snap: Snapshot, engine, *, horizon: int = 24, stride: int | None = None,
        warmup: int = 140, max_steps: int = 450, min_prob: float = 0.55,
        window: int = 260) -> dict:
    candles = snap.series(snap.tf)
    n = len(candles)
    if n < warmup + horizon + 10:
        return {"trades": 0, "error": "not enough history for a walk-forward"}
    stride = stride or max(1, n // max_steps)
    trades: list[_Trade] = []
    analysed = 0
    for i in range(warmup, n - 1, stride):
        sub = slice_snapshot(snap, candles[i].ts, window)
        if len(sub.series()) < 80 or len(sub.candles) == 0:
            continue
        try:
            card = engine.analyse(sub)
        except Exception:
            continue
        analysed += 1
        if card.action == "WAIT" or card.probability < min_prob:
            continue
        plan = card.plan
        # a limit order has to be reached within three bars to count
        reached = True
        p = plan.entry
        if plan.order_type == "Limit":
            reached = any((c.l <= p if card.action == "LONG" else c.h >= p)
                          for c in candles[i + 1:i + 4])
        if not reached:
            continue
        r, win, timeout = _simulate(candles, i, card.action, plan.entry, plan.sl,
                                    plan.tp1, horizon)
        trades.append(_Trade(candles[i].ts, card.symbol, card.tf, card.regime.name,
                             card.session, _top_family(card), card.probability,
                             plan.rr, r, win, timeout))

    return _summarise(trades, analysed)


def _bucket(trades: Sequence[_Trade]) -> dict:
    n = len(trades)
    if not n:
        return {"trades": 0}
    wins = [t for t in trades if t.win]
    rs = [t.r for t in trades]
    gross_win = sum(r for r in rs if r > 0)
    gross_loss = -sum(r for r in rs if r < 0)
    return {
        "trades": n,
        "hit_rate": round(len(wins) / n, 4),
        "mean_r": round(sum(rs) / n, 3),
        "expectancy_r": round(sum(rs) / n, 3),
        "profit_factor": round(gross_win / gross_loss, 2) if gross_loss else None,
        "mean_p": round(sum(t.prob for t in trades) / n, 4),
        "timeouts": sum(1 for t in trades if t.timeout),
    }


def _group(trades: Sequence[_Trade], key) -> dict:
    groups: dict[str, list[_Trade]] = {}
    for t in trades:
        groups.setdefault(key(t), []).append(t)
    return {k: _bucket(v) for k, v in sorted(groups.items(), key=lambda kv: -len(kv[1]))}


def _summarise(trades: list[_Trade], analysed: int) -> dict:
    overall = _bucket(trades)
    out = {
        "analysed": analysed,
        "trades": len(trades),
        **overall,
        "by_regime": _group(trades, lambda t: t.regime),
        "by_session": _group(trades, lambda t: t.session),
        "by_family": _group(trades, lambda t: t.family),
        "by_symbol": _group(trades, lambda t: t.symbol),
    }
    if trades:
        out["elo"] = round(1000 + 400 * math.tanh((overall["hit_rate"] - 0.5) * 4), 0)
    return out


def calibrate(results: dict[str, dict]) -> dict:
    """`results` is regime -> bucket, straight from run()["by_regime"]."""
    return calibrate_from_backtest({
        k: {"hit_rate": v.get("hit_rate", 0.5), "mean_p": v.get("mean_p", 0.5)}
        for k, v in results.items() if v.get("trades", 0) >= 15
    })


def write_calibration(cal: dict, path: str | None = None) -> str:
    path = path or os.path.join(os.path.dirname(__file__), "..", "config", "calibration.json")
    path = os.path.abspath(path)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"generated_at": __import__("time").time(), **cal}, fh, indent=2)
    return path


def format_report(res: dict) -> str:
    if res.get("error"):
        return res["error"]
    if not res.get("trades"):
        return (f"walk-forward: {res.get('analysed', 0)} bars analysed, no signal cleared the gates. "
                "That is a result, not a failure — the engine is allowed to stand aside.")
    lines = [
        f"walk-forward · {res['analysed']} bars analysed · {res['trades']} trades taken",
        f"  TP1-before-SL hit rate : {res['hit_rate']:.1%}   (model said {res['mean_p']:.1%})",
        f"  expectancy             : {res['mean_r']:+.2f} R per trade",
        f"  profit factor          : {res['profit_factor']}",
        f"  timeouts               : {res['timeouts']}",
    ]
    for title, key in (("regime", "by_regime"), ("session", "by_session"), ("lead family", "by_family")):
        lines.append(f"  by {title}:")
        for name, b in list(res[key].items())[:8]:
            lines.append(f"    {name:<12} n={b['trades']:<4} hit {b.get('hit_rate', 0):.0%} "
                         f"exp {b.get('mean_r', 0):+.2f}R pf {b.get('profit_factor')}")
    return "\n".join(lines)
