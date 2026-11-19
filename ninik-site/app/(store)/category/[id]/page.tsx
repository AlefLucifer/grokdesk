import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { ChevronLeft, Sparkles } from 'lucide-react';
import { ShopCatalog } from '@/components/catalog';
import { BreadcrumbsLd } from '@/components/json-ld';
import { categories } from '@/lib/catalog';
import { publicUrl } from '@/lib/site';

type Props = { params: Promise<{ id: string }> };
async function findCategory(params: Props['params']) {
  const { id } = await params;
  const category = categories.find((entry) => entry.id === id);
  if (!category) notFound();
  return category;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const category = await findCategory(params);
  return { title: category.title, description: category.intro, alternates: publicUrl() ? { canonical: `/category/${category.id}` } : undefined };
}

export default async function CategoryPage({ params }: Props) {
  const category = await findCategory(params);
  const origin = publicUrl();
  return <div className="shell inner-page">
    {origin && <BreadcrumbsLd origin={origin} items={[{ path: '/', name: 'خانه' }, { path: '/shop', name: 'محصولات' }, { path: `/category/${category.id}`, name: category.title }]} />}
    <div className="breadcrumbs"><Link href="/">خانه</Link><ChevronLeft size={15} /><Link href="/shop">محصولات</Link><ChevronLeft size={15} /><span>{category.name}</span></div>
    <div className="page-intro"><p className="eyebrow"><Sparkles size={17} /> {category.note}</p><h1>{category.title}</h1><p>{category.intro}</p></div>
    <nav className="filter-row" aria-label="دسته‌بندی محصولات">
      <Link className="chip" href="/shop">همه محصولات</Link>
      {categories.map((item) => <Link key={item.id} className="chip" href={`/category/${item.id}`} aria-current={item.id === category.id ? 'page' : undefined}>{item.name}</Link>)}
    </nav>
    <ShopCatalog key={category.id} initialCategory={category.id} lockCategory />
  </div>;
}
