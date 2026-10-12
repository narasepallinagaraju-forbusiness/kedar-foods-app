'use client'

import { useState } from 'react'
import Link from 'next/link'
import { MessageCircle, Menu, X } from 'lucide-react'
import SearchBox from '@/components/kedar/SearchBox'
import { getWhatsAppConfig } from '@/lib/api/site-config'
import { useSiteConfig } from '@/lib/api/hooks'
import { buildGeneralWhatsAppUrl } from '@/lib/api/whatsapp.mjs'

export default function Header({ initialSearch = '', onSearch = null, configEnabled = true }) {
  const [mobileOpen, setMobileOpen] = useState(false)
  const { data: siteConfig } = useSiteConfig(configEnabled)
  const whatsapp = getWhatsAppConfig(siteConfig)

  return (
    <header className="sticky top-0 z-40 w-full border-b border-gray-200 bg-white/90 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-3 sm:px-6">
        {/* Logo */}
        <Link href="/" className="flex shrink-0 items-center gap-2">
          {/* <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-500 text-white shadow-sm">
            <Wheat className="h-5 w-5" />
          </span> */}
          <img src="/logo.png" alt="Kedar Foods" className="h-9 w-9 rounded-lg object-contain" />
          <span className="flex flex-col leading-none">
            <span className="text-lg font-extrabold tracking-tight text-gray-900">Kedhar Foods</span>
            <span className="text-[10px] font-medium uppercase tracking-widest text-amber-600">Wholesale Supply</span>
          </span>
        </Link>

        {/* Search (desktop) */}
        <SearchBox
          initialSearch={initialSearch}
          onSearch={onSearch}
          placeholder="Search butter, flour, coffee beans..."
          className="hidden flex-1 md:block"
        />

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
          <SearchBox initialSearch={initialSearch} onSearch={onSearch} placeholder="Search products..." autoFocus />
        </div>
      )}
    </header>
  )
}
