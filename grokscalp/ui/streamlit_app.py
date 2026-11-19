"""GROK SCALP — Streamlit desk.

Run it with:
    streamlit run grokscalp/ui/streamlit_app.py --server.address 0.0.0.0

Everything on screen comes from `SignalEngine.analyse`. The UI never computes
a level of its own, so what you see is exactly what the CLI prints.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import streamlit as st

from grokscalp import __version__, config
from grokscalp.backtest import calibrate, format_report, run as run_backtest
from grokscalp.data import available_symbols, load_snapshot
from grokscalp.engine import SignalEngine, load_calibration
from grokscalp.render.card import render_card
from grokscalp.render.charts import build_figure
from grokscalp.risk import fmt_price
from grokscalp.vision import ChartReader

st.set_page_config(page_title="GROK SCALP — موتور سیگنال", page_icon="🎯",
                   layout="wide", initial_sidebar_state="expanded")

CSS = """
<style>
  .stApp { background: radial-gradient(1200px 600px at 80% -10%, #10203a 0%, #070b12 55%); }
  .stMarkdown, .stText, .stCaption { direction: rtl; text-align: right; }
  .stMarkdown code, .stMarkdown pre, .stDataFrame { direction: ltr; text-align: left; }
  .hero { display:flex; gap:18px; align-items:baseline; flex-wrap:wrap;
          border-bottom:1px solid rgba(120,180,255,.18); padding-bottom:10px; margin-bottom:14px; }
  .hero h1 { font-size:26px; margin:0; letter-spacing:.5px; }
  .hero .sub { color:#8da2bd; font-size:13px; }
  .chip { display:inline-block; padding:2px 10px; border-radius:999px; font-size:12px;
          border:1px solid rgba(120,180,255,.3); margin-inline-start:6px; color:#cfe3ff; }
  .long { color:#26a69a; font-weight:700; }
  .short { color:#ef5350; font-weight:700; }
  .wait { color:#b0bec5; font-weight:700; }
  .kv { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:10px; }
  .kv > div { background:rgba(255,255,255,.03); border:1px solid rgba(120,180,255,.12);
              border-radius:10px; padding:10px 12px; direction:rtl; text-align:right; }
  .kv .label { color:#8da2bd; font-size:12px; }
  .kv .value { font-size:19px; font-weight:600; margin-top:2px; }
  .note { color:#8da2bd; font-size:12px; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# --------------------------------------------------------------------------
# cached data helpers
# --------------------------------------------------------------------------

@st.cache_data(ttl=45, show_spinner=False)
def _snapshot(symbol: str, tf: str, live: bool, bars: int, seed: int):
    return load_snapshot(symbol, tf, live=live, bars=bars, seed=seed)


@st.cache_data(ttl=45, show_spinner=False)
def _image_reading(data: bytes | None, symbol: str, tf: str):
    if not data:
        return None
    return ChartReader().read(data, symbol, tf)


@st.cache_data(ttl=45, show_spinner=False)
def _card(symbol: str, tf: str, live: bool, bars: int, seed: int, equity: float,
          risk: float, image: bytes | None, lang: str):
    snap = _snapshot(symbol, tf, live, bars, seed)
    chart = _image_reading(image, symbol, tf)
    engine = SignalEngine(equity=equity, risk_pct=risk, calibration=load_calibration())
    return engine.analyse(snap, chart)


@st.cache_data(ttl=120, show_spinner=False)
def _scan(symbols: tuple[str, ...], tf: str, live: bool, seed: int):
    engine = SignalEngine(calibration=load_calibration())
    rows = []
    for sym in symbols:
        try:
            snap = _snapshot(sym, tf, live, config.DEFAULT_BARS, seed)
            card = engine.analyse(snap)
            rows.append({
                "نماد": sym, "اقدام": card.action, "رژیم": card.regime.name,
                "قیمت": fmt_price(snap.price), "احتمال": f"{card.probability:.0%}",
                "لبه": f"{card.edge:+.2f}", "تضاد": f"{card.conflict:.0%}",
                "ورود": fmt_price(card.plan.entry) if card.action != "WAIT" else "—",
                "SL": fmt_price(card.plan.sl) if card.action != "WAIT" else "—",
                "TP2": fmt_price(card.plan.tp2) if card.action != "WAIT" else "—",
                "R:R": f"1:{card.plan.rr:.1f}" if card.action != "WAIT" else "—",
            })
        except Exception as exc:  # never let one symbol break the scan
            rows.append({"نماد": sym, "اقدام": "ERROR", "رژیم": str(exc)[:40]})
    return rows


# --------------------------------------------------------------------------
# sidebar
# --------------------------------------------------------------------------

with st.sidebar:
    st.markdown("### 🎛️ تنظیمات")
    symbol_pick = st.selectbox("ارز", available_symbols(), index=0,
                               format_func=lambda s: s.replace("USDT", "/USDT"))
    custom = st.text_input("یا نماد دلخواه (مثلاً WIFUSDT یا PEPE)", "").strip().upper()
    symbol = custom or symbol_pick
    tf = st.radio("تایم‌فریم", list(config.TF_MINUTES), index=2, horizontal=True)
    live = st.toggle("داده واقعی از بایننس", value=False,
                     help="بدون کلید API؛ فقط اندپوینت‌های عمومی. اگر شبکه بسته باشد، شبیه‌ساز جایگزین می‌شود.")
    lang = "fa" if st.radio("زبان خروجی", ["فارسی", "English"], horizontal=True) == "فارسی" else "en"
    with st.expander("مدیریت سرمایه"):
        equity = st.number_input("سرمایه حساب (USDT)", 100.0, 10_000_000.0,
                                 float(config.DEFAULT_EQUITY), step=500.0)
        risk = st.slider("ریسک هر معامله (٪)", 0.25, float(config.MAX_RISK_PCT),
                         float(config.DEFAULT_RISK_PCT), 0.25)
    with st.expander("داده و اعتبار"):
        bars = st.slider("تعداد کندل", 200, 1000, config.DEFAULT_BARS, 50)
        seed = st.number_input("seed (شبیه‌ساز)", 0, 9999, 0)
    st.divider()
    st.markdown(f"<div class='note'>GROK SCALP v{__version__} · "
                f"۱۱ خانواده شواهد · خروجی صرفاً تحلیلی است، نه توصیه مالی.</div>",
                unsafe_allow_html=True)

# --------------------------------------------------------------------------
# hero
# --------------------------------------------------------------------------

st.markdown(
    "<div class='hero'><h1>🎯 GROK SCALP</h1>"
    "<div class='sub'>موتور سیگنال اسکالپینگ کریپتو — ساختار، اوردرفلو، سنتیمنت و تصویر چارت در یک کارت</div>"
    "<span class='chip'>SMC / ICT</span><span class='chip'>VSA / Wyckoff</span>"
    "<span class='chip'>Derivatives</span><span class='chip'>MTF</span>"
    "<span class='chip'>Vision</span></div>",
    unsafe_allow_html=True,
)

col_upload, col_meta = st.columns([1.1, 2.0])
with col_upload:
    upload = st.file_uploader("📷 اسکرین‌شات چارت (اختیاری)", type=["png", "jpg", "jpeg", "webp"])
with col_meta:
    st.markdown(
        "<div class='note'>تصویر چارت با مدل ویژن (در صورت وجود کلید) یا خواننده آفلاین تحلیل می‌شود و "
        "فقط به‌عنوان یکی از شواهد وزن می‌گیرد. بدون تصویر، موتور با داده‌های عددی کار می‌کند.</div>",
        unsafe_allow_html=True,
    )

image_bytes = upload.getvalue() if upload else None

with st.spinner("در حال خواندن بازار و اجرای موتور..."):
    started = time.time()
    card = _card(symbol, tf, live, int(bars), int(seed), float(equity), float(risk),
                 image_bytes, lang)
    elapsed = time.time() - started

snap = card.snapshot
price = snap.price if snap else 0.0
action_cls = {"LONG": "long", "SHORT": "short", "WAIT": "wait"}[card.action]
action_fa = {"LONG": "🟢 LONG — خرید", "SHORT": "🔴 SHORT — فروش",
             "WAIT": "⚪ WAIT — عدم ورود"}[card.action]
regime_fa = {"TREND_UP": "روند صعودی", "TREND_DOWN": "روند نزولی", "RANGE": "رنج",
             "HIGH_VOL": "نوسان بالا", "SQUEEZE": "فشردگی", "ILLIQUID": "کم‌عمق"}.get(card.regime.name, card.regime.name)
session_fa = {"ASIA": "آسیا", "LONDON": "لندن", "NY_AM": "نیویورک AM",
              "NY_PM": "نیویورک PM", "OFF_SESSION": "خارج سشن"}.get(card.session, card.session)

st.markdown(f"""
<div class="kv">
  <div><div class="label">نماد / تایم‌فریم</div><div class="value">{card.symbol} · {card.tf}</div></div>
  <div><div class="label">قیمت لحظه‌ای</div><div class="value">{fmt_price(price)}</div></div>
  <div><div class="label">اقدام</div><div class="value {action_cls}">{action_fa}</div></div>
  <div><div class="label">رژیم بازار / سشن</div><div class="value">{regime_fa} · {session_fa}</div>
       <div class="label">اطمینان رژیم {card.regime.confidence:.0%}</div></div>
</div>
""", unsafe_allow_html=True)

if card.action != "WAIT":
    p = card.plan
    st.markdown(f"""
<div class="kv" style="margin-top:10px">
  <div><div class="label">ناحیه ورود</div><div class="value">{fmt_price(p.entry_lo)} – {fmt_price(p.entry_hi)}</div></div>
  <div><div class="label">حد ضرر</div><div class="value short">{fmt_price(p.sl)}</div></div>
  <div><div class="label">اهداف</div><div class="value">{fmt_price(p.tp1)} · {fmt_price(p.tp2)} · {fmt_price(p.tp3)}</div></div>
  <div><div class="label">R:R تا TP2 / اهرم</div><div class="value">1:{p.rr:.1f} · {p.leverage}x</div>
       <div class="label">ریسک {p.risk_pct:.2f}٪ · مارجین {p.margin_pct:.0f}٪</div></div>
</div>
""", unsafe_allow_html=True)
else:
    st.info("موتور در این لحظه معامله‌ای نمی‌بیند. دلایل دقیق در بخش ۴ کارت آمده است — WAIT یک خروجی معتبر است.")

# --------------------------------------------------------------------------
# chart + card
# --------------------------------------------------------------------------

left, right = st.columns([1.45, 1.0])

with left:
    st.markdown("#### 📈 چارت و نواحی ساختاری")
    try:
        st.plotly_chart(build_figure(card), width="stretch", config={"displayModeBar": False})
    except Exception as exc:
        st.warning(f"رسم چارت ممکن نشد: {exc}")
    st.caption("نواحی نارنجی: اردربلاک‌های صعودی · بنفش: اردربلاک نزولی · سبز/قرمز کم‌رنگ: FVG · "
               "خط‌چین سفید: ورود، قرمز: استاپ، سبز: اهداف.")

with right:
    st.markdown("#### 🧾 کارت سیگنال")
    with st.container(border=True):
        st.markdown(render_card(card, lang))
    import json as _json
    from dataclasses import asdict
    d1, d2 = st.columns(2)
    d1.download_button("⬇️ کارت (Markdown)", render_card(card, lang),
                       file_name=f"{card.symbol}_{card.tf}_signal.md", use_container_width=True)
    payload = {k: v for k, v in asdict(card).items() if k != "snapshot"}
    d2.download_button("⬇️ داده (JSON)", _json.dumps(payload, ensure_ascii=False, indent=2,
                                                      default=str),
                       file_name=f"{card.symbol}_{card.tf}_signal.json", use_container_width=True)
    st.caption(f"زمان اجرا {elapsed * 1000:.0f} میلی‌ثانیه · منبع: {snap.source if snap else '—'} · "
               f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

# --------------------------------------------------------------------------
# tabs
# --------------------------------------------------------------------------

tab_ev, tab_flow, tab_news, tab_bt, tab_scan, tab_doc = st.tabs(
    ["🧩 شواهد", "🌊 اوردرفلو", "📰 سنتیمنت", "🧪 بک‌تست", "🔎 اسکن بازار", "📚 متدولوژی"])

with tab_ev:
    st.markdown("#### شواهد به تفکیک خانواده و جهت")
    try:
        import pandas as pd
        rows = [{
            "خانواده": e.family,
            "کد": e.code,
            "جهت": {1: "صعودی", -1: "نزولی", 0: "خنثی"}[e.direction],
            "وزن": round(e.weight, 2),
            "قدرت": round(e.strength, 2),
            "توضیح": e.note,
        } for e in sorted(card.evidence, key=lambda e: (e.family, -abs(e.signed)))]
        st.dataframe(pd.DataFrame(rows), width="stretch", height=430)
    except ImportError:
        for e in card.evidence:
            st.write(f"{e.family} · {e.direction:+d} · {e.weight:.2f}×{e.strength:.2f} — {e.note}")

    st.markdown("#### نواحی کلیدی")
    st.markdown(
        "\n".join(
            f"- **{z.kind.upper()}** {fmt_price(z.lo)} – {fmt_price(z.hi)} · {z.note}"
            for z in (card.structure.order_blocks + card.structure.fvgs)[:10]
        ) or "—"
    )

with tab_flow:
    d = snap.derivatives if snap else None
    if d:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("فاندینگ (۸ ساعته)", f"{d.funding * 100:+.4f}%",
                  f"{d.funding * 3 * 365 * 100:+.0f}% APR")
        c2.metric("تغییر OI", f"{d.oi_trend_pct:+.2f}%", f"{d.oi:,.0f} واحد")
        c3.metric("عدم‌تعادل اردربوک", f"{d.obi:+.2f}", f"اسپرد {d.orderbook.spread_bps:.1f}bps")
        c4.metric("جریان نهنگ", f"{d.whale_net:+,.0f}$", f"{len(d.whales)} پرینت")
        st.markdown("#### نقشه لیکوییدیشن (برآوردی) و نزدیک‌ترین مغناطیس‌ها")
        try:
            import pandas as pd
            liq = sorted(d.liquidations, key=lambda b: abs(b.price - price))[:14]
            st.dataframe(pd.DataFrame([{
                "سمت": "شورت" if b.side == "short" else "لانگ",
                "قیمت": fmt_price(b.price),
                "فاصله": f"{(b.price / price - 1) * 100:+.2f}%",
                "ارزش (USD)": f"{b.notional:,.0f}",
            } for b in liq]), width="stretch", height=320)
            st.bar_chart(pd.DataFrame({"قیمت": [fmt_price(b.price) for b in liq],
                                       "ارزش": [b.notional for b in liq]}).set_index("قیمت"))
        except ImportError:
            st.write(d.liquidations[:10])
        st.markdown("#### پرینت‌های نهنگ")
        for w in sorted(d.whales, key=lambda w: -w.notional)[:8]:
            st.write(f"{'🟢' if w.side == 'buy' else '🔴'} {w.notional:,.0f}$ @ {fmt_price(w.price)}")

with tab_news:
    s = snap.sentiment if snap else None
    if s:
        c1, c2, c3 = st.columns(3)
        c1.metric("شاخص ترس و طمع", s.fear_greed, s.fear_greed_label)
        c2.metric("تن اخبار", f"{s.news_score:+.2f}", f"{len(s.headlines)} تیتر")
        ev = s.next_event
        c3.metric("رویداد بعدی", ev.name if ev else "—",
                  f"{ev.minutes_away} دقیقه" if ev else "")
        for h in s.headlines:
            st.markdown(f"- **{h.score:+.2f}** · {h.title}  \n  <span class='note'>{h.source}</span>",
                        unsafe_allow_html=True)
        st.markdown("#### همبستگی کلان")
        m = snap.macro
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("BTC 24h", f"{m.btc_change_24h:+.2f}%", f"trend {m.btc_trend:+.2f}")
        c2.metric("BTC dominance", f"{m.btc_dominance:.2f}%")
        c3.metric("USDT.D", f"{m.usdt_dominance:.2f}%", f"{m.usdt_dom_change:+.2f}pp")
        c4.metric("DXY", f"{m.dxy:.2f}" if m.dxy else "—",
                  f"{m.dxy_change:+.2f}%" if m.dxy else None)
    if card.chart.available:
        st.markdown("#### خوانش تصویر چارت")
        st.write(f"روش: `{card.chart.method}` · روند: `{card.chart.trend_label}` · "
                 f"اطمینان: {card.chart.confidence:.0%} · موقعیت در رنج: {card.chart.range_position:.0%}")
        for n in card.chart.notes:
            st.markdown(f"- {n}")
        for p in card.chart.patterns:
            st.markdown(f"- الگو: {p}")

with tab_bt:
    st.markdown("#### اعتبارسنجی واک‌فوروارد")
    st.caption("موتور بار‌به‌بار روی تاریخچه اجرا می‌شود، فقط سیگنال‌های قابل انتشار را می‌گیرد و "
               "می‌سنجد TP1 قبل از استاپ خورده یا نه. نتیجه، احتمال کارت را کالیبره می‌کند.")
    bt_symbols = st.multiselect("نمادها", available_symbols(), default=[symbol])
    horizon = st.slider("افق نگهداری (کندل)", 6, 96, 24, 6)
    if st.button("اجرای بک‌تست", type="primary"):
        with st.spinner("در حال اجرای واک‌فوروارد..."):
            agg: dict[str, dict] = {}
            for sym in bt_symbols or [symbol]:
                snap_bt = _snapshot(sym, tf, live, 1200, int(seed))
                res = run_backtest(snap_bt, SignalEngine(equity=equity, risk_pct=risk),
                                   horizon=horizon, max_steps=260)
                st.markdown(f"**{sym} · {tf}**")
                st.code(format_report(res), language="text")
                for regime, bucket in (res.get("by_regime") or {}).items():
                    agg.setdefault(regime, {"trades": 0, "wins": 0.0, "p": 0.0})
                    n = bucket.get("trades", 0)
                    agg[regime]["trades"] += n
                    agg[regime]["wins"] += bucket.get("hit_rate", 0) * n
                    agg[regime]["p"] += bucket.get("mean_p", 0) * n
            st.session_state["calib_preview"] = {
                k: {"hit_rate": v["wins"] / v["trades"], "mean_p": v["p"] / v["trades"],
                    "trades": v["trades"]}
                for k, v in agg.items() if v["trades"]}
    if st.session_state.get("calib_preview"):
        st.markdown("#### کالیبراسیون پیشنهادی")
        st.json(calibrate(st.session_state["calib_preview"]))
        st.caption("برای ذخیره دائمی: `python -m grokscalp --backtest --live --calibrate`")

with tab_scan:
    st.markdown("#### اسکن هم‌زمان بازار")
    st.caption("همه نمادها با همان موتور و همان تایم‌فریم خوانده می‌شوند؛ ستون «لبه» فاصله خریدار/فروشنده است.")
    if st.button("اسکن نمادهای اصلی"):
        with st.spinner("در حال اسکن..."):
            rows = _scan(tuple(available_symbols()[:12]), tf, live, int(seed))
        try:
            import pandas as pd
            df = pd.DataFrame(rows)
            st.dataframe(df, width="stretch", height=460)
        except ImportError:
            st.write(rows)

with tab_doc:
    st.markdown("""
#### موتور چطور تصمیم می‌گیرد؟
1. **رژیم بازار** روی تایم‌فریم بالاتر تشخیص داده می‌شود (روند / رنج / نوسان بالا / فشردگی / کم‌عمق).
   وزن هر خانواده شواهد بر اساس همین رژیم تغییر می‌کند؛ یعنی موتور به یک استراتژی قفل نیست.
2. **یازده خانواده شواهد** اجرا می‌شوند: SMC/ICT (BOS، CHoCH، OB، FVG، سوییپ نقدینگی، OTE، پریمیوم/دیسکانت)،
   مولتی‌تایم‌فریم، مشتقات (OI، فاندینگ، CVD، اوردربوک، لیکوییدیشن، نهنگ)، VSA/وایکوف، اندیکاتورها و واگرایی،
   پروفایل حجم، الگوهای قیمتی و هارمونیک، همبستگی کلان، سنتیمنت و اخبار، تصویر چارت و سشن.
3. هر شاهد وزن × قدرت × اعتبار خانواده × ضریب رژیم را می‌گیرد. جمع خریدار و فروشنده دو عدد می‌سازد،
   تفاضلشان «لبه» و نسبتشان «تضاد» است.
4. **دروازه‌ها**: لبه کم، تضاد زیاد، شواهد ناکافی، مخالفت تایم‌فریم بالاتر، فاندینگ اشباع، اسپرد بد یا
   خبر مهم نزدیک ⇒ `WAIT`. این رایج‌ترین خروجی درست است.
5. **ریسک**: استاپ پشت ناحیه ابطال + بافر ATR؛ اهداف از نقدینگی و پروفایل حجم با کف R:R؛
   حجم پوزیشن از درصد ریسک حساب و فاصله استاپ، نه از یک عدد ثابت.
6. **احتمال** از مدل confluence می‌آید و با بک‌تست واک‌فوروارد (`config/calibration.json`) کالیبره می‌شود.

#### محدودیت‌ها (صادقانه)
- در حالت شبیه‌ساز، اعداد درباره «فرصت واقعی» چیزی نمی‌گویند؛ فقط موتور و استدلال را نشان می‌دهند.
- نقشه لیکوییدیشن بایننس دیگر عمومی نیست؛ این نقشه از نقدینگی سوئینگ‌ها برآورد می‌شود.
- خواننده آفلاین تصویر، محور قیمت را نمی‌خواند و سطح مطلق نمی‌سازد؛ برای سطح دقیق، کلید ویژن بدهید.
- خروجی تحلیل است، نه توصیه مالی. مسئولیت اندازه پوزیشن و ریسک با شماست.
""")
