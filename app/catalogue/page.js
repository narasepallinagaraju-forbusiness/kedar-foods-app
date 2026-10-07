'use client'

import { Suspense, useState, useMemo } from 'react'
import { useSearchParams } from 'next/navigation'
import { SlidersHorizontal, X, PackageSearch } from 'lucide-react'
import Header from '@/components/kedar/Header'
import Footer from '@/components/kedar/Footer'
import ProductCard from '@/components/kedar/ProductCard'
import { useCatalogIndex } from '@/lib/api/hooks'
import { filterCatalogItems, paginateCatalog } from '@/lib/api/catalog.mjs'
import { BUSINESS_TYPES } from '@/lib/data'

const PAGE_SIZE = 12
const EMPTY_PRODUCTS = []

function FilterGroup({ title, options, selected, onToggle }) {
  return (
    <div className="border-b border-gray-100 py-4">
      <h4 className="mb-3 text-sm font-bold text-gray-900">{title}</h4>
      <div className="space-y-2">
        {options.map((opt) => (
          <label key={opt} className="flex cursor-pointer items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              checked={selected.includes(opt)}
              onChange={() => onToggle(opt)}
              className="h-4 w-4 rounded border-gray-300 text-amber-500 accent-amber-500"
            />
            {opt}
          </label>
        ))}
      </div>
    </div>
  )
}

