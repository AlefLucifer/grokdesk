'use strict';
const { test, afterEach } = require('node:test');
const assert = require('node:assert/strict');
const handler = require('../api/market');
const original = global.fetch;
afterEach(() => { global.fetch = original; });
function res() { return { code: 200, headers: {}, setHeader(k,v){this.headers[k]=v}, status(n){this.code=n;return this}, json(data){this.data=data;return this} }; }
const id = 'A'.repeat(32);
const valid = { chainId: 'solana', pairAddress: id, baseToken: {symbol:'X',address:'C'.repeat(32)}, quoteToken: {symbol:'SOL'}, priceUsd:'1.5', liquidity:{usd:1000}, priceChange:{h24:1}, dexId:'raydium' };
test('returns sanitized Solana quotes and held pairs', async () => {
  global.fetch = async url => ({ ok:true, json:async()=> url.includes('token-profiles') ? [{chainId:'solana', tokenAddress:'C'.repeat(32)}] : url.includes('/tokens/v1/') ? [valid, {...valid,chainId:'ethereum'}] : {pairs:[{...valid, pairAddress:'B'.repeat(32)}]} });
  const r = res(); await handler({method:'GET', query:{pairs:'B'.repeat(32)}}, r); assert.equal(r.code,200); assert.equal(r.data.pairs.length,2); assert.equal(r.data.pairs[0].price,1.5); assert.equal(r.headers['Cache-Control'],'no-store');
});
test('rejects invalid pair identifiers and provider errors', async () => {
  const r = res(); await handler({method:'GET',query:{pairs:'https://evil.test'}},r); assert.equal(r.code,400);
  global.fetch = async () => { throw Error('offline'); }; const r2 = res(); await handler({method:'GET',query:{}},r2); assert.equal(r2.code,502);
});
