'use client';

import { useEffect, useRef, useState, type ReactNode } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { ArrowLeft, ChevronDown, FlaskConical, Heart, Menu, Search, ShieldCheck, ShoppingBag, Trash2, Truck, X } from 'lucide-react';
import { categories, freeShippingAt, matchesProduct, maxQuantity, money } from '@/lib/catalog';
import { useBrowserDemo } from './browser-demo';
import { Brand } from './brand';
import { Quantity, useShop } from './store-context';

const navigation = [
  { href: '/', label: 'خانه' }, { href: '/shop', label: 'محصولات' }, { href: '/#categories', label: 'دسته‌بندی‌ها' }, { href: '/guide', label: 'راهنمای خرید' },
];

export function Header() {
  const pathname = usePathname();
  const demo = useBrowserDemo();
  const [menu, setMenu] = useState(false);
  const [search, setSearch] = useState(false);
  const { count, cartOpen, setCartOpen } = useShop();
  return <>
    <div className="announcement">{demo ? <><FlaskConical size={15} aria-hidden="true" /> نسخهٔ آزمایشی؛ محصولات و قیمت‌ها نمونه‌اند. سفارش واقعی ثبت نمی‌شود.</> : <><Truck size={15} aria-hidden="true" />ارسال رایگان برای سفارش‌های {money(freeShippingAt)} تومان و بیشتر</>}</div>
    <header className="header">
      <div className="shell header-inner">
        <button className="icon-btn mobile-menu" type="button" aria-label="منو" aria-controls="main-nav" aria-expanded={menu} onClick={() => setMenu(!menu)}><Menu size={23} /></button>
        <Brand />
        <nav aria-label="ناوبری اصلی" id="main-nav" className={menu ? 'main-nav open' : 'main-nav'}>
          {navigation.map(({ href, label }) => <Link key={href} href={href} onClick={() => setMenu(false)} aria-current={pathname === href ? 'page' : undefined}>
            {label}{href.includes('#') && <ChevronDown size={13} strokeWidth={1.8} aria-hidden="true" />}
          </Link>)}
        </nav>
        <div className="header-tools">
          <button type="button" className="icon-btn" aria-label="جست‌وجو" onClick={() => setSearch(true)}><Search size={22} strokeWidth={1.75} /></button>
          <Link className="icon-btn header-favorites" href="/shop?favorites=1" aria-label="علاقه‌مندی‌ها"><Heart size={22} strokeWidth={1.75} /></Link>
          <button type="button" className="icon-btn bag-btn" aria-label={`سبد خرید، ${money(count)} کالا`} onClick={() => setCartOpen(true)}>
            <ShoppingBag size={21} strokeWidth={1.8} /><span className="bag-counter" aria-hidden="true">{money(count)}</span>
          </button>
        </div>
      </div>
    </header>
    <SearchDialog open={search} onClose={() => setSearch(false)} />
    <CartDrawer open={cartOpen} onClose={() => setCartOpen(false)} />
  </>;
}

function Dialog({ open, onClose, className, label, children }: { open: boolean; onClose: () => void; className: string; label: string; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    if (open && !node.open) node.showModal();
    else if (!open && node.open) node.close();
  }, [open]);
  return <dialog ref={ref} aria-label={label} className={className} onClose={onClose} onClick={(event) => { if (event.target === ref.current) {
    const rect = event.currentTarget.getBoundingClientRect();
    if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) onClose();
  } }}>
    {children}
  </dialog>;
}

function SearchDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { products } = useShop();
  const [query, setQuery] = useState('');
  const found = query.trim() ? products.filter((product) => matchesProduct(product, query)).slice(0, 5) : [];
  return <Dialog open={open} onClose={onClose} className="search-dialog" label="جست‌وجوی محصولات">
    <div className="dialog-heading"><h2>جست‌وجوی محصولات</h2><button type="button" className="icon-btn" aria-label="بستن جست‌وجو" onClick={onClose}><X size={22} /></button></div>
    <form action="/shop" method="get" className="search-form" onSubmit={onClose}>
      <Search size={20} aria-hidden="true" />
      <input autoFocus name="q" type="search" value={query} onChange={(event) => setQuery(event.target.value)} maxLength={100} placeholder="مثلاً خرس، سرهمی یا شیشه شیر…" aria-label="عبارت جست‌وجو" />
      <button className="button primary compact" type="submit">جست‌وجو</button>
    </form>
    {query.trim() ? <div className="search-results">
      {found.length ? found.map((product) => <Link href={`/product/${product.slug}`} onClick={onClose} key={product.slug}>
        <img src={product.image} alt="" width={50} height={50} />
        <span>{product.name}</span><small>{money(product.price)} تومان</small><ArrowLeft size={16} aria-hidden="true" />
      </Link>) : <p className="subtle">محصولی پیدا نشد. عبارت دیگری امتحان کنید.</p>}
    </div> : <div className="search-suggestions"><span>دسته‌بندی‌ها:</span>{categories.map((item) => <Link key={item.id} href={`/category/${item.id}`} onClick={onClose}>{item.name}</Link>)}</div>}
  </Dialog>;
}

function CartDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { items, subtotal, count, setQuantity } = useShop();
  return <Dialog open={open} onClose={onClose} className="cart-drawer" label="سبد خرید">
    <div className="drawer-body">
      <div className="dialog-heading"><h2>سبد خرید <small>{money(count)} کالا</small></h2><button type="button" className="icon-btn" aria-label="بستن سبد خرید" onClick={onClose}><X size={22} /></button></div>
      {items.length ? <>
        <div className="drawer-items">
          {items.map(({ product, quantity }) => <div className="drawer-item" key={product.slug}>
            <Link href={`/product/${product.slug}`} onClick={onClose}><img src={product.image} width="76" height="76" alt={product.name} /></Link>
            <div className="drawer-product"><Link href={`/product/${product.slug}`} onClick={onClose}>{product.name}</Link><small>{money(product.price)} تومان</small>
              <Quantity value={quantity} max={Math.min(maxQuantity, product.stock)} onChange={(next) => setQuantity(product, next)} />
            </div>
            <button type="button" className="icon-btn remove-btn" aria-label={`حذف ${product.name}`} onClick={() => setQuantity(product, 0)}><Trash2 size={17} strokeWidth={1.65} /></button>
          </div>)}
        </div>
        <div className="drawer-summary"><div><span>جمع کالاها</span><strong>{money(subtotal)} تومان</strong></div>
          <p>هزینهٔ ارسال در مرحلهٔ بعد محاسبه می‌شود.</p>
          <Link href="/checkout" className="button primary" onClick={onClose}>ادامه و ثبت سفارش <ArrowLeft size={18} /></Link>
        </div>
      </> : <div className="empty-state"><span className="empty-icon"><ShoppingBag size={34} strokeWidth={1.4} /></span><h3>سبد خریدت هنوز خالیه</h3><p>یه چیزی برای کوچولوت پیدا کن!</p><Link href="/shop" className="button primary compact" onClick={onClose}>دیدن محصولات <ArrowLeft size={17} /></Link></div>}
    </div>
  </Dialog>;
}

export function Footer() {
  return <footer className="footer">
    <div className="shell footer-main">
      <div className="footer-brand"><Brand /><p>برای بازی، یادگیری و لحظه‌های کوچک و قشنگ کودکی. با عشق، برای کوچولوها.</p></div>
      <div><h2>دسترسی سریع</h2><Link href="/shop">همهٔ محصولات</Link><Link href="/#categories">دسته‌بندی‌ها</Link><Link href="/shop?favorites=1">علاقه‌مندی‌ها</Link></div>
      <div><h2>راهنمای فروشگاه</h2><Link href="/guide">راهنمای خرید</Link><Link href="/guide#shipping">هزینه و روش ارسال</Link><Link href="/guide#privacy">حریم خصوصی</Link></div>
      <div className="footer-note"><ShieldCheck size={22} aria-hidden="true" /><div><strong>مدیریت فروشگاه</strong><Link href="/admin" rel="nofollow">ورود به پنل مدیریت <ArrowLeft size={14} /></Link></div></div>
    </div>
    <div className="shell footer-bottom"><span>تمام حقوق برای نینیک سایت محفوظ است.</span><span lang="en" dir="ltr">NINIK SHOP</span></div>
  </footer>;
}
