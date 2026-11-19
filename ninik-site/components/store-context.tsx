'use client';

import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { Check, Heart, Minus, Plus, ShoppingBag } from 'lucide-react';
import { maxLines, maxQuantity, money, type Product } from '@/lib/catalog';

import { useBrowserDemo } from './browser-demo';

type Item = { product: Product; quantity: number };
type State = Record<string, number>;
type Shop = {
  products: Product[];
  items: Item[];
  count: number;
  subtotal: number;
  ready: boolean;
  cartOpen: boolean;
  setCartOpen: (open: boolean) => void;
  add: (product: Product, quantity?: number) => void;
  setQuantity: (product: Product, quantity: number) => void;
  clearCart: () => void;
  favorites: string[];
  toggleFavorite: (slug: string) => void;
};
const Context = createContext<Shop | null>(null);
const ownQuantity = (cart: State, slug: string) => Object.hasOwn(cart, slug) ? cart[slug] : 0;

function fromStorage<T>(key: string, fallback: T): unknown {
  try { return JSON.parse(localStorage.getItem(key) ?? 'null') ?? fallback; } catch { return fallback; }
}

export function StoreProvider({ products: catalog, children }: { products: Product[]; children: ReactNode }) {
  const demo = useBrowserDemo();
  const products = demo ? demo.products.filter(({ active }) => active) : catalog;
  const [cart, setCart] = useState<State>({});
  const [favorites, setFavorites] = useState<string[]>([]);
  const [ready, setReady] = useState(false);
  const [cartOpen, setCartOpen] = useState(false);
  const [message, setMessage] = useState<{ value: string }>();
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const bag = fromStorage('ninik-bag-v1', {});
    const saved = fromStorage('ninik-favorites-v1', []);
    if (bag && typeof bag === 'object' && !Array.isArray(bag)) {
      setCart(Object.fromEntries(Object.entries(bag).filter(([slug, count]) => /^[a-z0-9-]{2,72}$/.test(slug) && Number.isInteger(count) && count > 0 && count <= maxQuantity).slice(0, maxLines)));
    }
    if (Array.isArray(saved)) setFavorites(saved.filter((slug): slug is string => typeof slug === 'string' && /^[a-z0-9-]{2,72}$/.test(slug)).slice(0, 800));
    setReady(true);
    return () => { if (timer.current) clearTimeout(timer.current); };
  }, []);

  useEffect(() => {
    if (!ready) return;
    try { localStorage.setItem('ninik-bag-v1', JSON.stringify(cart)); localStorage.setItem('ninik-favorites-v1', JSON.stringify(favorites)); } catch { /* Shopping still works without browser storage. */ }
  }, [ready, cart, favorites]);

  const items = products.flatMap((product) => ownQuantity(cart, product.slug) ? [{ product, quantity: cart[product.slug] }] : []);
  const count = items.reduce((sum, item) => sum + item.quantity, 0);
  const subtotal = items.reduce((sum, item) => sum + item.quantity * item.product.price, 0);
  function flash(value: string) {
    if (timer.current) clearTimeout(timer.current);
    setMessage({ value });
    timer.current = setTimeout(() => setMessage(undefined), 2800);
  }
  function setQuantity(product: Product, quantity: number) {
    setCart((current) => {
      const next = { ...current };
      if (quantity <= 0) delete next[product.slug];
      else next[product.slug] = Math.min(quantity, maxQuantity, product.stock);
      return next;
    });
  }
  function add(product: Product, quantity = 1) {
    const current = ownQuantity(cart, product.slug);
    if (current + quantity > Math.min(maxQuantity, product.stock)) {
      flash('موجودی کافی برای افزودن این تعداد نیست.'); return;
    }
    if (current === 0 && items.length >= maxLines) { flash('سبد خرید به حداکثر تعداد محصولات رسیده است.'); return; }
    setQuantity(product, current + quantity);
    flash('به سبد خرید اضافه شد.');
  }
  function toggleFavorite(slug: string) {
    const isSaved = favorites.includes(slug);
    setFavorites((current) => isSaved ? current.filter((item) => item !== slug) : [...current, slug]);
    flash(isSaved ? 'از علاقه‌مندی‌ها حذف شد.' : 'به علاقه‌مندی‌ها اضافه شد.');
  }
  return <Context.Provider value={{ products, count, subtotal, items, ready, cartOpen, setCartOpen, add, setQuantity, clearCart: () => setCart({}), favorites, toggleFavorite }}>
    {children}
    <div className="toast-region" role="status" aria-live="polite">
      {message && <div className="toast"><Check size={17} aria-hidden="true" />{message.value}</div>}
    </div>
  </Context.Provider>;
}

export function useShop() {
  const context = useContext(Context);
  if (!context) throw new Error('StoreProvider missing');
  return context;
}

export function FavoriteButton({ slug, large = false }: { slug: string; large?: boolean }) {
  const { favorites, toggleFavorite } = useShop();
  const saved = favorites.includes(slug);
  return <button className={`${large ? 'detail-heart' : 'favorite-btn'} ${saved ? 'is-favorite' : ''}`} type="button" aria-pressed={saved}
    aria-label={saved ? 'حذف از علاقه‌مندی‌ها' : 'افزودن به علاقه‌مندی‌ها'} onClick={() => toggleFavorite(slug)}>
    <Heart size={large ? 22 : 19} strokeWidth={1.75} fill={saved ? 'currentColor' : 'none'} aria-hidden="true" />
  </button>;
}

export function AddButton({ product }: { product: Product }) {
  const { add } = useShop();
  return <button type="button" className="add-btn" disabled={!product.stock} onClick={() => add(product)}
    aria-label={`افزودن ${product.name} به سبد خرید`} title={product.stock ? 'افزودن به سبد خرید' : 'ناموجود'}>
    <ShoppingBag size={19} strokeWidth={1.8} aria-hidden="true" />
  </button>;
}

export function Quantity({ value, min = 1, max, onChange }: { value: number; min?: number; max: number; onChange: (next: number) => void }) {
  return <div className="quantity" role="group" aria-label="تعداد محصول">
    <button type="button" onClick={() => onChange(value + 1)} disabled={value >= max} aria-label="افزایش تعداد"><Plus size={15} /></button>
    <output aria-label="تعداد">{money(value)}</output>
    <button type="button" onClick={() => onChange(value - 1)} disabled={value <= min} aria-label="کاهش تعداد"><Minus size={15} /></button>
  </div>;
}

export function ProductActions({ product }: { product: Product }) {
  const [quantity, setQuantity] = useState(1);
  const { add } = useShop();
  const max = Math.min(maxQuantity, product.stock);
  const selected = Math.min(quantity, max);
  return <div className="detail-actions">
    {max > 0 && <Quantity value={selected} max={max} onChange={setQuantity} />}
    <button type="button" className="button primary" disabled={!max} onClick={() => add(product, selected)}><ShoppingBag size={19} />{max ? 'افزودن به سبد خرید' : 'ناموجود'}</button>
    <FavoriteButton slug={product.slug} large />
  </div>;
}
