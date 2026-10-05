'use client'

import { MessageCircle } from 'lucide-react'
import { buildWaLink, getQuantities } from '@/lib/data'

export default function ProductCard({ product }) {
  const quantities = getQuantities(product)

  return (
    <article className="overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
      <div className="relative aspect-square overflow-hidden bg-gray-100">
        {product.image ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={product.image} alt={product.name} className="h-full w-full object-cover" />
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-gray-400">No image available</div>
        )}
        <span className="absolute left-3 top-3 rounded-full bg-white/95 px-2.5 py-1 text-xs font-semibold text-gray-700 shadow-sm">
          {product.brand}
        </span>
      </div>

      <div className="p-4">
        <p className="text-xs font-medium text-amber-700">{product.category}</p>
        <h2 className="mt-1 line-clamp-2 min-h-12 text-sm font-bold text-gray-900">{product.name}</h2>
        <p className="mt-2 line-clamp-2 min-h-10 text-xs text-gray-500">{product.description}</p>

        {quantities.length > 0 && (
          <p className="mt-3 text-xs text-gray-600">
            <span className="font-semibold">Pack sizes:</span> {quantities.join(', ')}
          </p>
        )}

        <a
          href={buildWaLink(product, quantities[0])}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-lg bg-emerald-600 px-3 py-2.5 text-sm font-semibold text-white transition hover:bg-emerald-700"
        >
          <MessageCircle className="h-4 w-4" /> Enquire on WhatsApp
        </a>
      </div>
    </article>
  )
}
