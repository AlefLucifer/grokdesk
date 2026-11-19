import { StoreProvider } from '@/components/store-context';
import { Footer, Header } from '@/components/shop-chrome';
import { getCatalog } from '@/lib/store';

export default async function StoreLayout({ children }: { children: React.ReactNode }) {
  const products = await getCatalog();
  return <StoreProvider products={products}>
    <Header />
    <main id="main" tabIndex={-1}>{children}</main>
    <Footer />
  </StoreProvider>;
}
