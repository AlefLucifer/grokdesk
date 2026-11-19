import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { ProductDetail } from '@/components/product-detail';
import { brand, browserDemoMode, publicUrl } from '@/lib/site';
import { getCatalog } from '@/lib/store';

type Props = { params: Promise<{ slug: string }> };
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const product = (await getCatalog()).find((item) => item.slug === slug);
  if (!product) return { title: 'محصول پیدا نشد', robots: { index: false, follow: false } };
  const origin = publicUrl();
  const path = `/product/${slug}`;
  return { title: product.name, description: product.description,
    alternates: origin ? { canonical: path } : undefined,
    openGraph: origin ? { title: product.name, siteName: brand, locale: 'fa_IR', description: product.description, url: path, images: [product.image] } : undefined };
}

export default async function ProductPage({ params }: Props) {
  const { slug } = await params;
  const product = (await getCatalog()).find((item) => item.slug === slug);
  if (!product && !browserDemoMode()) notFound();
  const origin = publicUrl();
  const schema = origin && product && {
    '@context': 'https://schema.org', '@type': 'Product', name: product.name, sku: product.slug, description: product.description,
    image: new URL(product.image, origin).href, offers: { '@type': 'Offer', price: product.price * 10, priceCurrency: 'IRR', url: `${origin}/product/${product.slug}`, availability: `https://schema.org/${product.stock ? 'InStock' : 'OutOfStock'}` },
  };
  return <div className="shell inner-page product-page">
    {schema && <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schema).replace(/</g, '\\u003c') }} />}
    <ProductDetail key={slug} slug={slug} />
  </div>;
}
