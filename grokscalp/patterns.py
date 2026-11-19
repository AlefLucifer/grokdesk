"""Candles, harmonics, VSA/Wyckoff and the classic chart patterns.

Patterns are confirmation, never the reason for a trade: they carry a low
family reliability and are only counted when a level or structure agrees.
Each detector returns plain dicts so the engine can attach them as evidence
without knowing what produced them.
"""

from __future__ import annotations

from typing import Sequence

from .indicators import clamp, mean, stdev
from .structure import Pivot
from .types import Candle


def _pattern(code: str, name: str, direction: int, strength: float, note: str) -> dict:
    return {"code": code, "name": name, "direction": direction,
            "strength": clamp(strength), "note": note}


# --------------------------------------------------------------------------
# candlesticks
# --------------------------------------------------------------------------

def candle_patterns(candles: Sequence[Candle], atr_v: float) -> list[dict]:
    if len(candles) < 5 or atr_v <= 0:
        return []
    out: list[dict] = []
    c, p, pp = candles[-1], candles[-2], candles[-3]
    rng = c.range
    body = c.body
    vol_mean = mean([x.v for x in candles[-20:-1]]) or 1.0
    vol_z = c.v / vol_mean - 1.0

    if c.bull and not p.bull and c.c > p.o and c.o <= p.c and body > p.body * 1.1:
        out.append(_pattern("engulf_bull", "bullish engulfing", 1,
                            0.55 + min(0.3, body / atr_v / 4),
                            f"body {body / atr_v:.1f} ATR engulfs the prior red candle, volume {vol_z:+.0%} vs 20-bar mean"))
    if (not c.bull) and p.bull and c.c < p.o and c.o >= p.c and body > p.body * 1.1:
        out.append(_pattern("engulf_bear", "bearish engulfing", -1,
                            0.55 + min(0.3, body / atr_v / 4),
                            f"body {body / atr_v:.1f} ATR engulfs the prior green candle, volume {vol_z:+.0%} vs 20-bar mean"))

    if body <= rng * 0.35 and c.lower_wick >= max(body, rng * 0.45) and c.upper_wick <= rng * 0.2:
        out.append(_pattern("hammer", "hammer / rejection wick", 1,
                            0.45 + min(0.3, c.lower_wick / atr_v / 3),
                            f"lower wick {c.lower_wick / atr_v:.1f} ATR rejected, close back in the top third"))
    if body <= rng * 0.35 and c.upper_wick >= max(body, rng * 0.45) and c.lower_wick <= rng * 0.2:
        out.append(_pattern("star", "shooting star / rejection wick", -1,
                            0.45 + min(0.3, c.upper_wick / atr_v / 3),
                            f"upper wick {c.upper_wick / atr_v:.1f} ATR sold, close back in the bottom third"))

    if body <= rng * 0.12 and rng > atr_v * 0.5:
        out.append(_pattern("doji", "doji / indecision", 0, 0.3,
                            "open and close nearly equal after a real range — the auction found no side"))
    if c.h <= p.h and c.l >= p.l:
        out.append(_pattern("inside", "inside bar compression", 0, 0.3,
                            "range inside the prior bar; expansion usually follows the break"))

    if (not pp.bull) and pp.body > atr_v * 0.5 and p.body < pp.body * 0.4 \
            and c.bull and c.c > (pp.o + pp.c) / 2:
        out.append(_pattern("morning_star", "morning star", 1, 0.6,
                            "three-bar reversal: capitulation, pause, strong reclaim"))
    if pp.bull and pp.body > atr_v * 0.5 and p.body < pp.body * 0.4 \
            and (not c.bull) and c.c < (pp.o + pp.c) / 2:
        out.append(_pattern("evening_star", "evening star", -1, 0.6,
                            "three-bar reversal: exhaustion, pause, strong rejection"))

    last3 = candles[-3:]
    if all(x.bull for x in last3) and all(last3[i].c > last3[i - 1].c for i in (1, 2)) \
            and all(x.body > atr_v * 0.3 for x in last3):
        out.append(_pattern("three_soldiers", "three white soldiers", 1, 0.55,
                            "three consecutive expanding green closes — aggressive demand"))
    if all(not x.bull for x in last3) and all(last3[i].c < last3[i - 1].c for i in (1, 2)) \
            and all(x.body > atr_v * 0.3 for x in last3):
        out.append(_pattern("three_crows", "three black crows", -1, 0.55,
                            "three consecutive expanding red closes — aggressive supply"))
    return out


# --------------------------------------------------------------------------
# harmonic patterns
# --------------------------------------------------------------------------

