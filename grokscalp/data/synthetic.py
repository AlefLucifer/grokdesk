"""Deterministic synthetic market.

Live REST is optional; this generator is what makes the engine runnable,
testable and demo-able with zero network. It is not a toy random walk: it
regime-switches, puts in displacement legs, sweeps the prior swing and prints
the volume to match, so every detector in the engine has something real to
find. Prices are scaled so all timeframes end on the same last price.
"""

from __future__ import annotations

import hashlib
import math
import random
from dataclasses import dataclass

from .. import config
from ..indicators import clamp, cvd
from ..types import (Candle, Derivatives, Headline, LiquidationBucket, Macro,
                     MacroEvent, OrderBook, Sentiment, Snapshot, WhalePrint)

REF_PRICE = {
    "BTCUSDT": 62_766.0, "ETHUSDT": 1_770.2, "SOLUSDT": 73.77, "BNBUSDT": 584.8,
    "XRPUSDT": 0.969, "DOGEUSDT": 0.05848, "ADAUSDT": 0.1527, "AVAXUSDT": 7.015,
    "LINKUSDT": 9.005, "TONUSDT": 1.60, "PEPEUSDT": 0.00000379, "WIFUSDT": 0.1313,
    "SUIUSDT": 0.7127, "ARBUSDT": 0.123, "OPUSDT": 0.0751, "NEARUSDT": 3.267,
    "APTUSDT": 0.4136, "INJUSDT": 7.082, "SEIUSDT": 0.03793, "TIAUSDT": 0.3399,
}

SYMBOLS = list(REF_PRICE)

#: per-bar volatility in log-return units
VOL = {"1m": 0.0009, "3m": 0.0014, "5m": 0.0018, "15m": 0.0030,
       "30m": 0.0040, "1h": 0.0060, "4h": 0.0110}

HEADLINES = [
    ("{sym} ETF inflows hit a weekly record as desks rotate back in", 0.55, "high"),
    ("Whale wallet accumulates {sym} for a third straight session", 0.45, "med"),
    ("Exchange reserves for {sym} fall to a two-year low", 0.40, "med"),
    ("{sym} funding turns negative as shorts press their luck", 0.15, "low"),
    ("Analysts flag thin liquidity in {sym} order books", -0.20, "low"),
    ("{sym} sees $40M of long liquidations in an hour", -0.55, "high"),
    ("Regulator signals fresh scrutiny of offshore venues", -0.40, "med"),
    ("Macro desk warns of a risk-off week into the CPI print", -0.35, "high"),
    ("Stablecoin supply expands, dry powder builds on the sidelines", 0.30, "med"),
]


def _seed(*parts) -> int:
    return int(hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:16], 16)


def ref_price(symbol: str) -> float:
    sym = symbol.upper()
    if sym in REF_PRICE:
        return REF_PRICE[sym]
    h = _seed("price", sym) % 9000
    return round(0.5 + h / 1000.0, 4)


def _bars_for(tf: str, bars: int) -> int:
    return bars


# --------------------------------------------------------------------------
# candles
# --------------------------------------------------------------------------

@dataclass
class _Seg:
    kind: str
    length: int
    drift: float
    vol_mult: float
    anchor: float


def _schedule(rng: random.Random, bars: int, vol: float, start_price: float) -> list[_Seg]:
    segs: list[_Seg] = []
    left = bars
    total_trend = 0.0
    while left > 0:
        n = min(left, rng.randint(35, 95))
        kind = rng.choices(["trend", "range", "chop", "vol"], weights=[0.36, 0.30, 0.20, 0.14])[0]
        if kind == "trend":
            drift = vol * rng.uniform(0.15, 0.40) * (1 if rng.random() < 0.5 else -1)
            vmult = rng.uniform(0.9, 1.3)
        elif kind == "range":
            drift = 0.0
            vmult = rng.uniform(0.6, 1.0)
        elif kind == "vol":
            drift = vol * rng.uniform(-0.2, 0.2)
            vmult = rng.uniform(1.5, 2.2)
        else:
            drift = vol * rng.uniform(-0.06, 0.06)
            vmult = rng.uniform(0.5, 0.8)
        segs.append(_Seg(kind, n, drift, vmult, start_price * math.exp(total_trend)))
        total_trend += drift * n
        left -= n
    return segs


