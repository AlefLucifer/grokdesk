import assert from 'node:assert/strict';
import { once } from 'node:events';
import { mkdtemp, rm } from 'node:fs/promises';
import { createServer } from 'node:net';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { randomBytes } from 'node:crypto';
import { spawn } from 'node:child_process';
import { setTimeout as sleep } from 'node:timers/promises';
import { test } from 'node:test';

async function launch(t, extra) {
  const socket = createServer();
  socket.listen(0, '127.0.0.1');
  await once(socket, 'listening');
  const { port } = socket.address();
  await new Promise((resolve) => socket.close(resolve));
  const base = `http://127.0.0.1:${port}`;
  const app = spawn(process.execPath, ['node_modules/next/dist/bin/next', 'start', '--hostname', '127.0.0.1', '--port', String(port)], {
    env: { ...process.env, NEXT_TELEMETRY_DISABLED: '1', VERCEL: '', VERCEL_ENV: '', DATABASE_URL: '', SITE_URL: '', NINIK_DEMO_MODE: '', NINIK_BROWSER_DEMO: '', NINIK_INDEX_BROWSER_DEMO: '', NINIK_DATA_DIR: '',
      NINIK_SESSION_SECRET: '', NINIK_ADMIN_PASSWORD: '', NINIK_ENABLE_ORDERS: '', GOOGLE_SITE_VERIFICATION: '', ...extra },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  let log = '';
  for (const stream of [app.stdout, app.stderr]) stream.on('data', (data) => { log = (log + data).slice(-4000); });
  t.after(async () => {
    if (app.exitCode === null && app.signalCode === null) {
      const done = once(app, 'exit'); app.kill(); await done;
    }
  });
  for (let attempt = 0; attempt < 60; attempt++) {
    if (app.exitCode !== null) throw new Error(log);
    try { if ((await fetch(base + '/robots.txt', { signal: AbortSignal.timeout(700) })).ok) return base; } catch {}
    await sleep(100);
  }
  throw new Error('Next.js did not start. Run npm run build first.\n' + log);
}

const post = (base, path, body, headers = {}) => fetch(`${base}${path}`, {
  method: 'POST', headers: { Origin: base, 'Content-Type': 'application/json', ...headers }, body: JSON.stringify(body),
});

test('demo storefront, authenticated management, and concurrent inventory', { timeout: 30_000 }, async (t) => {
  const directory = await mkdtemp(join(tmpdir(), 'ninik-test-'));
  const base = await launch(t, { NINIK_DEMO_MODE: '1', NINIK_DATA_DIR: directory, NINIK_SESSION_SECRET: randomBytes(32).toString('hex') });
  t.after(() => rm(directory, { force: true, recursive: true }));
  const home = await fetch(base);
  assert.equal(home.status, 200);
  assert.match(await home.text(), /نینیک سایت/);
  assert.match(await (await fetch(base + '/robots.txt')).text(), /Disallow: \/\s*$/);
  const loginPage = await fetch(base + '/admin');
  assert.match(loginPage.headers.get('x-robots-tag'), /noindex/);
  assert.match(await loginPage.text(), /ورود آزمایشی/);
  assert.equal((await post(base, '/api/admin/products', {})).status, 401);
  assert.equal((await post(base, '/api/admin/login', { demo: true }, { Origin: 'https://other.example.test' })).status, 403);
  const login = await post(base, '/api/admin/login', { demo: true });
  assert.equal(login.status, 200);
  const setCookie = login.headers.get('set-cookie');
  assert.match(setCookie, /HttpOnly/);
  const auth = { Cookie: setCookie.split(';')[0] };
  assert.match(await (await fetch(base + '/admin', { headers: auth })).text(), /نمای کلی فروشگاه/);

  const product = { slug: 'test-bear', name: 'خرس آزمایشی', description: 'توضیحات نمونه برای بررسی کاتالوگ', age: '',
    category: 'toys', price: 250000, oldPrice: null, stock: 1, image: '/images/teddy.webp', badge: '', active: true };
  assert.equal((await post(base, '/api/admin/products', { operation: 'create', product }, auth)).status, 200);
  assert.match(await (await fetch(base + '/product/test-bear')).text(), /خرس آزمایشی/);
  assert.equal((await post(base, '/api/orders', { lines: [{ slug: product.slug, quantity: 1, price: 1 }] })).status, 409);
  const payload = { lines: [{ slug: product.slug, quantity: 1, price: product.price }], customer: { name: 'DO_NOT_PERSIST_DEMO_INPUT' } };
  const attempts = await Promise.all([post(base, '/api/orders', payload), post(base, '/api/orders', payload)]);
  assert.deepEqual(attempts.map((res) => res.status).sort(), [201, 409]);
  const saved = await attempts.find((res) => res.status === 201).json();
  assert.match(saved.id, /^NNK-[A-F0-9]{14}$/);
  assert.equal(saved.total, 335000);
  const admin = await (await fetch(base + '/admin', { headers: auth })).text();
  assert.match(admin, new RegExp(saved.id));
  assert.match(admin, /خریدار نمونه/);
  assert.doesNotMatch(admin, /DO_NOT_PERSIST_DEMO_INPUT/);
  assert.doesNotMatch(await (await fetch(base + '/admin')).text(), new RegExp(saved.id));
  assert.equal((await post(base, '/api/admin/orders', { id: saved.id, status: 'cancelled' }, auth)).status, 200);
  assert.equal((await post(base, '/api/admin/orders', { id: saved.id, status: 'cancelled' }, auth)).status, 409);
  assert.equal((await post(base, '/api/orders', payload)).status, 201);
  assert.equal((await post(base, '/api/admin/products', { operation: 'update', product: { ...product, active: false, stock: 0 } }, auth)).status, 200);
  assert.equal((await fetch(base + '/product/test-bear')).status, 404);
  assert.match((await post(base, '/api/admin/logout', {}, auth)).headers.get('set-cookie'), /Max-Age=0/);
});

test('public metadata with a canonical URL and safe defaults without storage', { timeout: 20_000 }, async (t) => {
  const origin = 'https://ninik.example.test';
  const base = await launch(t, { SITE_URL: origin, VERCEL: '1', NINIK_DEMO_MODE: '1', GOOGLE_SITE_VERIFICATION: 'fixture-only' });
  const robots = await (await fetch(base + '/robots.txt')).text();
  assert.match(robots, /Disallow: \/api\//);
  assert.ok(robots.includes(`Sitemap: ${origin}/sitemap.xml`));
  const sitemap = await (await fetch(base + '/sitemap.xml')).text();
  assert.ok(sitemap.includes(`${origin}/product/fluffy-teddy`));
  assert.ok(!sitemap.includes('/checkout') && !sitemap.includes('/admin'));
  const page = await (await fetch(base + '/product/fluffy-teddy')).text();
  assert.ok(page.includes(`rel="canonical" href="${origin}/product/fluffy-teddy"`));
  assert.doesNotMatch(page, /"@type":"Offer"/);
  assert.match(page, /name="google-site-verification" content="fixture-only"/);
  const admin = await (await fetch(base + '/admin')).text();
  assert.doesNotMatch(admin, /ورود آزمایشی/);
  assert.equal((await post(base, '/api/orders', {})).status, 503);
  assert.equal((await post(base, '/api/admin/login', { demo: true })).status, 503);
});


test('browser demo is public but cannot write to the Vercel server', { timeout: 20_000 }, async (t) => {
  const base = await launch(t, { SITE_URL: 'https://ninik.example.test', VERCEL: '1', NINIK_BROWSER_DEMO: '1' });
  assert.match(await (await fetch(base)).text(), /محصولات و قیمت‌ها نمونه‌اند/);
  assert.match(await (await fetch(base + '/admin')).text(), /ورود آزمایشی/);
  assert.match(await (await fetch(base + '/robots.txt')).text(), /Disallow: \/\s*$/);
  assert.equal((await fetch(base + '/sitemap.xml')).status, 404);
  assert.equal((await post(base, '/api/admin/login', { demo: true })).status, 503);
  assert.equal((await post(base, '/api/orders', {})).status, 503);
});


test('online demo sitemap advertises only canonical, public pages', { timeout: 30_000 }, async (t) => {
  const origin = 'https://ninik.example.test';
  const base = await launch(t, {
    SITE_URL: origin, VERCEL: '1', VERCEL_ENV: 'production', NINIK_BROWSER_DEMO: '1', NINIK_INDEX_BROWSER_DEMO: '1', GOOGLE_SITE_VERIFICATION: 'fixture-only',
  });
  const response = await fetch(base + '/sitemap.xml');
  assert.equal(response.status, 200);
  assert.match(response.headers.get('content-type'), /application\/xml/);
  const xml = await response.text();
  const locations = Array.from(xml.matchAll(/<loc>([^<]+)<\/loc>/g), ([, url]) => url);
  assert.equal(new Set(locations).size, 16);
  assert.equal(locations.filter((url) => url.startsWith(origin + '/category/')).length, 5);
  assert.equal(locations.filter((url) => url.startsWith(origin + '/product/')).length, 8);
  assert.ok(locations.includes(origin + '/') && locations.includes(origin + '/shop') && locations.includes(origin + '/guide'));
  for (const location of locations) {
    const url = new URL(location);
    assert.equal(url.origin, origin);
    assert.equal(url.search, '');
    assert.equal(url.hash, '');
    assert.doesNotMatch(url.pathname, /^\/(?:admin|checkout|api)\b/);
    const page = await fetch(base + new URL(location).pathname, { headers: { 'User-Agent': 'Googlebot' }, redirect: 'error' });
    assert.equal(page.status, 200, location);
    const html = await page.text();
    const head = html.match(/<head>(.*?)<\/head>/s)?.[1] ?? '';
    const canonical = head.match(/<link rel="canonical" href="([^"]+)"/)?.[1];
    assert.ok(canonical, location + ' canonical exists in head');
    assert.equal(new URL(canonical).href, location);
    assert.match(head, /name="robots" content="index, follow"/);
    assert.doesNotMatch(html, /"@type":"Offer"/);
  }
  const home = await (await fetch(base, { headers: { 'User-Agent': 'Google-Site-Verification/1.0' } })).text();
  assert.match(home.match(/<head>(.*?)<\/head>/s)?.[1] ?? '', /name="google-site-verification" content="fixture-only"/);
  assert.match(home, /"@type":"WebSite"/);
  const category = await (await fetch(base + '/category/toys')).text();
  assert.match(category, /"@type":"BreadcrumbList"/);
  assert.ok(category.includes('/product/fluffy-teddy'));
  const redirect = await fetch(base + '/shop?category=toys', { redirect: 'manual' });
  assert.equal(redirect.status, 308);
  assert.equal(redirect.headers.get('location'), '/category/toys');
  for (const path of ['/admin', '/checkout', '/shop?q=toy', '/product/browser-only-slug']) {
    const page = await fetch(base + path);
    assert.match(await page.text(), /name="robots" content="noindex/);
    if (path === '/admin' || path === '/checkout') assert.match(page.headers.get('x-robots-tag'), /noindex/);
  }
});

test('preview never advertises an index even if production flags are present', { timeout: 20_000 }, async (t) => {
  const base = await launch(t, { SITE_URL: 'https://ninik.example.test', VERCEL: '1', VERCEL_ENV: 'preview', NINIK_BROWSER_DEMO: '1', NINIK_INDEX_BROWSER_DEMO: '1' });
  assert.match(await (await fetch(base + '/robots.txt')).text(), /Disallow: \/\s*$/);
  assert.equal((await fetch(base + '/sitemap.xml')).status, 404);
});
