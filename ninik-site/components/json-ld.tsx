export function JsonLd({ value }: { value: Record<string, unknown> }) {
  return <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(value).replace(/</g, '\\u003c') }} />;
}

export function BreadcrumbsLd({ origin, items }: { origin: string; items: { path: string; name: string }[] }) {
  return <JsonLd value={{
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: items.map(({ path, name }, index) => ({ '@type': 'ListItem', position: index + 1, name, item: new URL(path, origin).href })),
  }} />;
}
