"""Order flow and derivatives: CVD, OI, funding, book, liquidations, whales.

Crypto scalping is mostly a flow game. These reads decide whether a move has
positioning behind it or is just a wick, and they veto entries into crowded
funding.
"""

from __future__ import annotations

from typing import Sequence

from . import config
from .indicators import clamp, cvd, divergence, mean, pct_rank, zscore
from .types import Candle, Derivatives


def _ev(code: str, direction: int, weight: float, strength: float, note: str,
        family: str = "DERIV", **ref) -> dict:
    return {"code": code, "family": family, "direction": direction,
            "weight": clamp(weight), "strength": clamp(strength), "note": note, "ref": ref}


def price_change_pct(candles: Sequence[Candle], bars: int) -> float:
    if len(candles) <= bars:
        return 0.0
    a, b = candles[-1 - bars].c, candles[-1].c
    return (b / a - 1.0) * 100.0 if a else 0.0


# --------------------------------------------------------------------------
# CVD
# --------------------------------------------------------------------------

def cvd_read(candles: Sequence[Candle], bars: int = 20) -> list[dict]:
    series = cvd(candles)
    if len(series) < bars + 5:
        return []
    out: list[dict] = []
    dp = candles[-1].c - candles[-1 - bars].c
    dc = series[-1] - series[-1 - bars]
    scale = max(abs(series[-1]) * 0.05, mean([c.v for c in candles[-bars:]]) or 1.0)
    strength = clamp(abs(dc) / scale / 2)
    if dp > 0 and dc > 0:
        out.append(_ev("cvd_confirm_long", 1, 0.55, 0.4 + strength * 0.5,
                       f"CVD +{dc:,.0f} with price +{dp:+.4g} — aggressive buyers are lifting offers"))
    elif dp < 0 and dc < 0:
        out.append(_ev("cvd_confirm_short", -1, 0.55, 0.4 + strength * 0.5,
                       f"CVD {dc:,.0f} with price {dp:+.4g} — market sellers are hitting bids"))
    elif dp > 0 and dc < 0:
        out.append(_ev("cvd_absorb", -1, 0.6, 0.45 + strength * 0.4,
                       f"price up {dp:+.4g} while CVD fell {dc:,.0f} — the bid is passive, move is not backed by takers"))
    elif dp < 0 and dc > 0:
        out.append(_ev("cvd_absorb_up", 1, 0.6, 0.45 + strength * 0.4,
                       f"price down {dp:+.4g} while CVD rose {dc:,.0f} — sellers are being absorbed"))
    div = divergence([c.c for c in candles[-60:]], series[-60:], lookback=50, pivot=2)
    if div["kind"] == "bull":
        out.append(_ev("cvd_div_bull", 1, 0.65, div["strength"],
                       "bullish CVD divergence: price printed a lower low, cumulative delta did not"))
    elif div["kind"] == "bear":
        out.append(_ev("cvd_div_bear", -1, 0.65, div["strength"],
                       "bearish CVD divergence: price printed a higher high, cumulative delta did not"))
    return out


# --------------------------------------------------------------------------
# open interest
# --------------------------------------------------------------------------

def oi_read(deriv: Derivatives, candles: Sequence[Candle], bars: int = 12) -> list[dict]:
    if not deriv.oi_history or len(deriv.oi_history) < 3:
        return []
    dp = price_change_pct(candles, bars)
    doi = deriv.oi_trend_pct
    oi_z = zscore(deriv.oi_history[-30:]) if len(deriv.oi_history) >= 10 else 0.0
    out: list[dict] = []
    if dp > 0.10 and doi > 0.25:
        out.append(_ev("oi_long_build", 1, 0.6, clamp(0.4 + abs(doi) / 4),
                       f"OI {doi:+.2f}% with price {dp:+.2f}% — fresh longs, trend has new money behind it"))
    elif dp > 0.10 and doi < -0.25:
        out.append(_ev("oi_short_cover", 1, 0.45, clamp(0.35 + abs(doi) / 5),
                       f"OI {doi:+.2f}% with price {dp:+.2f}% — squeeze, shorts are covering rather than new longs"))
    elif dp < -0.10 and doi > 0.25:
        out.append(_ev("oi_short_build", -1, 0.6, clamp(0.4 + abs(doi) / 4),
                       f"OI {doi:+.2f}% with price {dp:+.2f}% — fresh shorts pressuring the tape"))
    elif dp < -0.10 and doi < -0.25:
        out.append(_ev("oi_long_liquidation", -1, 0.45, clamp(0.35 + abs(doi) / 5),
                       f"OI {doi:+.2f}% with price {dp:+.2f}% — longs are being liquidated out"))
    if oi_z > 1.8:
        out.append(_ev("oi_crowded", -1 if dp > 0 else 1, 0.35, 0.5,
                       f"open interest at {oi_z:+.1f}σ of its 30-sample range — positioning is crowded, squeezes get violent"))
    return out


