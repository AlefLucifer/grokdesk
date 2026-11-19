import type { CategoryId } from '@/lib/catalog';

export function CategoryArt({ category }: { category: CategoryId }) {
  const art = {
    toys: <>
      <circle cx="31" cy="22" r="11" fill="#D98A77"/><circle cx="66" cy="22" r="11" fill="#D98A77"/>
      <circle cx="31" cy="22" r="5" fill="#F5BAAD"/><circle cx="66" cy="22" r="5" fill="#F5BAAD"/>
      <path d="M48 16c16 0 27 11 27 24S64 60 48 60 22 52 22 40s11-24 26-24Z" fill="#E5A28D"/>
      <ellipse cx="48" cy="45" rx="13" ry="9" fill="#FCE0C8"/><circle cx="37" cy="36" r="2" fill="#593F3B"/><circle cx="59" cy="36" r="2" fill="#593F3B"/>
      <path d="M44 41q4-3 8 0l-4 4Z" fill="#795047"/><path d="M45 48q3 3 6 0" stroke="#795047" strokeWidth="1.5" fill="none" strokeLinecap="round"/>
      <path d="m37 60-11 10 13 5 9-10 9 10 13-5-11-10-11 4Z" fill="#C86482"/>
      <circle cx="48" cy="64" r="4" fill="#E791A8"/>
    </>,
    clothing: <>
      <path d="M37 17 23 21 12 41l13 8 7-10v23c0 7 9 13 16 13s16-6 16-13V39l7 10 13-8-11-20-14-4c-3 13-19 13-22 0Z" fill="#B5A1D5"/>
      <path d="M38 18c3 11 17 11 20 0" stroke="#8A6FAD" strokeWidth="2.2" strokeLinecap="round" fill="none"/>
      <path d="M33 56q15 0 15 13 0-13 15-13" stroke="#8A6FAD" strokeWidth="2" fill="none" strokeLinecap="round"/>
      <path d="M47.5 49c-16-9-7-16 .5-10 7-6 16 1-.5 10Z" fill="#FBE4EB"/>
      <circle cx="48" cy="70" r="1.4" fill="#FAF0FB"/>
    </>,
    essentials: <>
      <g transform="rotate(13 48 45)"><path d="M43 18v-3a5 5 0 0 1 10 0v3l7 11H36Z" fill="#E2A57C"/>
      <rect x="33" y="27" width="30" height="13" rx="5" fill="#DD986E"/>
      <rect x="34" y="38" width="28" height="33" rx="8" fill="#F6C291"/>
      <path d="M53 45h5m-5 7h5m-5 7h5" stroke="#A36C51" strokeWidth="1.7" strokeLinecap="round"/>
      <path d="M44 57c-10-6-4-11 0-7 5-4 10 1 0 7Z" fill="#FFF1E2"/></g>
      <path d="M22 28v8m-4-4h8m45 30v9m-4.5-4.5h9" stroke="#E2A57C" strokeWidth="2" strokeLinecap="round"/>
    </>,
    bath: <>
      <path d="M26 53c-5-8-2-19 3-23l-7-4 11-4a11 11 0 1 1 10 17c16-9 28-3 28 9 0 10-10 17-23 17-10 0-18-4-22-12Z" fill="#F4C768"/>
      <path d="M24 25l10 2-5 6-8-3c-3-2-2-4 3-5Z" fill="#DF966B"/>
      <circle cx="37" cy="24" r="1.9" fill="#5A493C"/><path d="M45 49q9 8 17-1" fill="none" stroke="#D89A4C" strokeWidth="2.2" strokeLinecap="round"/>
      <circle cx="69" cy="22" r="5" fill="#A6CFC0"/><circle cx="80" cy="30" r="3" fill="#A6CFC0"/>
      <path d="M17 70q5 4 10 0t10 0t10 0t10 0t10 0t10 0" fill="none" stroke="#87B9A5" strokeWidth="2.5" strokeLinecap="round"/>
    </>,
    learning: <>
      <rect x="16" y="38" width="32" height="29" rx="5" transform="rotate(-10 32 52)" fill="#E5AD64"/>
      <path d="m47 44 14-24c2-3 5-3 7 0l15 25c1 3-1 5-4 5H51c-4 0-6-3-4-6Z" fill="#95B6A7"/>
      <circle cx="63" cy="59" r="14" fill="#DC93A8"/><circle cx="63" cy="59" r="5.5" fill="#FAE7DA"/>
      <path d="m29 55 3-9 4 8m-6 0 5-1m4-33v10m-5-5h10" fill="none" stroke="#FFF4DE" strokeWidth="2.1" strokeLinecap="round"/>
    </>,
  }[category];
  return <svg viewBox="0 0 96 83" width="91" height="79" fill="none" aria-hidden="true">{art}</svg>;
}
