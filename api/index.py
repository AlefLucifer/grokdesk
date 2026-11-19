"""Vercel Python function for GROK SCALP.

One file, three routes, no framework: the engine is standard library, so the
whole API is a `BaseHTTPRequestHandler`. `dispatch()` is pure and reused by the
local dev server in `scripts/vercel_dev.py`, so what runs here is what you can
test on your machine.
"""

from __future__ import annotations

import base64
import binascii
import json
import os
import sys
import time
import traceback
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from grokscalp import __version__, config                      # noqa: E402
from grokscalp.data import available_symbols, load_snapshot   # noqa: E402
from grokscalp.engine import SignalEngine, load_calibration    # noqa: E402
from grokscalp.render.card import render_card, render_short    # noqa: E402
from grokscalp.risk import fmt_price                           # noqa: E402
from grokscalp.vision import ChartReader                       # noqa: E402

TFS = list(config.TF_MINUTES)
MAX_IMAGE = 4_000_000


def _clean_symbol(raw: str) -> str:
    sym = "".join(ch for ch in (raw or "").upper() if ch.isalnum())[:20]
    if not sym:
        return "BTCUSDT"
    if not any(sym.endswith(q) and len(sym) > len(q)
               for q in ("USDT", "USDC", "FDUSD", "BTC", "ETH")):
        sym += "USDT"
    return sym


def _float(q: dict, key: str, default: float, lo: float, hi: float) -> float:
    try:
        return max(lo, min(hi, float(q.get(key, [default])[0])))
    except (TypeError, ValueError):
        return default


def _market(snap) -> dict:
    """The derivatives / sentiment panel of the dashboard, flattened for JSON.

    The card carries prose about the flow; these are the raw numbers behind it
    so the UI can draw tables and metrics without re-reading the exchange.
    """
    d = snap.derivatives
    s = snap.sentiment
    m = snap.macro
    price = snap.price or 0.0

    def dist(b) -> float:
        return (b.price / price - 1.0) * 100.0 if price else 0.0

    liquidations = sorted(d.liquidations, key=lambda b: abs(b.price - price))[:8]
    events = sorted((e for e in s.events if e.minutes_away >= 0), key=lambda e: e.minutes_away)
    nxt = events[0] if events else None
    cvd = d.cvd or []
    funding = d.funding or 0.0
    return {
        "derivatives": {
            "funding": funding,
            "funding_bias": ("لانگ‌ها می‌پردازند" if funding > 0
                             else "شورت‌ها می‌پردازند" if funding < 0 else "خنثی"),
            "oi": d.oi,
            "oi_change": d.oi_trend_pct,
            "long_short_ratio": d.long_short_ratio,
            "taker_ratio": d.taker_ratio,
            "obi": d.obi,
            "spread": d.orderbook.spread_bps,
            "whale_net": d.whale_net,
            "whale_count": len(d.whales),
            "cvd": cvd[-1] if cvd else 0.0,
            "delta20": (cvd[-1] - cvd[-21]) if len(cvd) > 21 else 0.0,
            "liquidations": [
                {"price": b.price, "notional": b.notional, "side": b.side, "distance": dist(b)}
                for b in liquidations
            ],
        },
        "fear_greed": s.fear_greed,
        "fear_greed_label": s.fear_greed_label,
        "news_score": s.news_score,
        "headlines": [
            {"title": h.title, "source": h.source, "score": h.score, "impact": h.impact}
            for h in s.headlines[:12]
        ],
        "next_event": ({"name": nxt.name, "minutes_away": nxt.minutes_away,
                        "impact": nxt.impact} if nxt else None),
        "macro": {
            "btc_trend": m.btc_trend,
            "btc_change_24h": m.btc_change_24h,
            "btc_dominance": m.btc_dominance,
            "usdt_dominance": m.usdt_dominance,
            "usdt_dom_change": m.usdt_dom_change,
            "dxy": m.dxy,
            "dxy_change": m.dxy_change,
        },
    }


def _analyse(symbol: str, tf: str, live: bool, equity: float, risk: float, lang: str,
             image: bytes | None = None) -> dict:
    started = time.time()
    snap = load_snapshot(symbol, tf, live=live, bars=config.DEFAULT_BARS)
    chart = ChartReader().read(image, symbol, tf) if image else None
    engine = SignalEngine(equity=equity, risk_pct=risk, calibration=load_calibration())
    card = engine.analyse(snap, chart)

    payload = asdict(card)
    payload.pop("snapshot", None)
    series = [[c.ts, c.o, c.h, c.l, c.c, c.v] for c in snap.series()[-200:]]
    return {
        "card": payload,
        "market": _market(snap),
        "series": series,
        "price": snap.price,
        "source": snap.source,
        "text": render_card(card, lang),
        "short": render_short(card, lang),
        "meta": {
            "engine": "grokscalp",
            "version": __version__,
            "ms": int((time.time() - started) * 1000),
            "tf": tf,
            "symbol": snap.symbol,
            "live_requested": live,
            "labels": {"price": fmt_price(snap.price)},
        },
    }


