export const brand = 'نینیک سایت';
export const description = 'نینیک سایت؛ فروشگاه لوازم کودک و نوزاد، اسباب‌بازی، پوشاک کودک و بازی‌های آموزشی. دسته‌بندی‌ها را ببینید و خریدتان را انتخاب کنید.';

export function demoMode() {
  return process.env.NINIK_DEMO_MODE === '1' && !process.env.VERCEL;
}

export function persistentStorage() {
  return demoMode() || Boolean(process.env.DATABASE_URL || (!process.env.VERCEL && process.env.NINIK_DATA_DIR));
}

export function ordersEnabled() {
  return demoMode() || (persistentStorage() && process.env.NINIK_ENABLE_ORDERS === '1');
}

export function browserDemoMode() {
  return process.env.NINIK_BROWSER_DEMO === '1' && !persistentStorage();
}

// An unset SITE_URL keeps preview and incomplete deployments out of the index.
export function publicUrl() {
  if (demoMode() || browserDemoMode() || !process.env.SITE_URL) return null;
  try {
    const url = new URL(process.env.SITE_URL);
    return url.protocol === 'https:' && !url.username && !url.password && url.pathname === '/' && !url.search && !url.hash ? url.origin : null;
  } catch {
    return null;
  }
}