function CatalogueInner() {
  const searchParams = useSearchParams()
  const catalogQuery = useCatalogIndex()
  const products = catalogQuery.data?.items ?? EMPTY_PRODUCTS

  const [search, setSearch] = useState(() => searchParams.get('search') || '')
  const [brands, setBrands] = useState([])
  const [categories, setCategories] = useState(() => {
    const category = searchParams.get('category')
    return category ? [category] : []
  })
  const [businesses, setBusinesses] = useState(() => {
    const business = searchParams.get('business')
    return business && BUSINESS_TYPES.includes(business) ? [business] : []
  })
  const [showFilters, setShowFilters] = useState(false)
  const [visiblePages, setVisiblePages] = useState(1)

  const allBrands = useMemo(
    () => [...new Set(products.map((product) => product.brand))].sort(),
    [products],
  )
  const allCategories = useMemo(
    () => [...new Set(products.map((product) => product.category))].sort(),
    [products],
  )

  const toggle = (setter, list, val) => {
    setter(list.includes(val) ? list.filter((x) => x !== val) : [...list, val])
    setVisiblePages(1)
  }

  const filtered = useMemo(() => {
    return filterCatalogItems(products, {
      search,
      brands,
      categories,
      businessTypes: businesses,
    })
  }, [products, search, brands, categories, businesses])
  const visibleProducts = useMemo(() => {
    const pages = []
    for (let page = 0; page < visiblePages; page += 1) {
      pages.push(paginateCatalog(filtered, page, PAGE_SIZE))
    }
    return pages.flat()
  }, [filtered, visiblePages])

  const activeCount = brands.length + categories.length + businesses.length
  const clearAll = () => {
    setBrands([])
    setCategories([])
    setBusinesses([])
    setSearch('')
    setVisiblePages(1)
  }
  const handleSearch = (value) => {
    setSearch(value)
    setVisiblePages(1)
  }

  const Sidebar = (
    <div className="text-sm">
      <div className="flex items-center justify-between">
        <h3 className="text-base font-bold text-gray-900">Filters</h3>
        {activeCount > 0 && (
          <button onClick={clearAll} className="text-xs font-semibold text-amber-600 hover:underline">Clear all</button>
        )}
      </div>
      <FilterGroup title="Business Type" options={BUSINESS_TYPES} selected={businesses} onToggle={(v) => toggle(setBusinesses, businesses, v)} />
      <FilterGroup title="Brand" options={allBrands} selected={brands} onToggle={(v) => toggle(setBrands, brands, v)} />
      <FilterGroup title="Category" options={allCategories} selected={categories} onToggle={(v) => toggle(setCategories, categories, v)} />
    </div>
  )

  return (
    <div className="min-h-screen bg-white">
      <Header initialSearch={search} onSearch={handleSearch} />

      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
        <div className="mb-6">
          <h1 className="text-2xl font-extrabold text-gray-900">Product Catalogue</h1>
          <p className="mt-1 text-sm text-gray-500">
            {catalogQuery.isLoading
              ? 'Loading products...'
              : `${filtered.length} product${filtered.length !== 1 ? 's' : ''} available`}
          </p>
        </div>

        {/* Mobile filter toggle */}
        <button
          onClick={() => setShowFilters(true)}
          className="mb-4 inline-flex items-center gap-2 rounded-lg border border-gray-200 px-4 py-2 text-sm font-semibold text-gray-700 lg:hidden"
        >
          <SlidersHorizontal className="h-4 w-4" /> Filters{activeCount > 0 ? ` (${activeCount})` : ''}
        </button>

        <div className="flex gap-8">
          {/* Sidebar (desktop) */}
          <aside className="hidden w-60 shrink-0 lg:block">
            <div className="sticky top-24 rounded-2xl border border-gray-200 bg-white p-5">{Sidebar}</div>
          </aside>

          {/* Grid */}
          <main className="flex-1">
            {catalogQuery.isLoading ? (
              <p className="rounded-2xl border border-gray-200 py-20 text-center text-gray-500" aria-live="polite">
                Loading catalogue...
              </p>
            ) : catalogQuery.isError ? (
              <div className="rounded-2xl border border-gray-200 py-20 text-center" role="alert">
                <p className="font-semibold text-gray-700">Unable to load the catalogue.</p>
                <p className="mt-1 text-sm text-gray-500">{catalogQuery.error.message}</p>
                <button
                  onClick={() => catalogQuery.refetch()}
                  className="mt-4 rounded-full bg-amber-500 px-5 py-2 text-sm font-semibold text-white hover:bg-amber-600"
                >
                  Retry
                </button>
              </div>
            ) : filtered.length === 0 ? (
              <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-gray-300 py-20 text-center">
                <PackageSearch className="h-10 w-10 text-gray-300" />
                <p className="mt-3 font-semibold text-gray-700">
                  {products.length === 0 ? 'No products are available yet' : 'No products match your filters'}
                </p>
                <button onClick={clearAll} className="mt-2 text-sm font-semibold text-amber-600 hover:underline">Clear all filters</button>
              </div>
            ) : (
              <>
                <div className="catalogue-product-grid grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
                  {visibleProducts.map((product) => (
                    <ProductCard key={product.id} product={product} />
                  ))}
                </div>
                {visibleProducts.length < filtered.length && (
                  <div className="mt-8 text-center">
                    <button
                      onClick={() => setVisiblePages((pages) => pages + 1)}
                      className="rounded-full border border-gray-300 px-6 py-3 text-sm font-semibold text-gray-700 transition hover:border-amber-400 hover:text-amber-700"
                    >
                      Load more
                    </button>
                  </div>
                )}
              </>
            )}
          </main>
        </div>
      </div>

      {/* Mobile filter drawer */}
      {showFilters && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-black/40" onClick={() => setShowFilters(false)} />
          <div className="absolute left-0 top-0 h-full w-80 max-w-[85%] overflow-y-auto bg-white p-5 shadow-xl">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-base font-bold">Filters</span>
              <button onClick={() => setShowFilters(false)}><X className="h-5 w-5" /></button>
            </div>
            {Sidebar}
            <button onClick={() => setShowFilters(false)} className="mt-4 w-full rounded-lg bg-amber-500 py-2.5 text-sm font-semibold text-white">Show {filtered.length} results</button>
          </div>
        </div>
      )}

      <Footer />
    </div>
  )
}

export default function CataloguePage() {
  return (
    <Suspense fallback={<div className="flex min-h-screen items-center justify-center text-gray-400">Loading catalogue...</div>}>
      <CatalogueInner />
    </Suspense>
  )
}
