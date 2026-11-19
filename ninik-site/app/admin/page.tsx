import type { Metadata } from 'next';
import { AdminDashboard, AdminLogin, BrowserAdmin } from '@/components/admin';
import { adminEnabled, hasSession } from '@/lib/auth';
import { browserDemoMode, demoMode } from '@/lib/site';
import { readStore } from '@/lib/store';
import './admin.css';

export const metadata: Metadata = { title: 'پنل مدیریت', robots: { index: false, follow: false } };

export default async function AdminPage() {
  if (browserDemoMode()) return <BrowserAdmin />;
  const demo = demoMode();
  if (!(await hasSession())) return <AdminLogin demo={demo} enabled={adminEnabled()} />;
  const { products, orders } = await readStore();
  return <AdminDashboard demo={demo} products={products} orders={orders} />;
}
