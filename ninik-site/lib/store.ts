import 'server-only';
import { cache } from 'react';
import { mkdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { DatabaseSync } from 'node:sqlite';
import postgres from 'postgres';
import { seedProducts } from './catalog';
import type { StoreState } from './operations';
import { StoreError } from './store-error';
import { demoMode, persistentStorage } from './site';

export { StoreError };

type Row = { revision: number; payload: string };
type Driver = { read: () => Promise<Row>; replace: (payload: string, revision: number) => Promise<boolean> };
const initial = (): StoreState => ({ products: seedProducts, orders: [] });

// CAS persists the catalogue and orders in one atomic update so stock cannot be
// oversold by concurrent checkouts. This compact design is for a small storefront.
const schema = 'CREATE TABLE IF NOT EXISTS ninik_store (id INTEGER PRIMARY KEY, revision INTEGER NOT NULL, payload TEXT NOT NULL)';

async function createDriver(): Promise<Driver> {
  if (process.env.DATABASE_URL && !demoMode()) {
    const sql = postgres(process.env.DATABASE_URL, { max: 2, prepare: false, idle_timeout: 20, connect_timeout: 8 });
    try {
      // Serialize first-write schema creation across serverless instances.
      await sql.begin(async (tx) => {
        await tx`SELECT pg_advisory_xact_lock(527144128)`;
        await tx.unsafe(schema);
        await tx`INSERT INTO ninik_store (id, revision, payload) VALUES (1, 0, ${JSON.stringify(initial())}) ON CONFLICT (id) DO NOTHING`;
      });
    } catch (error) {
      await sql.end({ timeout: 1 });
      throw error;
    }
    return {
      read: async () => (await sql<Row[]>`SELECT revision, payload FROM ninik_store WHERE id = 1`)[0],
      replace: async (payload, revision) => (await sql`UPDATE ninik_store SET revision = revision + 1, payload = ${payload} WHERE id = 1 AND revision = ${revision}`).count === 1,
    };
  }
  const directory = resolve(/* turbopackIgnore: true */ process.env.NINIK_DATA_DIR || '.data');
  mkdirSync(directory, { recursive: true, mode: 0o700 });
  const db = new DatabaseSync(resolve(directory, demoMode() ? 'demo.sqlite' : 'store.sqlite'));
  db.exec('PRAGMA busy_timeout = 5000; PRAGMA journal_mode = WAL; ' + schema);
  db.prepare('INSERT INTO ninik_store (id, revision, payload) VALUES (1, 0, ?) ON CONFLICT (id) DO NOTHING').run(JSON.stringify(initial()));
  const load = db.prepare('SELECT revision, payload FROM ninik_store WHERE id = 1');
  const update = db.prepare('UPDATE ninik_store SET revision = revision + 1, payload = ? WHERE id = 1 AND revision = ?');
  return {
    read: async () => load.get() as Row,
    replace: async (payload, revision) => update.run(payload, revision).changes === 1,
  };
}

const instance = globalThis as typeof globalThis & { ninikDriver?: Promise<Driver> };
const driver = () => (instance.ninikDriver ??= createDriver().catch((error) => { delete instance.ninikDriver; throw error; }));

export async function readStore(): Promise<StoreState> {
  if (!persistentStorage()) return initial();
  return JSON.parse((await (await driver()).read()).payload) as StoreState;
}

export const getCatalog = cache(async () => (await readStore()).products.filter((product) => product.active));

export async function editStore<T>(edit: (state: StoreState) => T): Promise<T> {
  if (!persistentStorage()) throw new StoreError('ذخیره‌سازی فروشگاه هنوز راه‌اندازی نشده است.', 503);
  const database = await driver();
  for (let attempt = 0; attempt < 8; attempt += 1) {
    const { payload, revision } = await database.read();
    const state = JSON.parse(payload) as StoreState;
    const result = edit(state);
    if (await database.replace(JSON.stringify(state), revision)) return result;
  }
  throw new StoreError('فروشگاه مشغول است. یک بار دیگر تلاش کنید.', 409);
}
