'use client';

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { seedProducts, type Order } from '@/lib/catalog';
import { appendOrder, saveProduct, updateOrder, type StoreState } from '@/lib/operations';
import { object } from '@/lib/validation';

const storageKey = 'ninik-browser-demo-v1';
const sessionKey = 'ninik-browser-demo-admin';
const initial: StoreState = { products: seedProducts, orders: [] };

type Demo = StoreState & {
  ready: boolean;
  signedIn: boolean;
  manage: (action: string, data: unknown) => Promise<void>;
  placeOrder: (data: Record<string, unknown>) => Order;
};
const Context = createContext<Demo | null>(null);

function stored() {
  try {
    const value = JSON.parse(localStorage.getItem(storageKey) ?? 'null');
    if (Array.isArray(value?.products) && Array.isArray(value?.orders)) return value as StoreState;
  } catch { /* Fall back to sample data. */ }
  return null;
}

// Public demo: all edits and sample orders stay in this browser. This does not
// create an administrative session or send mutations/customer data to Vercel.
export function BrowserDemoProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState(initial);
  const [signedIn, setSignedIn] = useState(false);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    setState(stored() ?? initial);
    try { setSignedIn(sessionStorage.getItem(sessionKey) === 'yes'); } catch { /* Session still works until reload. */ }
    setReady(true);
    function sync(event: StorageEvent) {
      if (event.key === storageKey || event.key === null) setState(stored() ?? initial);
    }
    window.addEventListener('storage', sync);
    return () => window.removeEventListener('storage', sync);
  }, []);

  function edit<T>(fn: (draft: StoreState) => T) {
    const next = structuredClone(stored() ?? state);
    const result = fn(next);
    try { localStorage.setItem(storageKey, JSON.stringify(next)); }
    catch { throw new Error('ذخیره‌سازی مرورگر در دسترس نیست. اجازهٔ ذخیره‌سازی این سایت را بررسی کنید.'); }
    setState(next);
    return result;
  }

  async function manage(action: string, payload: unknown) {
    if (action === 'login' || action === 'logout') {
      const value = action === 'login';
      try { if (value) sessionStorage.setItem(sessionKey, 'yes'); else sessionStorage.removeItem(sessionKey); } catch { /* Use in-memory state. */ }
      setSignedIn(value);
      return;
    }
    if (!signedIn) throw new Error('ابتدا وارد پنل آزمایشی شوید.');
    if (action === 'products') edit((draft) => saveProduct(draft, object(payload)));
    else if (action === 'orders') edit((draft) => updateOrder(draft, object(payload)));
  }

  function placeOrder(data: Record<string, unknown>) {
    const id = 'NNK-' + crypto.randomUUID().replaceAll('-', '').slice(0, 14).toUpperCase();
    return edit((draft) => appendOrder(draft, data, id, true));
  }

  return <Context.Provider value={{ ...state, ready, signedIn, manage, placeOrder }}>{children}</Context.Provider>;
}

export const useBrowserDemo = () => useContext(Context);
