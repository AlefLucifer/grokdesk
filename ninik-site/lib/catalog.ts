export const categories = [
  { id: 'toys', name: 'اسباب‌بازی', color: 'rose', note: 'برای خنده و بازی', title: 'اسباب‌بازی کودک', intro: 'از عروسک‌های نرم برای بازی‌های خیالی تا هدیه‌های کوچک برای تولد. در صفحهٔ هر اسباب‌بازی می‌توانید توضیحات و ردهٔ سنی پیشنهادی آن را ببینید.' },
  { id: 'clothing', name: 'پوشاک کودک', color: 'lilac', note: 'نرم و دوست‌داشتنی', title: 'پوشاک کودک و نوزاد', intro: 'سرهمی و پاپوش برای روزهای اول نوزاد. برای مقایسه، ردهٔ سنی و جنس درج‌شده در توضیحات هر لباس را در نظر بگیرید.' },
  { id: 'essentials', name: 'لوازم نوزاد', color: 'peach', note: 'همراه روزهای اول', title: 'لوازم نوزاد', intro: 'وسایل روزمرهٔ نوزاد، از شیشه‌شیر تا کاسه و قاشق کودک. گنجایش، کاربرد و توضیحات شست‌وشوی محصول را پیش از انتخاب بررسی کنید.' },
  { id: 'bath', name: 'حمام و بهداشت', color: 'mint', note: 'وقت آب‌بازی', title: 'لوازم حمام و بهداشت کودک', intro: 'حوله و لوازم حمام برای مراقبت روزمره از کودک. برای انتخاب حولهٔ کلاه‌دار، به جنس و ردهٔ سنی درج‌شده در صفحهٔ محصول توجه کنید.' },
  { id: 'learning', name: 'بازی آموزشی', color: 'butter', note: 'بازی و یادگیری', title: 'بازی‌های آموزشی کودک', intro: 'رنگین‌کمان چوبی و جورچین‌های هندسی برای بازی با رنگ‌ها و شکل‌ها. پیش از انتخاب، ردهٔ سنی و اندازهٔ قطعه‌ها را بررسی کنید.' },
] as const;

export type CategoryId = (typeof categories)[number]['id'];
export type Product = {
  slug: string;
  name: string;
  description: string;
  age: string;
  category: CategoryId;
  price: number;
  oldPrice: number | null;
  stock: number;
  image: string;
  badge: string;
  active: boolean;
};

export const productImages = ['teddy', 'rainbow', 'romper', 'bottle', 'towel', 'sorter', 'booties', 'bowl'].map((name) => `/images/${name}.webp`);

