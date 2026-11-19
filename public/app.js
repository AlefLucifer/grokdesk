/* GROK SCALP — front-end. No framework, no CDN: the page must work even if a
   third-party script host is blocked. Everything it shows comes from
   /api/signal (or /api/analyse when a screenshot is attached). */

(() => {
  "use strict";

  const TFS = ["1m", "3m", "5m", "15m", "30m", "1h", "4h"];
  const FAMILY_FA = {
    SMC: "ساختار / SMC-ICT", MTF: "مولتی‌تایم‌فریم", DERIV: "مشتقات و اوردرفلو",
    VSA: "VSA / وایکوف", IND: "اندیکاتورها", VP: "پروفایل حجم",
    PATTERN: "الگوها", MACRO: "کلان", SENTIMENT: "سنتیمنت", VISION: "تصویر چارت",
    SESSION: "سشن",
  };
  const REGIME_FA = {
    TREND_UP: "روند صعودی", TREND_DOWN: "روند نزولی", RANGE: "رنج",
    HIGH_VOL: "نوسان بالا", SQUEEZE: "فشردگی", ILLIQUID: "کم‌عمق",
  };
  const SESSION_FA = {
    ASIA: "آسیا", LONDON: "لندن", NY_AM: "نیویورک AM", NY_PM: "نیویورک PM",
    OFF_SESSION: "خارج سشن",
  };

  const state = {
    symbol: "BTCUSDT",
    tf: "5m",
    live: true,
    equity: 10000,
    risk: 1.5,
    image: null,
    data: null,
  };

  const $ = (sel) => document.querySelector(sel);
  const el = (tag, cls, text) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (ch) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]
  ));

  function fmt(p) {
    if (p === null || p === undefined || Number.isNaN(Number(p))) return "—";
    const a = Math.abs(Number(p));
    const d = a >= 10000 ? 1 : a >= 100 ? 2 : a >= 1 ? 4 : a >= 0.01 ? 5 : 8;
    return Number(p).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
  }
  const pct = (x) => (x === null || x === undefined ? "—" : `${Math.round(Number(x) * 100)}٪`);
  const money = (x) => (x === null || x === undefined ? "—" : `${Math.round(Number(x)).toLocaleString("en-US")}$`);
  const clamp = (x, a, b) => Math.max(a, Math.min(b, x));

  // ---------------------------------------------------------------- state
  function readUrl() {
    const q = new URLSearchParams(location.search);
    if (q.get("symbol")) state.symbol = q.get("symbol").toUpperCase();
    if (TFS.includes(q.get("tf"))) state.tf = q.get("tf");
    if (q.get("live") === "0") state.live = false;
    if (q.get("live") === "1") state.live = true;
    if (q.get("equity")) state.equity = Number(q.get("equity")) || 10000;
    if (q.get("risk")) state.risk = Number(q.get("risk")) || 1.5;
  }
  function writeUrl() {
    const q = new URLSearchParams({
      symbol: state.symbol, tf: state.tf, live: state.live ? "1" : "0",
      equity: String(state.equity), risk: String(state.risk),
    });
    history.replaceState(null, "", `?${q.toString()}`);
  }

  // --------------------------------------------------------------- status
  function status(msg, kind) {
    const node = $("#status");
    node.textContent = msg || "";
    node.className = "status" + (kind ? ` ${kind}` : "");
  }

  // ---------------------------------------------------------------- fetch
  async function run() {
    const btn = $("#run");
    btn.disabled = true;
    status("در حال خواندن بازار و اجرای موتور…", "loading");
    try {
      let data;
      if (state.image) {
        const body = {
          symbol: state.symbol, tf: state.tf, live: state.live,
          equity: state.equity, risk: state.risk, image: state.image,
        };
        const res = await fetch("/api/analyse", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        data = await res.json();
        if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
      } else {
        const q = new URLSearchParams({
          symbol: state.symbol, tf: state.tf,
          live: state.live ? "1" : "0",
          equity: String(state.equity), risk: String(state.risk),
        });
        const res = await fetch(`/api/signal?${q.toString()}`);
        data = await res.json();
        if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
      }
      state.data = data;
      render(data);
      writeUrl();
      const card = data.card;
      status(`تحلیل ${card.symbol} ${card.tf} در ${data.meta.ms} میلی‌ثانیه — ${new Date().toLocaleTimeString("fa-IR")}`);
    } catch (err) {
      status(`خطا: ${err.message}`, "error");
      console.error(err);
    } finally {
      btn.disabled = false;
    }
  }

  // --------------------------------------------------------------- render
  function render(data) {
    const card = data.card;
    state.symbol = card.symbol;
    if ($("#symbol").value !== card.symbol) $("#symbol").value = card.symbol;
    const price = data.price;
    const liveRequested = data.meta.live_requested;
    const simulated = String(data.source).startsWith("synthetic");

    const src = $("#badge-source");
    src.textContent = simulated
      ? (liveRequested ? "شبیه‌ساز (داده واقعی در دسترس نبود)" : "داده شبیه‌ساز")
      : `زنده: ${data.source}`;
    src.className = "badge" + (simulated ? " warn" : "");
    $("#badge-version").textContent = `v${data.meta.version}`;

    renderSummary(card, price);
    renderWhy(card);
    renderEvidence(card);
    renderFlow(data);
    renderNews(data);
    $("#card-text").textContent = data.text;
    $("#chart-hint").textContent =
      `${card.symbol} · ${card.tf} · ${REGIME_FA[card.regime.name] || card.regime.name} · ` +
      `${data.series.length} کندل`;
    drawChart(data);
  }

  function stat(k, v, s, cls) {
    const box = el("div", "stat");
    box.appendChild(el("div", "k", k));
    const value = el("div", `v ${cls || ""}`.trim(), v);
    value.title = v;
    box.appendChild(value);
    if (s) box.appendChild(el("div", "s", s));
    return box;
  }

  function renderSummary(card, price) {
    const root = $("#summary");
    root.innerHTML = "";
    const p = card.plan;
    const wait = card.action === "WAIT";
    const actionText = { LONG: "🟢 LONG — خرید", SHORT: "🔴 SHORT — فروش", WAIT: "⚪ WAIT — عدم ورود" }[card.action];

    root.appendChild(stat("اقدام", actionText, wait ? "بازار برای ورود مناسب نیست" : p.order_type,
      card.action === "LONG" ? "long" : card.action === "SHORT" ? "short" : "wait"));
    root.appendChild(stat("قیمت", fmt(price), `${card.symbol} · ${card.tf}`));
    root.appendChild(stat("رژیم بازار", REGIME_FA[card.regime.name] || card.regime.name,
      `اطمینان ${pct(card.regime.confidence)} · ADX ${card.regime.adx.toFixed(1)}`));
    root.appendChild(stat("سشن", SESSION_FA[card.session] || card.session,
      `کیفیت ${pct(card.session_quality)}`));
    root.appendChild(stat("ناحیه ورود",
      wait ? "—" : (p.entry_hi !== p.entry_lo ? `${fmt(p.entry_lo)} – ${fmt(p.entry_hi)}` : fmt(p.entry)),
      wait ? "بدون سفارش" : `${p.order_type} · میانه ${fmt(p.entry)}`));
    root.appendChild(stat("حد ضرر", wait ? "—" : fmt(p.sl),
      wait ? "" : `${(p.stop_pct * 100).toFixed(2)}٪ از ورود`, wait ? "wait" : "short"));
    root.appendChild(stat("اهداف",
      wait ? "—" : `${fmt(p.tp1)} · ${fmt(p.tp2)} · ${fmt(p.tp3)}`,
      wait ? "" : "TP1 · TP2 · TP3"));
    root.appendChild(stat("احتمال / R:R", pct(card.probability),
      wait ? "تمایل جهت — ورود توصیه نمی‌شود" : `R:R 1:${p.rr.toFixed(1)} · لبه ${card.edge >= 0 ? "+" : ""}${card.edge.toFixed(2)}`));
    root.appendChild(stat("اهرم / مارجین", wait ? "—" : `${p.leverage}x · ${Math.round(p.margin_pct)}٪`,
      wait ? "" : `ریسک ${p.risk_pct.toFixed(2)}٪ ≈ ${Math.round(p.risk_amount)}$`));
    root.appendChild(stat("اجماع", `${Math.round(card.conviction * 100)}٪`,
      `خریدار ${card.bull_score.toFixed(2)} / فروشنده ${card.bear_score.toFixed(2)} · تضاد ${Math.round(card.conflict * 100)}٪`));
  }

  function listBlock(title, items, limit) {
    const frag = document.createDocumentFragment();
    frag.appendChild(el("h3", null, title));
    const ul = el("ul");
    (items || []).slice(0, limit || 99).forEach((t) => ul.appendChild(el("li", null, t)));
    if (!items || !items.length) ul.appendChild(el("li", null, "—"));
    frag.appendChild(ul);
    return frag;
  }

  function renderWhy(card) {
    const root = $("#why");
    root.innerHTML = "";

    const tags = el("div", "tags");
    (card.why_strategies || []).forEach((s) => tags.appendChild(el("span", "tag", s)));
    (card.warnings || []).slice(0, 2).forEach((w) => tags.appendChild(el("span", "tag warn", w)));
    root.appendChild(tags);

    if (card.action === "WAIT") {
      root.appendChild(listBlock("دلایل عدم ورود", card.wait_reasons));
    }
    root.appendChild(listBlock("دلایل تکنیکال", card.why_technical, 5));
    root.appendChild(listBlock("دیتا و سنتیمنت", card.why_data, 5));
    root.appendChild(listBlock("سشن، بیت‌کوین و رژیم", card.context, 4));
  }

  function renderEvidence(card) {
    const body = $("#evidence-table tbody");
    body.innerHTML = "";
    const rows = [...(card.evidence || [])].sort((a, b) => Math.abs(b.weight * b.strength) - Math.abs(a.weight * a.strength));
    rows.forEach((e) => {
      const tr = el("tr");
      tr.appendChild(el("td", null, FAMILY_FA[e.family] || e.family));
      const dir = el("td", e.direction > 0 ? "dir-up" : e.direction < 0 ? "dir-down" : "dir-flat",
        e.direction > 0 ? "▲ صعودی" : e.direction < 0 ? "▼ نزولی" : "خنثی");
      tr.appendChild(dir);
      tr.appendChild(el("td", "num", e.weight.toFixed(2)));
      tr.appendChild(el("td", "num", e.strength.toFixed(2)));
      tr.appendChild(el("td", null, e.note));
      body.appendChild(tr);
    });
    if (!rows.length) {
      const tr = el("tr");
      const td = el("td", null, "شاهدی ثبت نشد");
      td.colSpan = 5;
      tr.appendChild(td);
      body.appendChild(tr);
    }
  }

  function metric(k, v, s) {
    const box = el("div", "metric");
    box.appendChild(el("div", "k", k));
    box.appendChild(el("div", "v", v));
    if (s) box.appendChild(el("div", "s", s));
    return box;
  }

  function renderFlow(data) {
    const root = $("#flow");
    root.innerHTML = "";
    const m = data.market || {};
    const d = m.derivatives || {};
    root.appendChild(metric("فاندینگ (۸ ساعته)", `${(d.funding * 100).toFixed(4)}%`,
      `سالانه ${(d.funding * 3 * 365 * 100).toFixed(0)}% · ${d.funding_bias || ""}`));
    root.appendChild(metric("تغییر OI", `${d.oi_change >= 0 ? "+" : ""}${(d.oi_change || 0).toFixed(2)}%`,
      `${Math.round(d.oi || 0).toLocaleString("en-US")} واحد`));
    root.appendChild(metric("عدم‌تعادل اردربوک", (d.obi || 0).toFixed(2),
      `اسپرد ${(d.spread || 0).toFixed(1)} bps`));
    root.appendChild(metric("جریان نهنگ", money(d.whale_net), `${d.whale_count || 0} پرینت`));
    root.appendChild(metric("CVD تجمعی", Math.round(d.cvd || 0).toLocaleString("en-US"),
      `دلتای ۲۰ کندل ${Math.round(d.delta20 || 0).toLocaleString("en-US")}`));
    root.appendChild(metric("ترس و طمع", `${m.fear_greed ?? "—"}`, m.fear_greed_label || ""));

    const liq = d.liquidations || [];
    if (liq.length) {
      const wrap = el("div", "table-wrap");
      const table = el("table");
      table.innerHTML = "<thead><tr><th>سمت</th><th>قیمت</th><th>فاصله</th><th>ارزش (USD)</th></tr></thead>";
      const tb = el("tbody");
      liq.forEach((b) => {
        const tr = el("tr");
        tr.appendChild(el("td", null, b.side === "long" ? "لانگ" : "شورت"));
        tr.appendChild(el("td", "num", fmt(b.price)));
        tr.appendChild(el("td", "num", `${b.distance >= 0 ? "+" : ""}${b.distance.toFixed(2)}%`));
        tr.appendChild(el("td", "num", Math.round(b.notional).toLocaleString("en-US")));
        tb.appendChild(tr);
      });
      table.appendChild(tb);
      wrap.appendChild(table);
      root.appendChild(wrap);
    }
  }

  function renderNews(data) {
    const root = $("#news");
    root.innerHTML = "";
    const m = data.market || {};
    const macro = m.macro || {};
    root.appendChild(metric("تن اخبار", (m.news_score ?? 0).toFixed(2), `${(m.headlines || []).length} تیتر`));
    root.appendChild(metric("رویداد بعدی", m.next_event ? m.next_event.name : "—",
      m.next_event ? `${m.next_event.minutes_away} دقیقه دیگر` : ""));
    root.appendChild(metric("BTC ۲۴ ساعت", `${macro.btc_change_24h >= 0 ? "+" : ""}${(macro.btc_change_24h || 0).toFixed(2)}%`,
      `امتیاز روند ${(macro.btc_trend || 0).toFixed(2)}`));
    root.appendChild(metric("دامیننس BTC", `${(macro.btc_dominance || 0).toFixed(2)}%`));
    root.appendChild(metric("USDT.D", `${(macro.usdt_dominance || 0).toFixed(2)}%`,
      `${(macro.usdt_dom_change || 0) >= 0 ? "+" : ""}${(macro.usdt_dom_change || 0).toFixed(2)}pp`));
    root.appendChild(metric("DXY", macro.dxy ? macro.dxy.toFixed(2) : "—",
      macro.dxy ? `${macro.dxy_change >= 0 ? "+" : ""}${(macro.dxy_change || 0).toFixed(2)}%` : ""));

    const ul = $("#headlines");
    ul.innerHTML = "";
    (m.headlines || []).forEach((h) => {
      const li = el("li");
      const score = Number(h.score || 0);
      li.innerHTML = `<span class="${score >= 0 ? "dir-up" : "dir-down"}">${score >= 0 ? "▲" : "▼"} ${score.toFixed(2)}</span> · ${esc(h.title)} <span class="src">— ${esc(h.source || "")}</span>`;
      ul.appendChild(li);
    });
    if (!(m.headlines || []).length) {
      ul.appendChild(el("li", "src", "تیتری خوانده نشد (برای اخبار زنده به CRYPTOPANIC_TOKEN نیاز است)."));
    }
  }

  // ---------------------------------------------------------------- chart
  function ema(values, period) {
    const k = 2 / (period + 1);
    let prev = values[0];
    return values.map((v, i) => {
      if (i === 0) return prev;
      prev = v * k + prev * (1 - k);
      return prev;
    });
  }

  function drawChart(data) {
    const canvas = $("#chart");
    const wrap = canvas.parentElement;
    const w = Math.max(wrap.clientWidth, 200);
    const h = Math.max(wrap.clientHeight, 240);
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);

    const series = (data.series || []).slice(-160);
    if (!series.length) return;
    const card = data.card;
    const plan = card.plan || {};
    const zones = card.structure || {};
    const wait = card.action === "WAIT";

    const padL = 6, padR = 66, padT = 12, padB = 20;
    const volH = Math.max(34, h * 0.15);
    const plotW = w - padL - padR;
    const priceH = h - padT - padB - volH - 12;

    let hi = Math.max(...series.map((s) => s[2]));
    let lo = Math.min(...series.map((s) => s[3]));
    if (!wait) {
      hi = Math.max(hi, plan.tp3, plan.entry_hi);
      lo = Math.min(lo, plan.sl);
    }
    (zones.order_blocks || []).forEach((z) => { hi = Math.max(hi, z.hi); lo = Math.min(lo, z.lo); });
    const span = hi - lo || 1;
    hi += span * 0.03;
    lo -= span * 0.03;

    const x = (i) => padL + (i + 0.5) * (plotW / series.length);
    const y = (p) => padT + ((hi - p) / (hi - lo)) * priceH;
    const volTop = padT + priceH + 12;
    const maxVol = Math.max(...series.map((s) => s[5]), 1e-9);

    // grid + price axis
    ctx.font = "11px ui-monospace, Menlo, monospace";
    ctx.textBaseline = "middle";
    for (let i = 0; i <= 4; i += 1) {
      const price = lo + ((hi - lo) * i) / 4;
      const yy = y(price);
      ctx.strokeStyle = "rgba(120,180,255,.09)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(padL, yy);
      ctx.lineTo(padL + plotW, yy);
      ctx.stroke();
      ctx.fillStyle = "rgba(141,162,189,.9)";
      ctx.textAlign = "left";
      ctx.fillText(fmt(price), padL + plotW + 8, yy);
    }

    // structural zones behind price
    const idxFromTs = (ts) => {
      const found = series.findIndex((s) => s[0] >= ts);
      return found < 0 ? 0 : found;
    };
    (zones.order_blocks || []).forEach((z) => {
      const x0 = x(idxFromTs(z.ts || 0));
      const bull = /bull/.test(z.note);
      ctx.fillStyle = bull ? "rgba(255,167,38,.14)" : "rgba(156,123,255,.14)";
      ctx.fillRect(x0, y(z.hi), padL + plotW - x0, Math.max(2, y(z.lo) - y(z.hi)));
      ctx.strokeStyle = bull ? "rgba(255,167,38,.35)" : "rgba(156,123,255,.35)";
      ctx.strokeRect(x0, y(z.hi), padL + plotW - x0, Math.max(2, y(z.lo) - y(z.hi)));
    });
    (zones.fvgs || []).forEach((z) => {
      const x0 = x(idxFromTs(z.ts || 0));
      const bull = /bull/.test(z.note);
      ctx.fillStyle = bull ? "rgba(38,166,154,.12)" : "rgba(239,83,80,.12)";
      ctx.fillRect(x0, y(z.hi), padL + plotW - x0, Math.max(2, y(z.lo) - y(z.hi)));
    });

    // liquidity pools
    ctx.setLineDash([4, 4]);
    (zones.pools || []).slice(0, 4).forEach((p) => {
      const yy = y((p.lo + p.hi) / 2);
      const bsl = /BSL|highs/.test(p.note);
      ctx.strokeStyle = bsl ? "rgba(239,83,80,.35)" : "rgba(38,166,154,.35)";
      ctx.beginPath();
      ctx.moveTo(padL, yy);
      ctx.lineTo(padL + plotW, yy);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = bsl ? "rgba(239,83,80,.75)" : "rgba(38,166,154,.75)";
      ctx.textAlign = "right";
      ctx.fillText(bsl ? "BSL" : "SSL", padL + plotW - 2, yy - 7);
      ctx.setLineDash([4, 4]);
    });
    ctx.setLineDash([]);

    // candles
    const bw = Math.max(1.6, Math.min(9, (plotW / series.length) * 0.62));
    series.forEach((s, i) => {
      const [ts, o, hh, ll, c] = s;
      const bull = c >= o;
      const color = bull ? "#26a69a" : "#ef5350";
      const cx = x(i);
      ctx.strokeStyle = color;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(cx, y(hh));
      ctx.lineTo(cx, y(ll));
      ctx.stroke();
      ctx.fillStyle = color;
      const yo = y(o), yc = y(c);
      ctx.fillRect(cx - bw / 2, Math.min(yo, yc), bw, Math.max(1, Math.abs(yc - yo)));
    });

    // volume
    series.forEach((s, i) => {
      const bull = s[4] >= s[1];
      const vh = (s[5] / maxVol) * (volH - 4);
      ctx.fillStyle = bull ? "rgba(38,166,154,.45)" : "rgba(239,83,80,.45)";
      ctx.fillRect(x(i) - bw / 2, volTop + (volH - 4) - vh, bw, vh);
    });

    // EMAs
    const closes = series.map((s) => s[4]);
    [[21, "rgba(66,165,245,.85)"], [50, "rgba(171,71,188,.8)"]].forEach(([period, color]) => {
      const vals = ema(closes, period);
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.3;
      ctx.beginPath();
      vals.forEach((v, i) => (i ? ctx.lineTo(x(i), y(v)) : ctx.moveTo(x(i), y(v))));
      ctx.stroke();
    });

    // current price
    const last = closes[closes.length - 1];
    ctx.setLineDash([2, 3]);
    ctx.strokeStyle = "rgba(230,237,247,.35)";
    ctx.beginPath();
    ctx.moveTo(padL, y(last));
    ctx.lineTo(padL + plotW, y(last));
    ctx.stroke();
    ctx.setLineDash([]);

    // trade plan
    if (!wait) {
      const zoneTop = y(Math.max(plan.entry_lo, plan.entry_hi));
      const zoneBottom = y(Math.min(plan.entry_lo, plan.entry_hi));
      ctx.fillStyle = "rgba(255,255,255,.08)";
      ctx.fillRect(padL, zoneTop, plotW, Math.max(2, zoneBottom - zoneTop));

      const lines = [
        [plan.entry, "ورود " + fmt(plan.entry), "rgba(224,224,224,.9)"],
        [plan.tp1, "TP1 " + fmt(plan.tp1), "rgba(102,187,106,.9)"],
        [plan.tp2, "TP2 " + fmt(plan.tp2), "rgba(76,175,80,.95)"],
        [plan.tp3, "TP3 " + fmt(plan.tp3), "rgba(46,125,50,.95)"],
        [plan.sl, "SL " + fmt(plan.sl), "rgba(239,83,80,.95)"],
      ];
      lines.forEach(([value, label, color]) => {
        const yy = y(value);
        ctx.setLineDash([5, 4]);
        ctx.strokeStyle = color;
        ctx.lineWidth = 1.1;
        ctx.beginPath();
        ctx.moveTo(padL, yy);
        ctx.lineTo(padL + plotW, yy);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = color;
        ctx.textAlign = "left";
        ctx.font = "10px ui-monospace, Menlo, monospace";
        ctx.fillText(label, padL + plotW + 7, yy);
      });
    }

    // time axis
    ctx.fillStyle = "rgba(141,162,189,.75)";
    ctx.font = "10px ui-monospace, Menlo, monospace";
    const ticks = 4;
    for (let t = 0; t <= ticks; t += 1) {
      const i = Math.floor(((series.length - 1) * t) / ticks);
      const d = new Date(series[i][0]);
      const label = `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
      ctx.textAlign = t === 0 ? "left" : t === ticks ? "right" : "center";
      ctx.fillText(label, x(i), h - 8);
    }
  }

  // ----------------------------------------------------------------- scan
  async function scan() {
    const btn = $("#scan");
    btn.disabled = true;
    const body = $("#scan-table tbody");
    body.innerHTML = "";
    const tr = el("tr");
    const td = el("td", null, "در حال اسکن…");
    td.colSpan = 10;
    tr.appendChild(td);
    body.appendChild(tr);
    try {
      const q = new URLSearchParams({ tf: state.tf, live: "0" });
      const res = await fetch(`/api/scan?${q.toString()}`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
      body.innerHTML = "";
      data.rows.forEach((r) => {
        const row = el("tr");
        row.appendChild(el("td", "num", r.symbol));
        const act = el("td");
        const cls = r.action === "LONG" ? "long" : r.action === "SHORT" ? "short" : "wait";
        act.appendChild(el("span", `pill-mini ${cls}`, r.action));
        row.appendChild(act);
        row.appendChild(el("td", null, REGIME_FA[r.regime] || r.regime || "—"));
        row.appendChild(el("td", "num", r.price || "—"));
        row.appendChild(el("td", "num", r.probability != null ? `${r.probability}٪` : "—"));
        row.appendChild(el("td", "num", r.edge != null ? (r.edge > 0 ? "+" : "") + r.edge.toFixed(2) : "—"));
        row.appendChild(el("td", "num", r.entry || "—"));
        row.appendChild(el("td", "num", r.sl || "—"));
        row.appendChild(el("td", "num", r.tp2 || "—"));
        row.appendChild(el("td", "num", r.rr ? `1:${r.rr}` : "—"));
        body.appendChild(row);
      });
      status(`اسکن ${data.rows.length} نماد روی ${data.tf} انجام شد`);
    } catch (err) {
      body.innerHTML = "";
      const row = el("tr");
      const cell = el("td", "dir-down", `خطا: ${err.message}`);
      cell.colSpan = 10;
      row.appendChild(cell);
      body.appendChild(row);
    } finally {
      btn.disabled = false;
    }
  }

  // ----------------------------------------------------------------- init
  function buildTfs() {
    const root = $("#tfs");
    TFS.forEach((tf) => {
      const b = el("button", `pill${tf === state.tf ? " active" : ""}`, tf);
      b.dataset.tf = tf;
      b.addEventListener("click", () => {
        readInputs();
        state.tf = tf;
        [...root.children].forEach((c) => c.classList.toggle("active", c.dataset.tf === tf));
        run();
      });
      root.appendChild(b);
    });
  }

  function buildLive() {
    const on = $("#live-on"), off = $("#live-off");
    const sync = () => {
      on.classList.toggle("active", state.live);
      off.classList.toggle("active", !state.live);
    };
    on.addEventListener("click", () => { readInputs(); state.live = true; sync(); run(); });
    off.addEventListener("click", () => { readInputs(); state.live = false; sync(); run(); });
    sync();
  }

  async function loadSymbols() {
    try {
      const res = await fetch("/api/symbols");
      const data = await res.json();
      const list = $("#symbols");
      list.innerHTML = "";
      (data.symbols || []).forEach((s) => {
        const opt = document.createElement("option");
        opt.value = s;
        list.appendChild(opt);
      });
    } catch (e) {
      /* the input still accepts any symbol */
    }
  }

  function readInputs() {
    state.symbol = ($("#symbol").value || "BTCUSDT").trim().toUpperCase();
    state.equity = clamp(Number($("#equity").value) || 10000, 100, 10000000);
    state.risk = clamp(Number($("#risk").value) || 1.5, 0.1, 2);
  }

  function wire() {
    $("#symbol").value = state.symbol;
    $("#equity").value = String(state.equity);
    $("#risk").value = String(state.risk);
    $("#run").addEventListener("click", () => { readInputs(); run(); });
    $("#symbol").addEventListener("keydown", (e) => { if (e.key === "Enter") $("#run").click(); });
    $("#scan").addEventListener("click", scan);
    $("#copy-card").addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText($("#card-text").textContent);
        status("کارت کپی شد.");
      } catch (e) {
        status("کپی ممکن نشد؛ متن را دستی انتخاب کنید.", "error");
      }
    });
    $("#download-json").addEventListener("click", () => {
      if (!state.data) return;
      const blob = new Blob([JSON.stringify(state.data.card, null, 2)], { type: "application/json" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `${state.data.card.symbol}_${state.data.card.tf}_signal.json`;
      a.click();
      URL.revokeObjectURL(a.href);
    });
    $("#image").addEventListener("change", (e) => {
      const file = e.target.files && e.target.files[0];
      if (!file) { state.image = null; return; }
      if (file.size > 3.5 * 1024 * 1024) {
        status("تصویر بزرگ‌تر از ۳.۵ مگابایت است؛ یک اسکرین‌شات کوچک‌تر بفرستید.", "error");
        e.target.value = "";
        return;
      }
      const reader = new FileReader();
      reader.onload = () => {
        state.image = reader.result;
        status(`تصویر «${file.name}» آماده است؛ روی تحلیل بزنید.`);
      };
      reader.readAsDataURL(file);
    });
    $("#clear-image").addEventListener("click", () => {
      $("#image").value = "";
      state.image = null;
      status("تصویر حذف شد.");
    });

    document.querySelectorAll(".tabs button").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("active", b === btn));
        document.querySelectorAll(".tab-body").forEach((b) => b.classList.remove("active"));
        $(`#tab-${btn.dataset.tab}`).classList.add("active");
        if (btn.dataset.tab === "chart") drawChart(state.data);
      });
    });

    let timer = null;
    window.addEventListener("resize", () => {
      clearTimeout(timer);
      timer = setTimeout(() => { if (state.data) drawChart(state.data); }, 150);
    });
  }

  readUrl();
  buildTfs();
  buildLive();
  wire();
  loadSymbols();
  run();
})();
