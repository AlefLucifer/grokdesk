"""Signal card rendering — the exact output format, in Persian or English."""

from __future__ import annotations

from .. import config
from ..risk import fmt_price
from ..types import SignalCard

ICON_FA = {"LONG": "🟢 LONG (خرید)", "SHORT": "🔴 SHORT (فروش)",
           "WAIT": "⚪ WAIT (عدم ورود — بازار نامناسب)"}
ICON_EN = {"LONG": "🟢 LONG", "SHORT": "🔴 SHORT", "WAIT": "⚪ WAIT (no trade)"}

REGIME_FA = {"TREND_UP": "روند صعودی", "TREND_DOWN": "روند نزولی", "RANGE": "رنج / بدون روند",
             "HIGH_VOL": "نوسان بالا", "SQUEEZE": "فشردگی (اسکوییز)", "ILLIQUID": "کم‌عمق"}
SESSION_FA = {"ASIA": "آسیا", "LONDON": "لندن", "NY_AM": "نیویورک (صبح)",
              "NY_PM": "نیویورک (بعدازظهر)", "OFF_SESSION": "خارج از سشن اصلی"}
SESSION_EN = {"ASIA": "Asia", "LONDON": "London", "NY_AM": "New York AM",
              "NY_PM": "New York PM", "OFF_SESSION": "off-session"}
FAMILY_EN = {"SMC": "SMC / ICT structure", "MTF": "multi-timeframe alignment",
             "DERIV": "derivatives & order flow", "VSA": "VSA / Wyckoff",
             "IND": "indicators & divergence", "VP": "volume profile",
             "PATTERN": "price & candle patterns", "MACRO": "macro correlation",
             "SENTIMENT": "sentiment & news", "VISION": "chart vision",
             "SESSION": "session timing"}


def _pct(x: float, fa: bool, digits: int = 0) -> str:
    return f"{x * 100:.{digits}f}{'٪' if fa else '%'}"


def _zone(card: SignalCard, fa: bool) -> str:
    p = card.plan
    price = card.snapshot.price if card.snapshot else 0.0
    if card.action == "WAIT":
        return f"— ({'قیمت فعلی' if fa else 'last price'}: {fmt_price(price)})"
    if abs(p.entry_hi - p.entry_lo) < max(p.entry * 0.0002, 1e-12):
        return fmt_price(p.entry)
    mid = f"{'میانه' if fa else 'mid'}: {fmt_price(p.entry)}"
    return f"{fmt_price(p.entry_lo)} — {fmt_price(p.entry_hi)}  ({mid})"


def _wake(card: SignalCard, fa: bool) -> list[str]:
    st = card.structure
    out: list[str] = []
    if st.range_high and st.range_low:
        if fa:
            out.append(f"LONG فقط با کلوز کندل بالای {fmt_price(st.range_high)} و ریتست آن؛ "
                       f"SHORT فقط با کلوز زیر {fmt_price(st.range_low)} و ریتست آن.")
        else:
            out.append(f"LONG only on a candle close above {fmt_price(st.range_high)} plus a retest; "
                       f"SHORT only on a close below {fmt_price(st.range_low)} plus a retest.")
    if st.sweep:
        if fa:
            out.append(f"اگر نقدینگی روی {fmt_price(st.sweep['level'])} دوباره شکار شد و کندل داخل رنج بسته شد، "
                       f"همان سوییپ باید با CHoCH روی تایم‌فریم {card.tf} تأیید شود.")
        else:
            out.append(f"a fresh sweep of {fmt_price(st.sweep['level'])} that closes back inside, "
                       f"confirmed by a CHoCH on the {card.tf}.")
    if fa:
        out.append("تا زمانی که دلایل WAIT در همین بخش برطرف نشود، هیچ سفارشی ثبت نکنید.")
    else:
        out.append("no order until the WAIT reasons above are cleared.")
    return out