def gen_candles(symbol: str, tf: str, bars: int = config.DEFAULT_BARS,
                now_ms: int | None = None, seed: int = 0) -> list[Candle]:
    import time as _t
    now_ms = int(now_ms if now_ms is not None else _t.time() * 1000)
    step = config.TF_MINUTES[tf] * 60_000
    end = (now_ms // step) * step
    start = end - (bars - 1) * step
    rng = random.Random(_seed("candles", symbol.upper(), tf, seed, end // (step * 20)))
    vol = VOL[tf]
    base = ref_price(symbol) * rng.uniform(0.92, 1.06)
    segs = _schedule(rng, bars, vol, base)
    plan: list[_Seg] = []
    for s in segs:
        plan += [s] * s.length
    plan = plan[:bars]

    price = base
    candles: list[Candle] = []
    recent_high = price
    recent_low = price
    hi_buf: list[float] = []
    lo_buf: list[float] = []

    for i in range(bars):
        s = plan[i]
        v = vol * s.vol_mult
        drift = s.drift
        if s.kind == "range":
            drift += (s.anchor / price - 1.0) * 0.06
        ret = rng.gauss(drift, v)
        o = price
        c = o * math.exp(ret)
        hi = max(o, c) * (1 + abs(rng.gauss(0, v * 0.55)))
        lo = min(o, c) * (1 - abs(rng.gauss(0, v * 0.55)))
        volume = (0.55 + rng.random() * 1.1 + abs(ret) / max(v, 1e-9) * 0.7) * s.vol_mult

        # displacement leg: a clean break nobody can miss
        if i > 3 and rng.random() < 0.018:
            c = o * math.exp((1 if rng.random() < 0.5 else -1) * v * 3.2)
            hi = max(o, c) * (1 + v * 0.2)
            lo = min(o, c) * (1 - v * 0.2)
            volume *= 2.6

        # liquidity sweep: wick through the prior extreme, close back inside
        if i > 22 and rng.random() < 0.055 and hi_buf and lo_buf:
            if rng.random() < 0.5:
                target = max(hi_buf[-20:])
                hi = target * (1 + v * 0.9)
                c = min(c, target * (1 - v * 0.15))
                volume *= 2.2
            else:
                target = min(lo_buf[-20:])
                lo = target * (1 - v * 0.9)
                c = max(c, target * (1 + v * 0.15))
                volume *= 2.2

        hi = max(hi, o, c)
        lo = min(lo, o, c)
        tb_share = clamp(0.5 + ret / max(v, 1e-9) * 0.12 + rng.gauss(0, 0.07), 0.03, 0.97)
        candles.append(Candle(ts=start + i * step, o=o, h=hi, l=lo, c=c,
                              v=round(volume * 1000, 3), tb=round(volume * 1000 * tb_share, 3)))
        price = c
        hi_buf.append(hi)
        lo_buf.append(lo)
        recent_high = max(recent_high, hi)
        recent_low = min(recent_low, lo)

    day = end // 86_400_000
    drift = ((_seed("px", symbol.upper(), day) % 4000) / 100_000.0) - 0.02   # -2% .. +2% a day
    intraday = ((_seed("pxi", symbol.upper(), end // 900_000) % 1000) / 100_000.0) - 0.005
    scale = ref_price(symbol) * (1 + drift + intraday) / candles[-1].c
    return [Candle(c.ts, c.o * scale, c.h * scale, c.l * scale, c.c * scale, c.v, c.tb)
            for c in candles]


# --------------------------------------------------------------------------
# derivatives
# --------------------------------------------------------------------------

def gen_derivatives(candles: list[Candle], symbol: str, seed: int = 0) -> Derivatives:
    rng = random.Random(_seed("deriv", symbol.upper(), seed, candles[-1].ts // 300_000))
    price = candles[-1].c
    mom = (candles[-1].c / candles[-13].c - 1.0) if len(candles) > 13 else 0.0
    base_oi = (1.2e9 / max(price, 1e-9)) * rng.uniform(0.6, 1.8)
    oi_hist: list[float] = []
    level = 1.0
    for i in range(30):
        shock = rng.gauss(0, 0.0035) + mom * 0.02
        level *= (1 + shock)
        oi_hist.append(base_oi * level)

    funding_hist = [round(clamp(rng.gauss(0, 0.00032) + 0.00008 * math.tanh(mom * 25), -0.0012, 0.0012), 7)
                    for _ in range(30)]
    funding = funding_hist[-1]
    if rng.random() < 0.06:
        funding = round(funding + (0.0011 if rng.random() < 0.5 else -0.0011), 7)
        funding_hist[-1] = funding

    # liquidation heat map: recent swing highs carry short liqs, lows carry long liqs
    buckets: list[LiquidationBucket] = []
    for c in candles[-45:]:
        w = c.v * c.c * rng.uniform(8.0, 30.0)
        buckets.append(LiquidationBucket(price=c.h * 1.0008, notional=round(w * rng.uniform(0.7, 2.6), 2), side="short"))
        buckets.append(LiquidationBucket(price=c.l * 0.9992, notional=round(w * rng.uniform(0.7, 2.6), 2), side="long"))
    buckets.sort(key=lambda b: abs(b.price - price))
    buckets = buckets[:40]

    whales: list[WhalePrint] = []
    delta_bias = clamp(0.5 + mom * 40, 0.15, 0.85)
    for k in range(rng.randint(4, 11)):
        side = "buy" if rng.random() < delta_bias else "sell"
        whales.append(WhalePrint(
            ts=candles[-1].ts - rng.randint(0, 30) * config.TF_MINUTES["1m"] * 60_000,
            price=round(price * rng.uniform(0.999, 1.001), 8),
            notional=round(rng.uniform(60_000, 2_400_000), 0),
            side=side,
        ))

    bids: list[tuple[float, float]] = []
    asks: list[tuple[float, float]] = []
    tick = price * 0.00012
    bias = clamp(mom * 60, -0.8, 0.8)
    for k in range(25):
        b = price - tick * (k + 1)
        a = price + tick * (k + 1)
        size_b = rng.uniform(0.4, 2.5) * (1 + bias) * (1.6 if k < 5 else 1.0)
        size_a = rng.uniform(0.4, 2.5) * (1 - bias) * (1.6 if k < 5 else 1.0)
        bids.append((round(b, 8), round(max(0.05, size_b), 3)))
        asks.append((round(a, 8), round(max(0.05, size_a), 3)))

    return Derivatives(
        funding=funding, funding_history=funding_hist,
        oi=oi_hist[-1], oi_history=oi_hist,
        long_short_ratio=round(clamp(rng.gauss(1.4 + mom * 20, 0.7), 0.4, 4.0), 2),
        taker_ratio=round(clamp(1.0 + mom * 25 + rng.gauss(0, 0.1), 0.4, 2.5), 2),
        orderbook=OrderBook(bids=bids, asks=asks),
        liquidations=buckets, whales=whales, cvd=cvd(candles),
    )


# --------------------------------------------------------------------------
# sentiment & macro
# --------------------------------------------------------------------------

FG_LABELS = [(0, "Extreme Fear"), (25, "Fear"), (45, "Neutral"), (55, "Greed"), (75, "Extreme Greed")]


def fg_label(v: int) -> str:
    label = "Neutral"
    for threshold, name in FG_LABELS:
        if v >= threshold:
            label = name
    return label


def gen_sentiment(candles: list[Candle], symbol: str, seed: int = 0) -> Sentiment:
    rng = random.Random(_seed("sent", symbol.upper(), seed, candles[-1].ts // 600_000))
    mom = (candles[-1].c / candles[-25].c - 1.0) if len(candles) > 25 else 0.0
    fg = int(clamp(50 + mom * 2200 + rng.gauss(0, 14), 4, 96))
    hist = [int(clamp(fg + rng.gauss(0, 9), 2, 98)) for _ in range(14)]
    picks = rng.sample(HEADLINES, k=rng.randint(2, 4))
    heads = [Headline(ts=candles[-1].ts - rng.randint(5, 300) * 60_000,
                      title=t.format(sym=symbol.replace("USDT", "")),
                      source=rng.choice(["coindesk", "theblock", "x", "binance-square"]),
                      score=s, impact=imp) for t, s, imp in picks]
    score = sum(h.score for h in heads) / len(heads) if heads else 0.0
    events: list[MacroEvent] = []
    if rng.random() < 0.22:
        events.append(MacroEvent(ts=candles[-1].ts + rng.randint(8, 90) * 60_000,
                                 name=rng.choice(["US CPI", "FOMC decision", "NFP", "PCE print"]),
                                 impact="high", minutes_away=rng.randint(8, 90)))
    else:
        events.append(MacroEvent(ts=candles[-1].ts + rng.randint(4, 40) * 3_600_000,
                                 name=rng.choice(["US CPI", "FOMC decision", "NFP"]),
                                 impact="high", minutes_away=rng.randint(240, 2400)))
    return Sentiment(fear_greed=fg, fear_greed_label=fg_label(fg), fear_greed_history=hist,
                     news_score=round(score, 3), headlines=heads, events=events)


def gen_macro(candles: list[Candle], symbol: str, seed: int = 0) -> Macro:
    rng = random.Random(_seed("macro", symbol.upper(), seed, candles[-1].ts // 3_600_000))
    btc = gen_candles("BTCUSDT", "1h", 120, candles[-1].ts, seed)
    btc_trend = clamp((btc[-1].c / btc[-25].c - 1.0) * 60, -1, 1)
    if symbol.upper().startswith("BTC"):
        btc_trend = clamp((candles[-1].c / candles[-25].c - 1.0) * 60, -1, 1)
    return Macro(
        btc_trend=round(btc_trend, 3),
        btc_change_24h=round((btc[-1].c / btc[-25].c - 1.0) * 100, 2),
        btc_dominance=round(clamp(55 + rng.gauss(0, 2.5), 45, 65), 2),
        usdt_dominance=round(clamp(5.2 + rng.gauss(0, 0.5), 3.5, 8.0), 2),
        usdt_dom_change=round(rng.gauss(0, 0.08), 3),
        dxy=round(clamp(103.5 + rng.gauss(0, 1.8), 96, 112), 2),
        dxy_change=round(rng.gauss(0, 0.25), 2),
    )


# --------------------------------------------------------------------------
# snapshot
# --------------------------------------------------------------------------

def snapshot(symbol: str, tf: str, bars: int = config.DEFAULT_BARS,
             now_ms: int | None = None, seed: int = 0) -> Snapshot:
    symbol = symbol.upper()
    candles: dict[str, list[Candle]] = {}
    for each in [tf] + list(config.HTF_CHAIN.get(tf, ())) + ["15m", "1h"]:
        if each in candles:
            continue
        n = bars if each == tf else min(config.HTF_BARS, max(120, bars))
        candles[each] = gen_candles(symbol, each, n, now_ms, seed)
    base = candles[tf]
    deriv = gen_derivatives(base, symbol, seed)
    sent = gen_sentiment(base, symbol, seed)
    macro = gen_macro(base, symbol, seed)
    return Snapshot(symbol=symbol, tf=tf, candles=candles, derivatives=deriv,
                    sentiment=sent, macro=macro, source="synthetic",
                    as_of=base[-1].ts)
