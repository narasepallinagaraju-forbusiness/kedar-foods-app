'use client'

import { useEffect, useState, useSyncExternalStore } from 'react'
import Header from '../components/kedar/Header.js'
import Footer from '../components/kedar/Footer.js'
import { useCatalogIndex, useProduct } from '../app/lib/api/hooks.js'
import { getRelatedProducts } from '../app/lib/api/catalog.mjs'
import { parseProductSlug } from '../app/lib/api/slug.mjs'

const DEFAULT_TITLE = 'Kedar Foods | Wholesale Raw Materials for Bakeries, Cafes & Restaurants'

function subscribeToLocation(callback) {
  window.addEventListener('popstate', callback)
  return () => window.removeEventListener('popstate', callback)
}

function getPathname() {
  return window.location.pathname
}

function getServerPathname() {
  return ''
}

export default function ProductShell() {
  const pathname = useSyncExternalStore(subscribeToLocation, getPathname, getServerPathname)
  const slug = pathname ? parseProductSlug(pathname) : undefined
  const [packSelection, setPackSelection] = useState(null)
  const [imageFailure, setImageFailure] = useState(null)
  const productQuery = useProduct(slug)
  const product = productQuery.data
  const catalogQuery = useCatalogIndex(Boolean(product))
  const quantities = Array.isArray(product?.quantities) ? product.quantities : []
  const mainImageUrl = product?.image?.main ? `/${product.image.main}` : null
  const selectedPack = packSelection && packSelection.productId === product?.id
    ? packSelection.value
    : quantities[0] ?? ''
  const imageFailed = imageFailure?.url === mainImageUrl && imageFailure.failed
  const relatedProducts = product && catalogQuery.data
    ? getRelatedProducts(catalogQuery.data.items, product, 4)
    : []

  useEffect(() => {
    if (product) {
      document.title = `${product.name} | Kedar Foods`
    } else if (slug === null || productQuery.error?.status === 404) {
      document.title = DEFAULT_TITLE
    }

    return () => {
      document.title = DEFAULT_TITLE
    }
  }, [product, slug, productQuery.error])

  const notFound = slug === null || productQuery.error?.status === 404
  const loading = slug === undefined || (Boolean(slug) && productQuery.isLoading)
  const retryableError = Boolean(slug) && productQuery.isError && !notFound

  return (
    <div className="min-h-screen bg-white">
      <Header configEnabled={Boolean(slug)} />
      <main className="mx-auto min-h-[60vh] max-w-7xl px-4 py-8 sm:px-6 sm:py-12">
        <a href="/catalogue" className="text-sm font-semibold text-amber-600 hover:underline">
          ← Back to catalogue
        </a>

        {loading && (
          <p className="py-20 text-center text-gray-500" aria-live="polite">Loading product…</p>
        )}

        {notFound && (
          <section className="py-20 text-center">
            <h1 className="text-2xl font-extrabold text-gray-900">Product not found</h1>
            <p className="mt-2 text-gray-500">This product may have been removed or is no longer available.</p>
          </section>
        )}

        {retryableError && (
          <section className="py-20 text-center" role="alert">
            <h1 className="text-2xl font-extrabold text-gray-900">Unable to load product</h1>
            <p className="mt-2 text-gray-500">{productQuery.error.message}</p>
            <button
              onClick={() => productQuery.refetch()}
              className="mt-4 rounded-full bg-amber-500 px-5 py-2 text-sm font-semibold text-white hover:bg-amber-600"
            >
              Retry
            </button>
          </section>
        )}

        {product && (
          <>
            <article className="mt-6 grid overflow-hidden rounded-3xl border border-gray-200 bg-white shadow-sm md:grid-cols-2">
              <div className="flex min-h-72 items-center justify-center bg-gray-100 p-6 sm:min-h-96 sm:p-10">
                {mainImageUrl && !imageFailed ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={mainImageUrl}
                    alt={product.name}
                    onError={() => setImageFailure({ url: mainImageUrl, failed: true })}
                    className="max-h-[480px] w-full rounded-2xl object-contain"
                  />
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
                {product.sku && <p className="mt-2 text-xs font-medium uppercase tracking-wide text-gray-400">SKU: {product.sku}</p>}
                {product.description && <p className="mt-5 text-base leading-relaxed text-gray-600">{product.description}</p>}

                {quantities.length > 0 && (
                  <section className="mt-7">
                    <label htmlFor="pack-size" className="text-sm font-bold text-gray-900">Available pack sizes</label>
                    <select
                      id="pack-size"
                      value={selectedPack}
                      onChange={(event) =>
                        setPackSelection({ productId: product.id, value: event.target.value })
                      }
                      className="mt-3 block w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm font-semibold text-gray-700"
                    >
                      {quantities.map((quantity) => <option key={quantity} value={quantity}>{quantity}</option>)}
                    </select>
                  </section>
                )}

              </div>
            </article>

            {catalogQuery.isError && (
              <p className="mt-8 text-sm text-gray-500" role="status">
                Related products are temporarily unavailable.
              </p>
            )}
            {relatedProducts.length > 0 && (
              <section className="mt-12">
                <h2 className="text-xl font-bold text-gray-900">Related products</h2>
                <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
                  {relatedProducts.map((related) => (
                    <a
                      key={related.id}
                      href={`/products/${encodeURIComponent(related.slug)}`}
                      className="rounded-xl border border-gray-200 p-4 transition hover:border-amber-400"
                    >
                      <span className="text-xs font-semibold text-amber-700">{related.brand}</span>
                      <span className="mt-1 block font-semibold text-gray-900">{related.name}</span>
                    </a>
                  ))}
                </div>
              </section>
            )}
          </>
        )}
      </main>
      <Footer configEnabled={Boolean(slug)} />
    </div>
  )
}
