"""GROK SCALP — an all-in-one crypto scalping & signal engine.

The engine reads candles, derivatives, order flow, sentiment and an optional
chart screenshot, routes to whichever playbook fits the current market regime,
and prints a signal card with levels, risk and the reasoning behind them.

Runs on the Python standard library. Streamlit/plotly/Pillow are optional and
only needed for the dashboard and the offline chart reader.
"""

from __future__ import annotations

from .types import (  # noqa: F401
    Candle,
    ChartReading,
    Derivatives,
    Evidence,
    Level,
    Macro,
    SignalCard,
    Snapshot,
    TradePlan,
)
from .engine import SignalEngine, analyse  # noqa: F401

__version__ = "0.1.0"
__all__ = [
    "Candle",
    "ChartReading",
    "Derivatives",
    "Evidence",
    "Level",
    "Macro",
    "SignalCard",
    "Snapshot",
    "TradePlan",
    "SignalEngine",
    "analyse",
]
