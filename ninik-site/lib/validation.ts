import { asciiDigits, categories, maxLines, maxQuantity, type Order, type Product } from './catalog';
import { StoreError } from './store-error';

export function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new StoreError('اطلاعات ارسال‌شده معتبر نیست.');
  return value as Record<string, unknown>;
}

function text(value: unknown, min: number, max: number, label: string) {
  const result = typeof value === 'string' ? value.trim() : '';
  if (result.length < min || result.length > max) throw new StoreError(`${label} را درست وارد کنید.`);
  return result;
}

function integer(value: unknown, min: number, max: number, label: string) {
  const result = typeof value === 'number' ? value : NaN;
  if (!Number.isSafeInteger(result) || result < min || result > max) throw new StoreError(`${label} معتبر نیست.`);
  return result;
}

export const slugPattern = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

export function parseProduct(data: Record<string, unknown>): Product {
  const slug = text(data.slug, 2, 72, 'شناسه');
  if (!slugPattern.test(slug)) throw new StoreError('شناسه باید شامل حروف کوچک انگلیسی، عدد یا خط تیره باشد.');
  const category = categories.find((option) => option.id === data.category)?.id;
  if (!category) throw new StoreError('یک دسته‌بندی انتخاب کنید.');
  const image = text(data.image, 5, 1024, 'نشانی عکس');
  if (!/^\/images\/[a-z0-9-]+\.(?:webp|png|jpe?g)$/i.test(image)) {
    try {
      const url = new URL(image);
      if (url.protocol !== 'https:' || url.username || url.password) throw new Error();
    } catch { throw new StoreError('آدرس تصویر باید HTTPS یا یکی از عکس‌های فروشگاه باشد.'); }
  }
  const price = integer(data.price, 1, 999_999_999, 'قیمت');
  return {
    slug, category, image, price,
    oldPrice: data.oldPrice === null ? null : integer(data.oldPrice, price + 1, 999_999_999, 'قیمت قبلی'),
    name: text(data.name, 3, 100, 'نام محصول'),
    description: text(data.description, 10, 1600, 'توضیحات'),
    age: text(data.age, 0, 60, 'سن پیشنهادی'),
    stock: integer(data.stock, 0, 1_000_000, 'موجودی'),
    badge: text(data.badge, 0, 28, 'برچسب'),
    active: data.active === true,
  };
}

export function parseLines(value: unknown) {
  if (!Array.isArray(value) || value.length === 0 || value.length > maxLines) throw new StoreError('سبد خرید خالی است یا تعداد محصولات آن بیشتر از حد مجاز است.');
  const lines = value.map((line) => {
    const data = object(line);
    const slug = text(data.slug, 2, 72, 'شناسهٔ محصول');
    if (!slugPattern.test(slug)) throw new StoreError('محصول معتبر نیست.');
    return { slug, quantity: integer(data.quantity, 1, maxQuantity, 'تعداد'), price: integer(data.price, 1, 999_999_999, 'قیمت') };
  });
  if (new Set(lines.map((line) => line.slug)).size !== lines.length) throw new StoreError('یک محصول چند بار در سبد تکرار شده است.');
  return lines;
}

export function parseCustomer(value: unknown, demo: boolean): Order['customer'] {
  if (demo) return { name: 'خریدار نمونه', phone: '09000000000', city: 'شهر نمونه', address: 'نشانی آزمایشی — برای این سفارش ارسال انجام نمی‌شود.' };
  const data = object(value);
  const phone = asciiDigits(text(data.phone, 11, 18, 'شمارهٔ موبایل')).replace(/[\s-]/g, '');
  if (!/^09[0-9]{9}$/.test(phone)) throw new StoreError('شمارهٔ موبایل را به‌صورت ۱۱ رقم و با ۰۹ وارد کنید.');
  return { name: text(data.name, 3, 100, 'نام و نام خانوادگی'), phone, city: text(data.city, 2, 80, 'شهر'), address: text(data.address, 10, 500, 'نشانی') };
}
