import type { NextRequest } from 'next/server';
import { adminEnabled, checkPassword, hasSession, newSession, sessionAge, sessionCookie } from '@/lib/auth';
import { saveProduct, updateOrder } from '@/lib/operations';
import { body, json, limit, requireOrigin, respondError } from '@/lib/http';
import { demoMode } from '@/lib/site';
import { editStore, StoreError } from '@/lib/store';
import { object } from '@/lib/validation';

export const runtime = 'nodejs';

export async function POST(request: NextRequest, { params }: { params: Promise<{ action: string }> }) {
  try {
    requireOrigin(request);
    const { action } = await params;
    const demo = demoMode();
    const secure = Boolean(process.env.VERCEL) || request.nextUrl.protocol === 'https:' || request.headers.get('x-forwarded-proto')?.split(',')[0].trim() === 'https';
    const cookie = { httpOnly: true, secure, path: '/', sameSite: demo && secure ? 'none' as const : 'strict' as const, partitioned: demo && secure };
    if (action === 'login') {
      if (!adminEnabled()) throw new StoreError('ورود مدیریت هنوز راه‌اندازی نشده است.', 503);
      limit(request, 'admin-login', 10, 5 * 60_000);
      const data = object(await body(request));
      if (!(demo && data.demo === true) && !checkPassword(data.password)) throw new StoreError('رمز مدیریت درست نیست.', 401);
      const response = json({ ok: true });
      response.cookies.set(sessionCookie, newSession(), { ...cookie, maxAge: sessionAge });
      return response;
    }
    if (action === 'logout') {
      const response = json({ ok: true });
      response.cookies.set(sessionCookie, '', { ...cookie, maxAge: 0 });
      return response;
    }
    if (!(await hasSession())) throw new StoreError('ابتدا وارد پنل مدیریت شوید.', 401);
    const data = object(await body(request));
    if (action === 'products') {
      await editStore((state) => saveProduct(state, data));
      return json({ ok: true });
    }
    if (action === 'orders') {
      await editStore((state) => updateOrder(state, data));
      return json({ ok: true });
    }
    throw new StoreError('مسیر پیدا نشد.', 404);
  } catch (error) { return respondError(error); }
}
