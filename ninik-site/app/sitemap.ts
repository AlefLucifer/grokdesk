import type { MetadataRoute } from 'next';
import { publicUrl } from '@/lib/site';
import { getCatalog } from '@/lib/store';

export const dynamic = 'force-dynamic';

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const origin = publicUrl();
  if (!origin) return [];
  const products = await getCatalog();
  return ['/', '/shop', '/guide', ...products.map(({ slug }) => `/product/${slug}`)].map((route) => ({ url: `${origin}${route}` }));
}