_HARMONICS = {
    "Gartley":   {"ab": (0.55, 0.68), "bc": (0.35, 0.90), "cd": (1.10, 1.70), "xd": (0.72, 0.88)},
    "Bat":       {"ab": (0.38, 0.52), "bc": (0.35, 0.90), "cd": (1.50, 2.70), "xd": (0.84, 0.92)},
    "Butterfly": {"ab": (0.74, 0.82), "bc": (0.35, 0.90), "cd": (1.55, 2.30), "xd": (1.22, 1.68)},
    "Crab":      {"ab": (0.35, 0.65), "bc": (0.35, 0.90), "cd": (2.20, 3.70), "xd": (1.55, 1.68)},
    "Shark":     {"ab": (0.35, 0.65), "bc": (1.10, 1.95), "cd": (0.80, 1.15), "xd": (0.85, 1.15)},
}


def harmonic_patterns(zz: Sequence[Pivot], atr_v: float) -> list[dict]:
    if len(zz) < 5:
        return []
    x, a, b, c, d = zz[-5:]
    if not (x.kind == a.kind == b.kind == c.kind == d.kind):
        # zigzag alternates, so five consecutive points must alternate
        pass
    xa = abs(a.price - x.price)
    ab = abs(b.price - a.price)
    bc = abs(c.price - b.price)
    cd = abs(d.price - c.price)
    xd = abs(d.price - x.price)
    if min(xa, ab, bc, cd) <= 0:
        return []
    ratios = {"ab": ab / xa, "bc": bc / ab, "cd": cd / bc, "xd": xd / xa}
    best: dict | None = None
    for name, rules in _HARMONICS.items():
        score = 0.0
        for key, (lo, hi) in rules.items():
            v = ratios[key]
            if lo <= v <= hi:
                score += 0.25
            else:
                dist = min(abs(v - lo), abs(v - hi))
                score += max(0.0, 0.25 - dist * 0.5)
        if score >= 0.78 and (best is None or score > best["score"]):
            best = {"name": name, "score": score}
    if not best:
        return []
    direction = 1 if d.price < c.price else -1      # D low = bullish reversal
    return [_pattern(
        "harmonic", f"{best['name']} harmonic", direction, 0.35 + best["score"] * 0.4,
        f"XABCD ratios AB {ratios['ab']:.2f} · BC {ratios['bc']:.2f} · CD {ratios['cd']:.2f} · "
        f"XD {ratios['xd']:.2f}; PRZ at {d.price:.6g}",
    )]


# --------------------------------------------------------------------------
# VSA / Wyckoff
# --------------------------------------------------------------------------

def vsa_read(candles: Sequence[Candle], atr_v: float) -> list[dict]:
    if len(candles) < 40 or atr_v <= 0:
        return []
    out: list[dict] = []
    win = candles[-60:]
    vols = [c.v for c in win[:-1]] or [1.0]
    vmean = mean(vols) or 1.0
    vsd = stdev(vols) or 1.0
    hi = max(c.h for c in win[:-1])
    lo = min(c.l for c in win[:-1])
    c = candles[-1]
    vz = (c.v - vmean) / vsd
    spread = c.range / atr_v
    close_pos = (c.c - c.l) / max(c.range, 1e-9)

    if c.l < lo and c.c > lo and vz > 0.8:
        out.append(_pattern("spring", "Wyckoff spring", 1, clamp(0.5 + vz / 5),
                            f"swept the 60-bar low at {lo:.6g} on {vz:+.1f}σ volume and closed back inside — supply absorbed"))
    if c.h > hi and c.c < hi and vz > 0.8:
        out.append(_pattern("upthrust", "Wyckoff upthrust", -1, clamp(0.5 + vz / 5),
                            f"pushed through the 60-bar high at {hi:.6g} on {vz:+.1f}σ volume and closed back inside — demand absorbed"))
    if spread > 1.4 and vz > 1.2 and close_pos > 0.6 and not c.bull:
        out.append(_pattern("stopping_vol", "stopping volume", 1, clamp(0.45 + vz / 6),
                            f"wide red bar ({spread:.1f} ATR) on {vz:+.1f}σ volume closing {close_pos:.0%} up its range — sellers met by buyers"))
    if c.bull and spread > 0.8 and vz < -0.9:
        out.append(_pattern("no_demand", "no demand (up bar, thin volume)", -1, clamp(0.4 + abs(vz) / 8),
                            f"green bar on {vz:+.1f}σ volume — the mark-up has no professional bid behind it"))
    if (not c.bull) and spread < 0.6 and vz < -0.9:
        out.append(_pattern("no_supply", "no supply (down bar, thin volume)", 1, clamp(0.4 + abs(vz) / 8),
                            f"narrow red bar on {vz:+.1f}σ volume — sellers are not showing size"))
    if spread > 1.2 and vz < -0.7 and close_pos > 0.5:
        out.append(_pattern("effort_result", "effort vs result", 1, 0.4,
                            "wide range on below-average volume closing strong — absorption, not distribution"))

    # phase read over the window
    half = len(win) // 2
    first, second = win[:half], win[half:]
    trend_first = (first[-1].c / first[0].c - 1) * 100 if first[0].c else 0.0
    tight = (max(x.h for x in second) - min(x.l for x in second)) / max(atr_v, 1e-9)
    up_vol = mean([x.v for x in second if x.bull] or [0.0])
    dn_vol = mean([x.v for x in second if not x.bull] or [0.0])
    if trend_first < -2 and tight < 12 and up_vol > dn_vol:
        out.append(_pattern("wyckoff_acc", "Wyckoff accumulation", 1, 0.55,
                            f"markdown of {trend_first:.1f}% followed by a {tight:.0f}-ATR range where up-bars trade heavier than down-bars"))
    elif trend_first > 2 and tight < 12 and dn_vol > up_vol:
        out.append(_pattern("wyckoff_dist", "Wyckoff distribution", -1, 0.55,
                            f"markup of {trend_first:.1f}% followed by a {tight:.0f}-ATR range where down-bars trade heavier than up-bars"))
    return out


