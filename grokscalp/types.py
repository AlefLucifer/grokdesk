from __future__ import annotations

from dataclasses import dataclass, field
from time import time


# --------------------------------------------------------------------------
# raw market
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Candle:
    ts: int
    o: float
    h: float
    l: float
    c: float
    v: float = 0.0
    tb: float = 0.0          # taker buy base volume (aggressive buyers)

    @property
    def body(self) -> float:
        return abs(self.c - self.o)

    @property
    def range(self) -> float:
        return max(self.h - self.l, 1e-12)

    @property
    def bull(self) -> bool:
        return self.c >= self.o

    @property
    def upper_wick(self) -> float:
        return self.h - max(self.o, self.c)

    @property
    def lower_wick(self) -> float:
        return min(self.o, self.c) - self.l

    @property
    def delta(self) -> float:
        """Net aggressive flow in base units for this bar."""
        return 2.0 * self.tb - self.v

    @property
    def notional(self) -> float:
        return self.v * self.c


@dataclass
class OrderBook:
    bids: list[tuple[float, float]] = field(default_factory=list)   # price, size
    asks: list[tuple[float, float]] = field(default_factory=list)

    @property
    def best_bid(self) -> float | None:
        return self.bids[0][0] if self.bids else None

    @property
    def best_ask(self) -> float | None:
        return self.asks[0][0] if self.asks else None

    @property
    def mid(self) -> float | None:
        if self.best_bid and self.best_ask:
            return (self.best_bid + self.best_ask) / 2
        return None

    @property
    def spread_bps(self) -> float:
        mid = self.mid
        if not mid:
            return 0.0
        return (self.best_ask - self.best_bid) / mid * 10_000.0


@dataclass
class LiquidationBucket:
    price: float
    notional: float          # USD
    side: str                # "long" = longs get liquidated below price


@dataclass
class WhalePrint:
    ts: int
    price: float
    notional: float
    side: str                # "buy" | "sell"


@dataclass
class Derivatives:
    funding: float = 0.0                 # current rate per 8h, as a fraction
    funding_history: list[float] = field(default_factory=list)
    oi: float = 0.0                      # open interest, base units
    oi_history: list[float] = field(default_factory=list)
    long_short_ratio: float = 1.0
    taker_ratio: float = 1.0
    orderbook: OrderBook = field(default_factory=OrderBook)
    liquidations: list[LiquidationBucket] = field(default_factory=list)
    whales: list[WhalePrint] = field(default_factory=list)
    cvd: list[float] = field(default_factory=list)

    @property
    def oi_change_pct(self) -> float:
        if len(self.oi_history) < 2 or not self.oi_history[-2]:
            return 0.0
        return (self.oi_history[-1] / self.oi_history[-2] - 1.0) * 100.0

    @property
    def oi_trend_pct(self) -> float:
        """Change across the whole stored window (~2h of 5m points)."""
        if not self.oi_history or not self.oi_history[0]:
            return 0.0
        return (self.oi_history[-1] / self.oi_history[0] - 1.0) * 100.0

    @property
    def obi(self) -> float:
        """(-1..1) book imbalance from the top of the ladder."""
        b = sum(s for _, s in self.orderbook.bids[:15])
        a = sum(s for _, s in self.orderbook.asks[:15])
        if b + a <= 0:
            return 0.0
        return (b - a) / (b + a)

    @property
    def whale_net(self) -> float:
        return sum(p.notional if p.side == "buy" else -p.notional for p in self.whales)


# --------------------------------------------------------------------------
# context
# --------------------------------------------------------------------------

@dataclass
class Headline:
    ts: int
    title: str
    source: str = ""
    score: float = 0.0       # -1..1, negative = FUD
    impact: str = "med"      # low | med | high


@dataclass
class MacroEvent:
    ts: int
    name: str
    impact: str = "high"
    minutes_away: int = 999


@dataclass
class Sentiment:
    fear_greed: int = 50
    fear_greed_label: str = "Neutral"
    fear_greed_history: list[int] = field(default_factory=list)
    news_score: float = 0.0
    headlines: list[Headline] = field(default_factory=list)
    events: list[MacroEvent] = field(default_factory=list)

    @property
    def next_event(self) -> MacroEvent | None:
        live = [e for e in self.events if e.minutes_away >= 0]
        return min(live, key=lambda e: e.minutes_away) if live else None


@dataclass
class Macro:
    btc_trend: float = 0.0               # -1..1
    btc_change_24h: float = 0.0          # percent
    btc_dominance: float = 55.0
    usdt_dominance: float = 5.0
    usdt_dom_change: float = 0.0         # percentage points over 24h
    dxy: float | None = None
    dxy_change: float = 0.0              # percent over 24h


@dataclass
class Snapshot:
    symbol: str
    tf: str
    candles: dict[str, list[Candle]]
    derivatives: Derivatives = field(default_factory=Derivatives)
    sentiment: Sentiment = field(default_factory=Sentiment)
    macro: Macro = field(default_factory=Macro)
    source: str = "synthetic"
    as_of: int = 0

    @property
    def base(self) -> str:
        return self.symbol.upper()

    @property
    def price(self) -> float:
        series = self.candles.get(self.tf) or next(iter(self.candles.values()))
        return series[-1].c if series else 0.0

    def series(self, tf: str | None = None) -> list[Candle]:
        return self.candles.get(tf or self.tf, [])


