'use client'

import { useEffect, useState } from 'react'
import Header from '../components/kedar/Header.js'
import Footer from '../components/kedar/Footer.js'
import { buildWaLink, getQuantities } from '../app/lib/data.js'

// TEMPORARY Phase 0 product detail shell; replace its mock fetch with the public product API in Phase 2.
export default function ProductShell() {
  const [status, setStatus] = useState('loading')
  const [product, setProduct] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    const controller = new AbortController()

    async function loadProduct() {
      try {
        const pathname = window.location.pathname.replace(/\/+$/, '')
        const encodedSlug = pathname.split('/').pop()
        const slug = decodeURIComponent(encodedSlug || '')
        const response = await fetch(`/mock-api/products/${encodeURIComponent(slug)}`, {
          signal: controller.signal,
        })

        if (response.status === 404) {
          setStatus('not-found')
          return
        }
        if (!response.ok) {
          throw new Error(`Product request failed with HTTP ${response.status}`)
        }

        setProduct(await response.json())
        setStatus('product')
      } catch (caughtError) {
        if (controller.signal.aborted) return
        setError(caughtError instanceof Error ? caughtError.message : 'Unable to load product.')
        setStatus('error')
      }
    }

    loadProduct()
    return () => controller.abort()
  }, [])

  return (
    <div className="min-h-screen bg-white">
      <Header />
      <main className="mx-auto min-h-[60vh] max-w-7xl px-4 py-8 sm:px-6 sm:py-12">
        <a href="/catalogue" className="text-sm font-semibold text-amber-600 hover:underline">
          ← Back to catalogue
        </a>

        {status === 'loading' && (
          <p className="py-20 text-center text-gray-500" aria-live="polite">Loading product…</p>
        )}

        {status === 'not-found' && (
          <section className="py-20 text-center">
            <h1 className="text-2xl font-extrabold text-gray-900">Product not found</h1>
            <p className="mt-2 text-gray-500">This product may have been removed or is no longer available.</p>
          </section>
        )}

        {status === 'error' && (
          <section className="py-20 text-center" role="alert">
            <h1 className="text-2xl font-extrabold text-gray-900">Unable to load product</h1>
            <p className="mt-2 text-gray-500">{error}</p>
          </section>
        )}

        {status === 'product' && product && (
          <article className="mt-6 grid overflow-hidden rounded-3xl border border-gray-200 bg-white shadow-sm md:grid-cols-2">
            <div className="flex min-h-72 items-center justify-center bg-gray-100 p-6 sm:min-h-96 sm:p-10">
              {product.image ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={product.image} alt={product.name} className="max-h-[480px] w-full rounded-2xl object-contain" />
              ) : (
                <span className="text-sm text-gray-500">Product image unavailable</span>
              )}
            </div>

            <div className="flex flex-col p-6 sm:p-10">
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-bold text-amber-700">{product.brand}</span>
                <span className="rounded-full border border-gray-200 px-3 py-1 text-xs font-semibold text-gray-600">{product.category}</span>
              </div>
              <h1 className="mt-4 text-3xl font-extrabold leading-tight text-gray-900 sm:text-4xl">{product.name}</h1>
              {product.id && <p className="mt-2 text-xs font-medium uppercase tracking-wide text-gray-400">SKU: {product.id}</p>}
              {product.description && <p className="mt-5 text-base leading-relaxed text-gray-600">{product.description}</p>}

              {getQuantities(product).length > 0 && (
                <section className="mt-7">
                  <h2 className="text-sm font-bold text-gray-900">Available pack sizes</h2>
                  <ul className="mt-3 flex flex-wrap gap-2">
                    {getQuantities(product).map((quantity) => (
                      <li key={quantity} className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm font-semibold text-gray-700">
                        {quantity}
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              <a
                href={buildWaLink(product, getQuantities(product)[0])}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-8 inline-flex items-center justify-center rounded-xl bg-emerald-600 px-5 py-3 text-sm font-bold text-white transition hover:bg-emerald-700"
              >
                Enquire on WhatsApp
              </a>
            </div>
          </article>
        )}
      </main>
      <Footer />
    </div>
  )
}
