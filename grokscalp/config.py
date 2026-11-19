"""Static configuration: timeframes, killzones, family weights, thresholds.

Everything a trader would want to tune lives here. The engine never hardcodes
a threshold inline, so the routing table and the confluence maths stay
auditable.
"""

from __future__ import annotations

# --------------------------------------------------------------------------
# timeframes
# --------------------------------------------------------------------------

TF_MINUTES: dict[str, int] = {
    "1m": 1,
    "3m": 3,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "4h": 240,
}

SCALP_TFS = ("1m", "3m", "5m", "15m", "30m")

#: higher timeframes used for the multi-timeframe read, nearest first
HTF_CHAIN: dict[str, tuple[str, ...]] = {
    "1m": ("5m", "15m", "1h"),
    "3m": ("15m", "1h", "4h"),
    "5m": ("15m", "1h", "4h"),
    "15m": ("1h", "4h"),
    "30m": ("1h", "4h"),
    "1h": ("4h",),
    "4h": (),
}

#: how many bars of history each timeframe normally needs
DEFAULT_BARS = 400
HTF_BARS = 300

# --------------------------------------------------------------------------
# sessions / killzones (UTC, crypto is 24/7 so these are softer than FX)
# --------------------------------------------------------------------------

KILLZONES: dict[str, tuple[int, int]] = {
    "ASIA": (0, 4),
    "LONDON": (7, 11),
    "NY_AM": (12, 16),
    "NY_PM": (16, 20),
}

#: how much a signal is discounted when the session is thin
SESSION_QUALITY: dict[str, float] = {
    "LONDON": 1.00,
    "NY_AM": 1.00,
    "ASIA": 0.80,
    "NY_PM": 0.70,
    "OFF_SESSION": 0.55,
}

# --------------------------------------------------------------------------
# strategy families
# --------------------------------------------------------------------------

#: reliability of each family's evidence, 0..1. Used as a multiplier on the
#: raw weight so a candle pattern can never outvote a broken structure.
FAMILY_RELIABILITY: dict[str, float] = {
    "SMC": 1.00,        # BOS / CHoCH / OB / FVG / sweeps / OTE
    "MTF": 1.05,        # higher timeframe agreement
    "DERIV": 0.90,      # OI, funding, CVD, order book, liquidations
    "VSA": 0.80,        # volume spread analysis / wyckoff
    "IND": 0.80,        # oscillators, divergences, EMA ribbon, ichimoku
    "VP": 0.75,         # volume profile
    "PATTERN": 0.55,    # candlesticks, harmonics, chart patterns
    "MACRO": 0.65,      # BTC, DXY, USDT dominance
    "SENTIMENT": 0.55,  # fear & greed, news
    "VISION": 0.85,     # chart screenshot
    "SESSION": 0.30,    # killzone timing
}

#: regime -> family multiplier. This is the "dynamic strategy routing": the
#: same evidence counts differently in a squeeze than in a trend.
REGIME_WEIGHTS: dict[str, dict[str, float]] = {
    "TREND_UP": {
        "SMC": 1.20, "MTF": 1.25, "DERIV": 1.15, "VSA": 0.85, "IND": 1.00,
        "VP": 1.00, "PATTERN": 0.90, "MACRO": 1.00, "SENTIMENT": 0.80,
        "VISION": 1.10, "SESSION": 1.00,
    },
    "TREND_DOWN": {
        "SMC": 1.20, "MTF": 1.25, "DERIV": 1.15, "VSA": 0.85, "IND": 1.00,
        "VP": 1.00, "PATTERN": 0.90, "MACRO": 1.00, "SENTIMENT": 0.80,
        "VISION": 1.10, "SESSION": 1.00,
    },
    "RANGE": {
        "SMC": 0.95, "MTF": 0.75, "DERIV": 1.00, "VSA": 1.25, "IND": 1.15,
        "VP": 1.25, "PATTERN": 1.05, "MACRO": 0.80, "SENTIMENT": 0.70,
        "VISION": 1.00, "SESSION": 0.90,
    },
    "HIGH_VOL": {
        "SMC": 0.90, "MTF": 1.10, "DERIV": 1.20, "VSA": 0.80, "IND": 0.80,
        "VP": 0.90, "PATTERN": 0.65, "MACRO": 0.70, "SENTIMENT": 0.60,
        "VISION": 0.95, "SESSION": 0.90,
    },
    "SQUEEZE": {
        "SMC": 0.85, "MTF": 0.90, "DERIV": 1.05, "VSA": 1.15, "IND": 1.20,
        "VP": 1.10, "PATTERN": 0.90, "MACRO": 0.75, "SENTIMENT": 0.60,
        "VISION": 0.90, "SESSION": 0.85,
    },
    "ILLIQUID": {
        "SMC": 0.70, "MTF": 0.70, "DERIV": 0.70, "VSA": 1.00, "IND": 0.70,
        "VP": 0.90, "PATTERN": 0.50, "MACRO": 0.60, "SENTIMENT": 0.50,
        "VISION": 0.60, "SESSION": 0.50,
    },
}

