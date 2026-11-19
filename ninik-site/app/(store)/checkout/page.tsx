import type { Metadata } from 'next';
import { Checkout } from '@/components/checkout';
import { browserDemoMode, demoMode, ordersEnabled } from '@/lib/site';

export const metadata: Metadata = { title: 'ثبت سفارش', robots: { index: false, follow: false } };
export default function CheckoutPage() { return <Checkout enabled={ordersEnabled() || browserDemoMode()} demo={demoMode() || browserDemoMode()} />; }
