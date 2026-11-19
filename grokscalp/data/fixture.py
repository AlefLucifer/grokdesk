"""Capture-and-replay: turn raw exchange JSON into a Snapshot, or load one.

Useful when the box that runs the dashboard has no exchange access, when you
want a reproducible card for a post, or when you want to hand someone the exact
data behind a signal. `dump()` writes the snapshot, `load()` reads it back.

The builders accept the exchange's own payloads (Binance klines/premiumIndex/
openInterest/depth, alternative.me fng, Frankfurter FX, CoinGecko global), so no
transformation is needed between `curl` and this module.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..indicators import cvd
from ..types import (Candle, Derivatives, LiquidationBucket, Macro, MacroEvent,
                     OrderBook, Sentiment, Snapshot, WhalePrint)


def parse_klines(rows: list[list[Any]]) -> list[Candle]:
    out: list[Candle] = []
    for r in rows:
        try:
            out.append(Candle(
                ts=int(r[0]), o=float(r[1]), h=float(r[2]), l=float(r[3]),
                c=float(r[4]), v=float(r[5]),
                tb=float(r[9]) if len(r) > 9 else 0.0,
            ))
        except (TypeError, ValueError, IndexError):
            continue
    return out


def _dxy(rates: dict[str, Any]) -> float:
    return (50.14348112 * (1 / float(rates["EUR"])) ** -0.576
            * float(rates["JPY"]) ** 0.136 * (1 / float(rates["GBP"])) ** -0.119
            * float(rates["CAD"]) ** 0.091 * float(rates["SEK"]) ** 0.042
            * float(rates["CHF"]) ** 0.036)


def _liquidation_estimate(candles: list[Candle], price: float) -> list[LiquidationBucket]:
    buckets: list[LiquidationBucket] = []
    for c in candles[-60:]:
        w = c.v * c.c
        if w <= 0:
            continue
        buckets.append(LiquidationBucket(c.h * 1.0009, round(w * 1.6, 2), "short"))
        buckets.append(LiquidationBucket(c.l * 0.9991, round(w * 1.6, 2), "long"))
    buckets.sort(key=lambda b: abs(b.price - price))
    return buckets[:50]


def from_api(*, symbol: str, tf: str, klines: list[list[Any]],
             htf: dict[str, list[list[Any]]] | None = None,
             funding: dict[str, Any] | None = None,
             funding_history: list[dict[str, Any]] | None = None,
             open_interest: dict[str, Any] | None = None,
             oi_history: list[dict[str, Any]] | None = None,
             depth: dict[str, Any] | None = None,
             fng: dict[str, Any] | None = None,
             fx: dict[str, Any] | None = None,
             glob: dict[str, Any] | None = None,
             btc_24h: dict[str, Any] | None = None,
             headlines: list[dict[str, Any]] | None = None,
             events: list[dict[str, Any]] | None = None,
             now_ms: int | None = None) -> Snapshot:
    base = parse_klines(klines)
    if not base:
        raise ValueError("no usable klines")
    price = base[-1].c
    candles: dict[str, list[Candle]] = {tf: base}
    for name, rows in (htf or {}).items():
        parsed = parse_klines(rows)
        if parsed:
            candles[name] = parsed

    deriv = Derivatives(cvd=cvd(base))
    if funding:
        deriv.funding = float(funding.get("lastFundingRate", 0.0))
    if funding_history:
        deriv.funding_history = [float(x["fundingRate"]) for x in funding_history
                                 if "fundingRate" in x]
    if open_interest:
        deriv.oi = float(open_interest.get("openInterest", 0.0))
    if oi_history:
        deriv.oi_history = [float(x["sumOpenInterest"]) for x in oi_history
                            if "sumOpenInterest" in x]
    if deriv.oi and not deriv.oi_history:
        deriv.oi_history = [deriv.oi]
    if depth:
        deriv.orderbook = OrderBook(
            bids=[(float(p), float(q)) for p, q in depth.get("bids", [])],
            asks=[(float(p), float(q)) for p, q in depth.get("asks", [])],
        )
    deriv.liquidations = _liquidation_estimate(base, price)
    deriv.whales = []

    sent = Sentiment()
    if fng:
        try:
            row = fng["data"][0]
            sent.fear_greed = int(row["value"])
            sent.fear_greed_label = row.get("value_classification", "")
            sent.fear_greed_history = [int(r["value"]) for r in fng["data"]]
        except (KeyError, IndexError, TypeError, ValueError):
            pass
    if headlines:
        from ..types import Headline
        sent.headlines = [Headline(ts=int(h.get("ts", 0)), title=h.get("title", ""),
                                   source=h.get("source", ""), score=float(h.get("score", 0.0)),
                                   impact=h.get("impact", "med")) for h in headlines]
        if sent.headlines:
            sent.news_score = sum(h.score for h in sent.headlines) / len(sent.headlines)
    if events:
        sent.events = [MacroEvent(ts=int(e.get("ts", 0)), name=e.get("name", "event"),
                                  impact=e.get("impact", "high"),
                                  minutes_away=int(e.get("minutes_away", 999))) for e in events]

    macro = Macro()
    if btc_24h:
        macro.btc_change_24h = float(btc_24h.get("priceChangePercent", 0.0))
        macro.btc_trend = max(-1.0, min(1.0, macro.btc_change_24h / 5.0))
    if glob:
        try:
            dom = glob["data"]["market_cap_percentage"]
            macro.btc_dominance = float(dom.get("btc", macro.btc_dominance))
            macro.usdt_dominance = float(dom.get("usdt", macro.usdt_dominance))
        except (KeyError, TypeError, ValueError):
            pass
    if fx and fx.get("rates"):
        try:
            macro.dxy = round(_dxy(fx["rates"]), 2)
        except (KeyError, TypeError, ValueError):
            pass

    return Snapshot(symbol=symbol.upper(), tf=tf, candles=candles, derivatives=deriv,
                    sentiment=sent, macro=macro,
                    source="fixture:captured", as_of=base[-1].ts or int(now_ms or 0))


def dump(snap: Snapshot, path: str | Path) -> str:
    """Serialise a snapshot so the exact card can be reproduced later."""
    payload = {
        "symbol": snap.symbol, "tf": snap.tf, "source": snap.source, "as_of": snap.as_of,
        "candles": {tf: [[c.ts, c.o, c.h, c.l, c.c, c.v, c.tb] for c in series]
                    for tf, series in snap.candles.items()},
        "derivatives": {
            "funding": snap.derivatives.funding,
            "funding_history": snap.derivatives.funding_history,
            "oi": snap.derivatives.oi,
            "oi_history": snap.derivatives.oi_history,
            "long_short_ratio": snap.derivatives.long_short_ratio,
            "taker_ratio": snap.derivatives.taker_ratio,
            "orderbook": {"bids": snap.derivatives.orderbook.bids,
                          "asks": snap.derivatives.orderbook.asks},
            "liquidations": [[b.price, b.notional, b.side] for b in snap.derivatives.liquidations],
            "whales": [[w.ts, w.price, w.notional, w.side] for w in snap.derivatives.whales],
        },
        "sentiment": {
            "fear_greed": snap.sentiment.fear_greed,
            "fear_greed_label": snap.sentiment.fear_greed_label,
            "fear_greed_history": snap.sentiment.fear_greed_history,
            "news_score": snap.sentiment.news_score,
            "headlines": [h.__dict__ for h in snap.sentiment.headlines],
            "events": [e.__dict__ for e in snap.sentiment.events],
        },
        "macro": snap.macro.__dict__,
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return str(path)


def load(path: str | Path) -> Snapshot:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    candles = {tf: [Candle(ts=r[0], o=r[1], h=r[2], l=r[3], c=r[4], v=r[5],
                           tb=r[6] if len(r) > 6 else 0.0) for r in rows]
               for tf, rows in data["candles"].items()}
    d = data.get("derivatives", {})
    deriv = Derivatives(
        funding=d.get("funding", 0.0),
        funding_history=d.get("funding_history", []),
        oi=d.get("oi", 0.0),
        oi_history=d.get("oi_history", []),
        long_short_ratio=d.get("long_short_ratio", 1.0),
        taker_ratio=d.get("taker_ratio", 1.0),
        orderbook=OrderBook(bids=[(p, q) for p, q in d.get("orderbook", {}).get("bids", [])],
                            asks=[(p, q) for p, q in d.get("orderbook", {}).get("asks", [])]),
        liquidations=[LiquidationBucket(*b) for b in d.get("liquidations", [])],
        whales=[WhalePrint(*w) for w in d.get("whales", [])],
    )
    tf = data["tf"]
    deriv.cvd = cvd(candles[tf])
    s = data.get("sentiment", {})
    sent = Sentiment(
        fear_greed=s.get("fear_greed", 50), fear_greed_label=s.get("fear_greed_label", "Neutral"),
        fear_greed_history=s.get("fear_greed_history", []),
        news_score=s.get("news_score", 0.0),
    )
    from ..types import Headline
    sent.headlines = [Headline(**h) for h in s.get("headlines", [])]
    sent.events = [MacroEvent(**e) for e in s.get("events", [])]
    macro = Macro(**data.get("macro", {}))
    return Snapshot(symbol=data["symbol"], tf=tf, candles=candles, derivatives=deriv,
                    sentiment=sent, macro=macro, source=data.get("source", "fixture"),
                    as_of=data.get("as_of", candles[tf][-1].ts))


def load_snapshot(symbol: str, tf: str, *, path: str | Path | None = None) -> Snapshot:
    """Small adapter so the CLI can treat a fixture like any other source."""
    if not path:
        raise ValueError("a fixture path is required")
    snap = load(path)
    if snap.tf != tf:
        raise ValueError(f"fixture is {snap.tf}, not {tf}")
    return snap


__all__ = ["from_api", "dump", "load", "load_snapshot", "parse_klines"]
