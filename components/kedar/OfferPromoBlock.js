'use client'

import { Sparkles } from 'lucide-react'
import { safeLink } from '@/lib/api/safe-link.mjs'
import { getCatalogImageUrl } from '@/lib/api/catalog.mjs'

// Conditional promo block shown between the header and the hero carousel.
// Returns null (fully collapsed) when the offer is inactive.
export default function OfferPromoBlock({ offer, loaded }) {
  if (!loaded || !offer?.enabled) return null
  const offerLink = safeLink(offer.link)
  const posterUrl =
    typeof offer.image === 'string' && offer.image.startsWith('media/offer/')
      ? getCatalogImageUrl(offer.image)
      : null

  return (
    <section className="dark-promo-block border-b border-amber-100 bg-gradient-to-r from-amber-50 via-orange-50 to-amber-50">
      <div className="mx-auto flex max-w-7xl flex-col items-center justify-center gap-6 px-4 py-6 sm:px-6 md:flex-row md:py-8">
        {posterUrl && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={posterUrl}
            alt=""
            decoding="async"
            style={{ maxHeight: 220, maxWidth: '100%', width: 'auto', height: 'auto', objectFit: 'contain' }}
            className="rounded-xl shadow-sm"
          />
        )}
        <div className="text-center">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-500 px-3 py-1 text-xs font-bold uppercase tracking-wide text-white">
            <Sparkles className="h-3.5 w-3.5" /> Special Offer
          </span>
          <h2 className="mt-3 text-2xl font-extrabold leading-tight text-gray-900 sm:text-3xl">{offer.text}</h2>
          {offerLink && (
            <a
              href={offerLink}
              className="mt-4 inline-flex items-center rounded-full bg-amber-500 px-6 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-amber-600"
            >
              View offer
            </a>
          )}
        </div>
      </div>
    </section>
  )
}
