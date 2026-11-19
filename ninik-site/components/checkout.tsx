'use client';

import { useState, type FormEvent } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ArrowLeft, Check, ChevronLeft, FlaskConical, PackageCheck, ShoppingBag } from 'lucide-react';
import { money, shippingPrice } from '@/lib/catalog';
import { useBrowserDemo } from './browser-demo';
import { useShop } from './store-context';

export function Checkout({ enabled, demo }: { enabled: boolean; demo: boolean }) {
  const { ready, items, subtotal, setCartOpen, clearCart } = useShop();
  const router = useRouter();
  const browser = useBrowserDemo();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [success, setSuccess] = useState<{ id: string; total: number }>();
  const shipping = shippingPrice(subtotal);
  const stale = items.some(({ product, quantity }) => quantity > product.stock);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || !enabled || !items.length || stale) return;
    const fields = Object.fromEntries(new FormData(event.currentTarget));
    setBusy(true); setMessage('');
    try {
      const data = { customer: demo ? null : fields, lines: items.map(({ product, quantity }) => ({ slug: product.slug, quantity, price: product.price })) };
      if (browser) {
        const order = browser.placeOrder(data);
        setSuccess({ id: order.id, total: order.total }); clearCart(); return;
      }
      const response = await fetch('/api/orders', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
      const result = await response.json();
      if (!response.ok) { if (response.status === 409) router.refresh(); throw new Error(result.error); }
      setSuccess({ id: result.id, total: result.total }); clearCart(); router.refresh();
    } catch (error) { setMessage(error instanceof Error && error.message ? error.message : 'ارتباط برقرار نشد. دوباره تلاش کنید.'); }
    finally { setBusy(false); }
  }
  return <div className="shell inner-page checkout-page">
    <div className="breadcrumbs"><Link href="/">خانه</Link><ChevronLeft size={15} /><Link href="/shop">محصولات</Link><ChevronLeft size={15} /><span>ثبت سفارش</span></div>
    {success ? <div className="empty-state order-success"><span className="empty-icon success-icon"><Check size={39} /></span><h1>{demo ? 'سفارش آزمایشی ثبت شد' : 'درخواست سفارش ثبت شد'}</h1>
      <p>کد سفارش را برای پیگیری نگه دارید.</p><bdi className="order-code" dir="ltr">{success.id}</bdi><p>مبلغ سفارش: {money(success.total)} تومان</p>
      <p>{demo ? 'این سفارش نمونه است؛ پرداخت و ارسال انجام نمی‌شود.' : 'هیچ مبلغی از شما دریافت نشده است.'}</p>
      <Link className="button primary" href="/shop">بازگشت به فروشگاه <ArrowLeft size={18} /></Link></div>
      : !ready ? <div className="empty-state"><p>در حال بازکردن سبد خرید…</p></div>
      : !items.length ? <div className="empty-state"><span className="empty-icon"><ShoppingBag size={34} /></span><h1>سبد خرید خالی است</h1><p>برای ثبت سفارش، ابتدا محصولی انتخاب کنید.</p><Link className="button primary" href="/shop">دیدن محصولات <ArrowLeft size={18} /></Link></div>
      : <>
        <div className="page-intro"><p className="eyebrow"><PackageCheck size={17} /> مرحلهٔ پایانی خرید</p><h1>ثبت سفارش</h1><p>علاقه‌مندی‌های کوچولوت یک قدم نزدیک‌ترند.</p></div>
        <div className="checkout-grid">
          <form className="panel checkout-form" onSubmit={submit}>
            <h2>اطلاعات گیرنده</h2>
            {demo && <p className="notice"><FlaskConical size={19} /> پیش‌نمایش آزمایشی است. فقط اطلاعات نمونه ثبت می‌شود؛ پرداخت یا ارسال انجام نمی‌شود.</p>}
            {!enabled && <p className="notice">ثبت سفارش واقعی در این نسخه فعال نیست.</p>}
            <fieldset disabled={!enabled || busy}>
              <label>نام و نام خانوادگی<input autoComplete="name" name="name" required minLength={3} maxLength={100} readOnly={demo} defaultValue={demo ? 'خریدار نمونه' : ''} /></label>
              <div className="form-two">
                <label>شمارهٔ موبایل<input autoComplete="tel-national" inputMode="tel" dir="ltr" type="tel" name="phone" required minLength={11} maxLength={18} placeholder="09xxxxxxxxx" readOnly={demo} defaultValue={demo ? '09000000000' : ''} /></label>
                <label>شهر<input autoComplete="address-level2" name="city" required minLength={2} maxLength={80} readOnly={demo} defaultValue={demo ? 'شهر نمونه' : ''} /></label>
              </div>
              <label>نشانی کامل<textarea autoComplete="street-address" name="address" rows={3} required minLength={10} maxLength={500} readOnly={demo} defaultValue={demo ? 'نشانی نمونه — بدون ارسال' : ''} /></label>
            </fieldset>
            <p className="subtle">{demo ? 'هیچ اطلاعات شخصی وارد نکنید.' : 'درگاه آنلاین متصل نیست. با ثبت سفارش مبلغی کسر نمی‌شود.'} <Link href="/guide#privacy">حریم خصوصی</Link></p>
            {message && <p className="form-error" role="alert">{message}</p>}
            {stale && <p className="form-error" role="alert">موجودی تغییر کرده است. لطفاً <button type="button" onClick={() => setCartOpen(true)}>سبد را ویرایش کنید</button>.</p>}
            <button className="button primary" type="submit" disabled={busy || !enabled || stale}>{busy ? 'در حال ثبت…' : demo ? 'ثبت سفارش آزمایشی' : 'ثبت درخواست خرید'} <ArrowLeft size={18} /></button>
          </form>
          <section className="panel checkout-summary" aria-label="خلاصهٔ سفارش"><h2>خلاصهٔ سفارش</h2>
            {items.map(({ product, quantity }) => <div className="checkout-item" key={product.slug}>
              <img src={product.image} alt="" width={54} height={54} /><div><Link href={`/product/${product.slug}`}>{product.name}</Link><small>{money(quantity)} عدد</small></div><strong>{money(product.price * quantity)}</strong>
            </div>)}
            <dl className="summary-totals"><div><dt>جمع کالاها</dt><dd>{money(subtotal)} تومان</dd></div><div><dt>هزینهٔ ارسال</dt><dd>{shipping ? `${money(shipping)} تومان` : 'رایگان'}</dd></div><div className="grand-total"><dt>جمع سفارش</dt><dd>{money(subtotal + shipping)} تومان</dd></div></dl>
            <button type="button" className="text-button" onClick={() => setCartOpen(true)}>ویرایش سبد خرید</button>
          </section>
        </div>
      </>}
  </div>;
}