def _why(card: SignalCard, fa: bool) -> tuple[str, list[str], list[str], list[str]]:
    if fa:
        return ("، ".join(card.why_strategies), card.why_technical, card.why_data, card.context)

    strategies = ", ".join(FAMILY_EN.get(f, f) for f in (card.strategy_families or []))
    tech = [e.note for e in sorted(card.evidence, key=lambda e: -abs(e.signed))
            if e.family in ("SMC", "IND", "PATTERN", "VSA", "MTF", "VP")][:6]
    flow = [e.note for e in sorted(card.evidence, key=lambda e: -abs(e.signed))
            if e.family in ("DERIV", "MACRO", "SENTIMENT", "VISION")][:6]
    snap = card.snapshot
    ctx: list[str] = []
    if snap:
        ctx.append(f"session: {SESSION_EN.get(card.session, card.session)} (quality {card.session_quality:.0%})")
        r = card.regime
        ctx.append(f"regime: {r.name} — {r.playbook}. ADX {r.adx:.1f}, ATR {r.atr_pct:.2f}% of price, "
                   f"volume {r.volume_z:+.1f}σ, band width at the {r.bb_width_pct:.0%} percentile")
        if not snap.symbol.startswith("BTC"):
            ctx.append(f"BTC: {snap.macro.btc_change_24h:+.2f}% in 24h, trend score {snap.macro.btc_trend:+.2f}")
        dxy = f", DXY {snap.macro.dxy:.2f} ({snap.macro.dxy_change:+.2f}%)" if snap.macro.dxy else ""
        ctx.append(f"USDT dominance {snap.macro.usdt_dominance:.2f}% "
                   f"({snap.macro.usdt_dom_change:+.2f} pp){dxy}")
        ctx.append(f"fear & greed {snap.sentiment.fear_greed} ({snap.sentiment.fear_greed_label}), "
                   f"funding {snap.derivatives.funding * 100:+.4f}%/8h")
        ev = snap.sentiment.next_event
        if ev:
            ctx.append(f"next event: {ev.name} in {ev.minutes_away} min")
    return strategies, tech, flow, ctx


