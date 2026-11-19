import 'server-only';
import { createHash, createHmac, randomBytes, timingSafeEqual } from 'node:crypto';
import { cookies } from 'next/headers';
import { demoMode, persistentStorage } from './site';

export const sessionCookie = 'ninik_admin';
export const sessionAge = 8 * 60 * 60;
const runtime = globalThis as typeof globalThis & { ninikDemoSecret?: string };
const digest = (value: string) => createHash('sha256').update(value).digest();

function secret(): string | undefined {
  const key = process.env.NINIK_SESSION_SECRET;
  if (demoMode()) return key || (runtime.ninikDemoSecret ??= randomBytes(32).toString('hex'));
  return key && key.length >= 32 && (process.env.NINIK_ADMIN_PASSWORD?.length ?? 0) >= 12 && persistentStorage()
    ? key + ':' + digest(process.env.NINIK_ADMIN_PASSWORD!).toString('hex')
    : undefined;
}

export const adminEnabled = () => Boolean(secret());

export function checkPassword(password: unknown) {
  const defined = process.env.NINIK_ADMIN_PASSWORD;
  return typeof password === 'string' && password.length <= 512 && defined && defined.length >= 12 && timingSafeEqual(digest(password), digest(defined));
}

const sign = (message: string, key: string) => createHmac('sha256', key).update(message).digest('base64url');

export function newSession() {
  const key = secret();
  if (!key) throw new Error('Admin is not configured');
  const payload = `${Math.floor(Date.now() / 1000) + sessionAge}.${randomBytes(24).toString('base64url')}`;
  return `${payload}.${sign(payload, key)}`;
}

export async function hasSession() {
  const key = secret();
  if (!key) return false;
  const token = (await cookies()).get(sessionCookie)?.value;
  if (!token || !/^\d{10,13}\.[A-Za-z0-9_-]{32}\.[A-Za-z0-9_-]{43}$/.test(token)) return false;
  const [exp, nonce, signature] = token.split('.');
  return Number(exp) > Math.floor(Date.now() / 1000)
    && timingSafeEqual(Buffer.from(signature), Buffer.from(sign(`${exp}.${nonce}`, key)));
}
