import type { Metadata } from 'next';
import Link from 'next/link';
import { ChevronLeft, Sparkles } from 'lucide-react';
import { ShopCatalog } from '@/components/catalog';
import { categories } from '@/lib/catalog';
import { publicUrl } from '@/lib/site';

type Params = { q?: string | string[]; category?: string | string[]; favorites?: string | string[] };
export async function generateMetadata({ searchParams }: { searchParams: Promise<Params> }): Promise<Metadata> {
  const params = await searchParams;
  const index = Boolean(publicUrl()) && !Object.keys(params).length;
  return { title: 'محصولات کودک و نوزاد', description: 'اسباب‌بازی، پوشاک کودک، لوازم نوزاد و بازی‌های آموزشی را در نینیک سایت پیدا کنید.',
    robots: { index, follow: Boolean(publicUrl()) }, alternates: publicUrl() ? { canonical: '/shop' } : undefined };
}

export default async function ShopPage({ searchParams }: { searchParams: Promise<Params> }) {
  const { q, category, favorites } = await searchParams;
  const selected = categories.find((item) => item.id === category);
  const query = typeof q === 'string' ? q.slice(0, 100) : '';
  return <div className="shell inner-page">
    <div className="breadcrumbs"><Link href="/">خانه</Link><ChevronLeft size={15} /><span>محصولات</span></div>
    <div className="page-intro"><p className="eyebrow"><Sparkles size={17} /> کلی چیز برای دل‌های کوچولو</p>
      <h1>{favorites === '1' ? 'علاقه‌مندی‌ها' : selected?.name ?? 'فروشگاه نینیک'}</h1><p>از اولین لباس نوزاد تا یک بازی تازه؛ چیزی که دنبالش هستی را پیدا کن.</p>
    </div>
    <ShopCatalog key={`${selected?.id}:${query}:${favorites === '1'}`} initialCategory={selected?.id ?? ''} initialQuery={query} initialFavorites={favorites === '1'} />
  </div>;
}