# --------------------------------------------------------------------------
# funding
# --------------------------------------------------------------------------

def funding_read(deriv: Derivatives) -> list[dict]:
    f = deriv.funding
    ann = f * 3 * 365 * 100
    out: list[dict] = []
    hist = deriv.funding_history or []
    rank = pct_rank(hist, f) if hist else 0.5
    if f >= config.FUNDING_EXTREME:
        out.append(_ev("funding_extreme_long", -1, 0.7, clamp(0.5 + f / 0.002),
                       f"funding {f * 100:+.4f}%/8h ({ann:+.0f}% APR, {rank:.0%} percentile) — longs pay a fortune, the long side is crowded"))
    elif f >= config.FUNDING_HOT:
        out.append(_ev("funding_hot_long", -1, 0.45, clamp(0.35 + (f - config.FUNDING_HOT) / 0.002),
                       f"funding {f * 100:+.4f}%/8h ({ann:+.0f}% APR) — longs crowded, a flush would be cheap"))
    elif f <= -config.FUNDING_EXTREME:
        out.append(_ev("funding_extreme_short", 1, 0.7, clamp(0.5 + abs(f) / 0.002),
                       f"funding {f * 100:+.4f}%/8h ({ann:+.0f}% APR) — shorts pay heavily, the short side is crowded"))
    elif f <= -config.FUNDING_HOT:
        out.append(_ev("funding_hot_short", 1, 0.45, clamp(0.35 + (abs(f) - config.FUNDING_HOT) / 0.002),
                       f"funding {f * 100:+.4f}%/8h ({ann:+.0f}% APR) — shorts crowded, squeeze fuel is stacked"))
    else:
        out.append(_ev("funding_neutral", 0, 0.2, 0.5,
                       f"funding {f * 100:+.4f}%/8h ({ann:+.0f}% APR) — no crowding, positioning is clean"))
    return out


def funding_bias(deriv: Derivatives) -> str:
    f = deriv.funding
    if f >= config.FUNDING_EXTREME:
        return "لانگ‌های بسیار شلوغ"
    if f >= config.FUNDING_HOT:
        return "لانگ‌ها شلوغ"
    if f <= -config.FUNDING_EXTREME:
        return "شورت‌های بسیار شلوغ"
    if f <= -config.FUNDING_HOT:
        return "شورت‌ها شلوغ"
    return "خنثی"


# --------------------------------------------------------------------------
# order book
# --------------------------------------------------------------------------

def obi_read(deriv: Derivatives) -> list[dict]:
    ob = deriv.orderbook
    if not ob.bids or not ob.asks:
        return []
    obi = deriv.obi
    spread = ob.spread_bps
    out: list[dict] = []
    if obi >= 0.25:
        out.append(_ev("obi_bid", 1, 0.45, clamp(0.3 + abs(obi)),
                       f"book imbalance {obi:+.2f} — {sum(s for _, s in ob.bids[:15]) / max(sum(s for _, s in ob.asks[:15]), 1e-9):.2f}x more bid size in the top 15 levels"))
    elif obi <= -0.25:
        out.append(_ev("obi_ask", -1, 0.45, clamp(0.3 + abs(obi)),
                       f"book imbalance {obi:+.2f} — asks dominate the top of the ladder, rallies get sold into"))
    else:
        out.append(_ev("obi_neutral", 0, 0.15, 0.5,
                       f"book imbalance {obi:+.2f} — balanced ladder"))
    if spread > 12:
        out.append(_ev("spread_wide", 0, 0.3, 0.6,
                       f"spread {spread:.1f} bps — execution cost is real, wait for a tighter book"))
    return out


# --------------------------------------------------------------------------
# liquidations
# --------------------------------------------------------------------------

