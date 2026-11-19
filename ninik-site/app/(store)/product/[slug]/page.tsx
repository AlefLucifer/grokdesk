import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { BreadcrumbsLd, JsonLd } from '@/components/json-ld';
import { ProductDetail } from '@/components/product-detail';
import { categoryName } from '@/lib/catalog';
import { brand, browserDemoMode, ordersEnabled, publicUrl } from '@/lib/site';
import { getCatalog } from '@/lib/store';

type Props = { params: Promise<{ slug: string }> };
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const product = (await getCatalog()).find((item) => item.slug === slug);
  if (!product) return { title: 'محصول پیدا نشد', robots: { index: false, follow: false } };
  const origin = publicUrl();
  const path = `/product/${slug}`;
  const description = browserDemoMode() ? `${product.description} (محصول نمونهٔ نینیک سایت؛ فروش واقعی فعال نیست.)` : product.description;
  return { title: product.name, description,
    alternates: origin ? { canonical: path } : undefined,
    openGraph: origin ? { title: product.name, siteName: brand, locale: 'fa_IR', description, url: path, images: [product.image] } : undefined };
}

export default async function ProductPage({ params }: Props) {
  const { slug } = await params;
  const product = (await getCatalog()).find((item) => item.slug === slug);
  if (!product && !browserDemoMode()) notFound();
  const origin = publicUrl();
  // Don't send pretend offers or availability to Google for catalogue samples.
  const offerSchema = origin && product && ordersEnabled() && {
    '@context': 'https://schema.org', '@type': 'Product', name: product.name, sku: product.slug, description: product.description,
    image: new URL(product.image, origin).href,
    offers: { '@type': 'Offer', price: product.price * 10, priceCurrency: 'IRR', url: `${origin}/product/${product.slug}`, availability: `https://schema.org/${product.stock ? 'InStock' : 'OutOfStock'}` },
  };
  return <div className="shell inner-page product-page">
    {origin && product && <BreadcrumbsLd origin={origin} items={[{ path: '/', name: 'خانه' }, { path: `/category/${product.category}`, name: categoryName(product.category) }, { path: `/product/${slug}`, name: product.name }]} />}
    {offerSchema && <JsonLd value={offerSchema} />}
    <ProductDetail key={slug} slug={slug} />
  </div>;
}
