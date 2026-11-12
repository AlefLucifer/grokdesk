'use strict';
(() => {
  const $ = id => document.getElementById(id), key = 'grokdesk-auto-paper-v1';
  let state;
  try {
    state = JSON.parse(localStorage.getItem(key)) || Paper.fresh();
    if (!Number.isFinite(state.cash) || !state.positions || !Array.isArray(state.trades) || !Array.isArray(state.entryTimes) || !state.cooldown || !Number.isFinite(state.wins) || !Number.isFinite(state.losses) || !Number.isFinite(state.flat)) throw Error();
  } catch { state = Paper.fresh(); }
  let pairs = new Map(), fetchedAt = 0, ok = false, loading = false, running = false;
  const money = value => '$' + value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const price = value => '$' + value.toLocaleString('en-US', { maximumSignificantDigits: 6 });
  const active = () => ok && Date.now() - fetchedAt < 90000;
  function save() { try { localStorage.setItem(key, JSON.stringify(state)); } catch { $('message').textContent = 'ذخیره در مرورگر ممکن نیست؛ داده‌ها ممکن است از بین بروند.'; } }
  function cell(row, text, className) { const td = document.createElement('td'); td.textContent = text; if (className) td.className = className; row.appendChild(td); return td; }
  function empty(table, text, span) { const row = table.insertRow(); const td = cell(row, text); td.colSpan = span; }
  function render() {
    const isActive = active();
    $('cash').textContent = money(state.cash); $('count').textContent = Object.keys(state.positions).length;
    $('bot-status').textContent = running ? (isActive ? 'فعال — در حال بررسی بازار' : 'فعال، منتظر داده معتبر') : 'متوقف';
    $('start').disabled = running; $('pause').disabled = !running;
    const closed = state.wins + state.losses + state.flat;
    $('winrate').textContent = closed ? (100 * state.wins / closed).toFixed(1) + '%' : '—';
    $('record').textContent = `${state.wins} برد / ${state.losses} باخت / ${state.flat} سربه‌سر · ${closed} بسته‌شده`;
    $('realized').textContent = money(state.realized);
    const tbody = $('markets'); tbody.replaceChildren();
    for (const p of pairs.values()) {
      const row = tbody.insertRow(); const label = cell(row, p.symbol + ' / ' + p.quote); const small = document.createElement('small'); small.textContent = p.dex + ' · ' + p.id.slice(0, 8); label.appendChild(small);
      cell(row, price(p.price), 'ltr'); cell(row, p.change5m == null ? '—' : p.change5m.toFixed(2) + '%', 'ltr'); cell(row, p.liquidity == null ? '—' : money(p.liquidity), 'ltr'); cell(row, Paper.eligible(p) ? 'واجد شرایط' : 'رد شده');
    }
    const positions = $('positions'); positions.replaceChildren(); let value = 0, complete = isActive;
    for (const pos of Object.values(state.positions)) {
      const p = pairs.get(pos.id), row = positions.insertRow(); cell(row, pos.symbol + ' · ' + pos.id.slice(0, 8)); cell(row, price(pos.entry), 'ltr'); cell(row, money(pos.cost), 'ltr');
      if (p && isActive) { const v = pos.quantity * p.price * (1 - Paper.FEE); value += v; cell(row, price(p.price), 'ltr'); cell(row, money(v - pos.cost), v >= pos.cost ? 'up ltr' : 'down ltr'); }
      else { complete = false; cell(row, 'قیمت موجود نیست'); cell(row, '—'); }
      cell(row, new Date(pos.opened).toLocaleString('fa-IR'));
    }
    if (!Object.keys(state.positions).length) empty(positions, 'هنوز موقعیت بازی وجود ندارد.', 6);
    $('equity').textContent = complete ? money(state.cash + value) : 'نامشخص'; $('pnl').textContent = complete ? money(state.cash + value - Paper.INITIAL) : 'نامشخص';
    const trades = $('trades'); trades.replaceChildren();
    for (const t of state.trades) { const row = trades.insertRow(); cell(row, t.side); cell(row, t.symbol + ' · ' + t.id.slice(0, 8)); cell(row, money(t.dollars), 'ltr'); cell(row, price(t.price), 'ltr'); cell(row, t.pnl == null ? '—' : money(t.pnl), 'ltr'); cell(row, t.reason); cell(row, new Date(t.at).toLocaleString('fa-IR')); }
    if (!state.trades.length) empty(trades, 'ربات هنوز معامله‌ای ثبت نکرده است.', 7);
    if (!isActive && fetchedAt) $('status').textContent = 'داده در دسترس نیست؛ تا دریافت قیمت معتبر معامله‌ای انجام نمی‌شود.';
  }
  async function refresh() {
    if (loading) return; loading = true;
    try {
      const ids = Object.keys(state.positions), response = await fetch('/api/market' + (ids.length ? '?pairs=' + encodeURIComponent(ids.join(',')) : ''), { cache: 'no-store' });
      if (!response.ok) throw Error(); const data = await response.json();
      if (!Array.isArray(data.pairs) || !data.pairs.length) throw Error();
      pairs = new Map(data.pairs.filter(p => p && typeof p.id === 'string' && Number.isFinite(p.price) && p.price > 0).map(p => [p.id, p]));
      if (!pairs.size) throw Error(); fetchedAt = Date.now(); ok = true;
      $('status').textContent = 'DexScreener · دریافت: ' + new Date(fetchedAt).toLocaleTimeString('fa-IR');
      if (running) { Paper.step(state, [...pairs.values()], fetchedAt); save(); }
    } catch { ok = false; $('status').textContent = 'دریافت قیمت ناموفق بود؛ معاملات تا دریافت داده معتبر متوقف‌اند.'; }
    finally { loading = false; render(); }
  }
  $('start').addEventListener('click', () => { running = true; $('message').textContent = 'ربات روشن است؛ معامله بعد از دریافت داده معتبر انجام می‌شود.'; render(); refresh(); });
  $('pause').addEventListener('click', () => { running = false; $('message').textContent = 'ربات متوقف شد؛ موقعیت‌ها تا راه‌اندازی مجدد بسته نمی‌شوند.'; render(); });
  $('reset').addEventListener('click', () => { if (confirm('ربات متوقف و تمام معاملات و حساب مجازی پاک شود؟')) { running = false; state = Paper.fresh(); save(); $('message').textContent = 'حساب بازنشانی شد.'; render(); } });
  $('refresh').addEventListener('click', refresh);
  render(); refresh(); setInterval(refresh, 30000); setInterval(render, 5000);
})();
