"""Levels, stops, targets and sizing.

The stop is always placed where the analysis dies — under the zone and the
swing that defines it — never at a round percentage. Sizing is derived from
that stop, so a wide stop means a smaller position, not a wider loss.
"""

from __future__ import annotations

import math
from typing import Iterable, Sequence

from . import config
from .indicators import clamp, volume_profile
from .types import Candle, Level, Regime, Structure, TradePlan


ZONE_FA = {
    "bullish order block": "اردربلاک صعودی",
    "bearish order block": "اردربلاک نزولی",
    "bullish FVG": "FVG صعودی",
    "bearish FVG": "FVG نزولی",
}


def zone_note_fa(note: str) -> str:
    out = note
    for en, fa in ZONE_FA.items():
        out = out.replace(en, fa)
    out = out.replace("filled", "پر شده").replace("%", "٪")
    return out


def price_decimals(p: float) -> int:
    if p >= 10_000:
        return 1
    if p >= 1_000:
        return 2
    if p >= 100:
        return 2
    if p >= 1:
        return 4
    if p >= 0.01:
        return 5
    return 8


def fmt_price(p: float) -> str:
    if p is None:
        return "—"
    d = price_decimals(p)
    return f"{p:,.{d}f}"


def _zone_score(z: Level, price: float, atr_v: float, side: int) -> float:
    """Closer, stronger, and (for longs) below price is better."""
    if atr_v <= 0:
        return 0.0
    dist = (price - z.hi) / atr_v if side > 0 else (z.lo - price) / atr_v
    if dist < -0.25:          # zone is on the wrong side of price
        return -1.0
    proximity = clamp(1.0 - max(dist, 0.0) / 3.0)
    inside = 1.0 if z.contains(price) else 0.0
    return proximity * 0.6 + z.strength * 0.4 + inside * 0.35


def _pick_zone(zones: Iterable[Level], price: float, atr_v: float, side: int) -> Level | None:
    best, best_s = None, 0.0
    for z in zones:
        s = _zone_score(z, price, atr_v, side)
        if s > best_s:
            best, best_s = z, s
    return best if best_s > 0.35 else None


def _targets(candidates: Iterable[float], entry: float, sl: float, side: int,
             r_multiples: Sequence[float]) -> tuple[float, float, float]:
    R = abs(entry - sl)
    levels = sorted({round(c, 12) for c in candidates
                     if (c - entry) * side > R * 0.8 and abs(c - entry) > R * 0.2})
    if side < 0:
        levels = sorted(levels, reverse=True)
    tps: list[float] = []
    for mult in r_multiples:
        want = entry + side * R * mult
        chosen = None
        for lv in levels:
            dist = abs(lv - entry)
            if not (R * (mult - 0.35) <= dist <= R * (mult + 1.10)):
                continue
            if tps and dist <= abs(tps[-1] - entry) + R * 0.15:
                continue
            chosen = lv
            break
        if chosen is None:
            chosen = want
        if tps and (chosen - tps[-1]) * side < R * 0.2:
            chosen = tps[-1] + side * R * 0.2
        tps.append(round(chosen, 12))
    return tps[0], tps[1], tps[2]


