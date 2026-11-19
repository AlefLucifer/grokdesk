from __future__ import annotations

from . import synthetic

__all__ = ["load_snapshot", "available_symbols", "QUOTES"]

QUOTES = ("USDT", "USDC", "FDUSD", "BTC", "ETH", "BNB")


def normalize(symbol: str) -> str:
    sym = (symbol or "").strip().upper().replace("/", "").replace("-", "").replace(" ", "")
    if not sym:
        return "BTCUSDT"
    if any(sym.endswith(q) and len(sym) > len(q) for q in QUOTES):
        return sym
    return sym + "USDT"


def available_symbols() -> list[str]:
    return list(synthetic.SYMBOLS)


def load_snapshot(symbol: str, tf: str, *, live: bool = False, bars: int = 400,
                  now_ms: int | None = None, seed: int = 0):
    """One entry point for both modes.

    `live=False` keeps everything offline and deterministic. `live=True` tries
    the public Binance endpoints and degrades to synthetic if the network or the
    symbol is unavailable, so the card always renders.
    """
    sym = normalize(symbol)
    if live:
        try:
            from . import binance
            return binance.load(sym, tf, bars=bars, now_ms=now_ms, seed=seed)
        except Exception as exc:  # network, rate limit, unknown symbol
            snap = synthetic.snapshot(sym, tf, bars=bars, now_ms=now_ms, seed=seed)
            snap.source = f"synthetic (live failed: {type(exc).__name__})"
            return snap
    return synthetic.snapshot(sym, tf, bars=bars, now_ms=now_ms, seed=seed)
