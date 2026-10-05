'use client'

// Sitewide promotional offer, persisted to localStorage so admin edits
// instantly reflect on the live site (no server reboot).

import { useState, useEffect, useCallback } from 'react'

const STORAGE_KEY = 'kedar_site_offer_v2'

export const DEFAULT_OFFER = {
  isActive: true,
  image: '/anniversary-offer.png',
  headline: 'Shop Anniversary Celebration!',
  description: 'Purchase ₹5,000 - Get 2% Discount | Purchase ₹10,000 - Get 3% Discount',
}

export function useSiteOffer() {
  const [offer, setOffer] = useState(DEFAULT_OFFER)
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    try {
      const raw = typeof window !== 'undefined' && window.localStorage.getItem(STORAGE_KEY)
      if (raw) {
        const stored = JSON.parse(raw)
        // Browser storage must hydrate after the initial server/client render.
        // eslint-disable-next-line react-hooks/set-state-in-effect
        if (stored && typeof stored === 'object') setOffer({ ...DEFAULT_OFFER, ...stored })
      }
    } catch (e) {
      console.error('Failed to read site offer', e)
    }
    setLoaded(true)
  }, [])

  const updateOffer = useCallback((patch) => {
    setOffer((prev) => {
      const next = { ...prev, ...patch }
      try {
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
      } catch (e) {
        console.error('Failed to persist site offer', e)
      }
      return next
    })
  }, [])

  const resetOffer = useCallback(() => {
    try {
      window.localStorage.removeItem(STORAGE_KEY)
    } catch (e) {
      console.error('Failed to reset site offer', e)
    }
    setOffer(DEFAULT_OFFER)
  }, [])

  return { offer, loaded, updateOffer, resetOffer }
}
