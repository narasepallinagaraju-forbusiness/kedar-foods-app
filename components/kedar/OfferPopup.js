'use client'

import { useState, useEffect } from 'react'
import { X } from 'lucide-react'
import { safeLink } from '@/lib/api/safe-link.mjs'

const SEEN_KEY = 'kedar_offer_popup_seen'

// First-visit offer popup: appears 1.5s after landing, once per session.
export default function OfferPopup({ offer, loaded }) {
  const [open, setOpen] = useState(false)

  useEffect(() => {
    if (!loaded || !offer?.enabled) return
    let seen = false
    try { seen = sessionStorage.getItem(SEEN_KEY) === '1' } catch {}
    if (seen) return
    const t = setTimeout(() => {
      setOpen(true)
      try { sessionStorage.setItem(SEEN_KEY, '1') } catch {}
    }, 1500)
    return () => clearTimeout(t)
  }, [loaded, offer?.enabled])

  const close = () => {
    try { sessionStorage.setItem(SEEN_KEY, '1') } catch {}
    setOpen(false)
  }

  if (!open || !offer?.enabled) return null
  const offerLink = safeLink(offer.link)

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center px-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={close} />
      <div className="relative w-full max-w-md overflow-hidden rounded-2xl bg-white shadow-2xl">
        <button
          onClick={close}
          aria-label="Close offer"
          className="offer-popup-close absolute right-3 top-3 z-10 flex h-8 w-8 items-center justify-center rounded-full bg-white/90 text-gray-700 shadow transition hover:bg-white"
        >
          <X className="h-5 w-5" />
        </button>
        <div className="p-5 text-center">
          <h3 className="text-xl font-extrabold text-gray-900">{offer.text}</h3>
          {offerLink && (
            <a
              href={offerLink}
              onClick={close}
              className="mt-4 inline-flex items-center rounded-full bg-amber-500 px-6 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-amber-600"
            >
              View offer
            </a>
          )}
        </div>
      </div>
    </div>
  )
}