def render_card(card: SignalCard, lang: str = "fa") -> str:
    fa = lang != "en"
    p = card.plan
    snap = card.snapshot
    price = snap.price if snap else 0.0
    no_trade = card.action == "WAIT"

    def lv(x: float | None) -> str:
        return "—" if no_trade or not x else fmt_price(x)

    regime = REGIME_FA.get(card.regime.name, card.regime.name) if fa else card.regime.name
    session = (SESSION_FA if fa else SESSION_EN).get(card.session, card.session)
    strategies, tech, flow, ctx = _why(card, fa)

    out: list[str] = []
    out.append(f"### 🎯 {'کارت سیگنال هوشمند' if fa else 'Signal Card'}: {card.symbol} | "
               f"{'تایم‌فریم' if fa else 'timeframe'}: {card.tf}")
    out.append("")
    out.append(f"- **{'نوع پوزیشن' if fa else 'Action'} (Action):** {(ICON_FA if fa else ICON_EN)[card.action]}")
    order_txt = ("ثبت نشود" if fa else "no order") if no_trade else p.order_type
    out.append(f"- **{'نوع سفارش' if fa else 'Order type'}:** {order_txt}")
    out.append(f"- **{'قیمت لحظه‌ای' if fa else 'Last price'}:** {fmt_price(price)}   |   "
               f"**{'رژیم بازار' if fa else 'Regime'}:** {regime} ({card.regime.confidence:.0%})   |   "
               f"**{'سشن' if fa else 'Session'}:** {session}")
    out.append("")
    out.append(f"#### 📊 1. {'نقاط کلیدی معامله (Execution Levels)' if fa else 'Execution levels'}")
    out.append(f"- **{'نقطه ورود بهینه (Entry Zone)' if fa else 'Entry zone'}:** {_zone(card, fa)}")
    out.append(f"- **{'اهداف قیمتی' if fa else 'Take profits'}:**")
    tp_labels = [("سیو سود و ریسک‌فری", "de-risk"), ("هدف اصلی", "main target"),
                 ("تارگت پتانسیل بالا", "runner")]
    for i, (value, rr) in enumerate(((p.tp1, p.rr_tp1), (p.tp2, p.rr), (p.tp3, p.rr_tp3)), start=1):
        label = tp_labels[i - 1][0 if fa else 1]
        suffix = "" if no_trade else f"   — R:R 1:{rr:.1f}"
        out.append(f"  - 🎯 TP {i} ({label}): {lv(value)}{suffix}")
    sl_suffix = "" if no_trade else (f"   — {p.stop_pct * 100:.2f}٪ از قیمت ورود" if fa
                                     else f"   — {p.stop_pct * 100:.2f}% of entry")
    out.append(f"- **{'حد ضرر (Stop Loss)' if fa else 'Stop loss'}:** {lv(p.sl)}{sl_suffix}")
    out.append("")
    out.append(f"#### ⚖️ 2. {'مدیریت ریسک و احتمالات (Risk & Probability)' if fa else 'Risk & probability'}")
    prob_note = (f" {'(برای جهت متمایل؛ بدون معامله)' if fa else '(leaning side, no trade)'}" if no_trade else "")
    out.append(f"- **{'احتمال موفقیت (Win Rate Probability)' if fa else 'Win probability'}:** "
               f"{_pct(card.probability, fa)}{prob_note}")
    out.append(f"- **{'نسبت ریسک به ریوارد (R:R)' if fa else 'Risk / reward'}:** "
               f"{'—' if no_trade else f'1:{p.rr:.1f}'}")
    out.append(f"- **{'اهرم پیشنهادی' if fa else 'Leverage'}:** {'—' if no_trade else f'{p.leverage}x'}")
    if no_trade:
        capital = "—"
    elif fa:
        capital = (f"{p.risk_pct:.2f}٪ ریسک / {p.margin_pct:.0f}٪ مارجین "
                   f"(روی حساب {config.DEFAULT_EQUITY:,.0f} دلاری: ریسک {p.risk_amount:,.0f} دلار)")
    else:
        capital = (f"{p.risk_pct:.2f}% risk / {p.margin_pct:.0f}% margin "
                   f"(on a {config.DEFAULT_EQUITY:,.0f} USD account: {p.risk_amount:,.0f} USD at risk)")
    out.append(f"- **{'درصد درگیری سرمایه' if fa else 'Capital at risk'}:** {capital}")
    pct = "٪" if fa else "%"
    out.append(f"- **{'امتیاز اجماع' if fa else 'Confluence'}:** {card.conviction * 100:.0f}{pct} "
               f"{'لبه' if fa else 'edge'} · {'خریدار' if fa else 'bull'} {card.bull_score:.2f} / "
               f"{'فروشنده' if fa else 'bear'} {card.bear_score:.2f} · "
               f"{'تضاد' if fa else 'conflict'} {card.conflict * 100:.0f}{pct} · "
               f"{len(card.evidence)} {'شاهد' if fa else 'atoms'}")
    out.append("")
    why_title = 'استراتژی منتخب و چرایی سیگنال (The "WHY")' if fa else "The why"
    out.append(f"#### 🧠 3. {why_title}")
    out.append(f"- **{'استراتژی‌های به کار رفته' if fa else 'Strategies used'}:** {strategies or '—'}")
    out.append(f"- **{'دلایل تکنیکال (بر اساس چارت)' if fa else 'Technical reasons'}:**")
    for t in (tech or ["—"]):
        out.append(f"  - {t}")
    out.append(f"- **{'دلایل دیتامحور و سنتیمنت' if fa else 'Flow & sentiment'}:**")
    for t in (flow or ["—"]):
        out.append(f"  - {t}")
    out.append(f"- **{'وضعیت سشن و بیت‌کوین' if fa else 'Session & BTC'}:**")
    for t in (ctx or ["—"]):
        out.append(f"  - {t}")
    out.append("")
    out.append(f"#### ⚠️ 4. {'شرایط ابطال و مدیریت معامله (Trade Management)' if fa else 'Invalidation & management'}")
    if no_trade:
        out.append(f"- **{'دلایل عدم ورود' if fa else 'Why no trade'}:**")
        for r in (card.wait_reasons if fa else card.wait_reasons_en) or card.wait_reasons:
            out.append(f"  - {r}")
        out.append(f"- **{'شرط فعال شدن سیگنال' if fa else 'Re-arm conditions'}:**")
        for r in _wake(card, fa):
            out.append(f"  - {r}")
        out.append(f"- **{'مدیریت معامله' if fa else 'Management'}:** "
                   f"{'پوزیشنی باز نمی‌شود؛ فقط واچ‌لیست را به‌روز نگه دارید.' if fa else 'no position — keep it on the watchlist.'}")
    else:
        out.append(f"- **{'شرط ابطال قبل از ورود' if fa else 'Invalidation before entry'}:**")
        for r in (p.invalidation if fa else (p.invalidation_en or p.invalidation)):
            out.append(f"  - {r}")
        out.append(f"- **{'استراتژی Trailing Stop' if fa else 'Trailing plan'}:**")
        for r in (p.trailing if fa else (p.trailing_en or p.trailing)):
            out.append(f"  - {r}")
    out.append("")
    out.append(f"#### 🔍 {'شفافیت داده' if fa else 'Data transparency'}")
    fam = card_calibration(card)
    out.append(f"- {'وزن شواهد به تفکیک خانواده' if fa else 'Weighted evidence by family'}: "
               + " · ".join(f"{k} {v:.2f}" for k, v in sorted(fam.items(), key=lambda kv: -kv[1])))
    out.append(f"- {'منبع داده' if fa else 'Data source'}: {snap.source if snap else '—'}"
               f"   |   {'اعتبار کارت' if fa else 'card TTL'}: {p.ttl_bars} {'کندل' if fa else 'bars'}")
    cal = (card.calibration or {}).get("offset") or {}
    if cal:
        out.append(f"- {'کالیبراسیون' if fa else 'Calibration'}: "
                   + ", ".join(f"{k} {v:+.0%}" for k, v in cal.items())
                   + (" (از بکتست واک‌فوروارد)" if fa else " (from the walk-forward)"))
    else:
        out.append("- " + ("احتمال مدل‌محور است؛ برای کالیبراسیون، بک‌تست را روی داده واقعی اجرا کنید."
                           if fa else "probability is model-based; run the backtest on live data to calibrate it."))
    if card.chart.available:
        out.append(f"- {'تصویر چارت' if fa else 'Chart image'}: {card.chart.method} · "
                   f"{card.chart.trend_label} · {'اطمینان' if fa else 'confidence'} {card.chart.confidence:.0%}")
    for w in (card.warnings if fa else (card.warnings_en or card.warnings)):
        out.append(f"- ⚠️ {w}")
    out.append("")
    out.append("_این خروجی تحلیل الگوریتمی است، نه توصیه مالی. مدیریت ریسک و حجم پوزیشن با شماست._"
               if fa else
               "_Algorithmic analysis, not financial advice. Position sizing and risk are yours._")
    return "\n".join(out)


