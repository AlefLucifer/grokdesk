import type { Metadata } from 'next';
import Link from 'next/link';
import { ArrowLeft, ChevronLeft, HeartHandshake } from 'lucide-react';
import { freeShippingAt, money, shippingPrice } from '@/lib/catalog';
import { publicUrl } from '@/lib/site';

export function generateMetadata(): Metadata {
  return { title: 'راهنمای خرید و ارسال', description: 'روش ثبت سفارش، هزینهٔ ارسال و حریم خصوصی در فروشگاه نینیک سایت.', alternates: publicUrl() ? { canonical: '/guide' } : undefined };
}

export default function Guide() {
  return <div className="shell inner-page guide-page">
    <div className="breadcrumbs"><Link href="/">خانه</Link><ChevronLeft size={15} /><span>راهنمای خرید</span></div>
    <div className="page-intro"><p className="eyebrow"><HeartHandshake size={18} /> همراه شما در خرید</p><h1>راهنمای خرید نینیک</h1><p>چطور خرید کنیم و بعد از ثبت سفارش چه اتفاقی می‌افتد؟</p></div>
    <div className="guide-content">
      <section id="how-to-buy"><h2>۱. انتخاب و ثبت سفارش</h2><p>محصول را به سبد خرید اضافه کنید. در مرحلهٔ ثبت سفارش، جمع کالاها و هزینهٔ ارسال را می‌بینید. پس از ثبت، کد سفارش را نگه دارید.</p></section>
      <section id="shipping"><h2>۲. هزینهٔ ارسال</h2><p>هزینهٔ ارسال {money(shippingPrice(1))} تومان است. ارسال برای سبدهای {money(freeShippingAt)} تومان و بیشتر رایگان است. در نسخهٔ آزمایشی بسته‌ای ارسال نمی‌شود.</p></section>
      <section id="payment"><h2>۳. پرداخت و پیگیری</h2><p>درگاه پرداخت آنلاین هنوز متصل نیست. کد سفارش به معنی پرداخت یا ارسال کالا نیست.</p></section>
      <section id="privacy"><h2>حریم خصوصی</h2><p>سبد خرید و علاقه‌مندی‌ها در مرورگر شما نگهداری می‌شوند. در حالت فروش واقعی، اطلاعات تماس و نشانی برای رسیدگی به سفارش به‌صورت خصوصی در پنل مدیریت نمایش داده می‌شوند. نسخهٔ آزمایشی فقط از اطلاعات نمونه استفاده می‌کند.</p></section>
      <Link href="/shop" className="button primary">رفتن به فروشگاه <ArrowLeft size={18} /></Link>
    </div>
  </div>;
}
