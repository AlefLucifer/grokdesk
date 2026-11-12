(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.Paper = factory();
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const FEE = 0.003;
  const INITIAL = 10000;
  const fresh = () => ({ cash: INITIAL, positions: {}, trades: [] });
  function buy(state, pair, dollars) {
    if (!pair || !Number.isFinite(pair.price) || pair.price <= 0 || !Number.isFinite(dollars) || dollars <= 0 || dollars > state.cash + 1e-8) throw Error('مبلغ یا قیمت معتبر نیست، یا موجودی کافی ندارید.');
    if (!state.positions[pair.id] && Object.keys(state.positions).length >= 20) throw Error('حداکثر ۲۰ موقعیت باز مجاز است.');
    const quantity = dollars * (1 - FEE) / pair.price;
    const position = state.positions[pair.id] || { id: pair.id, symbol: pair.symbol, quantity: 0, cost: 0 };
    position.quantity += quantity;
    position.cost += dollars;
    state.positions[pair.id] = position;
    state.cash -= dollars;
    state.trades.unshift({ side: 'خرید', symbol: pair.symbol, dollars, price: pair.price, at: new Date().toISOString() });
    state.trades = state.trades.slice(0, 50);
  }
  function sell(state, pair) {
    const position = pair && state.positions[pair.id];
    if (!position || !Number.isFinite(pair.price) || pair.price <= 0) throw Error('قیمت معتبر برای فروش موجود نیست.');
    const proceeds = position.quantity * pair.price * (1 - FEE);
    state.cash += proceeds;
    delete state.positions[pair.id];
    state.trades.unshift({ side: 'فروش', symbol: position.symbol, dollars: proceeds, price: pair.price, at: new Date().toISOString() });
    state.trades = state.trades.slice(0, 50);
  }
  return { fresh, buy, sell, FEE, INITIAL };
});
