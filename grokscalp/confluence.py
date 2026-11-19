"""Turning evidence into a probability.

Every atom contributes `weight × strength × family reliability × regime
multiplier`. Nothing is allowed to be a black box: the card prints the atoms,
so a reader can see exactly which of them paid for the confidence.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import config
from .types import Evidence

#: how much weighted evidence counts as a "full" read; below this the engine
#: discounts the edge even if the two sides are far apart
FULL_READ = 3.0


@dataclass
class Verdict:
    action: str = "WAIT"
    bull: float = 0.0
    bear: float = 0.0
    edge: float = 0.0
    conflict: float = 0.0
    conviction: float = 0.0
    probability: float = 0.5
    count: int = 0
    reasons: list[str] = field(default_factory=list)
    reasons_en: list[str] = field(default_factory=list)
    weighted: dict[str, float] = field(default_factory=dict)

    @property
    def side(self) -> int:
        return 1 if self.action == "LONG" else -1 if self.action == "SHORT" else 0


def contribution(e: Evidence, regime: str) -> float:
    fam = config.FAMILY_RELIABILITY.get(e.family, 0.5)
    reg = config.REGIME_WEIGHTS.get(regime, config.REGIME_WEIGHTS["RANGE"]).get(e.family, 1.0)
    return e.weight * e.strength * fam * reg


def aggregate(evidence: list[Evidence], regime: str,
              calibration: dict | None = None) -> Verdict:
    bull = bear = 0.0
    by_family: dict[str, float] = {}
    for e in evidence:
        c = contribution(e, regime)
        by_family[e.family] = by_family.get(e.family, 0.0) + c
        if e.direction > 0:
            bull += c
        elif e.direction < 0:
            bear += c
    total = bull + bear
    diff = bull - bear
    balance = diff / total if total else 0.0
    mass = min(1.0, total / FULL_READ)
    edge = balance * mass
    conflict = (min(bull, bear) / max(bull, bear)) if max(bull, bear) > 0 else 1.0

    p_long = 0.5 + config.PROB_SPREAD * math.tanh(config.PROB_GAIN * edge)
    offset = config.CALIBRATION_PRIOR.get(regime, 0.0)
    if calibration:
        offset = calibration.get("offset", {}).get(regime, offset)
    p_long = min(config.MAX_WIN_PROBABILITY, max(config.MIN_WIN_PROBABILITY, p_long + offset))
    probability = p_long if edge >= 0 else 1.0 - p_long

    v = Verdict(bull=round(bull, 3), bear=round(bear, 3), edge=round(edge, 4),
                conflict=round(conflict, 3), conviction=round(abs(edge), 3),
                probability=round(probability, 3), count=len(evidence),
                weighted={k: round(x, 3) for k, x in by_family.items()})
    return v


def decide(v: Verdict, *, mtf: float, event_minutes: int | None, spread_bps: float,
           regime: str, funding: float, side_hint: int = 0) -> Verdict:
    """Apply the gates. A failure here is not a bug, it is the engine saying
    there is no trade — which is the most common correct answer."""
    reasons: list[str] = []
    reasons_en: list[str] = []
    direction = 1 if v.edge > 0 else -1 if v.edge < 0 else 0

    def add(fa: str, en: str) -> None:
        reasons.append(fa)
        reasons_en.append(en)

    if regime == "ILLIQUID":
        add("بازار کم‌عمق است (ILLIQUID): اسپرد و سایه‌های قیمتی به ضرر شماست.",
            "the tape is illiquid: spread and wicks work against you.")
    if v.count < config.MIN_EVIDENCE:
        add(f"تعداد شواهد کافی نیست ({v.count} از حداقل {config.MIN_EVIDENCE}).",
            f"only {v.count} evidence atoms, {config.MIN_EVIDENCE} required.")
    if abs(v.edge) < config.MIN_EDGE or v.conviction < config.MIN_CONVICTION:
        add(f"لبه آماری ضعیف است (edge {v.edge:+.2f} در برابر حداقل {config.MIN_EDGE:.2f}).",
            f"edge {v.edge:+.2f} is inside the noise band (minimum {config.MIN_EDGE:.2f}).")
    if v.conflict > config.MAX_CONFLICT:
        add(f"تضاد سیگنال‌ها بالا است ({v.conflict:.0%}): خریدار و فروشنده هر دو شواهد جدی دارند.",
            f"evidence conflict {v.conflict:.0%}: buyers and sellers both have a real case.")
    if mtf * direction < -0.25 and abs(mtf) > 0.30:
        add("تایم‌فریم‌های بالاتر خلاف جهت سیگنال هستند؛ در جهت روند بزرگ‌تر معامله کنید.",
            "higher timeframes lean the other way; trade with the larger trend.")
    if event_minutes is not None and 0 <= event_minutes <= config.EVENT_BLACKOUT_MIN:
        add(f"رویداد اقتصادی مهم تا {event_minutes} دقیقه دیگر؛ قبل از خبر پوزیشن باز نکنید.",
            f"high-impact macro event in {event_minutes} min; no new risk into the print.")
    if abs(funding) >= config.FUNDING_EXTREME and funding * direction > 0:
        add(f"فاندینگ {funding * 100:+.4f}% در جهت سیگنال اشباع شده است؛ ریسک اسکوییز روی سر شما است.",
            f"funding {funding * 100:+.4f}% is extreme on the signal's side; squeeze risk sits on you.")
    if spread_bps > 18:
        add(f"اسپرد {spread_bps:.1f} bps است؛ هزینه ورود و خروج لبه را می‌خورد.",
            f"spread is {spread_bps:.1f} bps; the round trip eats the edge.")

    if reasons:
        v.action = "WAIT"
        v.reasons = reasons
        v.reasons_en = reasons_en
    else:
        v.action = "LONG" if v.edge > 0 else "SHORT"
    return v


def calibrate_from_backtest(results: dict[str, dict]) -> dict:
    """Turn measured hit rates into bounded probability offsets.

    `results` maps a regime to {"hit_rate": float, "mean_p": float}. The offset
    is capped at ±8 points so a small sample can nudge the model, never take it
    over.
    """
    offset = {}
    for regime, r in results.items():
        if not r or "hit_rate" not in r or "mean_p" not in r:
            continue
        offset[regime] = round(max(-0.08, min(0.08, r["hit_rate"] - r["mean_p"])), 4)
    return {"offset": offset}