const sample = (data: Omit<Product, 'active'>): Product => ({ ...data, active: true });
export const seedProducts: Product[] = [
  sample({ slug: 'fluffy-teddy', name: 'عروسک خرسی پشمالو', description: 'یک دوست نرم و بغلی برای وقت بازی و داستان‌خوانی. رنگ خنثی و بافت پشمالوی خرس، آن را به هدیه‌ای دوست‌داشتنی برای اتاق کودک تبدیل می‌کند.', age: '۳ سال به بالا', category: 'toys', price: 645000, oldPrice: 780000, stock: 18, image: productImages[0], badge: 'پرفروش' }),
  sample({ slug: 'wooden-rainbow', name: 'رنگین‌کمان چوبی مونته‌سوری', description: 'شش قوس رنگی که هر بار به شکلی تازه کنار هم چیده می‌شوند. برای ساخت پل، برج و هر چیزی که کودک در خیال خود می‌بیند.', age: '۳ سال به بالا', category: 'learning', price: 890000, oldPrice: null, stock: 14, image: productImages[1], badge: 'انتخاب نینیک' }),
  sample({ slug: 'cotton-romper', name: 'سرهمی نخی صورتی نوزاد', description: 'سرهمی سبک و نرم با پارچهٔ نخی راه‌راه و دکمه‌های جلویی؛ انتخابی ساده برای لباس روزمره یا هدیهٔ نوزاد.', age: '۳ تا ۶ ماه', category: 'clothing', price: 495000, oldPrice: 590000, stock: 23, image: productImages[2], badge: '' }),
  sample({ slug: 'silicone-bottle', name: 'شیشه شیر سیلیکونی نوزاد', description: 'بطری سبک با بدنهٔ نرم و طراحی ساده، با گنجایش ۱۶۰ میلی‌لیتر. بعد از هر بار مصرف طبق دستور سازنده شسته شود.', age: 'نوزاد', category: 'essentials', price: 345000, oldPrice: null, stock: 12, image: productImages[3], badge: 'جدید' }),
  sample({ slug: 'bear-hood-towel', name: 'حوله کلاه‌دار خرسی', description: 'حولهٔ نخی سبز با کلاه گوش‌دار، برای اینکه خشک‌کردن کودک بعد از حمام راحت‌تر باشد.', age: '۰ تا ۲ سال', category: 'bath', price: 620000, oldPrice: null, stock: 10, image: productImages[4], badge: '' }),
  sample({ slug: 'wooden-shape-sorter', name: 'مکعب چوبی جورچین اشکال', description: 'مکعبی چوبی با قطعه‌های هندسی رنگی. کودک با امتحان‌کردن قطعه‌ها، شکل‌های همسان را پیدا می‌کند.', age: '۳ سال به بالا', category: 'learning', price: 780000, oldPrice: 890000, stock: 7, image: productImages[5], badge: '' }),
  sample({ slug: 'knitted-booties', name: 'پاپوش بافتنی نوزاد', description: 'یک جفت پاپوش نرم و بافتنی به رنگ آبی ملایم برای گرم‌ماندن پاهای کوچک در روزهای خنک.', age: '۰ تا ۶ ماه', category: 'clothing', price: 325000, oldPrice: null, stock: 8, image: productImages[6], badge: '' }),
  sample({ slug: 'silicone-mealtime-set', name: 'ست غذاخوری سیلیکونی', description: 'ست شامل کاسه، قاشق و لیوان کوچک با رنگ یاسی؛ مناسب برای تمرین غذاخوردن با نظارت بزرگسال.', age: '۶ ماه به بالا', category: 'essentials', price: 545000, oldPrice: null, stock: 15, image: productImages[7], badge: 'جدید' }),
];

export const categoryName = (id: CategoryId) => categories.find((item) => item.id === id)?.name ?? '';
export const money = (amount: number) => new Intl.NumberFormat('fa-IR').format(amount);
export const freeShippingAt = 2_000_000;
export const shippingPrice = (subtotal: number) => subtotal >= freeShippingAt || subtotal === 0 ? 0 : 85000;
export const maxQuantity = 10;
export const maxLines = 20;

export function asciiDigits(value: string) {
  return value.replace(/[۰-۹٠-٩]/g, (n) => String(n.charCodeAt(0) & 15));
}

export function searchText(value: string) {
  return asciiDigits(value).replace(/ي/g, 'ی').replace(/ك/g, 'ک').replace(/[\u200c\u200d]/g, ' ').replace(/\s+/g, ' ').trim().toLowerCase();
}

export function matchesProduct(product: Product, query: string) {
  const haystack = searchText(`${product.name} ${categoryName(product.category)} ${product.description} ${product.age}`);
  return searchText(query).split(' ').every((part) => haystack.includes(part));
}

export const statuses = { new: 'ثبت‌شده', preparing: 'در حال آماده‌سازی', shipped: 'ارسال‌شده', cancelled: 'لغوشده' } as const;
export type OrderStatus = keyof typeof statuses;
export const nextStatuses: Record<OrderStatus, OrderStatus[]> = {
  new: ['preparing', 'cancelled'], preparing: ['shipped', 'cancelled'], shipped: [], cancelled: [],
};
export type Order = {
  id: string;
  createdAt: string;
  status: OrderStatus;
  subtotal: number;
  shipping: number;
  total: number;
  customer: { name: string; phone: string; city: string; address: string };
  lines: { slug: string; name: string; quantity: number; price: number }[];
};
