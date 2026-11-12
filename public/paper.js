(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.Paper = factory();
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const FEE = 0.003, INITIAL = 10000, HOUR = 3600000;
  const fresh = () => ({ cash: INITIAL, positions: {}, trades: [], wins: 0, losses: 0, flat: 0, realized: 0, entryTimes: [], cooldown: {} });
  function eligible(p) {
    return !!p && typeof p.id === 'string' && typeof p.token === 'string' && p.token.length > 0 &&
      Number.isFinite(p.price) && p.price > 0 && Number.isFinite(p.liquidity) && p.liquidity >= 10000 &&
      Number.isFinite(p.volume24h) && p.volume24h >= 10000 && Number.isFinite(p.trades5m) && p.trades5m >= 20 &&
      Number.isFinite(p.change5m) && p.change5m >= 1 && p.change5m <= 15;
  }
  function step(state, quotes, now) {
    // Called only for a successful, fresh poll while the operator has started the bot.
    if (!Number.isFinite(now)) throw Error('Invalid time');
    const lookup = new Map(quotes.filter(p => p && typeof p.id === 'string' && Number.isFinite(p.price) && p.price > 0).map(p => [p.id, p]));
    for (const pos of Object.values(state.positions)) {
      const p = lookup.get(pos.id);
      if (!p) continue; // Never invent a price for a missing position.
      const change = p.price / pos.entry - 1;
      const reason = change <= -0.10 ? 'حد ضرر' : change >= 0.15 ? 'حد سود' : now - pos.opened >= HOUR ? 'پایان زمان' : null;
      if (!reason) continue;
      const proceeds = pos.quantity * p.price * (1 - FEE), pnl = proceeds - pos.cost;
      state.cash += proceeds; state.realized += pnl;
      if (pnl > 0) state.wins++; else if (pnl < 0) state.losses++; else state.flat++;
      state.trades.unshift({ side: 'فروش', symbol: pos.symbol, id: pos.id, dollars: proceeds, price: p.price, pnl, reason, at: now });
      delete state.positions[pos.id]; state.cooldown[pos.token] = now + HOUR;
    }
    state.entryTimes = state.entryTimes.filter(t => now - t < HOUR);
    for (const [token, expiry] of Object.entries(state.cooldown)) if (expiry <= now) delete state.cooldown[token];
    // Choose the highest reported five-minute trading activity first.
    const ranked = quotes.filter(eligible).sort((a, b) => b.trades5m - a.trades5m);
    for (const p of ranked) {
      if (Object.keys(state.positions).length >= 3 || state.entryTimes.length >= 6 || state.cash < 1) break;
      if (state.positions[p.id] || Object.values(state.positions).some(pos => pos.token === p.token) || state.cooldown[p.token] > now) continue;
      const cost = state.cash * 0.05; // below original RISK's 15% position cap
      state.cash -= cost;
      state.positions[p.id] = { id: p.id, token: p.token, symbol: p.symbol, quantity: cost * (1 - FEE) / p.price, cost, entry: p.price, opened: now };
      state.entryTimes.push(now);
      state.trades.unshift({ side: 'خرید', symbol: p.symbol, id: p.id, dollars: cost, price: p.price, pnl: null, reason: 'عبور از فیلترها', at: now });
    }
    state.trades = state.trades.slice(0, 200);
  }
  return { fresh, eligible, step, FEE, INITIAL };
});
