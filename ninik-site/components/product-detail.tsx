'use client';

import Link from 'next/link';
import { ChevronLeft, CircleCheck, Package, Sparkles } from 'lucide-react';
import { categoryName, money } from '@/lib/catalog';
import { useBrowserDemo } from './browser-demo';
import { ProductCard } from './catalog';
import { ProductActions, useShop } from './store-context';

export function ProductDetail({ slug }: { slug: string }) {
  const { products } = useShop();
  const browser = useBrowserDemo();
  const product = products.find((item) => item.slug === slug);
  if (!product) return <div className="empty-state">
    {browser && !browser.ready ? <p>در حال بازکردن محصول…</p> : <><h1>این محصول پیدا نشد</h1><Link className="button outline" href="/shop">بازگشت به محصولات</Link></>}
  </div>;
  const related = products.filter((item) => item.slug !== slug).sort((a, b) => Number(b.category === product.category) - Number(a.category === product.category)).slice(0, 4);
  return <>
    <div className="breadcrumbs"><Link href="/">خانه</Link><ChevronLeft size={15} /><Link href="/shop">محصولات</Link><ChevronLeft size={15} /><Link href={`/category/${product.category}`}>{categoryName(product.category)}</Link></div>
    <div className="product-detail">
      <div className="detail-photo"><img src={product.image} alt={product.name} width={680} height={680} fetchPriority="high" />{product.badge && <span className="product-badge">{product.badge}</span>}</div>
      <div className="detail-copy">
        <p className="eyebrow"><Sparkles size={17} /> {categoryName(product.category)}</p><h1>{product.name}</h1><p className="detail-description">{product.description}</p>
        <div className="detail-facts">{product.age && <span><Package size={17} /> سن پیشنهادی: {product.age}</span>}<span className={product.stock ? 'in-stock' : 'sold-out'}><CircleCheck size={17} /> {product.stock ? 'موجود در فروشگاه' : 'ناموجود'}</span></div>
        <div className="detail-price"><strong>{money(product.price)} <small>تومان</small></strong>{product.oldPrice && <del>{money(product.oldPrice)} تومان</del>}</div>
        <ProductActions product={product} />
      </div>
    </div>
    {!!related.length && <section className="related"><div className="section-heading"><p className="eyebrow"><span /> برای یک انتخاب تازه</p><h2>شاید این‌ها را هم دوست داشته باشی</h2></div><div className="product-grid">{related.map((item) => <ProductCard key={item.slug} product={item} />)}</div></section>}
  </>;
}