# --------------------------------------------------------------------------
# chart patterns
# --------------------------------------------------------------------------

def chart_patterns(candles: Sequence[Candle], atr_v: float, zz: Sequence[Pivot]) -> list[dict]:
    if len(candles) < 40 or atr_v <= 0:
        return []
    out: list[dict] = []
    highs = [p for p in zz if p.kind == "H"][-3:]
    lows = [p for p in zz if p.kind == "L"][-3:]
    c = candles[-1]

    if len(highs) == 2 and abs(highs[0].price - highs[1].price) < atr_v * 0.35:
        neck = min(x.l for x in candles[highs[0].i:highs[1].i + 1])
        if c.c < neck:
            out.append(_pattern("double_top", "double top, neckline broken", -1, 0.65,
                                f"two highs at {mean([highs[0].price, highs[1].price]):.6g} and the neckline {neck:.6g} gave way"))
        else:
            out.append(_pattern("double_top_unconf", "double top forming", -1, 0.3,
                                f"equal highs at {highs[1].price:.6g}; neckline {neck:.6g} still holds"))
    if len(lows) == 2 and abs(lows[0].price - lows[1].price) < atr_v * 0.35:
        neck = max(x.h for x in candles[lows[0].i:lows[1].i + 1])
        if c.c > neck:
            out.append(_pattern("double_bottom", "double bottom, neckline broken", 1, 0.65,
                                f"two lows at {mean([lows[0].price, lows[1].price]):.6g} and the neckline {neck:.6g} gave way"))
        else:
            out.append(_pattern("double_bottom_unconf", "double bottom forming", 1, 0.3,
                                f"equal lows at {lows[1].price:.6g}; neckline {neck:.6g} still caps"))
    if len(highs) == 3 and highs[0].price > highs[1].price > highs[2].price \
            and len(lows) == 3 and lows[0].price < lows[1].price < lows[2].price:
        out.append(_pattern("triangle", "symmetrical triangle", 0, 0.45,
                            "lower highs into higher lows — compression, direction comes from the break"))
    # breakout of the recent range with participation
    prior = candles[-45:-1]
    if len(prior) > 20:
        rh = max(x.h for x in prior)
        rl = min(x.l for x in prior)
        vmean = mean([x.v for x in prior]) or 1.0
        if c.c > rh and c.v > vmean * 1.4:
            out.append(_pattern("breakout_up", "range breakout on volume", 1, 0.6,
                                f"closed above the 45-bar high {rh:.6g} on {c.v / vmean:.1f}x average volume"))
        if c.c < rl and c.v > vmean * 1.4:
            out.append(_pattern("breakout_dn", "range breakdown on volume", -1, 0.6,
                                f"closed below the 45-bar low {rl:.6g} on {c.v / vmean:.1f}x average volume"))
    return out


def range_compression(candles: Sequence[Candle], atr_v: float) -> float:
    """0..1 — how compressed the last 20 bars are versus the 20 before."""
    if len(candles) < 45 or atr_v <= 0:
        return 0.5
    recent = max(c.h for c in candles[-20:]) - min(c.l for c in candles[-20:])
    prior = max(c.h for c in candles[-45:-20]) - min(c.l for c in candles[-45:-20])
    if prior <= 0:
        return 0.5
    return clamp(1.0 - recent / prior)