def _scan(symbols: list[str], tf: str, live: bool, seed: int) -> dict:
    engine = SignalEngine(calibration=load_calibration())
    rows = []
    for sym in symbols[:16]:
        try:
            snap = load_snapshot(sym, tf, live=live, bars=300, seed=seed)
            card = engine.analyse(snap)
            rows.append({
                "symbol": snap.symbol, "action": card.action, "regime": card.regime.name,
                "price": fmt_price(snap.price), "probability": round(card.probability * 100),
                "edge": round(card.edge, 2), "conflict": round(card.conflict * 100),
                "entry": fmt_price(card.plan.entry) if card.action != "WAIT" else "—",
                "sl": fmt_price(card.plan.sl) if card.action != "WAIT" else "—",
                "tp2": fmt_price(card.plan.tp2) if card.action != "WAIT" else "—",
                "rr": round(card.plan.rr, 1) if card.action != "WAIT" else None,
                "leverage": card.plan.leverage if card.action != "WAIT" else None,
                "session": card.session,
            })
        except Exception as exc:  # one bad symbol must not kill the scan
            rows.append({"symbol": sym, "action": "ERROR", "regime": "",
                         "error": f"{type(exc).__name__}: {exc}"})
    return {"rows": rows, "tf": tf, "live": live}


def _vision(body: dict) -> dict:
    raw = body.get("image") or ""
    if not raw:
        raise ValueError("image is required (base64 or data URL)")
    if "," in raw[:200] and raw.lstrip().startswith("data:"):
        raw = raw.split(",", 1)[1]
    try:
        data = base64.b64decode(raw, validate=False)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("image is not valid base64") from exc
    if len(data) > MAX_IMAGE:
        raise ValueError("image is larger than 4 MB")
    reading = ChartReader().read(data, _clean_symbol(body.get("symbol", "")),
                                 str(body.get("tf", "")))
    return asdict(reading)


def dispatch(method: str, path: str, body: bytes | None = None) -> tuple[int, dict]:
    """(status, payload) for every route. Used by the handler and the dev server."""
    u = urlparse(path)
    q = parse_qs(u.query)
    route = u.path.rstrip("/") or "/"

    try:
        if route in ("/api/health", "/health"):
            return 200, {"ok": True, "engine": "grokscalp", "version": __version__,
                         "timeframes": TFS, "symbols": available_symbols()}
        if route == "/api/symbols":
            return 200, {"symbols": available_symbols()}

        if route == "/api/signal":
            tf = q.get("tf", ["5m"])[0]
            if tf not in TFS:
                return 400, {"error": f"timeframe must be one of {TFS}"}
            symbol = _clean_symbol(q.get("symbol", ["BTCUSDT"])[0])
            live = q.get("live", ["1"])[0] not in ("0", "false", "no")
            equity = _float(q, "equity", config.DEFAULT_EQUITY, 100, 10_000_000)
            risk = _float(q, "risk", config.DEFAULT_RISK_PCT, 0.1, config.MAX_RISK_PCT)
            lang = "en" if q.get("lang", ["fa"])[0] == "en" else "fa"
            return 200, _analyse(symbol, tf, live, equity, risk, lang)

        if route == "/api/scan":
            tf = q.get("tf", ["5m"])[0]
            if tf not in TFS:
                return 400, {"error": f"timeframe must be one of {TFS}"}
            raw = q.get("symbols", [""])[0]
            symbols = [_clean_symbol(s) for s in raw.split(",") if s.strip()] or available_symbols()[:10]
            live = q.get("live", ["0"])[0] not in ("0", "false", "no")
            return 200, _scan(symbols, tf, live, int(_float(q, "seed", 0, 0, 99999)))

        if route == "/api/vision" and method == "POST":
            payload = json.loads((body or b"{}").decode("utf-8") or "{}")
            return 200, _vision(payload)

        if route == "/api/analyse" and method == "POST":
            payload = json.loads((body or b"{}").decode("utf-8") or "{}")
            tf = str(payload.get("tf", "5m"))
            if tf not in TFS:
                return 400, {"error": f"timeframe must be one of {TFS}"}
            image = payload.get("image")
            image_bytes = None
            if image:
                if image.lstrip().startswith("data:") and "," in image:
                    image = image.split(",", 1)[1]
                image_bytes = base64.b64decode(image, validate=False)
            return 200, _analyse(_clean_symbol(str(payload.get("symbol", "BTCUSDT"))), tf,
                                 bool(payload.get("live", True)),
                                 float(payload.get("equity", config.DEFAULT_EQUITY)),
                                 float(payload.get("risk", config.DEFAULT_RISK_PCT)),
                                 "en" if payload.get("lang") == "en" else "fa",
                                 image_bytes)

        return 404, {"error": "unknown route", "path": u.path,
                     "routes": ["/api/health", "/api/symbols", "/api/signal",
                                "/api/scan", "/api/vision", "/api/analyse"]}
    except Exception as exc:
        return 500, {"error": str(exc), "type": type(exc).__name__,
                     "trace": traceback.format_exc(limit=3)}


class handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        status, payload = dispatch("GET", self.path)
        self._send(status, payload)

    def do_POST(self) -> None:  # noqa: N802
        try:
            length = int(self.headers.get("content-length") or 0)
        except ValueError:
            length = 0
        body = self.rfile.read(min(length, 6_000_000)) if length else b""
        status, payload = dispatch("POST", self.path, body)
        self._send(status, payload)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, fmt: str, *args) -> None:  # keep Vercel logs readable
        sys.stderr.write("%s\n" % (fmt % args))
