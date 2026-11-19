'use client';

import { useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, Heart, Search, SlidersHorizontal } from 'lucide-react';
import { categories, categoryName, matchesProduct, money, type CategoryId, type Product } from '@/lib/catalog';
import { AddButton, FavoriteButton, useShop } from './store-context';

export function ProductCard({ product }: { product: Product }) {
  const percent = product.oldPrice ? Math.round((product.oldPrice - product.price) * 100 / product.oldPrice) : 0;
  return <article className="product-card">
    <div className="product-visual">
      <Link className="product-image" href={`/product/${product.slug}`} aria-label={product.name}>
        <img src={product.image} width={680} height={680} alt={product.name} loading="lazy" />
      </Link>
      <FavoriteButton slug={product.slug} />
      {!!(product.badge || percent || !product.stock) && <span className={`product-badge ${percent ? 'sale' : ''}`}>{!product.stock ? 'ناموجود' : percent ? `${money(percent)}٪ تخفیف` : product.badge}</span>}
    </div>
    <div className="product-content">
      <span className="product-category">{categoryName(product.category)}</span>
      <h3><Link href={`/product/${product.slug}`}>{product.name}</Link></h3>
      <div className="product-bottom"><div className="price-stack">
        <strong>{money(product.price)} <span>تومان</span></strong>
        {product.oldPrice && <del>{money(product.oldPrice)}</del>}
      </div><AddButton product={product} /></div>
    </div>
  </article>;
}

export function ShopCatalog({ initialCategory, initialQuery = '', initialFavorites = false, lockCategory = false }: { initialCategory: CategoryId | ''; initialQuery?: string; initialFavorites?: boolean; lockCategory?: boolean }) {
  const { products, favorites, ready } = useShop();
  const [category, setCategory] = useState(initialCategory);
  const [query, setQuery] = useState(initialQuery);
  const [showFavorites, setShowFavorites] = useState(initialFavorites);
  const [sort, setSort] = useState('default');
  const filtered = products.filter((product) => (!category || product.category === category) && (!showFavorites || favorites.includes(product.slug)) && matchesProduct(product, query));
  if (sort === 'low') filtered.sort((a, b) => a.price - b.price);
  if (sort === 'high') filtered.sort((a, b) => b.price - a.price);
  if (sort === 'new') filtered.reverse();
  return <>
    <div className="catalog-toolbar">
      <label className="catalog-search"><Search size={19} aria-hidden="true" /><input type="search" aria-label="جست‌وجو در محصولات" placeholder="جست‌وجو در محصولات…" value={query} onChange={(event) => setQuery(event.target.value)} maxLength={100} /></label>
      <label className="catalog-sort"><SlidersHorizontal size={18} aria-hidden="true" /><span className="sr-only">مرتب‌سازی محصولات</span><select value={sort} onChange={(event) => setSort(event.target.value)}><option value="default">ترتیب فروشگاه</option><option value="low">ارزان‌ترین</option><option value="high">گران‌ترین</option><option value="new">تازه‌ترین</option></select></label>
    </div>
    {!lockCategory && <div className="filter-row" aria-label="فیلتر محصولات">
      <button type="button" className="chip" aria-pressed={!category && !showFavorites} onClick={() => { setCategory(''); setShowFavorites(false); }}>همه محصولات</button>
      {categories.map((item) => <button type="button" key={item.id} className="chip" aria-pressed={item.id === category} onClick={() => setCategory(category === item.id ? '' : item.id)}>{item.name}</button>)}
      <button type="button" className="chip" aria-pressed={showFavorites} onClick={() => setShowFavorites(!showFavorites)}><Heart size={15} /> علاقه‌مندی‌ها</button>
    </div>}
    <p className="result-count" aria-live="polite">{showFavorites && !ready ? 'در حال خواندن علاقه‌مندی‌ها…' : `${money(filtered.length)} محصول`}</p>
    {filtered.length ? <div className="product-grid">{filtered.map((product) => <ProductCard key={product.slug} product={product} />)}</div> : (!showFavorites || ready) && <div className="empty-state result-empty">
      <span className="empty-icon">{showFavorites ? <Heart size={32} strokeWidth={1.5} /> : <Search size={32} strokeWidth={1.5} />}</span>
      <h2>{showFavorites ? 'در این فهرست علاقه‌مندی‌ای نیست' : 'محصولی پیدا نشد'}</h2><p>جست‌وجو یا فیلتر را تغییر بده تا انتخاب‌های دیگر را ببینی.</p>
      <button type="button" className="button outline compact" onClick={() => { setCategory(lockCategory ? initialCategory : ''); setQuery(''); setShowFavorites(false); }}>{lockCategory ? 'حذف عبارت جست‌وجو' : 'نمایش همهٔ محصولات'} <ArrowLeft size={16} /></button>
    </div>}
  </>;
}

export function FeaturedProducts() {
  const { products } = useShop();
  return products.length ? <div className="product-grid">{products.slice(0, 4).map((item) => <ProductCard key={item.slug} product={item} />)}</div> : <p className="subtle">محصولات به‌زودی اضافه می‌شوند.</p>;
}
