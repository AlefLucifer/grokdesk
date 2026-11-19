import Link from 'next/link';
import { Bear } from '@/components/brand';

export default function NotFound() {
  return <main className="shell inner-page" id="main"><div className="empty-state"><span className="empty-icon"><Bear size={46} /></span><h1>این صفحه پیدا نشد</h1><p>ممکن است محصول دیگر در فروشگاه موجود نباشد.</p><Link className="button primary" href="/shop">بازگشت به محصولات</Link></div></main>;
}
