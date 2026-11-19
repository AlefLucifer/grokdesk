"""Regime classification and the routing table that follows from it.

The engine does not run one strategy. It asks what kind of tape this is, then
weights every family accordingly: mean-reversion families get louder in a
range, trend families get louder in a trend, and everything gets quieter when
the book thins out.
"""

from __future__ import annotations

from typing import Sequence

from . import config
from .indicators import (adx, atr, bollinger, clamp, ema, last, pct_rank, zscore)
from .types import Candle, Regime


def _slope_pct(series: Sequence[float | None], lookback: int = 10) -> float:
    vals = [v for v in series[-lookback:] if v is not None]
    if len(vals) < 3 or vals[0] == 0:
        return 0.0
    return (vals[-1] / vals[0] - 1.0) * 100.0


def classify(candles: Sequence[Candle], htf: Sequence[Candle] | None = None) -> Regime:
    if len(candles) < 60:
        return Regime("ILLIQUID", 0.2, config.REGIME_PLAYBOOK["ILLIQUID"],
                      notes=["not enough history to classify the regime"])
    closes = [c.c for c in candles]
    atr_s = atr(candles, 14)
    valid_atr = [v for v in atr_s[-150:] if v]
    cur_atr = last(atr_s) or (candles[-1].c * 0.004)
    ap = cur_atr / candles[-1].c * 100.0
    atr_rank = pct_rank(valid_atr, cur_atr) if valid_atr else 0.5
    _, _, _, bw = bollinger(closes, 20, 2.0)
    bw_valid = [v for v in bw[-150:] if v is not None]
    bw_now = last(bw) or 0.0
    bw_rank = pct_rank(bw_valid, bw_now) if bw_valid else 0.5

    adx_s, pdi_s, mdi_s = adx(candles, 14)
    adx_now = last(adx_s) or 0.0
    pdi, mdi = last(pdi_s) or 0.0, last(mdi_s) or 0.0

    vols = [c.v for c in candles[-30:]]
    vol_z = zscore(vols[:-1], candles[-1].v) if len(vols) > 3 else 0.0

    ref = htf if htf and len(htf) > 60 else candles
    ref_closes = [c.c for c in ref]
    e50 = ema(ref_closes, min(50, max(10, len(ref) // 4)))
    e200 = ema(ref_closes, min(150, max(30, len(ref) // 2)))
    slope = _slope_pct(ema(ref_closes, 21), 12)
    above = (last(e50) or ref_closes[-1]) > (last(e200) or ref_closes[-1])
    align = 1 if (slope > 0 and above) else -1 if (slope < 0 and not above) else 0

    notes: list[str] = []
    name = "RANGE"
    conf = 0.5

    if vol_z < -1.3 and atr_rank < 0.35:
        name, conf = "ILLIQUID", clamp(0.55 + abs(vol_z) / 6)
        notes.append(f"volume {vol_z:+.1f}σ below its 30-bar mean and range at the {atr_rank:.0%} percentile — thin tape")
    elif atr_rank > 0.85 or bw_rank > 0.90:
        name = "HIGH_VOL"
        conf = clamp(0.55 + max(atr_rank - 0.85, bw_rank - 0.90) * 2)
        notes.append(f"ATR at the {atr_rank:.0%} percentile and band width at the {bw_rank:.0%} — volatility is expanding")
    elif adx_now >= 24 and align != 0 and abs(slope) >= 0.10:
        name = "TREND_UP" if align > 0 else "TREND_DOWN"
        conf = clamp(0.45 + (adx_now - 24) / 50 + min(abs(slope) / 2, 0.25))
        notes.append(f"ADX {adx_now:.1f} with DI{'+/−' if pdi > mdi else '−/+'} {pdi:.1f}/{mdi:.1f} and a {slope:+.2f}% EMA slope on the higher timeframe")
    elif bw_rank < 0.28 and adx_now < 22:
        name = "SQUEEZE"
        conf = clamp(0.5 + (0.28 - bw_rank))
        notes.append(f"band width at the {bw_rank:.0%} percentile with ADX {adx_now:.1f} — compression before expansion")
    elif adx_now < 21:
        name = "RANGE"
        conf = clamp(0.45 + (21 - adx_now) / 30)
        notes.append(f"ADX {adx_now:.1f} and price chopping inside a {abs(slope):.2f}% drift — no trend to follow")
    else:
        name = "TREND_UP" if (slope >= 0 or pdi > mdi) else "TREND_DOWN"
        conf = 0.45
        notes.append(f"ADX {adx_now:.1f} is trending but the higher timeframe is not aligned — moderate conviction")

    if abs(vol_z) > 1.5:
        notes.append(f"the last bar traded {vol_z:+.1f}σ volume, so the current print is not a quiet one")

    conf = clamp(conf, 0.25, 0.95)
    return Regime(name, round(conf, 3), config.REGIME_PLAYBOOK[name],
                  adx=round(adx_now, 2), atr_pct=round(ap, 4),
                  atr_percentile=round(atr_rank, 3), volume_z=round(vol_z, 2),
                  bb_width_pct=round(bw_rank, 3), ema_slope=round(slope, 3),
                  notes=notes)


def family_weights(name: str) -> dict[str, float]:
    return config.REGIME_WEIGHTS.get(name, config.REGIME_WEIGHTS["RANGE"])


def tactics(name: str) -> dict:
    """Execution rules that change with the regime."""
    base = {
        "size_multiplier": 1.0,
        "prefer_limit": True,
        "allow_breakout_chase": False,
        "min_rr": 1.6,
        "ttl_bars": config.SIGNAL_TTL_BARS,
        "require_discount": False,
    }
    if name in ("TREND_UP", "TREND_DOWN"):
        base.update(size_multiplier=1.0, min_rr=1.8, require_discount=True, ttl_bars=8)
    elif name == "RANGE":
        base.update(size_multiplier=0.9, min_rr=1.5, ttl_bars=5)
    elif name == "HIGH_VOL":
        base.update(size_multiplier=0.6, min_rr=2.0, ttl_bars=4, prefer_limit=True)
    elif name == "SQUEEZE":
        base.update(size_multiplier=0.85, min_rr=2.0, ttl_bars=6)
    elif name == "ILLIQUID":
        base.update(size_multiplier=0.35, min_rr=2.5, ttl_bars=3)
    return base


def mtf_agreement(candles_by_tf: dict[str, list[Candle]], base_tf: str) -> tuple[float, dict[str, int]]:
    """Directional read of every higher timeframe, weighted by distance from
    the traded one. Returns (-1..1, {tf: dir})."""
    reads: dict[str, int] = {}
    score = 0.0
    total = 0.0
    for i, tf in enumerate(config.HTF_CHAIN.get(base_tf, ())):
        series = candles_by_tf.get(tf) or []
        if len(series) < 30:
            continue
        closes = [c.c for c in series]
        fast = last(ema(closes, 21)) or closes[-1]
        slow = last(ema(closes, 50)) or closes[-1]
        direction = 1 if fast > slow * 1.0005 else -1 if fast < slow * 0.9995 else 0
        reads[tf] = direction
        w = 1.0 / (i + 1)
        score += direction * w
        total += w
    return (score / total if total else 0.0), reads


def macro_risk(macro, symbol: str) -> list[dict]:
    """BTC, USDT.D and DXY as evidence for anything that is not BTC."""
    out: list[dict] = []
    is_btc = symbol.upper().startswith("BTC")
    if not is_btc:
        d = 1 if macro.btc_trend > 0.15 else -1 if macro.btc_trend < -0.15 else 0
        out.append({
            "code": "btc_bias", "family": "MACRO", "direction": d,
            "weight": 0.6, "strength": clamp(abs(macro.btc_trend) + 0.2),
            "note": f"BTC {macro.btc_change_24h:+.1f}% in 24h and {macro.btc_trend:+.2f} trend score — "
                    f"{'the tide is with the alts' if d > 0 else 'alts are swimming against BTC' if d < 0 else 'BTC is flat, no macro tailwind'}",
            "ref": {},
        })
    d_usdt = -1 if macro.usdt_dom_change > 0.08 else 1 if macro.usdt_dom_change < -0.08 else 0
    out.append({
        "code": "usdt_d", "family": "MACRO", "direction": d_usdt,
        "weight": 0.4, "strength": clamp(abs(macro.usdt_dom_change) * 3 + 0.2),
        "note": f"USDT dominance {macro.usdt_dominance:.2f}% ({macro.usdt_dom_change:+.2f} pp) — "
                f"{'money parked in stablecoins, risk off' if d_usdt < 0 else 'stablecoin money rotating into coins, risk on' if d_usdt > 0 else 'no rotation'}",
        "ref": {},
    })
    if macro.dxy is not None:
        d_dxy = -1 if macro.dxy_change > 0.10 else 1 if macro.dxy_change < -0.10 else 0
        out.append({
            "code": "dxy", "family": "MACRO", "direction": d_dxy,
            "weight": 0.35, "strength": clamp(abs(macro.dxy_change) * 2 + 0.2),
            "note": f"DXY {macro.dxy:.2f} ({macro.dxy_change:+.2f}%) — "
                    f"{'dollar bid is a headwind for crypto' if d_dxy < 0 else 'dollar offered is a tailwind' if d_dxy > 0 else 'dollar flat'}",
            "ref": {},
        })
    return out