def liquidation_read(deriv: Derivatives, price: float, atr_v: float) -> tuple[list[dict], list[float], list[float]]:
    """Returns evidence plus the liquidation magnets above and below price."""
    above = [b for b in deriv.liquidations if b.price > price]
    below = [b for b in deriv.liquidations if b.price <= price]
    above.sort(key=lambda b: b.price)
    below.sort(key=lambda b: -b.price)
    out: list[dict] = []
    top_above = above[:3]
    top_below = below[:3]
    if top_above:
        b = top_above[0]
        dist = (b.price / price - 1) * 100
        out.append(_ev("liq_magnet_up", 1, 0.35, clamp(1.0 - abs(dist) / 2.0) if abs(dist) < 2 else 0.3,
                       f"liquidation cluster {b.notional:,.0f} USD at {b.price:.6g} ({dist:+.2f}%) — price is drawn to it"))
    if top_below:
        b = top_below[0]
        dist = (b.price / price - 1) * 100
        out.append(_ev("liq_magnet_down", -1, 0.35, clamp(1.0 - abs(dist) / 2.0) if abs(dist) < 2 else 0.3,
                       f"liquidation cluster {b.notional:,.0f} USD at {b.price:.6g} ({dist:+.2f}%) — price is drawn to it"))
    long_liq = sum(b.notional for b in deriv.liquidations if b.side == "long")
    short_liq = sum(b.notional for b in deriv.liquidations if b.side == "short")
    if long_liq + short_liq > 0:
        skew = (short_liq - long_liq) / (long_liq + short_liq)
        out.append(_ev("liq_skew", 1 if skew > 0 else -1 if skew < 0 else 0, 0.3, clamp(abs(skew)),
                       f"liquidation heatmap skew {skew:+.2f} — {'shorts' if skew > 0 else 'longs'} are the fuel "
                       f"({short_liq:,.0f} vs {long_liq:,.0f} USD)"))
    return out, [b.price for b in top_above], [b.price for b in top_below]


# --------------------------------------------------------------------------
# whales / taker flow
# --------------------------------------------------------------------------

def whale_read(deriv: Derivatives, candles: Sequence[Candle]) -> list[dict]:
    out: list[dict] = []
    if deriv.whales:
        buys = sum(p.notional for p in deriv.whales if p.side == "buy")
        sells = sum(p.notional for p in deriv.whales if p.side == "sell")
        net = buys - sells
        total = buys + sells
        if total > 0:
            share = net / total
            biggest = max(deriv.whales, key=lambda p: p.notional)
            out.append(_ev("whale_flow", 1 if net > 0 else -1 if net < 0 else 0, 0.55, clamp(0.3 + abs(share)),
                           f"whale prints: {buys:,.0f} USD bought vs {sells:,.0f} USD sold "
                           f"(net {net:+,.0f}); largest single print {biggest.notional:,.0f} USD"))
    if len(candles) >= 20:
        recent = candles[-20:]
        tb = sum(c.tb for c in recent)
        tot = sum(c.v for c in recent)
        if tot > 0:
            ratio = tb / tot
            direction = 1 if ratio > 0.55 else -1 if ratio < 0.45 else 0
            out.append(_ev("taker_flow", direction, 0.4, clamp(abs(ratio - 0.5) * 4),
                           f"taker buy share {ratio:.0%} over the last 20 bars — aggressive "
                           f"{'buying' if ratio > 0.5 else 'selling'} dominates"))
    if deriv.long_short_ratio:
        lsr = deriv.long_short_ratio
        out.append(_ev("lsr", -1 if lsr > 2.2 else 1 if lsr < 0.8 else 0, 0.25, clamp(abs(lsr - 1.5) / 2),
                       f"long/short account ratio {lsr:.2f}" + (" — retail is heavily long, contrarian" if lsr > 2.2
                                                                 else " — retail is leaning short, contrarian" if lsr < 0.8 else "")))
    return out


def derivatives_evidence(deriv: Derivatives, candles: Sequence[Candle], price: float,
                         atr_v: float) -> tuple[list[dict], list[float], list[float]]:
    out: list[dict] = []
    out += cvd_read(candles)
    out += oi_read(deriv, candles)
    out += funding_read(deriv)
    out += obi_read(deriv)
    liq_ev, up, down = liquidation_read(deriv, price, atr_v)
    out += liq_ev
    out += whale_read(deriv, candles)
    return out, up, down
