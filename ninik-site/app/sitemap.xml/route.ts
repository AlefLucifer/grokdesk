import { categories } from '@/lib/catalog';
import { publicUrl } from '@/lib/site';
import { getCatalog } from '@/lib/store';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

function escapeXml(value: string) {
  return value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&apos;');
}

export async function GET() {
  const origin = publicUrl();
  if (!origin) return new Response('Sitemap is only available on the public site.', { status: 404 });
  const products = await getCatalog();
  const paths = ['/', '/shop', '/guide', ...categories.map(({ id }) => `/category/${id}`), ...products.map(({ slug }) => `/product/${slug}`)];
  const urls = paths.map((path) => `  <url><loc>${escapeXml(new URL(path, origin).href)}</loc></url>`);
  const xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">', ...urls, '</urlset>', ''].join('\n');
  return new Response(xml, { headers: { 'Content-Type': 'application/xml; charset=UTF-8', 'Cache-Control': 'public, max-age=0, s-maxage=300' } });
}
