import type { Metadata } from 'next';
import '@fontsource-variable/vazirmatn';
import './globals.css';
import { BrowserDemoProvider } from '@/components/browser-demo';
import { brand, browserDemoMode, description, publicUrl } from '@/lib/site';

export const dynamic = 'force-dynamic';

export function generateMetadata(): Metadata {
  const url = publicUrl();
  return {
    metadataBase: url ? new URL(url) : undefined,
    title: { default: `${brand} | فروشگاه اسباب‌بازی و لوازم کودک`, template: `%s | ${brand}` },
    description,
    robots: { index: Boolean(url), follow: Boolean(url) },
    verification: url && process.env.GOOGLE_SITE_VERIFICATION ? { google: process.env.GOOGLE_SITE_VERIFICATION } : undefined,
    openGraph: { type: 'website', locale: 'fa_IR', siteName: brand, title: brand, description, url: url ?? undefined },
  };
}

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="fa" dir="rtl"><body>
    <a href="#main" className="skip-link">رفتن به محتوای اصلی</a>
    {browserDemoMode() ? <BrowserDemoProvider>{children}</BrowserDemoProvider> : children}
  </body></html>;
}
