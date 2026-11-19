import { randomBytes } from 'node:crypto';
import type { NextRequest } from 'next/server';
import { appendOrder } from '@/lib/operations';
import { body, json, limit, requireOrigin, respondError } from '@/lib/http';
import { demoMode, ordersEnabled } from '@/lib/site';
import { editStore, StoreError } from '@/lib/store';
import { object } from '@/lib/validation';

export const runtime = 'nodejs';

export async function POST(request: NextRequest) {
  try {
    requireOrigin(request);
    if (!ordersEnabled()) throw new StoreError('ثبت سفارش هنوز فعال نیست.', 503);
    limit(request, 'checkout', 10, 60_000);
    const data = object(await body(request));
    const id = 'NNK-' + randomBytes(7).toString('hex').toUpperCase();
    const order = await editStore((state) => appendOrder(state, data, id, demoMode()));
    return json({ id: order.id, total: order.total }, 201);
  } catch (error) { return respondError(error); }
}
