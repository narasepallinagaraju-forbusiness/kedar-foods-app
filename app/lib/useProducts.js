'use client'

// Local-state product store with localStorage persistence.
// Admin edits are merged over the base mock data and survive page reloads
// on the same browser. Swap this for an API-backed store in Phase 2.

import { useState, useEffect, useCallback } from 'react'
import { PRODUCTS } from '@/lib/data'

const STORAGE_KEY = 'kedar_products_v1'

export function useProducts() {
  const [products, setProducts] = useState(PRODUCTS)
  const [loaded, setLoaded] = useState(false)

  // Hydrate from localStorage after mount to avoid SSR mismatch.
  useEffect(() => {
    try {
      const raw = typeof window !== 'undefined' && window.localStorage.getItem(STORAGE_KEY)
      if (raw) {
        const stored = JSON.parse(raw)
        // Browser storage must hydrate after the initial server/client render.
        // eslint-disable-next-line react-hooks/set-state-in-effect
        if (Array.isArray(stored) && stored.length) setProducts(stored)
      }
    } catch (e) {
      console.error('Failed to read stored products', e)
    }
    setLoaded(true)
  }, [])

  const persist = useCallback((next) => {
    setProducts(next)
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
    } catch (e) {
      console.error('Failed to persist products', e)
    }
  }, [])

  const updateProduct = useCallback((id, patch) => {
    setProducts((prev) => {
      const next = prev.map((p) => (p.id === id ? { ...p, ...patch } : p))
      try {
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
      } catch (e) {
        console.error('Failed to persist products', e)
      }
      return next
    })
  }, [])

  const addProduct = useCallback((product) => {
    setProducts((prev) => {
      const next = [...prev, product]
      try {
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
      } catch (e) {
        console.error('Failed to persist products', e)
      }
      return next
    })
  }, [])

  const resetProducts = useCallback(() => {
    try {
      window.localStorage.removeItem(STORAGE_KEY)
    } catch (e) {
      console.error('Failed to reset products', e)
    }
    setProducts(PRODUCTS)
  }, [])

  return { products, loaded, addProduct, updateProduct, resetProducts, persist }
}
