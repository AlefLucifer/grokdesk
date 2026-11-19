"""Live adapters: Binance USDⓈ-M futures, CoinGecko, alternative.me, Frankfurter.

Only public endpoints, no keys. Every call is best-effort: a missing dataset
degrades the card (with a note) instead of killing the analysis. If the exchange
cannot be reached at all, `load()` falls back to the synthetic market.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

from .. import config
from ..indicators import cvd
from ..types import (Candle, Derivatives, Headline, LiquidationBucket, Macro,
                     MacroEvent, OrderBook, Sentiment, Snapshot, WhalePrint)

FAPI = "https://fapi.binance.com"
API = "https://api.binance.com"
UA = {"User-Agent": "grokscalp/0.1 (+https://github.com/AlefLucifer/grokdesk)"}
_CACHE: dict[str, tuple[float, Any]] = {}
TTL = 15.0


class DataError(RuntimeError):
    pass


def _get(url: str, timeout: float = 8.0, ttl: float = TTL) -> Any:
    now = time.time()
    hit = _CACHE.get(url)
    if hit and now - hit[0] < ttl:
        return hit[1]
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read())
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as exc:
        raise DataError(f"{url}: {exc}") from exc
    _CACHE[url] = (now, data)
    return data


def _try(url: str, default: Any = None, timeout: float = 6.0) -> Any:
    try:
        return _get(url, timeout=timeout)
    except DataError:
        return default


def _klines(symbol: str, tf: str, limit: int, futures: bool = True) -> list[Candle]:
    base = FAPI + "/fapi/v1/klines" if futures else API + "/api/v3/klines"
    url = f"{base}?symbol={symbol}&interval={tf}&limit={min(limit, 1500)}"
    rows = _get(url)
    return [Candle(ts=int(r[0]), o=float(r[1]), h=float(r[2]), l=float(r[3]), c=float(r[4]),
                   v=float(r[5]), tb=float(r[9]) if len(r) > 9 else 0.0) for r in rows]


def _depth(symbol: str, limit: int = 100) -> OrderBook:
    d = _try(f"{FAPI}/fapi/v1/depth?symbol={symbol}&limit={limit}", {})
    return OrderBook(bids=[(float(p), float(q)) for p, q in d.get("bids", [])],
                     asks=[(float(p), float(q)) for p, q in d.get("asks", [])])


def _liquidations(symbol: str, candles: list[Candle], price: float) -> list[LiquidationBucket]:
    """Binance no longer serves forceOrders publicly, so the map is estimated
    from where leveraged entries cluster: swing highs (short liqs) and swing
    lows (long liqs), weighted by the volume that traded there."""
    out: list[LiquidationBucket] = []
    for c in candles[-60:]:
        w = c.v * c.c
        if w <= 0:
            continue
        out.append(LiquidationBucket(c.h * 1.0009, round(w * 1.6, 2), "short"))
        out.append(LiquidationBucket(c.l * 0.9991, round(w * 1.6, 2), "long"))
    out.sort(key=lambda b: abs(b.price - price))
    return out[:50]


def _whales(symbol: str, price: float) -> list[WhalePrint]:
    trades = _try(f"{FAPI}/fapi/v1/aggTrades?symbol={symbol}&limit=1000", [])
    if not isinstance(trades, list):
        return []
    prints = []
    for t in trades:
        try:
            p, q, ts = float(t["p"]), float(t["q"]), int(t["T"])
        except (KeyError, ValueError):
            continue
        notional = p * q
        if notional >= 50_000:
            prints.append(WhalePrint(ts=ts, price=p, notional=notional,
                                     side="sell" if t.get("m") else "buy"))
    prints.sort(key=lambda p: p.ts)
    return prints[-25:]


def _derivatives(symbol: str, candles: list[Candle], price: float) -> tuple[Derivatives, list[str]]:
    notes: list[str] = []
    d = Derivatives(orderbook=_depth(symbol), cvd=cvd(candles))

    pi = _try(f"{FAPI}/fapi/v1/premiumIndex?symbol={symbol}", {})
    if pi:
        d.funding = float(pi.get("lastFundingRate", 0.0))
    hist = _try(f"{FAPI}/fapi/v1/fundingRate?symbol={symbol}&limit=30", [])
    if isinstance(hist, list) and hist:
        d.funding_history = [float(h["fundingRate"]) for h in hist]
    else:
        notes.append("funding history unavailable")

    oi = _try(f"{FAPI}/fapi/v1/openInterest?symbol={symbol}", {})
    if oi:
        d.oi = float(oi.get("openInterest", 0.0))
    oi_hist = _try(f"{FAPI}/futures/data/openInterestHist?symbol={symbol}&period=5m&limit=30", [])
    if isinstance(oi_hist, list) and oi_hist:
        d.oi_history = [float(x["sumOpenInterest"]) for x in oi_hist]
    elif d.oi:
        d.oi_history = [d.oi]
        notes.append("OI history estimated from the latest print")
    else:
        notes.append("open interest unavailable")

    lsr = _try(f"{FAPI}/futures/data/globalLongShortAccountRatio?symbol={symbol}&period=5m&limit=1", [])
    if isinstance(lsr, list) and lsr:
        d.long_short_ratio = float(lsr[-1]["longShortRatio"])
    tk = _try(f"{FAPI}/futures/data/takerlongshortRatio?symbol={symbol}&period=5m&limit=1", [])
    if isinstance(tk, list) and tk:
        d.taker_ratio = float(tk[-1]["buySellRatio"])

    d.liquidations = _liquidations(symbol, candles, price)
    notes.append("liquidation map is estimated from swing liquidity (no public forceOrders)")
    d.whales = _whales(symbol, price)
    return d, notes


def _macro(symbol: str) -> tuple[Macro, list[str]]:
    notes: list[str] = []
    m = Macro()
    btc = _try(f"{FAPI}/fapi/v1/klines?symbol=BTCUSDT&interval=1h&limit=30", [])
    if isinstance(btc, list) and len(btc) > 25:
        closes = [float(x[4]) for x in btc]
        m.btc_trend = max(-1.0, min(1.0, (closes[-1] / closes[-25] - 1) * 60))
        m.btc_change_24h = round((closes[-1] / closes[-25] - 1) * 100, 2)
    else:
        notes.append("BTC context unavailable")

    glob = _try("https://api.coingecko.com/api/v3/global", {})
    try:
        dom = glob["data"]["market_cap_percentage"]
        m.btc_dominance = round(float(dom.get("btc", m.btc_dominance)), 2)
        m.usdt_dominance = round(float(dom.get("usdt", m.usdt_dominance)), 2)
    except (KeyError, TypeError, ValueError):
        notes.append("CoinGecko dominance unavailable")

    fx = _try("https://api.frankfurter.app/latest?from=USD&to=EUR,JPY,GBP,CAD,SEK,CHF", {})
    if isinstance(fx, dict) and fx.get("rates"):
        r = fx["rates"]
        try:
            m.dxy = round(_dxy(r), 2)
            yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
            prev = _try(f"https://api.frankfurter.app/{yesterday}?from=USD&to=EUR,JPY,GBP,CAD,SEK,CHF", {})
            if prev.get("rates"):
                m.dxy_change = round((m.dxy / _dxy(prev["rates"]) - 1) * 100, 2)
        except (KeyError, ValueError):
            notes.append("DXY unavailable")
    return m, notes


def _dxy(rates: dict) -> float:
    eurusd = 1 / float(rates["EUR"])
    usdjpy = float(rates["JPY"])
    gbpusd = 1 / float(rates["GBP"])
    usdcad = float(rates["CAD"])
    usdsek = float(rates["SEK"])
    usdchf = float(rates["CHF"])
    return (50.14348112 * eurusd ** -0.576 * usdjpy ** 0.136 * gbpusd ** -0.119
            * usdcad ** 0.091 * usdsek ** 0.042 * usdchf ** 0.036)


def _sentiment(symbol: str) -> tuple[Sentiment, list[str]]:
    notes: list[str] = []
    s = Sentiment()
    fng = _try("https://api.alternative.me/fng/?limit=15", {})
    try:
        rows = fng["data"]
        s.fear_greed = int(rows[0]["value"])
        s.fear_greed_label = rows[0]["value_classification"]
        s.fear_greed_history = [int(r["value"]) for r in rows]
    except (KeyError, TypeError, ValueError, IndexError):
        notes.append("fear & greed unavailable")

    token = __import__("os").getenv("CRYPTOPANIC_TOKEN")
    if token:
        url = ("https://cryptopanic.com/api/v1/posts/?auth_token=" + token
               + "&currencies=" + symbol.replace("USDT", "") + "&public=true")
        posts = _try(url, {})
        try:
            heads = []
            for p in posts["results"][:6]:
                title = p["title"]
                score = _news_score(title)
                heads.append(Headline(ts=0, title=title, source=p.get("source", {}).get("title", ""),
                                      score=score, impact=p.get("kind", "news")))
            s.headlines = heads
            if heads:
                s.news_score = round(sum(h.score for h in heads) / len(heads), 3)
        except (KeyError, TypeError):
            notes.append("news fetch failed")
    else:
        notes.append("no CRYPTOPANIC_TOKEN: news tone is neutral")

    evs = _try("https://nfs.faireconomy.media/ff_calendar_thisweek.json", [])
    if isinstance(evs, list):
        now = datetime.now(timezone.utc)
        for e in evs:
            try:
                if e.get("impact") != "High":
                    continue
                when = datetime.fromisoformat(e["date"])
                mins = int((when - now).total_seconds() // 60)
                if -30 < mins < 2880:
                    s.events.append(MacroEvent(ts=int(when.timestamp() * 1000), name=e["title"],
                                               impact="high", minutes_away=mins))
            except (KeyError, ValueError, TypeError):
                continue
    s.events.sort(key=lambda e: e.minutes_away)
    return s, notes


def _news_score(title: str) -> float:
    t = title.lower()
    pos = ("surge", "record", "inflow", "approve", "adopt", "rally", "breakout", "partnership", "burn")
    neg = ("hack", "exploit", "ban", "lawsuit", "outflow", "plunge", "liquidation", "probe", "fraud", "delay")
    p = sum(1 for w in pos if w in t)
    n = sum(1 for w in neg if w in t)
    return max(-1.0, min(1.0, (p - n) * 0.4))


def load(symbol: str, tf: str, bars: int = config.DEFAULT_BARS,
         now_ms: int | None = None, seed: int = 0) -> Snapshot:
    symbol = symbol.upper()
    notes: list[str] = []
    futures = True
    try:
        base = _klines(symbol, tf, bars, futures=True)
    except DataError:
        futures = False
        base = _klines(symbol, tf, bars, futures=False)
        notes.append("spot market: derivatives unavailable")

    candles: dict[str, list[Candle]] = {tf: base}
    for each in list(config.HTF_CHAIN.get(tf, ())) + ["15m", "1h"]:
        if each in candles:
            continue
        try:
            candles[each] = _klines(symbol, each, config.HTF_BARS if each != tf else bars, futures=futures)
        except DataError:
            notes.append(f"{each} history unavailable")
    price = base[-1].c
    deriv = Derivatives(cvd=cvd(base))
    if futures:
        deriv, dnotes = _derivatives(symbol, base, price)
        notes += dnotes
    macro, mnotes = _macro(symbol)
    notes += mnotes
    sent, snotes = _sentiment(symbol)
    notes += snotes
    src = "binance-live" + (f" · {len(notes)} caveats" if notes else "")
    return Snapshot(symbol=symbol, tf=tf, candles=candles, derivatives=deriv,
                    sentiment=sent, macro=macro, source=src, as_of=base[-1].ts)