def build_plan(action: str, price: float, candles: Sequence[Candle], st: Structure,
               atr_v: float, regime: Regime, tf: str, *, equity: float = config.DEFAULT_EQUITY,
               risk_pct: float = config.DEFAULT_RISK_PCT, size_mult: float = 1.0,
               extra_up: Sequence[float] = (), extra_dn: Sequence[float] = (),
               ttl_bars: int = config.SIGNAL_TTL_BARS, min_rr: float = 1.6) -> TradePlan:
    plan = TradePlan(action=action, ttl_bars=ttl_bars)
    side = 1 if action == "LONG" else -1 if action == "SHORT" else 0
    if side == 0 or price <= 0 or atr_v <= 0:
        plan.order_type = "no order"
        return plan

    same_side = [z for z in st.order_blocks + st.fvgs
                 if (z.hi <= price + 0.3 * atr_v if side > 0 else z.lo >= price - 0.3 * atr_v)]
    if side > 0:
        same_side += [z for z in st.sr if z.mid < price]
        if st.ote:
            same_side.append(st.ote)
    else:
        same_side += [z for z in st.sr if z.mid > price]
        if st.ote:
            same_side.append(st.ote)

    zone = _pick_zone(same_side, price, atr_v, side)
    pad = atr_v * config.ENTRY_PAD_ATR

    if zone is not None:
        lo, hi = sorted((zone.lo - pad, zone.hi + pad))
        if zone.contains(price, pad):
            entry = price if (price - zone.mid) * side <= 0 else zone.mid
            order = "Limit"
        else:
            entry = zone.mid
            order = "Limit"
        note = zone.note
    else:
        entry = price
        lo = hi = price
        order = "Market Execution" if regime.name != "HIGH_VOL" else "Limit"
        note = "no clean zone below/above — momentum entry at the market"

    entry = clamp(entry, lo, hi) if hi > lo else entry
    swing = min(c.l for c in candles[-8:]) if side > 0 else max(c.h for c in candles[-8:])
    invalid = min(lo, swing) if side > 0 else max(hi, swing)
    sl = invalid - side * atr_v * config.ATR_SL_BUFFER
    if (entry - sl) * side <= 0:
        sl = entry - side * atr_v * 1.2

    # keep the stop inside the band a scalp can survive
    min_stop = price * config.MIN_STOP_PCT
    max_stop = price * config.MAX_STOP_PCT.get(tf, 0.03)
    dist = abs(entry - sl)
    if dist < min_stop:
        sl = entry - side * min_stop
    elif dist > max_stop:
        sl = entry - side * max_stop
    dist = abs(entry - sl)

    vp = volume_profile(candles, 24)
    up_levels = list(extra_up) + [z.mid for z in st.pools if "BSL" in z.note or "highs" in z.note]
    dn_levels = list(extra_dn) + [z.mid for z in st.pools if "SSL" in z.note or "lows" in z.note]
    up_levels += [z.mid for z in st.sr if z.mid > entry] + [vp["vah"], st.range_high]
    dn_levels += [z.mid for z in st.sr if z.mid < entry] + [vp["val"], st.range_low]
    if vp["poc"]:
        (up_levels if vp["poc"] > entry else dn_levels).append(vp["poc"])
    cand = up_levels if side > 0 else dn_levels
    tp1, tp2, tp3 = _targets(cand, entry, sl, side, config.TP_R)

    R = abs(entry - sl)
    plan.entry, plan.entry_lo, plan.entry_hi = entry, lo, hi
    plan.sl, plan.tp1, plan.tp2, plan.tp3 = sl, tp1, tp2, tp3
    plan.order_type = order
    plan.stop_pct = dist / price
    plan.rr_tp1 = abs(tp1 - entry) / R if R else 0.0
    plan.rr_tp3 = abs(tp3 - entry) / R if R else 0.0
    plan.rr = abs(tp2 - entry) / R if R else 0.0

    # ---- sizing -----------------------------------------------------------
    risk_pct = min(config.MAX_RISK_PCT, max(0.1, risk_pct * size_mult))
    plan.risk_pct = round(risk_pct, 2)
    risk_amount = equity * risk_pct / 100.0
    qty = risk_amount / dist if dist else 0.0
    notional = qty * entry
    lev_liq = max(1, int(1.0 / max(plan.stop_pct * config.LIQ_BUFFER, 1e-6)))
    lev_cap = max(1, min(lev_liq, config.MAX_LEVERAGE.get(tf, 10)))
    if notional > equity * lev_cap:
        notional = equity * lev_cap * 0.9
        qty = notional / entry
        risk_amount = qty * dist
        plan.risk_pct = round(risk_amount / equity * 100, 2)
    lev = max(1, min(lev_cap, math.ceil(notional / equity)))
    margin = notional / lev if lev else notional
    plan.leverage = int(lev)
    plan.qty = qty
    plan.notional = notional
    plan.risk_amount = risk_amount
    plan.margin_pct = round(margin / equity * 100, 2) if equity else 0.0

    # ---- trade management -------------------------------------------------
    plan.invalidation = [
        f"کنسل سفارش اگر قیمت قبل از پر شدن، {fmt_price(invalid)} را با کلوز کندل بشکند ({zone_note_fa(note)}).",
        f"اگر بین ورود و TP1 یک CHoCH مخالف روی {tf} ثبت شود، پوزیشن را ببندید.",
        "اگر فاندینگ خلاف جهت به محدوده اشباع برسد یا OI بیش از ۵٪ در یک کندل بریزد، خروج دستی.",
        f"اعتبار سیگنال {ttl_bars} کندل است؛ بعد از آن دوباره تحلیل کنید.",
    ]
    plan.trailing = [
        f"بعد از TP1: استاپ به نقطه ورود ({fmt_price(entry)}) منتقل شود و ۵۰٪ پوزیشن بسته شود.",
        f"بعد از TP2: استاپ به TP1 ({fmt_price(tp1)}) و تریل با ۱.۰×ATR ({fmt_price(atr_v)}) تا TP3.",
        "اگر کندل مخالف با حجم بالای ۲ برابر میانگین بسته شد، تریل را به کندل قبل ببندید.",
    ]
    plan.invalidation_en = [
        f"cancel the order if price closes through {fmt_price(invalid)} before it fills ({note}).",
        f"a CHoCH against the position on the {tf} before TP1 invalidates the trade — close it.",
        "manual exit if funding flips into extreme territory against you or OI drops more than 5% in one bar.",
        f"the card is valid for {ttl_bars} bars; re-run the analysis after that.",
    ]
    plan.trailing_en = [
        f"after TP1: move the stop to entry ({fmt_price(entry)}) and close 50% of the position.",
        f"after TP2: stop to TP1 ({fmt_price(tp1)}), then trail by 1.0×ATR ({fmt_price(atr_v)}) to TP3.",
        "if an opposing candle closes on more than 2× average volume, trail to the prior candle.",
    ]
    return plan
