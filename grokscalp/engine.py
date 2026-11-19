"""The engine: one snapshot in, one signal card out.

Flow: read the tape -> classify the regime -> run every playbook -> weight the
evidence by regime -> gate it -> size the trade -> explain it.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Sequence

from . import config
from .confluence import aggregate, decide
from .derivatives import derivatives_evidence, funding_bias, price_change_pct
from .indicators import (adx, atr, bollinger, clamp, divergence, ema, ichimoku,
                         last, macd, rsi, stoch, value_at, volume_profile, vwap,
                         zscore)
from .patterns import candle_patterns, chart_patterns, harmonic_patterns, vsa_read
from .regime import classify, macro_risk, mtf_agreement, tactics
from .risk import build_plan, fmt_price
from .structure import analyse_structure, trendline, zigzag
from .types import (Candle, ChartReading, Evidence, Regime, SignalCard, Snapshot,
                    Structure, TradePlan)

Calibration = dict


PLAYBOOK_FA = {
    "TREND_UP": "ادامه روند: خرید پولبک به تقاضا، نه مقابله با قدرت",
    "TREND_DOWN": "ادامه روند: فروش پولبک به عرضه، نه گرفتن چاقوی در حال سقوط",
    "RANGE": "بازگشت به میانگین بین لبه‌های رنج؛ معامله از لبه‌ها به سمت میانه",
    "HIGH_VOL": "انبساط نوسان: صبر برای سوییپ، معامله روی بازپس‌گیری، نصف کردن حجم",
    "SQUEEZE": "فشردگی: بریک‌اوت شکار نکن؛ اولین ریتست بعد از انبساط",
    "ILLIQUID": "بازار نازک: ورود نکن، اسپرد و سایه‌ها به ضرر توست",
}
SESSION_FA_SHORT = {"ASIA": "آسیا", "LONDON": "لندن", "NY_AM": "نیویورک (صبح)",
                    "NY_PM": "نیویورک (بعدازظهر)", "OFF_SESSION": "خارج از سشن اصلی"}

#: Persian labels for the structural read and the pattern atoms
STRUCTURE_FA = {"bullish": "صعودی", "bearish": "نزولی", "unclear": "نامشخص",
                "bullish (stale)": "صعودی (قدیمی)", "bearish (stale)": "نزولی (قدیمی)"}
PATTERN_FA = {
    "engulf_bull": "پوشای صعودی", "engulf_bear": "پوشای نزولی",
    "hammer": "چکش / رد شدن سایه پایین", "star": "ستاره دنباله‌دار / رد سایه بالا",
    "doji": "دوجی (بی‌تصمیمی)", "inside": "اینساید بار (فشردگی)",
    "morning_star": "ستاره صبحگاهی", "evening_star": "ستاره شامگاهی",
    "three_soldiers": "سه سرباز سفید", "three_crows": "سه کلاغ سیاه",
    "harmonic": "الگوی هارمونیک", "spring": "اسپرینگ وایکوف (شکار فروشنده)",
    "upthrust": "آپ‌تراست وایکوف (شکار خریدار)", "stopping_vol": "حجم متوقف‌کننده",
    "no_demand": "نبود تقاضا", "no_supply": "نبود عرضه", "effort_result": "تلاش در برابر نتیجه",
    "wyckoff_acc": "فاز انباشت وایکوف", "wyckoff_dist": "فاز توزیع وایکوف",
    "double_top": "سقف دوقلو با شکست گردن", "double_top_unconf": "سقف دوقلوی در حال شکل‌گیری",
    "double_bottom": "کف دوقلو با شکست گردن", "double_bottom_unconf": "کف دوقلوی در حال شکل‌گیری",
    "triangle": "مثلث متقارن (فشردگی)", "breakout_up": "بریک‌اوت صعودی با حجم",
    "breakout_dn": "بریک‌دان نزولی با حجم",
}


# --------------------------------------------------------------------------
# session
# --------------------------------------------------------------------------

def session_of(ts_ms: int) -> tuple[str, float]:
    hour = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).hour
    for name, (start, end) in config.KILLZONES.items():
        if start <= hour < end:
            return name, config.SESSION_QUALITY[name]
    return "OFF_SESSION", config.SESSION_QUALITY["OFF_SESSION"]


def _ev(code: str, family: str, direction: int, weight: float, strength: float,
        note: str, **ref) -> dict:
    return {"code": code, "family": family, "direction": direction,
            "weight": clamp(weight), "strength": clamp(strength), "note": note, "ref": ref}


# --------------------------------------------------------------------------
# evidence builders
# --------------------------------------------------------------------------

def smc_evidence(candles: Sequence[Candle], st: Structure, atr_v: float, price: float) -> list[dict]:
    out: list[dict] = []
    if st.events:
        ev = st.events[-1]
        age = len(candles) - 1 - ev["i"]
        if age <= 25:
            d = ev["direction"]
            out.append(_ev(
                f"{ev['kind'].lower()}_{'bull' if d > 0 else 'bear'}",
                "SMC", d, 0.85, clamp(0.9 - age / 30),
                f"{ev['kind']} {'bullish' if d > 0 else 'bearish'} through {ev['price']:.6g} "
                f"{age} bars ago (close {ev['close']:.6g})",
                level=ev["price"], age=age,
            ))
    if st.sweep:
        sw = st.sweep
        out.append(_ev(
            "liquidity_sweep", "SMC", sw["direction"], 0.8, sw["score"],
            f"{sw['side']} swept at {sw['level']:.6g}, closed back inside on "
            f"{sw['volume_z']:.1f}x average volume ({sw['bars_ago']} bars ago)",
            level=sw["level"], bars_ago=sw["bars_ago"],
        ))
    for z in st.order_blocks:
        if z.contains(price, atr_v * 0.15):
            d = 1 if "bull" in z.note else -1
            strict = z.contains(price)
            side_txt = "inside" if strict else "retesting"
            out.append(_ev("ob_price_inside", "SMC", d, 0.8 if strict else 0.65, z.strength,
                           f"price is {side_txt} a {z.note} {z.lo:.6g}–{z.hi:.6g}",
                           lo=z.lo, hi=z.hi, strict=strict))
            break
    for z in st.fvgs:
        if z.contains(price, atr_v * 0.1) and "0%" not in z.note:
            d = 1 if "bull" in z.note else -1
            out.append(_ev("fvg_price_inside", "SMC", d, 0.55, z.strength,
                           f"price is trading {'in' if z.contains(price) else 'back at'} a {z.note} "
                           f"{z.lo:.6g}–{z.hi:.6g}", lo=z.lo, hi=z.hi))
            break
    if st.ote and st.ote.contains(price, atr_v * 0.2):
        d = 1 if st.trend >= 0 else -1
        out.append(_ev("ote", "SMC", d, 0.65, 0.7,
                       f"price sits in the optimal trade entry {st.ote.lo:.6g}–{st.ote.hi:.6g} "
                       "of the last impulse", lo=st.ote.lo, hi=st.ote.hi))
    if st.premium_discount < 0.30:
        out.append(_ev("discount", "SMC", 1, 0.45, clamp(1.0 - st.premium_discount * 2),
                       f"price in the lower {st.premium_discount:.0%} of the range — discount, buys have room"))
    elif st.premium_discount > 0.70:
        out.append(_ev("premium", "SMC", -1, 0.45, clamp((st.premium_discount - 0.5) * 2),
                       f"price in the upper {st.premium_discount:.0%} of the range — premium, buys are late"))
    # draw on liquidity: the nearest unswept pool
    above = [z for z in st.pools if z.lo > price and ("BSL" in z.note or "highs" in z.note)]
    below = [z for z in st.pools if z.hi < price and ("SSL" in z.note or "lows" in z.note)]
    if above and (not below or (above[0].lo - price) < (price - below[0].hi)):
        z = min(above, key=lambda x: x.lo)
        out.append(_ev("draw_up", "SMC", 1, 0.4, clamp(z.strength),
                       f"nearest pool of buy-side liquidity sits at {z.mid:.6g} "
                       f"({(z.mid / price - 1) * 100:+.2f}%) — a natural draw", level=z.mid))
    elif below:
        z = max(below, key=lambda x: x.hi)
        out.append(_ev("draw_down", "SMC", -1, 0.4, clamp(z.strength),
                       f"nearest pool of sell-side liquidity sits at {z.mid:.6g} "
                       f"({(z.mid / price - 1) * 100:+.2f}%) — a natural draw", level=z.mid))
    for z in st.sr[:2]:
        d = 1 if z.mid < price else -1
        out.append(_ev("sr", "SMC", d, 0.35, z.strength,
                       f"{z.note} at {z.mid:.6g}", level=z.mid))
    tl = trendline(candles, zigzag(candles, 2), price, atr_v)
    for key, val in tl.items():
        if val["broken"]:
            out.append(_ev("trendline_break", "SMC", 1 if key == "resistance" else -1,
                           0.5, clamp(0.4 + val["touches"] * 0.1),
                           f"{key} trendline ({val['direction']} slope, {val['touches']} touches) broken at {val['value']:.6g}",
                           level=val["value"]))
    return out


def indicator_evidence(candles: Sequence[Candle], atr_v: float, regime: Regime) -> list[dict]:
    out: list[dict] = []
    closes = [c.c for c in candles]
    price = closes[-1]
    rsi_s = rsi(closes, 14)
    r = last(rsi_s)
    if r is not None:
        if r < 30:
            out.append(_ev("rsi_oversold", "IND", 1, 0.4, clamp((30 - r) / 20 + 0.3),
                           f"RSI {r:.1f} — oversold, bounce risk is elevated"))
        elif r > 70:
            out.append(_ev("rsi_overbought", "IND", -1, 0.4, clamp((r - 70) / 20 + 0.3),
                           f"RSI {r:.1f} — overbought, late longs pay for it"))
        else:
            out.append(_ev("rsi_mid", "IND", 0, 0.15, 0.5, f"RSI {r:.1f} — neutral"))
        div = divergence(closes[-80:], rsi_s[-80:], lookback=70)
        if div["kind"] == "bull":
            out.append(_ev("rsi_div_bull", "IND", 1, 0.7, div["strength"],
                           "bullish RSI divergence: lower low in price, higher low in RSI"))
        elif div["kind"] == "bear":
            out.append(_ev("rsi_div_bear", "IND", -1, 0.7, div["strength"],
                           "bearish RSI divergence: higher high in price, lower high in RSI"))
    line, sig, hist = macd(closes)
    h, hp = value_at(hist, -1), value_at(hist, -2)
    if h is not None and hp is not None:
        if h > 0 >= hp:
            out.append(_ev("macd_cross_up", "IND", 1, 0.5, 0.6, "MACD histogram just crossed above zero"))
        elif h < 0 <= hp:
            out.append(_ev("macd_cross_dn", "IND", -1, 0.5, 0.6, "MACD histogram just crossed below zero"))
        elif h > 0 and h > hp:
            out.append(_ev("macd_up", "IND", 1, 0.3, 0.45, f"MACD histogram positive and rising ({h:+.5g})"))
        elif h < 0 and h < hp:
            out.append(_ev("macd_dn", "IND", -1, 0.3, 0.45, f"MACD histogram negative and falling ({h:+.5g})"))
    e9, e21, e50, e200 = ema(closes, 9), ema(closes, 21), ema(closes, 50), ema(closes, 200)
    a, b, c50 = last(e9), last(e21), last(e50)
    if a and b and c50:
        if a > b > c50 and price > a:
            out.append(_ev("ema_ribbon_up", "IND", 1, 0.55, 0.7,
                           f"EMA ribbon stacked bullish (9 {a:.6g} > 21 {b:.6g} > 50 {c50:.6g}) with price above it"))
        elif a < b < c50 and price < a:
            out.append(_ev("ema_ribbon_dn", "IND", -1, 0.55, 0.7,
                           f"EMA ribbon stacked bearish (9 {a:.6g} < 21 {b:.6g} < 50 {c50:.6g}) with price below it"))
    e200v = last(e200)
    if e200v:
        out.append(_ev("ema200", "IND", 1 if price > e200v else -1, 0.35, 0.55,
                       f"price {'above' if price > e200v else 'below'} the 200 EMA ({e200v:.6g})"))
    _, up, lo, width = bollinger(closes, 20, 2.0)
    u, l = last(up), last(lo)
    if u and l:
        if price > u:
            out.append(_ev("bb_upper", "IND", -1, 0.35, 0.55, f"close above the upper Bollinger band ({u:.6g}) — stretched"))
        elif price < l:
            out.append(_ev("bb_lower", "IND", 1, 0.35, 0.55, f"close below the lower Bollinger band ({l:.6g}) — stretched"))
        bw_pct = regime.bb_width_pct
        if bw_pct < 0.2:
            out.append(_ev("bb_squeeze", "IND", 0, 0.3, 0.6, f"band width at the {bw_pct:.0%} percentile — squeeze, breakout pending"))
    k, d = stoch(candles)
    kv, dv = last(k), last(d)
    if kv is not None and dv is not None:
        if kv < 20 and kv > dv:
            out.append(_ev("stoch_up", "IND", 1, 0.3, 0.5, f"stochastic {kv:.0f}/{dv:.0f} turning up from oversold"))
        elif kv > 80 and kv < dv:
            out.append(_ev("stoch_dn", "IND", -1, 0.3, 0.5, f"stochastic {kv:.0f}/{dv:.0f} turning down from overbought"))
    ich = ichimoku(candles)
    ct, cb = last(ich["cloud_top"]), last(ich["cloud_bottom"])
    tk, kj = last(ich["tenkan"]), last(ich["kijun"])
    if ct and cb and tk and kj:
        if price > ct and tk > kj:
            out.append(_ev("ichi_up", "IND", 1, 0.45, 0.6, f"price above the cloud ({cb:.6g}–{ct:.6g}) with tenkan over kijun"))
        elif price < cb and tk < kj:
            out.append(_ev("ichi_dn", "IND", -1, 0.45, 0.6, f"price below the cloud ({cb:.6g}–{ct:.6g}) with tenkan under kijun"))
        else:
            out.append(_ev("ichi_flat", "IND", 0, 0.2, 0.5, "price inside the ichimoku cloud — no directional edge"))
    vw = vwap(candles[-120:])
    v = vw[-1]
    if v:
        out.append(_ev("vwap", "IND", 1 if price > v else -1, 0.4,
                       clamp(abs(price - v) / max(atr_v, 1e-9) / 2 + 0.3),
                       f"price {'above' if price > v else 'below'} session VWAP ({v:.6g})"))
    adx_s, pdi_s, mdi_s = adx(candles, 14)
    adx_v, pdi, mdi = last(adx_s) or 0.0, last(pdi_s) or 0.0, last(mdi_s) or 0.0
    if adx_v > 22:
        out.append(_ev("di", "IND", 1 if pdi > mdi else -1, 0.4, clamp(adx_v / 60),
                       f"ADX {adx_v:.1f} with DI {'+' if pdi > mdi else '−'} leading ({pdi:.1f}/{mdi:.1f}) — directional tape"))
    vol_z = zscore([c.v for c in candles[-30:-1]], candles[-1].v)
    if vol_z > 1.2 and candles[-1].body > atr_v * 0.5:
        out.append(_ev("volume_bar", "IND", 1 if candles[-1].bull else -1,
                       clamp(0.3 + vol_z / 8), clamp(vol_z / 4),
                       f"last bar traded {vol_z:+.1f}σ volume with a {candles[-1].body / atr_v:.1f} ATR body"))
    return out


def vp_evidence(candles: Sequence[Candle], price: float) -> list[dict]:
    vp = volume_profile(candles, 24)
    if not vp["poc"]:
        return []
    out: list[dict] = []
    if price > vp["vah"]:
        out.append(_ev("vp_above", "VP", 1, 0.5, 0.6,
                       f"price accepted above the value area (VAH {vp['vah']:.6g}) — buyers in control"))
    elif price < vp["val"]:
        out.append(_ev("vp_below", "VP", -1, 0.5, 0.6,
                       f"price below the value area (VAL {vp['val']:.6g}) — sellers in control"))
    else:
        out.append(_ev("vp_inside", "VP", 0, 0.25, 0.5,
                       f"price inside the value area ({vp['val']:.6g}–{vp['vah']:.6g}); POC {vp['poc']:.6g} is the magnet"))
    return out


def mtf_evidence(reads: dict[str, int], base_tf: str) -> list[dict]:
    out: list[dict] = []
    for tf, d in reads.items():
        out.append(_ev(f"mtf_{tf}", "MTF", d, 0.5, 0.55 if d else 0.3,
                       f"{tf} structure reads {'bullish' if d > 0 else 'bearish' if d < 0 else 'flat'}"))
    return out


def pattern_evidence(candles: Sequence[Candle], atr_v: float, zz) -> list[dict]:
    out: list[dict] = []
    for p in candle_patterns(candles, atr_v):
        out.append(_ev(p["code"], "PATTERN", p["direction"], 0.5, p["strength"], p["note"]))
    for p in harmonic_patterns(zz, atr_v):
        out.append(_ev(p["code"], "PATTERN", p["direction"], 0.65, p["strength"], p["note"]))
    for p in vsa_read(candles, atr_v):
        out.append(_ev(p["code"], "VSA", p["direction"], 0.7, p["strength"], p["note"]))
    for p in chart_patterns(candles, atr_v, zz):
        out.append(_ev(p["code"], "PATTERN", p["direction"], 0.6, p["strength"], p["note"]))
    return out


def sentiment_evidence(sent, macro, symbol: str) -> list[dict]:
    out: list[dict] = []
    out += macro_risk(macro, symbol)
    fg = sent.fear_greed
    if fg <= 20:
        out.append(_ev("fear_greed", "SENTIMENT", 1, 0.45, clamp((25 - fg) / 30),
                       f"fear & greed {fg} ({sent.fear_greed_label}) — capitulation readings are contrarian fuel"))
    elif fg >= 80:
        out.append(_ev("fear_greed", "SENTIMENT", -1, 0.45, clamp((fg - 75) / 30),
                       f"fear & greed {fg} ({sent.fear_greed_label}) — everyone is in, the exit is crowded"))
    else:
        out.append(_ev("fear_greed", "SENTIMENT", 0, 0.15, 0.5,
                       f"fear & greed {fg} ({sent.fear_greed_label}) — no extremes"))
    if abs(sent.news_score) > 0.15:
        out.append(_ev("news", "SENTIMENT", 1 if sent.news_score > 0 else -1, 0.4,
                       clamp(abs(sent.news_score)),
                       f"news tone {sent.news_score:+.2f} across {len(sent.headlines)} headlines — "
                       f"{'FOMO bid' if sent.news_score > 0 else 'FUD pressure'}"))
    ev = sent.next_event
    if ev is not None and 0 <= ev.minutes_away <= 180:
        out.append(_ev("macro_event", "SENTIMENT", 0, 0.2, 0.6,
                       f"{ev.name} in {ev.minutes_away} min — scheduled volatility, size accordingly"))
    return out


def vision_evidence(chart: ChartReading, price: float, atr_v: float) -> list[dict]:
    if not chart.available:
        return []
    out: list[dict] = []
    if chart.trend:
        out.append(_ev("vision_trend", "VISION", chart.trend, 0.8, chart.confidence,
                       f"chart screenshot reads {chart.trend_label} via {chart.method}"))
    for pat in chart.patterns[:3]:
        out.append(_ev("vision_pattern", "VISION", 0, 0.4, chart.confidence,
                       f"screenshot shows: {pat}"))
    for s in chart.support[:2]:
        if abs(s - price) < atr_v * 1.5:
            out.append(_ev("vision_support", "VISION", 1, 0.45, chart.confidence * 0.9,
                           f"screenshot support at {s:.6g} is {abs(s - price) / atr_v:.1f} ATR away", level=s))
    for r in chart.resistance[:2]:
        if abs(r - price) < atr_v * 1.5:
            out.append(_ev("vision_resistance", "VISION", -1, 0.45, chart.confidence * 0.9,
                           f"screenshot resistance at {r:.6g} is {abs(r - price) / atr_v:.1f} ATR away", level=r))
    if chart.range_position < 0.25:
        out.append(_ev("vision_discount", "VISION", 1, 0.35, chart.confidence * 0.7,
                       f"screenshot price sits in the bottom {chart.range_position:.0%} of its range"))
    elif chart.range_position > 0.75:
        out.append(_ev("vision_premium", "VISION", -1, 0.35, chart.confidence * 0.7,
                       f"screenshot price sits in the top {chart.range_position:.0%} of its range"))
    return out


def load_calibration(path: str | None = None) -> dict:
    path = path or os.path.join(os.path.dirname(__file__), "..", "config", "calibration.json")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


# --------------------------------------------------------------------------
# engine
# --------------------------------------------------------------------------

class SignalEngine:
    def __init__(self, *, equity: float = config.DEFAULT_EQUITY,
                 risk_pct: float = config.DEFAULT_RISK_PCT,
                 calibration: Calibration | None = None) -> None:
        self.equity = equity
        self.risk_pct = risk_pct
        self.calibration = calibration if calibration is not None else load_calibration()

    # -- public -----------------------------------------------------------
    def analyse(self, snap: Snapshot, chart: ChartReading | None = None) -> SignalCard:
        tf = snap.tf
        candles = snap.series(tf)
        chart = chart or ChartReading()
        price = candles[-1].c if candles else 0.0
        as_of = candles[-1].ts if candles else snap.as_of
        session, sess_q = session_of(as_of)

        if len(candles) < 80:
            regime = Regime("ILLIQUID", 0.2, config.REGIME_PLAYBOOK["ILLIQUID"],
                            notes=["not enough candles for a read"])
            st = Structure()
            card = SignalCard(symbol=snap.symbol, tf=tf, action="WAIT", order_type="no order",
                              plan=TradePlan(action="WAIT", order_type="no order"),
                              probability=0.5, conviction=0.0, edge=0.0, bull_score=0.0,
                              bear_score=0.0, conflict=1.0, regime=regime, session=session,
                              session_quality=sess_q, structure=st, evidence=[],
                              wait_reasons=["تاریخچه کندل کافی برای تحلیل وجود ندارد."],
                              warnings=["not enough candles"], snapshot=snap, chart=chart)
            return card

        atr_s = atr(candles, 14)
        atr_v = last(atr_s) or price * 0.004
        k = 2 if config.TF_MINUTES[tf] <= 5 else 3
        st = analyse_structure(candles, atr_v, k=k)
        htf = snap.series("1h") or snap.series("15m") or candles
        regime = classify(candles, htf)
        mtf, reads = mtf_agreement(snap.candles, tf)
        tac = tactics(regime.name)

        # ---- evidence -----------------------------------------------------
        raw: list[dict] = []
        raw += smc_evidence(candles, st, atr_v, price)
        raw += indicator_evidence(candles, atr_v, regime)
        raw += vp_evidence(candles, price)
        raw += mtf_evidence(reads, tf)
        raw += pattern_evidence(candles, atr_v, zigzag(candles, k))
        deriv_ev, liq_up, liq_dn = derivatives_evidence(snap.derivatives, candles, price, atr_v)
        raw += deriv_ev
        raw += sentiment_evidence(snap.sentiment, snap.macro, snap.symbol)
        raw += vision_evidence(chart, price, atr_v)
        raw.append(_ev("session", "SESSION", 0, 0.2, sess_q,
                       f"{session} session (quality {sess_q:.0%})"))

        evidence = [Evidence(**d) for d in raw]
        verdict = aggregate(evidence, regime.name, self.calibration)
        event = snap.sentiment.next_event
        verdict = decide(verdict, mtf=mtf, event_minutes=event.minutes_away if event else None,
                         spread_bps=snap.derivatives.orderbook.spread_bps,
                         regime=regime.name, funding=snap.derivatives.funding)

        action = verdict.action
        plan = TradePlan(action="WAIT", order_type="no order")
        if action != "WAIT":
            plan = build_plan(action, price, candles, st, atr_v, regime, tf,
                              equity=self.equity, risk_pct=self.risk_pct,
                              size_mult=tac["size_multiplier"],
                              extra_up=liq_up, extra_dn=liq_dn,
                              ttl_bars=tac["ttl_bars"], min_rr=tac["min_rr"])

        card = SignalCard(
            symbol=snap.symbol, tf=tf, action=action, order_type=plan.order_type,
            plan=plan, probability=verdict.probability, conviction=verdict.conviction,
            edge=verdict.edge, bull_score=verdict.bull, bear_score=verdict.bear,
            conflict=verdict.conflict, regime=regime, session=session,
            session_quality=sess_q, structure=st, evidence=evidence,
            wait_reasons=verdict.reasons, wait_reasons_en=verdict.reasons_en,
            snapshot=snap, chart=chart,
            calibration=self.calibration,
        )
        self._explain(card, reads, mtf, price, atr_v, liq_up, liq_dn)
        self._warn(card, snap, atr_v)
        return card

    # -- prose ------------------------------------------------------------
    def _explain(self, card: SignalCard, reads: dict[str, int], mtf: float, price: float,
                 atr_v: float, liq_up: Sequence[float], liq_dn: Sequence[float]) -> None:
        snap = card.snapshot
        st, d = card.structure, snap.derivatives
        fams = sorted({e.family for e in card.top(10)}, key=lambda f: -abs(sum(
            e.signed for e in card.evidence if e.family == f)))

        labels = {
            "SMC": "ساختار بازار / SMC-ICT", "MTF": "هم‌راستایی مولتی‌تایم‌فریم",
            "DERIV": "دیتای مشتقات و اوردرفلو", "VSA": "حجم و وایکوف",
            "IND": "اندیکاتورها و واگرایی", "VP": "پروفایل حجم",
            "PATTERN": "الگوهای قیمتی و کندلی", "MACRO": "همبستگی کلان",
            "SENTIMENT": "سنتیمنت و اخبار", "VISION": "تحلیل تصویر چارت",
            "SESSION": "سشن معاملاتی",
        }
        card.why_strategies = [labels.get(f, f) for f in fams[:5]]
        card.strategy_families = fams[:5]

        # --- technical ----------------------------------------------------
        tech: list[str] = []
        if st.events:
            ev = st.events[-1]
            age = len(card.snapshot.series()) - 1 - ev["i"]
            tech.append(f"ساختار: {ev['kind']} {'صعودی' if ev['direction'] > 0 else 'نزولی'} با کلوز "
                        f"{fmt_price(ev['close'])} روی سطح {fmt_price(ev['price'])} "
                        f"({age} کندل قبل) — روند {STRUCTURE_FA.get(st.label, st.label)}.")
        else:
            tech.append(f"ساختار: بدون شکست معتبر اخیر؛ وضعیت "
                        f"{STRUCTURE_FA.get(st.label, st.label)} تا زمانی که یک سقف/کف سوئینگ بشکند.")
        if st.sweep:
            sw = st.sweep
            tech.append(f"نقدینگی: سوییپ {sw['side']} روی {fmt_price(sw['level'])} با سایه "
                        f"{sw['wick_atr']:.1f}×ATR و بازگشت به داخل رنج ({sw['bars_ago']} کندل قبل) — "
                        f"{'شکار استاپ فروشندگان' if sw['direction'] > 0 else 'شکار استاپ خریداران'}.")
        inside = [z for z in st.order_blocks if z.contains(price, atr_v * 0.15)]
        if inside:
            z = inside[0]
            where = "داخل" if z.contains(price) else "روی لبه"
            from .risk import zone_note_fa
            tech.append(f"ناحیه: قیمت {where} {zone_note_fa(z.note)} در بازه {fmt_price(z.lo)} تا "
                        f"{fmt_price(z.hi)} است؛ این ناحیه مبنای ورود و ابطال است.")
        elif st.order_blocks:
            z = min(st.order_blocks, key=lambda x: abs(x.mid - price))
            tech.append(f"نزدیک‌ترین اردربلاک در {fmt_price(z.lo)}–{fmt_price(z.hi)} "
                        f"({abs(z.mid - price) / atr_v:.1f}×ATR فاصله) — ورود بهتر است روی ریتست همین ناحیه باشد.")
        if st.ote:
            tech.append(f"OTE: بازه {fmt_price(st.ote.lo)} تا {fmt_price(st.ote.hi)} "
                        f"(فیبو ۶۱.۸٪ تا ۷۹٪ آخرین موج) — {'قیمت داخل آن است' if st.ote.contains(price, atr_v * 0.2) else 'هنوز پر نشده'}.")
        tech.append(f"رنج ۶۰ کندلی: {fmt_price(st.range_low)} تا {fmt_price(st.range_high)}؛ قیمت در "
                    f"{st.premium_discount:.0%} رنج ({'پریمیوم' if st.premium_discount > 0.5 else 'دیسکانت'}).")
        if reads:
            tech.append("مولتی‌تایم‌فریم: " + "، ".join(
                f"{tf} {'صعودی' if v > 0 else 'نزولی' if v < 0 else 'خنثی'}" for tf, v in reads.items()) +
                f" (امتیاز تجمعی {mtf:+.2f}).")
        for e in [e for e in card.evidence if e.family in ("PATTERN", "VSA")][:2]:
            name = PATTERN_FA.get(e.code, e.code)
            tech.append(f"الگو: {name} — قدرت {e.strength:.0%} "
                        f"({'تأیید صعودی' if e.direction > 0 else 'تأیید نزولی' if e.direction < 0 else 'بی‌طرف'}).")
        card.why_technical = tech

        # --- data ---------------------------------------------------------
        data: list[str] = []
        dp = price_change_pct(card.snapshot.series(), 12)
        doi = d.oi_trend_pct
        data.append(f"فاندینگ: {d.funding * 100:+.4f}٪ هر ۸ ساعت (سالانه {d.funding * 3 * 365 * 100:+.0f}٪) — "
                    f"{funding_bias(d)}.")
        data.append(f"OI: {d.oi:,.0f} واحد، تغییر {doi:+.2f}٪ همراه با قیمت {dp:+.2f}٪ — "
                    + ("ورود پول تازه به سمت لانگ." if dp > 0 and doi > 0.2 else
                       "بستن شورت‌ها، رالی بدون پول تازه." if dp > 0 and doi < -0.2 else
                       "شورت‌های تازه در حال فشار." if dp < 0 and doi > 0.2 else
                       "لیکویید شدن لانگ‌ها." if dp < 0 and doi < -0.2 else
                       "پوزیشن‌ها بدون تغییر محسوس."))
        cvd_last = d.cvd[-1] if d.cvd else 0.0
        data.append(f"CVD: {cvd_last:+,.0f} واحد تجمعی؛ دلتای ۲۰ کندل اخیر "
                    f"{sum(c.delta for c in card.snapshot.series()[-20:]):+,.0f} — "
                    f"{'خریدار تهاجمی غالب' if sum(c.delta for c in card.snapshot.series()[-20:]) > 0 else 'فروشنده تهاجمی غالب'}.")
        data.append(f"اردربوک: عدم‌تعادل {d.obi:+.2f}، اسپرد {d.orderbook.spread_bps:.1f} bps؛ "
                    f"جریان نهنگ‌ها {d.whale_net:+,.0f} دلار.")
        if liq_up or liq_dn:
            near = min(([("بالا", x) for x in liq_up] + [("پایین", x) for x in liq_dn]),
                       key=lambda t: abs(t[1] - price), default=None)
            if near:
                data.append(f"لیکوییدیشن: نزدیک‌ترین خوشه در سمت {near[0]} روی {fmt_price(near[1])} "
                            f"({(near[1] / price - 1) * 100:+.2f}٪) — مغناطیس قیمت.")
        sent = snap.sentiment
        data.append(f"ترس و طمع: {sent.fear_greed} ({sent.fear_greed_label})؛ تن اخبار {sent.news_score:+.2f}.")
        if sent.headlines:
            data.append("تیترها: " + " | ".join(h.title for h in sent.headlines[:2]))
        card.why_data = data

        # --- context ------------------------------------------------------
        macro = snap.macro
        ctx = [f"سشن: {SESSION_FA_SHORT.get(card.session, card.session)} "
               f"(کیفیت {card.session_quality:.0%}) — "
               f"{'بهترین نقدینگی روز' if card.session_quality >= 0.95 else 'نقدینگی متوسط' if card.session_quality >= 0.7 else 'نقدینگی کم، ریسک ویک بالاست'}."]
        if not snap.symbol.upper().startswith("BTC"):
            ctx.append(f"بیت‌کوین: {macro.btc_change_24h:+.2f}٪ در ۲۴ ساعت (امتیاز روند {macro.btc_trend:+.2f}) — "
                       + ("اجازه حرکت به آلت‌کوین می‌دهد." if macro.btc_trend > 0.15 else
                          "فشار فروش روی کل بازار؛ لانگ آلت پرریسک است." if macro.btc_trend < -0.15 else
                          "خنثی است؛ تصمیم را به ساختار خود ارز بسپارید."))
        ctx.append(f"USDT.D: {macro.usdt_dominance:.2f}٪ ({macro.usdt_dom_change:+.2f}pp)"
                   + (f" | DXY: {macro.dxy:.2f} ({macro.dxy_change:+.2f}٪)" if macro.dxy is not None else "")
                   + ".")
        ev = sent.next_event
        if ev:
            ctx.append(f"رویداد اقتصادی: {ev.name} تا {ev.minutes_away} دقیقه دیگر (اثر {ev.impact}).")
        ctx.append(f"رژیم بازار: {card.regime.name} — {PLAYBOOK_FA.get(card.regime.name, card.regime.playbook)}. "
                   f"ADX {card.regime.adx:.1f}، ATR {card.regime.atr_pct:.2f}٪ قیمت، حجم {card.regime.volume_z:+.1f}σ.")
        card.context = ctx

        if card.action == "WAIT":
            card.order_type = "no order"
            card.plan.action = "WAIT"
            card.plan.order_type = "no order"

    def _warn(self, card: SignalCard, snap: Snapshot, atr_v: float) -> None:
        w, we = card.warnings, card.warnings_en

        def add(fa: str, en: str) -> None:
            w.append(fa)
            we.append(en)

        if snap.source.startswith("synthetic"):
            add("داده‌ها شبیه‌سازی‌شده‌اند (paper): موتور و منطق را اعتبارسنجی می‌کند، نه فرصت واقعی را.",
                "synthetic (paper) data: validates the engine and the reasoning, not a live opportunity.")
        if not card.chart.available:
            add("تصویر چارت ارائه نشده یا خوانده نشده؛ بخش Vision غیرفعال است.",
                "no chart screenshot supplied or readable; the vision family is off.")
        elif card.chart.method == "vision-lite":
            add("چارت با خواننده آفلاین (vision-lite) تحلیل شد؛ برای دقت بیشتر تصویر را با کلید API بفرستید.",
                "screenshot read with the offline vision-lite reader; set a vision API key for full reads.")
        if abs(snap.derivatives.funding) >= config.FUNDING_EXTREME:
            add("فاندینگ در محدوده اشباع است؛ ریسک لیکوییدیشن زنجیره‌ای بالاست.",
                "funding is extreme; cascade-liquidation risk is elevated.")
        ev = snap.sentiment.next_event
        if ev and ev.minutes_away <= 60:
            add(f"رویداد {ev.name} نزدیک است؛ نوسان برنامه‌ریزی‌شده.",
                f"{ev.name} is close; expect scheduled volatility.")
        if card.regime.name == "HIGH_VOL":
            add("نوسان بالاست؛ حجم پوزیشن را کم و استاپ را واقعی‌تر بگذارید.",
                "volatility is high; size down and place the stop where it belongs.")
        gap = min((abs(z.mid - snap.price) for z in card.structure.order_blocks + card.structure.fvgs),
                  default=999 * atr_v)
        if card.action == "LONG" and card.structure.premium_discount > 0.82:
            add("ورود در پریمیوم رنج است؛ این نقطه ورود دارد به تعقیب قیمت نزدیک می‌شود.",
                "the long entry sits in the top of the range — this is closer to chasing than to value.")
        if card.action == "SHORT" and card.structure.premium_discount < 0.18:
            add("شورت در کف رنج است؛ ریسک بازگشت سریع از ناحیه تقاضا بالاست.",
                "the short entry sits at the bottom of the range — demand can snap back fast.")
        if card.action != "WAIT" and gap > atr_v * 2.5:
            add("قیمت از نزدیک‌ترین ناحیه ساختاری دور است؛ ورود مارکت در این نقطه ریسک تعقیب دارد.",
                "price is far from the nearest structural zone; a market entry here is chase risk.")


def analyse(snap: Snapshot, chart: ChartReading | None = None, **kw) -> SignalCard:
    return SignalEngine(**kw).analyse(snap, chart)
