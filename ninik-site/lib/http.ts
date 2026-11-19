import 'server-only';
import { NextRequest, NextResponse } from 'next/server';
import { StoreError } from './store';

const headers = { 'Cache-Control': 'private, no-store', 'X-Robots-Tag': 'noindex, nofollow' };
export const json = (value: unknown, status = 200) => NextResponse.json(value, { status, headers });

export function respondError(error: unknown) {
  if (error instanceof StoreError) return json({ error: error.message }, error.status);
  // Do not expose URLs, credentials, customer data or database error details.
  console.error('Ninik API: unexpected server error.', error instanceof Error ? error.name : 'UnknownError');
  return json({ error: 'مشکلی پیش آمد؛ لطفاً دوباره تلاش کنید.' }, 500);
}

export function requireOrigin(request: NextRequest) {
  const origin = request.headers.get('origin');
  let host: string;
  try {
    const url = new URL(origin ?? '');
    if (!['http:', 'https:'].includes(url.protocol) || request.headers.get('sec-fetch-site') === 'cross-site') throw new Error();
    host = url.host;
  } catch { throw new StoreError('درخواست از نشانی معتبر ارسال نشده است.', 403); }
  const hosts = [request.nextUrl.host, request.headers.get('host'), request.headers.get('x-forwarded-host')?.split(',')[0].trim()];
  if (!hosts.includes(host)) throw new StoreError('درخواست از نشانی معتبر ارسال نشده است.', 403);
}

export async function body(request: NextRequest) {
  if (request.headers.get('content-type')?.split(';')[0].trim() !== 'application/json' || !request.body) {
    throw new StoreError('قالب درخواست معتبر نیست.', 415);
  }
  const limit = 16000;
  if (Number(request.headers.get('content-length')) > limit) throw new StoreError('حجم درخواست بیش از حد مجاز است.', 413);
  const stream = request.body.getReader();
  const decoder = new TextDecoder('utf-8', { fatal: true });
  let count = 0;
  let raw = '';
  try {
    for (;;) {
      const { value, done } = await stream.read();
      if (done) break;
      count += value.byteLength;
      if (count > limit) {
        await stream.cancel();
        throw new StoreError('حجم درخواست بیش از حد مجاز است.', 413);
      }
      raw += decoder.decode(value, { stream: true });
    }
    return JSON.parse(raw + decoder.decode()) as unknown;
  } catch (error) {
    if (error instanceof StoreError) throw error;
    throw new StoreError('اطلاعات ارسال‌شده معتبر نیست.');
  }
}

type Window = { count: number; ends: number };
const runtime = globalThis as typeof globalThis & { ninikRate?: Map<string, Window> };

export function limit(request: NextRequest, action: string, maximum: number, duration: number) {
  const buckets = runtime.ninikRate ??= new Map();
  const addr = (request.headers.get('x-vercel-forwarded-for') || request.headers.get('x-forwarded-for') || '').split(',').at(-1)?.trim().slice(0, 64) || 'local';
  const now = Date.now();
  if (buckets.size >= 1024) {
    for (const [key, bucket] of buckets) if (bucket.ends <= now) buckets.delete(key);
    if (buckets.size >= 1024 && !buckets.has(`${action}:${addr}`)) throw new StoreError('درخواست‌ها زیاد است. کمی دیگر تلاش کنید.', 429);
  }
  const key = `${action}:${addr}`;
  const previous = buckets.get(key);
  const window = previous && previous.ends > now ? previous : { count: 0, ends: now + duration };
  if (++window.count > maximum) throw new StoreError('درخواست‌ها زیاد است. کمی دیگر تلاش کنید.', 429);
  buckets.set(key, window);
}