# --------------------------------------------------------------------------
# analysis
# --------------------------------------------------------------------------

@dataclass
class Evidence:
    """One readable atom of confluence. The card shows these; the score is
    just their weighted sum, so every point of probability is traceable."""
    code: str
    family: str
    direction: int          # +1 long, -1 short, 0 neutral
    weight: float           # 0..1, before family/regime multipliers
    strength: float         # 0..1, how clean the read is
    note: str               # what a human would say
    ref: dict = field(default_factory=dict)

    @property
    def signed(self) -> float:
        return self.direction * self.weight * self.strength


@dataclass
class Level:
    kind: str               # ob | fvg | sr | liq | ote | vp | entry | sl | tp
    lo: float
    hi: float
    note: str = ""
    strength: float = 0.5
    ts: int = 0

    @property
    def mid(self) -> float:
        return (self.lo + self.hi) / 2

    def contains(self, price: float, pad: float = 0.0) -> bool:
        return self.lo - pad <= price <= self.hi + pad


@dataclass
class Structure:
    trend: int = 0                       # -1/0/+1 on the traded timeframe
    label: str = "unclear"
    events: list[dict] = field(default_factory=list)   # BOS / CHoCH
    last_high: float = 0.0
    last_low: float = 0.0
    swing_highs: list[float] = field(default_factory=list)
    swing_lows: list[float] = field(default_factory=list)
    order_blocks: list[Level] = field(default_factory=list)
    fvgs: list[Level] = field(default_factory=list)
    pools: list[Level] = field(default_factory=list)   # BSL above / SSL below
    sr: list[Level] = field(default_factory=list)
    ote: Level | None = None
    sweep: dict = field(default_factory=dict)
    range_high: float = 0.0
    range_low: float = 0.0
    premium_discount: float = 0.5        # 0 = range low, 1 = range high


@dataclass
class Regime:
    name: str
    confidence: float
    playbook: str
    adx: float = 0.0
    atr_pct: float = 0.0
    atr_percentile: float = 0.5
    volume_z: float = 0.0
    bb_width_pct: float = 0.5
    ema_slope: float = 0.0
    notes: list[str] = field(default_factory=list)


@dataclass
class ChartReading:
    """What the vision layer extracted from a screenshot."""
    available: bool = False
    method: str = "none"                 # vision-api | vision-lite | none
    trend: int = 0
    trend_label: str = "unknown"
    range_position: float = 0.5
    support: list[float] = field(default_factory=list)
    resistance: list[float] = field(default_factory=list)
    patterns: list[str] = field(default_factory=list)
    indicators_seen: list[str] = field(default_factory=list)
    timeframe_seen: str = ""
    notes: list[str] = field(default_factory=list)
    confidence: float = 0.0
    raw: dict = field(default_factory=dict)


@dataclass
class TradePlan:
    action: str = "WAIT"
    order_type: str = "no order"
    entry: float = 0.0
    entry_lo: float = 0.0
    entry_hi: float = 0.0
    sl: float = 0.0
    tp1: float = 0.0
    tp2: float = 0.0
    tp3: float = 0.0
    rr: float = 0.0
    rr_tp1: float = 0.0
    rr_tp3: float = 0.0
    leverage: int = 1
    risk_pct: float = 1.5
    margin_pct: float = 0.0
    notional: float = 0.0
    qty: float = 0.0
    risk_amount: float = 0.0
    stop_pct: float = 0.0
    invalidation: list[str] = field(default_factory=list)
    trailing: list[str] = field(default_factory=list)
    invalidation_en: list[str] = field(default_factory=list)
    trailing_en: list[str] = field(default_factory=list)
    ttl_bars: int = 6

    @property
    def risk_reward(self) -> float:
        risk = abs(self.entry - self.sl)
        return abs(self.tp2 - self.entry) / risk if risk else 0.0


@dataclass
class SignalCard:
    symbol: str
    tf: str
    action: str                        # LONG | SHORT | WAIT
    order_type: str
    plan: TradePlan
    probability: float
    conviction: float
    edge: float
    bull_score: float
    bear_score: float
    conflict: float
    regime: Regime
    session: str
    session_quality: float
    structure: Structure
    evidence: list[Evidence]
    why_strategies: list[str] = field(default_factory=list)
    why_technical: list[str] = field(default_factory=list)
    why_data: list[str] = field(default_factory=list)
    context: list[str] = field(default_factory=list)
    wait_reasons: list[str] = field(default_factory=list)
    wait_reasons_en: list[str] = field(default_factory=list)
    strategy_families: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    warnings_en: list[str] = field(default_factory=list)
    chart: ChartReading = field(default_factory=ChartReading)
    snapshot: Snapshot | None = None
    calibration: dict = field(default_factory=dict)
    generated_at: float = field(default_factory=time)

    def top(self, n: int = 6) -> list[Evidence]:
        side = 1 if self.action == "LONG" else -1 if self.action == "SHORT" else 0
        pool = [e for e in self.evidence if side == 0 or e.direction == side]
        return sorted(pool, key=lambda e: -abs(e.signed))[:n]
