'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Search, MessageCircle, Menu, X, Wheat } from 'lucide-react'
import { getWhatsAppConfig } from '@/lib/api/site-config'
import { useSiteConfig } from '@/lib/api/hooks'
import { buildGeneralWhatsAppUrl } from '@/lib/api/whatsapp.mjs'

export default function Header({ initialSearch = '', onSearch = null, configEnabled = true }) {
  const router = useRouter()
  const [query, setQuery] = useState(initialSearch)
  const [mobileOpen, setMobileOpen] = useState(false)
  const { data: siteConfig } = useSiteConfig(configEnabled)
  const whatsapp = getWhatsAppConfig(siteConfig)

  const handleSubmit = (e) => {
    e.preventDefault()
    if (onSearch) {
      onSearch(query)
    } else {
      router.push(`/catalogue?search=${encodeURIComponent(query)}`)
    }
  }

  return (
    <header className="sticky top-0 z-40 w-full border-b border-gray-200 bg-white/90 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-3 sm:px-6">
        {/* Logo */}
        <Link href="/" className="flex shrink-0 items-center gap-2">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-500 text-white shadow-sm">
            <Wheat className="h-5 w-5" />
          </span>
          <span className="flex flex-col leading-none">
            <span className="text-lg font-extrabold tracking-tight text-gray-900">Kedar Foods</span>
            <span className="text-[10px] font-medium uppercase tracking-widest text-amber-600">Wholesale Supply</span>
          </span>
        </Link>

        {/* Search (desktop) */}
        <form onSubmit={handleSubmit} className="relative hidden flex-1 md:block">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search butter, flour, coffee beans..."
            className="w-full rounded-full border border-gray-200 bg-gray-50 py-2 pl-10 pr-4 text-sm text-gray-800 outline-none transition focus:border-amber-400 focus:bg-white focus:ring-2 focus:ring-amber-100"
          />
        </form>

        <div className="ml-auto flex items-center gap-2">
          <Link href="/catalogue" className="hidden rounded-full px-4 py-2 text-sm font-semibold text-gray-700 hover:text-amber-600 sm:block">
            Catalogue
          </Link>
          <a
            href={buildGeneralWhatsAppUrl(whatsapp)}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 rounded-full bg-emerald-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-700"
          >
            <MessageCircle className="h-4 w-4" />
            <span className="hidden sm:inline">Enquire on WhatsApp</span>
            <span className="sm:hidden">Enquire</span>
          </a>
          <button
            onClick={() => setMobileOpen((v) => !v)}
            className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-gray-200 text-gray-700 md:hidden"
            aria-label="Toggle search"
          >
            {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </div>

      {/* Search (mobile) */}
      {mobileOpen && (
        <div className="border-t border-gray-100 px-4 py-3 md:hidden">
          <form onSubmit={handleSubmit} className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search products..."
              className="w-full rounded-full border border-gray-200 bg-gray-50 py-2 pl-10 pr-4 text-sm outline-none focus:border-amber-400 focus:bg-white"
            />
          </form>
        </div>
      )}
    </header>
  )
}
