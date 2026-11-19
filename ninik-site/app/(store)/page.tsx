import type { Metadata } from 'next';
import Link from 'next/link';
import { ArrowLeft, ChevronLeft, Gift, HeartHandshake, Sparkles, Truck } from 'lucide-react';
import { FeaturedProducts } from '@/components/catalog';
import { JsonLd } from '@/components/json-ld';
import { CategoryArt } from '@/components/category-art';
import { categories, freeShippingAt, money } from '@/lib/catalog';
import { brand, publicUrl } from '@/lib/site';

export function generateMetadata(): Metadata {
  const url = publicUrl();
  return url ? { alternates: { canonical: '/' } } : {};
}

export default function Home() {
  const origin = publicUrl();
  return <div className="shell home">
    {origin && <JsonLd value={{ '@context': 'https://schema.org', '@type': 'WebSite', name: brand, alternateName: 'Ninik Site', url: `${origin}/` }} />}
    <section className="hero" aria-labelledby="hero-title">
      <img className="hero-art" src="/images/hero.webp" alt="خرس عروسکی کرم و رنگین‌کمان چوبی روی زمینهٔ صورتی" width={1264} height={848} fetchPriority="high" />
      <div className="hero-decor hero-star" aria-hidden="true"><Sparkles size={34} strokeWidth={1.2} /></div>
      <div className="hero-copy">
        <p className="hero-kicker"><Sparkles size={16} strokeWidth={1.8} /> با عشق، برای کوچک‌ترها</p>
        <h1 id="hero-title">برای دنیای رنگی<br/><em>کوچولوهای شما</em></h1>
        <p className="hero-description">اسباب‌بازی‌های دوست‌داشتنی و لوازم ضروری کودک؛ با دقت انتخاب‌شده برای روزهای قشنگ کودکی.</p>
        <div className="hero-buttons">
          <Link href="/shop" className="button primary">مشاهده محصولات <ArrowLeft size={19} /></Link>
          <Link href="#categories" className="button hero-outline">دسته‌بندی‌ها</Link>
        </div>
      </div>
    </section>

    <section className="category-section" id="categories" aria-labelledby="category-title">
      <div className="section-heading centered"><p className="eyebrow"><span /> یه انتخاب برای هر لحظه <span /></p><h2 id="category-title">دسته‌بندی محصولات</h2></div>
      <div className="category-grid">
        {categories.map(({ id, name, note, color }) => <Link href={`/category/${id}`} className={`category-card ${color}`} key={id}>
          <CategoryArt category={id} /><strong>{name}</strong><span>{note}</span>
        </Link>)}
      </div>
    </section>

    <section className="featured" id="products" aria-labelledby="featured-title">
      <div className="section-heading section-split">
        <div><p className="eyebrow"><span /> انتخاب‌های دوست‌داشتنی</p><h2 id="featured-title">محبوب‌های نینیک</h2></div>
        <Link className="button outline" href="/shop">همه محصولات <ArrowLeft size={18} /></Link>
      </div>
      <FeaturedProducts />
    </section>

    <section className="benefits" aria-label="راهنمای فروشگاه">
      <div><span className="benefit-icon"><Truck size={24} strokeWidth={1.65} /></span><div><h3>ارسال رایگان</h3><p>از {money(freeShippingAt)} تومان خرید</p></div></div>
      <div><span className="benefit-icon"><Gift size={24} strokeWidth={1.65} /></span><div><h3>ایده برای هدیه</h3><p>برای روزهای خاص کوچولوها</p></div></div>
      <div><span className="benefit-icon"><HeartHandshake size={24} strokeWidth={1.65} /></span><div><h3>راهنمای خرید</h3><Link href="/guide">هرآنچه برای سفارش لازم است <ChevronLeft size={15} /></Link></div></div>
    </section>
  </div>;
}
