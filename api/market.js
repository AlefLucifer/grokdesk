'use strict';

// A fixed, read-only upstream. Never accepts a URL or credentials from clients.
const BASE = 'https://api.dexscreener.com';
const PAIR_ID = /^[A-Za-z0-9]{20,64}$/;

async function requestJson(url) {
  const response = await fetch(url, { signal: AbortSignal.timeout(10000), headers: { Accept: 'application/json' } });
  if (!response.ok) throw new Error('Market data provider returned an error');
  return response.json();
}

function cleanPair(pair) {
  const price = Number(pair.priceUsd);
  if (pair.chainId !== 'solana' || !PAIR_ID.test(pair.pairAddress || '') || !Number.isFinite(price) || price <= 0) return null;
  return {
    id: pair.pairAddress,
    symbol: String(pair.baseToken?.symbol || '?').slice(0, 30),
    name: String(pair.baseToken?.name || '?').slice(0, 80),
    token: String(pair.baseToken?.address || ''),
    quote: String(pair.quoteToken?.symbol || '?').slice(0, 30),
    dex: String(pair.dexId || '?').slice(0, 30),
    price,
    change24h: Number.isFinite(Number(pair.priceChange?.h24)) && pair.priceChange?.h24 != null ? Number(pair.priceChange.h24) : null,
    liquidity: Number.isFinite(Number(pair.liquidity?.usd)) && pair.liquidity?.usd != null ? Number(pair.liquidity.usd) : null,
    url: /^https:\/\/dexscreener\.com\/solana\/[a-zA-Z0-9]+$/.test(pair.url || '') ? pair.url : null,
  };
}

module.exports = async function handler(req, res) {
  if (req.method !== 'GET') return res.status(405).json({ error: 'Method not allowed' });
  const raw = typeof req.query.pairs === 'string' ? req.query.pairs : '';
  const ids = raw ? raw.split(',') : [];
  if (ids.length > 20 || ids.some(id => !PAIR_ID.test(id))) return res.status(400).json({ error: 'Invalid pair addresses' });
  try {
    const [profiles, held] = await Promise.all([
      requestJson(`${BASE}/token-profiles/latest/v1`),
      ids.length ? requestJson(`${BASE}/latest/dex/pairs/solana/${ids.join(',')}`) : Promise.resolve({ pairs: [] }),
    ]);
    if (!Array.isArray(profiles)) throw new Error('Market data unavailable');
    const tokens = [...new Set(profiles.filter(p => p.chainId === 'solana' && PAIR_ID.test(p.tokenAddress || '')).map(p => p.tokenAddress))].slice(0, 30);
    if (!tokens.length) throw new Error('Market data unavailable');
    const tokenPairs = await requestJson(`${BASE}/tokens/v1/solana/${tokens.join(',')}`);
    if (!Array.isArray(tokenPairs)) throw new Error('Market data unavailable');
    const matches = tokenPairs.filter(p => tokens.includes(p.baseToken?.address)).map(cleanPair).filter(Boolean).sort((a, b) => (b.liquidity || 0) - (a.liquidity || 0));
    const byId = new Map(matches.slice(0, 30).map(pair => [pair.id, pair]));
    (held.pairs || []).map(cleanPair).filter(Boolean).forEach(pair => byId.set(pair.id, pair));
    res.setHeader('Cache-Control', 'no-store');
    return res.status(200).json({ pairs: [...byId.values()], fetchedAt: new Date().toISOString(), source: 'DexScreener' });
  } catch (err) {
    return res.status(502).json({ error: 'Market data temporarily unavailable' });
  }
};
