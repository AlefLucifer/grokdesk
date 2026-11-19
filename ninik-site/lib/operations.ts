import { nextStatuses, shippingPrice, statuses, type Order, type OrderStatus, type Product } from './catalog';
import { StoreError } from './store-error';
import { object, parseCustomer, parseLines, parseProduct } from './validation';

export type StoreState = { products: Product[]; orders: Order[] };

export function saveProduct(state: StoreState, data: Record<string, unknown>) {
  const product = parseProduct(object(data.product));
  const index = state.products.findIndex((existing) => existing.slug === product.slug);
  if (data.operation === 'create') {
    if (index >= 0) throw new StoreError('این شناسه قبلاً استفاده شده است.', 409);
    state.products.push(product);
  } else if (data.operation === 'update') {
    if (index < 0) throw new StoreError('محصول پیدا نشد.', 404);
    state.products[index] = product;
  } else throw new StoreError('عملیات معتبر نیست.');
}

export function updateOrder(state: StoreState, data: Record<string, unknown>) {
  const status = data.status as OrderStatus;
  if (typeof status !== 'string' || !Object.hasOwn(statuses, status)) throw new StoreError('وضعیت سفارش معتبر نیست.');
  const order = state.orders.find((item) => item.id === data.id);
  if (!order) throw new StoreError('سفارش پیدا نشد.', 404);
  if (!nextStatuses[order.status].includes(status)) throw new StoreError('این تغییر برای وضعیت فعلی سفارش مجاز نیست.', 409);
  order.status = status;
  if (status === 'cancelled') {
    for (const line of order.lines) {
      const product = state.products.find((item) => item.slug === line.slug);
      if (product) product.stock += line.quantity;
    }
  }
}

export function appendOrder(state: StoreState, data: Record<string, unknown>, id: string, demo: boolean): Order {
  const items = parseLines(data.lines);
  const customer = parseCustomer(data.customer, demo);
  const lines = items.map(({ slug, quantity, price }) => {
    const product = state.products.find((item) => item.slug === slug && item.active);
    if (!product || quantity > product.stock) throw new StoreError(`موجودی «${product?.name ?? 'یکی از محصولات'}» کافی نیست. سبدتان را به‌روز کنید.`, 409);
    if (price !== product.price) throw new StoreError(`قیمت «${product.name}» تغییر کرده است. سبدتان را به‌روز کنید.`, 409);
    product.stock -= quantity;
    return { slug, quantity, price: product.price, name: product.name };
  });
  const subtotal = lines.reduce((sum, line) => sum + line.price * line.quantity, 0);
  const shipping = shippingPrice(subtotal);
  const order: Order = { id, customer, lines, subtotal, shipping, total: subtotal + shipping, createdAt: new Date().toISOString(), status: 'new' };
  state.orders.unshift(order);
  return order;
}