def card_calibration(card: SignalCard) -> dict:
    """Recompute the family totals actually used in the score (for the footer)."""
    from ..confluence import contribution
    totals: dict[str, float] = {}
    for e in card.evidence:
        totals[e.family] = totals.get(e.family, 0.0) + contribution(e, card.regime.name)
    return {k: round(v, 2) for k, v in totals.items()}


def render_short(card: SignalCard, lang: str = "fa") -> str:
    fa = lang != "en"
    price = card.snapshot.price if card.snapshot else 0.0
    if card.action == "WAIT":
        return (f"{card.symbol:<10} {card.tf:<4} ⚪ WAIT   "
                f"{(REGIME_FA.get(card.regime.name, card.regime.name) if fa else card.regime.name):<10} "
                f"{'لبه' if fa else 'edge'} {card.edge:+.2f}  "
                f"{'احتمال' if fa else 'p'} {card.probability:.0%}  "
                f"({len(card.wait_reasons)} {'مانع' if fa else 'blockers'})")
    arrow = "🟢" if card.action == "LONG" else "🔴"
    return (f"{card.symbol:<10} {card.tf:<4} {arrow} {card.action:<5} {card.regime.name:<9} "
            f"entry {fmt_price(card.plan.entry):>12}  sl {fmt_price(card.plan.sl):>12}  "
            f"tp2 {fmt_price(card.plan.tp2):>12}  rr 1:{card.plan.rr:.1f}  p {card.probability:.0%}  "
            f"lev {card.plan.leverage}x  (px {fmt_price(price)})")
