import type { MetadataRoute } from 'next';
import { publicUrl } from '@/lib/site';

export const dynamic = 'force-dynamic';

export default function robots(): MetadataRoute.Robots {
  const origin = publicUrl();
  return origin ? {
    rules: { userAgent: '*', allow: '/', disallow: ['/admin', '/api/', '/checkout'] },
    sitemap: `${origin}/sitemap.xml`,
  } : { rules: { userAgent: '*', disallow: '/' } };
}