#: playbook line printed on the card, one per regime
REGIME_PLAYBOOK: dict[str, str] = {
    "TREND_UP": "trend continuation: buy pullbacks into demand, do not fade strength",
    "TREND_DOWN": "trend continuation: sell pullbacks into supply, do not catch knives",
    "RANGE": "mean reversion between the range edges; fade extremes, target the mid",
    "HIGH_VOL": "volatility expansion: wait for the sweep, trade the reclaim, halve size",
    "SQUEEZE": "compression: no breakout chasing; trade the first retest after expansion",
    "ILLIQUID": "thin tape: stand aside, spreads and wicks are hostile",
}

# --------------------------------------------------------------------------
# confluence
# --------------------------------------------------------------------------

#: minimum net edge (0..1 after normalisation) before the engine will call a
#: direction instead of WAIT
MIN_EDGE = 0.16
MIN_CONVICTION = 0.28

#: if both sides are backed this evenly, the market has no read
MAX_CONFLICT = 0.62

#: hard floors
MIN_EVIDENCE = 4
MIN_MTF_AGREEMENT = -0.25   # HTF may disagree slightly, not fight the trade
MIN_WIN_PROBABILITY = 0.34
MAX_WIN_PROBABILITY = 0.82

#: probability mapping. p = 0.5 + SPREAD * tanh(EDGE_GAIN * edge)
PROB_SPREAD = 0.30
PROB_GAIN = 1.25

#: calibration by regime, replaced at runtime by config/calibration.json when
#: a backtest has been run on this box
CALIBRATION_PRIOR: dict[str, float] = {
    "TREND_UP": 0.0,
    "TREND_DOWN": 0.0,
    "RANGE": -0.02,
    "HIGH_VOL": -0.03,
    "SQUEEZE": -0.01,
    "ILLIQUID": -0.05,
}

# --------------------------------------------------------------------------
# risk
# --------------------------------------------------------------------------

ATR_SL_BUFFER = 0.35          # stop sits this many ATRs beyond the invalidation
ENTRY_PAD_ATR = 0.10          # widen the entry zone by this many ATRs
MIN_STOP_PCT = 0.0015         # 0.15% — anything tighter is noise
MAX_STOP_PCT = {"1m": 0.012, "3m": 0.018, "5m": 0.022, "15m": 0.030,
                "30m": 0.038, "1h": 0.055, "4h": 0.090}

#: take-profit ladder expressed in R, blended with structure where it exists
TP_R = (1.4, 2.6, 4.2)

#: leverage caps per timeframe — scalps can lever more than swing entries
MAX_LEVERAGE = {"1m": 20, "3m": 15, "5m": 12, "15m": 8, "30m": 6, "1h": 4, "4h": 3}

#: liquidation sits this many stop-widths beyond the stop
LIQ_BUFFER = 3.0
DEFAULT_EQUITY = 10_000.0
DEFAULT_RISK_PCT = 1.5
MAX_RISK_PCT = 2.0

#: signal lifetime in bars
SIGNAL_TTL_BARS = 6

# --------------------------------------------------------------------------
# vetoes
# --------------------------------------------------------------------------

#: funding above this (per 8h) means longs are crowded
FUNDING_HOT = 0.0005
#: absolute funding that makes a directional entry a bad idea
FUNDING_EXTREME = 0.0010
#: order book imbalance beyond this is a wall, not a signal
OBI_EXTREME = 0.75
#: a high-impact macro event inside this window freezes new entries
EVENT_BLACKOUT_MIN = 30
