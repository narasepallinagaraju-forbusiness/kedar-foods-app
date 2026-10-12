'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Search } from 'lucide-react'
import { useCatalogIndex } from '@/lib/api/hooks'
import { filterCatalogItems, getDisplayName } from '@/lib/api/catalog.mjs'

const MAX_SUGGESTIONS = 6

export default function SearchBox({ initialSearch = '', onSearch = null, placeholder, className = '', autoFocus = false }) {
  const router = useRouter()
  const containerRef = useRef(null)
  const [query, setQuery] = useState(initialSearch)
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const [touched, setTouched] = useState(autoFocus)
  const catalogQuery = useCatalogIndex(touched)

  const trimmed = query.trim()
  const suggestions = useMemo(() => {
    if (!trimmed || !catalogQuery.data?.items) return []
    return filterCatalogItems(catalogQuery.data.items, { search: trimmed }).slice(0, MAX_SUGGESTIONS)
  }, [trimmed, catalogQuery.data])

  useEffect(() => {
    const handlePointerDown = (event) => {
      if (containerRef.current && !containerRef.current.contains(event.target)) setOpen(false)
    }
    document.addEventListener('pointerdown', handlePointerDown)
    return () => document.removeEventListener('pointerdown', handlePointerDown)
  }, [])

  const goToProduct = (product) => {
    setOpen(false)
    router.push(`/products/${encodeURIComponent(product.slug)}`)
  }

  const submitSearch = () => {
    setOpen(false)
    if (onSearch) onSearch(query)
    else router.push(`/catalogue?search=${encodeURIComponent(query)}`)
  }

  const handleSubmit = (event) => {
    event.preventDefault()
    if (active >= 0 && suggestions[active]) goToProduct(suggestions[active])
    else submitSearch()
  }

  const handleKeyDown = (event) => {
    if (event.key === 'Escape') {
      setOpen(false)
      return
    }
    if (!suggestions.length) return
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setOpen(true)
      setActive((index) => (index + 1) % suggestions.length)
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActive((index) => (index <= 0 ? suggestions.length - 1 : index - 1))
    }
  }

  const showList = open && trimmed && (suggestions.length > 0 || catalogQuery.isSuccess)

  return (
    <form ref={containerRef} onSubmit={handleSubmit} className={`relative ${className}`} role="search">
      <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
      <input
        value={query}
        onChange={(event) => {
          setQuery(event.target.value)
          setOpen(true)
          setActive(-1)
        }}
        onFocus={() => {
          setTouched(true)
          setOpen(true)
        }}
        onKeyDown={handleKeyDown}
        autoFocus={autoFocus}
        autoComplete="off"
        placeholder={placeholder}
        aria-label="Search products"
        role="combobox"
        aria-expanded={Boolean(showList)}
        aria-controls="search-suggestions"
        aria-autocomplete="list"
        className="w-full rounded-full border border-gray-200 bg-gray-50 py-2 pl-10 pr-4 text-sm text-gray-800 outline-none transition focus:border-amber-400 focus:bg-white focus:ring-2 focus:ring-amber-100"
      />
      {showList && (
        <ul
          id="search-suggestions"
          role="listbox"
          className="absolute left-0 right-0 top-full z-50 mt-2 overflow-hidden rounded-2xl border border-gray-200 bg-white py-1 shadow-xl"
        >
          {suggestions.map((product, index) => (
            <li key={product.id} role="option" aria-selected={index === active}>
              <button
                type="button"
                onMouseEnter={() => setActive(index)}
                onClick={() => goToProduct(product)}
                className={`flex w-full items-center justify-between gap-3 px-4 py-2 text-left text-sm ${index === active ? 'bg-amber-50 text-amber-700' : 'text-gray-800 hover:bg-gray-50'}`}
              >
                <span className="truncate font-medium">{getDisplayName(product)}</span>
                <span className="shrink-0 text-xs text-gray-500">{product.category}</span>
              </button>
            </li>
          ))}
          {suggestions.length === 0 && (
            <li className="px-4 py-3 text-sm text-gray-500">No matching products</li>
          )}
          <li className="border-t border-gray-100">
            <button
              type="button"
              onClick={submitSearch}
              className="w-full px-4 py-2 text-left text-sm font-semibold text-amber-600 hover:bg-gray-50"
            >
              See all results for &quot;{trimmed}&quot;
            </button>
          </li>
        </ul>
      )}
    </form>
  )
}
