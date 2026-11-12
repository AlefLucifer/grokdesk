'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const key = 'grokdesk-paper-v1';
  let state;
  try { state = JSON.parse(localStorage.getItem(key)) || Paper.fresh(); if (!Number.isFinite(state.cash) || !state.positions || !Array.isArray(state.trades)) throw Error(); }
  catch { state = Paper.fresh(); }
  let pairs = new Map(), fetchedAt = 0, ok = false, loading = false;
  const money = value => '$' + value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const price = value => '$' + value.toLocaleString('en-US', { maximumSignificantDigits: 6 });
  const active = () => ok && Date.now() - fetchedAt < 90000;
  function save() { try { localStorage.setItem(key, JSON.stringify(state)); } catch { $('message').textContent = 'ذخیره در مرورگر ممکن نیست؛ داده‌ها بعد از بستن صفحه ممکن است از بین بروند.'; } }
  function cell(row, text, className) { const td = document.createElement('td'); td.textContent = text; if (className) td.className = className; row.appendChild(td); return td; }
  function action(row, label, fn, disabled) { const td = document.createElement('td'), btn = document.createElement('button'); btn.textContent = label; btn.disabled = disabled; btn.addEventListener('click', fn); td.appendChild(btn); row.appendChild(td); }
  function render() {
    const isActive = active();
    $('cash').textContent = money(state.cash); $('count').textContent = Object.keys(state.positions).length;
    const selected = $('pair').value;
    $('pair').replaceChildren(new Option('انتخاب کنید', ''));
    for (const p of pairs.values()) $('pair').add(new Option(`${p.symbol} / ${p.quote} · ${p.dex} · ${p.id.slice(0, 6)}`, p.id));
    if (pairs.has(selected)) $('pair').value = selected;
    $('buy').disabled = !isActive || !$('pair').value;
    const tbody = $('markets'); tbody.replaceChildren();
    for (const p of pairs.values()) {
      const row = tbody.insertRow(); const label = cell(row, p.symbol + ' / ' + p.quote); const small = document.createElement('small'); small.textContent = p.dex + ' · ' + p.id.slice(0, 8); label.appendChild(small);
      cell(row, price(p.price), 'ltr'); cell(row, p.change24h == null ? '—' : p.change24h.toFixed(2) + '%', p.change24h == null ? '' : p.change24h >= 0 ? 'up ltr' : 'down ltr'); cell(row, p.liquidity == null ? '—' : money(p.liquidity), 'ltr');
      action(row, 'انتخاب', () => { $('pair').value = p.id; $('buy').disabled = !active(); }, !isActive);
    }
    const positions = $('positions'); positions.replaceChildren(); let value = 0, complete = isActive;
    for (const pos of Object.values(state.positions)) {
      const p = pairs.get(pos.id), row = positions.insertRow(); cell(row, pos.symbol + ' · ' + pos.id.slice(0, 8)); cell(row, pos.quantity.toLocaleString('en-US', { maximumSignificantDigits: 7 }), 'ltr'); cell(row, money(pos.cost), 'ltr');
      if (p && isActive) { const v = pos.quantity * p.price * (1 - Paper.FEE); value += v; cell(row, money(v), 'ltr'); cell(row, money(v - pos.cost), v >= pos.cost ? 'up ltr' : 'down ltr'); }
      else { complete = false; cell(row, 'قیمت موجود نیست'); cell(row, '—'); }
      action(row, 'فروش کامل', () => { if (!active() || !pairs.has(pos.id)) return; try { Paper.sell(state, pairs.get(pos.id)); save(); render(); $('message').textContent = 'فروش مجازی ثبت شد.'; } catch(e) { $('message').textContent = e.message; } }, !isActive || !p);
    }
    if (!Object.keys(state.positions).length) { const row = positions.insertRow(); const td = cell(row, 'هنوز موقعیت بازی ندارید.'); td.colSpan = 6; }
    $('equity').textContent = complete ? money(state.cash + value) : 'نامشخص'; $('pnl').textContent = complete ? money(state.cash + value - Paper.INITIAL) : 'نامشخص';
    const trades = $('trades'); trades.replaceChildren();
    for (const t of state.trades) { const row = trades.insertRow(); cell(row, t.side); cell(row, t.symbol); cell(row, money(t.dollars), 'ltr'); cell(row, price(t.price), 'ltr'); cell(row, new Date(t.at).toLocaleString('fa-IR')); }
    if (!state.trades.length) { const row = trades.insertRow(); const td = cell(row, 'هنوز معامله‌ای ثبت نشده است.'); td.colSpan = 5; }
    if (!isActive && fetchedAt) $('status').textContent = 'قیمت‌ها در دسترس یا به‌روز نیستند؛ معامله غیرفعال است.';
  }
  async function refresh() {
    if (loading) return; loading = true; $('refresh').disabled = true;
    try {
      const ids = Object.keys(state.positions); const response = await fetch('/api/market' + (ids.length ? '?pairs=' + encodeURIComponent(ids.join(',')) : ''), { cache: 'no-store' });
      if (!response.ok) throw Error(); const data = await response.json();
      if (!Array.isArray(data.pairs) || !data.pairs.length) throw Error();
      pairs = new Map(data.pairs.filter(p => p && typeof p.id === 'string' && Number.isFinite(p.price) && p.price > 0).map(p => [p.id, p]));
      if (!pairs.size) throw Error(); fetchedAt = Date.now(); ok = true;
      $('status').textContent = 'داده DexScreener · دریافت: ' + new Date(fetchedAt).toLocaleTimeString('fa-IR');
    } catch { ok = false; $('status').textContent = 'دریافت قیمت ناموفق بود؛ معامله غیرفعال است. دوباره تلاش کنید.'; }
    finally { loading = false; $('refresh').disabled = false; render(); }
  }
  $('pair').addEventListener('change', render);
  $('buy').addEventListener('click', () => { if (!active()) return; try { Paper.buy(state, pairs.get($('pair').value), Number($('amount').value)); save(); render(); $('message').textContent = 'خرید مجازی ثبت شد.'; } catch(e) { $('message').textContent = e.message; } });
  $('reset').addEventListener('click', () => { if (confirm('حساب مجازی و تاریخچه آن پاک و موجودی به ۱۰٬۰۰۰ دلار برگردد؟')) { state = Paper.fresh(); save(); render(); } });
  $('refresh').addEventListener('click', refresh);
  render(); refresh(); setInterval(refresh, 30000); setInterval(render, 5000);
})();
