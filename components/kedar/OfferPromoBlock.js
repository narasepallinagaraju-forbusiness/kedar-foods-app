'use client'

import { Sparkles, BadgePercent, MessageCircle } from 'lucide-react'
import { buildOfferWaLink } from '@/lib/data'

// Conditional promo block shown between the header and the hero carousel.
// Returns null (fully collapsed) when the offer is inactive.
export default function OfferPromoBlock({ offer, loaded }) {
  if (!loaded || !offer?.isActive) return null

  const lines = (offer.description || '')
    .split('|')
    .map((s) => s.trim())
    .filter(Boolean)

  return (
    <section className="border-b border-amber-100 bg-gradient-to-r from-amber-50 via-orange-50 to-amber-50">
      <div className="mx-auto grid max-w-7xl items-center gap-6 px-4 py-6 sm:px-6 md:grid-cols-2 md:py-8">
        {/* Poster */}
        <div className="flex justify-center">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={offer.image}
            alt={offer.headline}
            className="max-h-[380px] w-auto rounded-xl object-contain shadow-md"
          />
        </div>

        {/* Details */}
        <div className="text-center md:text-left">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-500 px-3 py-1 text-xs font-bold uppercase tracking-wide text-white">
            <Sparkles className="h-3.5 w-3.5" /> Limited Time Offer
          </span>
          <h2 className="mt-3 text-3xl font-extrabold leading-tight text-gray-900 sm:text-4xl">{offer.headline}</h2>

          <ul className="mt-5 space-y-2.5">
            {lines.map((l, i) => (
              <li key={i} className="flex items-center justify-center gap-2 text-base font-semibold text-gray-800 md:justify-start">
                <BadgePercent className="h-5 w-5 shrink-0 text-amber-600" /> {l}
              </li>
            ))}
          </ul>

          <a
            href={buildOfferWaLink(offer)}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-6 inline-flex items-center gap-2 rounded-full bg-emerald-600 px-6 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-700"
          >
            <MessageCircle className="h-4 w-4" /> Claim Anniversary Offer on WhatsApp
          </a>
        </div>
      </div>
    </section>
  )
}
