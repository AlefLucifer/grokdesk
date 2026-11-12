'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const Paper = require('../public/paper.js');
const pair = { id: 'abc', symbol: 'TEST', price: 2 };
test('buy and sell apply fees and preserve cash accounting', () => {
  const s = Paper.fresh(); Paper.buy(s, pair, 100);
  assert.equal(s.cash, 9900); assert.equal(s.positions.abc.quantity, 49.85); assert.equal(s.positions.abc.cost, 100);
  Paper.sell(s, pair); assert.ok(Math.abs(s.cash - (9900 + 100 * .997 * .997)) < 1e-9); assert.equal(Object.keys(s.positions).length, 0); assert.equal(s.trades.length, 2);
});
test('reject invalid sizes, overdraws and missing price', () => {
  const s = Paper.fresh(); for (const x of [0, -1, NaN, Infinity, 10001]) assert.throws(() => Paper.buy(s, pair, x));
  assert.throws(() => Paper.buy(s, { ...pair, price: 0 }, 10)); assert.throws(() => Paper.sell(s, pair)); assert.equal(s.cash, 10000);
});
test('maximum of 20 open positions', () => {
  const s = Paper.fresh(); for (let i = 0; i < 20; i++) Paper.buy(s, { ...pair, id: String(i) }, 1);
  assert.throws(() => Paper.buy(s, { ...pair, id: 'other' }, 1)); Paper.buy(s, { ...pair, id: '0' }, 1);
});
