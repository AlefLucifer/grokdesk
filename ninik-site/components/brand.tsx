import Link from 'next/link';
import { brand } from '@/lib/site';

export function Bear({ size = 30 }: { size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 40 40" fill="none" aria-hidden="true">
    <path d="M9.5 17a6.1 6.1 0 1 1 7-8.9m7 0a6.1 6.1 0 1 1 7 8.9" fill="currentColor" opacity=".42"/>
    <path d="M9.5 17a6.1 6.1 0 1 1 7-8.9m7 0a6.1 6.1 0 1 1 7 8.9" stroke="currentColor" strokeWidth="2.15" strokeLinecap="round"/>
    <path d="M20 10c-7.6 0-13.7 5.8-13.7 12.8C6.3 30 12.4 34 20 34s13.7-4 13.7-11.2C33.7 15.8 27.6 10 20 10Z" fill="currentColor" opacity=".18"/>
    <path d="M20 10c-7.6 0-13.7 5.8-13.7 12.8C6.3 30 12.4 34 20 34s13.7-4 13.7-11.2C33.7 15.8 27.6 10 20 10Z" stroke="currentColor" strokeWidth="2.15"/>
    <circle cx="14.8" cy="22" r="1.35" fill="currentColor"/><circle cx="25.2" cy="22" r="1.35" fill="currentColor"/>
    <path d="M18.3 24.1c0-.9 3.4-.9 3.4 0 0 .7-1.1 1.5-1.7 1.5s-1.7-.8-1.7-1.5Z" fill="currentColor"/>
    <path d="M17.8 28.2c1.2 1 3.2 1 4.4 0" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
  </svg>;
}

export function Brand() {
  return <Link href="/" className="brand" aria-label={`${brand} — خانه`}>
    <span className="brand-mark"><Bear /></span>
    <span className="brand-text"><strong>{brand}</strong><small lang="en" dir="ltr">NINIK SHOP</small></span>
  </Link>;
}
