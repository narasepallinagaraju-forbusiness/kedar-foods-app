'use client'

import { getCatalogImageUrl } from '@/lib/api/catalog.mjs'

export default function ProductCard({ product }) {
  const quantities = Array.isArray(product.quantities) ? product.quantities : []
  const imageUrl = getCatalogImageUrl(product.thumbnailKey)

  return (
    <article className="overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
      <div className="product-card-image relative overflow-hidden bg-gray-100">
        {imageUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={imageUrl} alt={product.name} loading="lazy" className="h-full w-full object-cover" />
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-gray-400">No image available</div>
        )}
        <span className="absolute left-3 top-3 rounded-full bg-white/95 px-2.5 py-1 text-xs font-semibold text-gray-700 shadow-sm">
          {product.brand}
        </span>
      </div>

      <div className="p-4">
        <p className="text-xs font-medium text-amber-700">{product.category}</p>
        <h2 className="mt-1 line-clamp-2 min-h-12 text-sm font-bold text-gray-900">
          <a href={`/products/${encodeURIComponent(product.slug)}`} className="hover:text-amber-600">
            {product.name}
          </a>
        </h2>
        <p className="mt-2 text-xs text-gray-500">SKU: {product.sku}</p>

        {quantities.length > 0 && (
          <p className="mt-3 text-xs text-gray-600">
            <span className="font-semibold">Pack sizes:</span> {quantities.join(', ')}
          </p>
        )}
      </div>
    </article>
  )
}
