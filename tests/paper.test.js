'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const Paper = require('../public/paper.js');
const pair = { id: 'abc', token: 'mint', symbol: 'TEST', price: 2, liquidity: 10000, volume24h:10000, trades5m:20, change5m:3 };
test('entries use market filters and enforce three positions', () => {
  const s = Paper.fresh(); const candidates = Array.from({length: 5}, (_, i) => ({...pair,id:String(i),token:String(i)}));
  Paper.step(s,candidates, 100); assert.equal(Object.keys(s.positions).length,3); assert.equal(s.trades.length,3);
  assert.equal(Paper.eligible({...pair,liquidity:null}),false); assert.equal(Paper.eligible({...pair,change5m:99}),false); assert.equal(Paper.eligible({...pair,trades5m:19}),false);
});
test('take profit records a net closed-trade win and fee on both sides', () => {
  const s = Paper.fresh(); Paper.step(s,[pair],100); assert.equal(s.cash,9500); assert.equal(s.wins,0);
  Paper.step(s,[{...pair,price:2.4}],200); const expected = 500 * .997 * 1.2 * .997 - 500;
  assert.equal(s.wins,1); assert.equal(s.losses,0); assert.equal(Object.keys(s.positions).length,0); assert.ok(Math.abs(s.realized-expected)<1e-7);
  assert.equal(s.trades[0].reason,'حد سود');
});
test('stop loss, cooldown, and missing prices never trigger phantom exit', () => {
  const s = Paper.fresh(); Paper.step(s,[pair],100); Paper.step(s,[],4000000); assert.equal(Object.keys(s.positions).length,1);
  Paper.step(s,[{...pair,price:1.7}],4000001); assert.equal(s.losses,1); assert.equal(Object.keys(s.positions).length,0); assert.equal(s.trades[0].reason,'حد ضرر');
  Paper.step(s,[pair],4000002); assert.equal(Object.keys(s.positions).length,0); Paper.step(s,[pair],7600002); assert.equal(Object.keys(s.positions).length,1);
});
test('maximum time closes a position on a valid price even if entry filter no longer matches', () => {
  const s = Paper.fresh(); Paper.step(s,[pair],10); Paper.step(s,[{...pair,change5m:null}],3600010); assert.equal(s.losses,1); assert.equal(s.trades[0].reason,'پایان زمان');
});
test('reject duplicate token and enforce six entries per hour', () => {
  const s = Paper.fresh(); s.entryTimes = [1,2,3,4,5,6]; Paper.step(s,[pair],100); assert.equal(Object.keys(s.positions).length,0);
  s.entryTimes = []; Paper.step(s,[pair,{...pair,id:'other'}],100); assert.equal(Object.keys(s.positions).length,1);
});
