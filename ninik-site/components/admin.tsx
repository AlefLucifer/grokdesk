'use client';

import { useState, type FormEvent } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ArrowLeft, ChartNoAxesColumnIncreasing, ClipboardList, Eye, FlaskConical, LayoutDashboard, LockKeyhole, LogOut, Package, PackageOpen, Pencil, Plus, ShoppingBag, TriangleAlert } from 'lucide-react';
import { categories, categoryName, money, nextStatuses, productImages, statuses, type Order, type OrderStatus, type Product } from '@/lib/catalog';
import { Bear, Brand } from './brand';
import { useBrowserDemo } from './browser-demo';

async function adminRequest(action: string, data: unknown) {
  const response = await fetch(`/api/admin/${action}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
  const result = await response.json().catch(() => null);
  if (!response.ok) throw new Error(result?.error || 'ارتباط با فروشگاه برقرار نشد. دوباره تلاش کنید.');
}

export function BrowserAdmin() {
  const browser = useBrowserDemo();
  if (!browser) return null;
  return browser.signedIn ? <AdminDashboard demo products={browser.products} orders={browser.orders} /> : <AdminLogin demo enabled={browser.ready} />;
}

export function AdminLogin({ demo, enabled }: { demo: boolean; enabled: boolean }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const router = useRouter();
  const browser = useBrowserDemo();
  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || !enabled) return;
    const form = new FormData(event.currentTarget);
    setBusy(true); setError('');
    try { await (browser?.manage ?? adminRequest)('login', demo ? { demo: true } : { password: form.get('password') }); if (!browser) router.refresh(); }
    catch (error) { setError(error instanceof Error ? error.message : 'ورود انجام نشد.'); setBusy(false); }
  }
  return <main className="admin-login" id="main"><div className="admin-login-inner">
    <Link href="/" className="admin-back"><ArrowLeft size={17} /> بازگشت به فروشگاه</Link>
    <div className="panel login-panel">
      <div className="login-mark"><Bear size={41} /></div><p className="eyebrow">نینیک سایت</p><h1>ورود به پنل مدیریت</h1><p className="subtle">محصولات، موجودی و سفارش‌های فروشگاه را مدیریت کنید.</p>
      {demo && <p className="notice"><FlaskConical size={18} /> {browser ? 'این پنل آزمایشی است؛ فقط سفارش‌ها و محصولات این مرورگر را تغییر می‌دهد.' : 'این پنل آزمایشی است و به حساب واقعی فروشگاه متصل نیست.'}</p>}
      {!enabled && <p className="notice">مدیریت هنوز راه‌اندازی نشده است.</p>}
      <form onSubmit={login}>
        {enabled && !demo && <label className="field">رمز مدیریت<input name="password" autoComplete="current-password" type="password" dir="ltr" maxLength={512} required /></label>}
        {error && <p className="form-error" role="alert">{error}</p>}
        <button className="button primary" type="submit" disabled={busy || !enabled}><LockKeyhole size={17} />{busy ? 'در حال ورود…' : demo ? 'ورود آزمایشی' : 'ورود به مدیریت'}</button>
      </form>
    </div>
  </div></main>;
}

const sections = [
  { id: 'overview', name: 'نمای کلی', icon: LayoutDashboard }, { id: 'products', name: 'محصولات', icon: Package }, { id: 'orders', name: 'سفارش‌ها', icon: ClipboardList },
] as const;
type Section = (typeof sections)[number]['id'];
const displayDate = new Intl.DateTimeFormat('fa-IR', { dateStyle: 'medium', timeZone: 'Asia/Tehran' });

export function AdminDashboard({ demo, products, orders }: { demo: boolean; products: Product[]; orders: Order[] }) {
  const [view, setView] = useState<Section>('overview');
  const [editing, setEditing] = useState<Product | 'new' | null>(null);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [leaving, setLeaving] = useState(false);
  const router = useRouter();
  const browser = useBrowserDemo();
  const active = products.filter((product) => product.active);
  const metrics = [
    { icon: Package, label: 'محصولات فعال', value: money(active.length), hint: 'منتشرشده در فروشگاه', tone: 'pink' },
    { icon: ShoppingBag, label: 'سفارش‌های جدید', value: money(orders.filter((order) => order.status === 'new').length), hint: 'نیازمند بررسی', tone: 'lilac' },
    { icon: TriangleAlert, label: 'موجودی کم', value: money(active.filter((product) => product.stock < 5).length), hint: 'کمتر از ۵ عدد', tone: 'peach' },
    { icon: ChartNoAxesColumnIncreasing, label: 'ارزش سفارش‌ها', value: money(orders.filter((order) => order.status !== 'cancelled').reduce((sum, order) => sum + order.total, 0)), hint: 'تومان، بدون سفارش‌های لغوشده', tone: 'mint' },
  ];
  function navigate(next: Section) { setView(next); setEditing(null); setNotice(''); setError(''); }
  async function logout() {
    if (leaving) return;
    setLeaving(true);
    try { await (browser?.manage ?? adminRequest)('logout', {}); if (!browser) router.refresh(); }
    catch (error) { setError(error instanceof Error ? error.message : 'خروج انجام نشد.'); setLeaving(false); }
  }
  return <div className="admin-layout">
    <aside className="admin-sidebar">
      <Brand />
      <p className="admin-sidebar-label">مدیریت فروشگاه</p>
      <nav aria-label="بخش‌های مدیریت">
        {sections.map(({ id, name, icon: Icon }) => <button type="button" key={id} aria-current={id === view ? 'page' : undefined} onClick={() => navigate(id)}><Icon size={19} />{name}</button>)}
      </nav>
      <div className="admin-sidebar-bottom"><Link href="/"><Eye size={19} />نمایش فروشگاه</Link><button type="button" disabled={leaving} onClick={logout}><LogOut size={19} />خروج</button></div>
    </aside>
    <main className="admin-main" id="main" tabIndex={-1}>
      <header className="admin-top"><div><p className="eyebrow"><span /> نینیک سایت</p><h1>{view === 'overview' ? 'نمای کلی فروشگاه' : sections.find(({ id }) => id === view)?.name}</h1></div>
        {demo && <span className="demo-label"><FlaskConical size={16} /> محیط آزمایشی</span>}
      </header>
      {notice && <p className="admin-success" role="status">{notice}</p>}{error && <p className="form-error" role="alert">{error}</p>}
      {view === 'overview' && <>
        <div className="metric-grid">{metrics.map(({ icon: Icon, label, value, hint, tone }) => <section key={label} className="metric"><span className={`metric-icon ${tone}`}><Icon size={22} /></span><h2>{label}</h2><strong>{value}</strong><p>{hint}</p></section>)}</div>
        <section className="panel admin-list"><div className="admin-section-title"><div><h2>آخرین سفارش‌ها</h2><p>سفارش‌های ثبت‌شده در نینیک سایت</p></div><button type="button" className="button outline compact" onClick={() => navigate('orders')}>همهٔ سفارش‌ها <ArrowLeft size={16} /></button></div>
          {orders.length ? <OrderList orders={orders.slice(0, 4)} onChange={() => { if (!browser) router.refresh(); }} /> : <EmptyOrders />}
        </section>
      </>}
      {view === 'products' && <section className="panel admin-list">
        {editing ? <ProductEditor key={editing === 'new' ? 'new' : editing.slug} product={editing === 'new' ? null : editing} onCancel={() => setEditing(null)} onSave={() => { setEditing(null); setNotice('محصول ذخیره شد.'); if (!browser) router.refresh(); }} /> : <>
          <div className="admin-section-title"><div><h2>کاتالوگ فروشگاه</h2><p>{money(products.length)} محصول؛ ویرایش قیمت، موجودی و انتشار</p></div><button type="button" className="button primary compact" onClick={() => { setNotice(''); setEditing('new'); }}><Plus size={17} />محصول جدید</button></div>
          <div className="table-wrap"><table className="admin-table"><thead><tr><th scope="col">محصول</th><th scope="col">دسته‌بندی</th><th scope="col">قیمت (تومان)</th><th scope="col">موجودی</th><th scope="col">وضعیت</th><th scope="col">عملیات</th></tr></thead>
            <tbody>{products.map((product) => <tr key={product.slug}><th scope="row"><span className="table-product"><img src={product.image} width={42} height={42} alt="" />{product.name}</span></th><td>{categoryName(product.category)}</td><td>{money(product.price)}</td><td>{money(product.stock)}</td><td><span className={`status ${product.active ? 'shipped' : 'cancelled'}`}>{product.active ? 'فعال' : 'پنهان'}</span></td><td><button type="button" className="text-button table-edit" onClick={() => { setNotice(''); setEditing(product); }} aria-label={`ویرایش ${product.name}`}><Pencil size={15} /> ویرایش</button></td></tr>)}</tbody>
          </table></div>
        </>}
      </section>}
      {view === 'orders' && <section className="panel admin-list"><div className="admin-section-title"><div><h2>سفارش‌های فروشگاه</h2><p>{money(orders.length)} سفارش؛ جزئیات و وضعیت ارسال</p></div></div>
        {orders.length ? <OrderList orders={orders} onChange={() => { setNotice('وضعیت سفارش ذخیره شد.'); if (!browser) router.refresh(); }} /> : <EmptyOrders />}
      </section>}
    </main>
  </div>;
}

function EmptyOrders() { return <div className="empty-state admin-empty"><span className="empty-icon"><PackageOpen size={33} strokeWidth={1.5} /></span><h3>هنوز سفارشی ثبت نشده</h3><p>سفارش‌های جدید بعد از ثبت اینجا نمایش داده می‌شوند.</p></div>; }

function ProductEditor({ product, onCancel, onSave }: { product: Product | null; onCancel: () => void; onSave: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const browser = useBrowserDemo();
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const fields = new FormData(event.currentTarget);
    const old = fields.get('oldPrice');
    const slug = product?.slug || String(fields.get('slug') || '').trim() || `item-${crypto.randomUUID().slice(0, 12)}`;
    const edited = { ...Object.fromEntries(fields), slug, price: Number(fields.get('price')), stock: Number(fields.get('stock')), oldPrice: old ? Number(old) : null, active: fields.has('active') };
    setBusy(true); setError('');
    try { await (browser?.manage ?? adminRequest)('products', { operation: product ? 'update' : 'create', product: edited }); onSave(); }
    catch (error) { setError(error instanceof Error ? error.message : 'ذخیره انجام نشد.'); setBusy(false); }
  }
  return <><div className="admin-section-title"><div><h2>{product ? 'ویرایش محصول' : 'افزودن محصول جدید'}</h2><p>قیمت‌ها به تومان هستند؛ محصول پنهان در فروشگاه نمایش داده نمی‌شود.</p></div><button className="button outline compact" type="button" disabled={busy} onClick={onCancel}>بازگشت</button></div>
    <form className="product-editor" onSubmit={save}>
      <div className="form-two"><label className="field">نام محصول<input name="name" defaultValue={product?.name} required minLength={3} maxLength={100} /></label>
        <label className="field">شناسهٔ نشانی <input name="slug" dir="ltr" readOnly={Boolean(product)} placeholder="مثال: little-bear" defaultValue={product?.slug} pattern="[a-z0-9]+(-[a-z0-9]+)*" maxLength={72} /></label></div>
      <label className="field">توضیحات<textarea name="description" defaultValue={product?.description} required minLength={10} maxLength={1600} rows={4} /></label>
      <div className="form-two"><label className="field">دسته‌بندی<select name="category" defaultValue={product?.category ?? 'toys'}>{categories.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label className="field">سن پیشنهادی<input name="age" defaultValue={product?.age} maxLength={60} /></label></div>
      <div className="form-three"><label className="field">قیمت<input name="price" type="number" dir="ltr" min={1} max={999999999} defaultValue={product?.price} required /></label>
        <label className="field">قیمت قبلی (اختیاری)<input name="oldPrice" type="number" dir="ltr" min={1} max={999999999} defaultValue={product?.oldPrice ?? undefined} /></label>
        <label className="field">موجودی<input name="stock" type="number" dir="ltr" min={0} max={1000000} defaultValue={product?.stock ?? 0} required /></label></div>
      <div className="form-two"><label className="field">نشانی تصویر (HTTPS یا تصویر نمونه)<input name="image" list="sample-images" dir="ltr" defaultValue={product?.image ?? productImages[0]} required maxLength={1024} /></label>
        <label className="field">برچسب (اختیاری)<input name="badge" defaultValue={product?.badge} maxLength={28} placeholder="مثلاً جدید" /></label></div>
      <datalist id="sample-images">{productImages.map((image) => <option key={image} value={image} />)}</datalist>
      <label className="check-field"><input type="checkbox" name="active" defaultChecked={product?.active ?? true} /> در فروشگاه نمایش داده شود</label>
      {error && <p role="alert" className="form-error">{error}</p>}
      <button type="submit" className="button primary" disabled={busy}>{busy ? 'در حال ذخیره…' : 'ذخیرهٔ محصول'}</button>
    </form></>;
}

function OrderList({ orders, onChange }: { orders: Order[]; onChange: () => void }) {
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const browser = useBrowserDemo();
  async function update(id: string, status: OrderStatus) {
    if (busy) return;
    setBusy(id); setError('');
    try { await (browser?.manage ?? adminRequest)('orders', { id, status }); onChange(); }
    catch (error) { setError(error instanceof Error ? error.message : 'تغییر وضعیت انجام نشد.'); }
    finally { setBusy(''); }
  }
  return <div className="admin-orders">{error && <p className="form-error" role="alert">{error}</p>}
    {orders.map((order) => <details key={order.id}>
      <summary><span><bdi dir="ltr">{order.id}</bdi><small>{displayDate.format(new Date(order.createdAt))}</small></span><strong>{money(order.total)} تومان</strong><span className={`status ${order.status}`}>{statuses[order.status]}</span></summary>
      <div className="order-inside"><div><h3>گیرنده</h3><p>{order.customer.name} · <bdi dir="ltr">{order.customer.phone}</bdi></p><p>{order.customer.city}، {order.customer.address}</p></div>
        <div><h3>اقلام سفارش</h3>{order.lines.map((item) => <p key={item.slug}>{item.name} × {money(item.quantity)} — {money(item.price * item.quantity)} تومان</p>)}<p>ارسال: {order.shipping ? `${money(order.shipping)} تومان` : 'رایگان'}</p></div>
      </div>
      {!!nextStatuses[order.status].length && <form className="order-actions" onSubmit={(event) => { event.preventDefault(); const status = new FormData(event.currentTarget).get('status'); if (status) void update(order.id, status as OrderStatus); }}>
        <label className="field">تغییر وضعیت<select key={order.status} name="status" defaultValue={nextStatuses[order.status][0]}>{nextStatuses[order.status].map((status) => <option key={status} value={status}>{statuses[status]}</option>)}</select></label>
        <button className="button outline compact" type="submit" disabled={Boolean(busy)}>{busy === order.id ? 'در حال ذخیره…' : 'ذخیرهٔ وضعیت'}</button>
      </form>}
    </details>)}
  </div>;
}
