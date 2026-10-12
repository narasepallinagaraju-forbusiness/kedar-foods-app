'use client'

import Link from 'next/link'
import { Wheat, MessageCircle, MapPin } from 'lucide-react'
import { getWhatsAppConfig } from '@/lib/api/site-config'
import { useSiteConfig } from '@/lib/api/hooks'
import { buildGeneralWhatsAppUrl } from '@/lib/api/whatsapp.mjs'

export default function Footer({ configEnabled = true }) {
  const { data: siteConfig } = useSiteConfig(configEnabled)
  const whatsapp = getWhatsAppConfig(siteConfig)

  return (
    <footer className="mt-16 border-t border-gray-200 bg-gray-50">
      <div className="mx-auto grid max-w-7xl gap-8 px-4 py-10 sm:px-6 md:grid-cols-3">
        <div>
          <div className="flex items-center gap-2">
            {/* <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-500 text-white">
              <Wheat className="h-4 w-4" />
            </span> */}
            <img src="/logo.png" alt="Kedar Foods" className="h-9 w-9 rounded-lg object-contain" />
            <span className="text-base font-extrabold text-gray-900">Kedhar Foods</span>
          </div>
          <p className="mt-3 max-w-xs text-sm text-gray-500">
            Wholesale raw materials for bakeries, cafes and restaurants. Quality you can bake on.
          </p>
        </div>
        <div className="text-sm">
          <h4 className="font-semibold text-gray-900">Quick Links</h4>
          <ul className="mt-3 space-y-2 text-gray-500">
            <li><Link href="/" className="hover:text-amber-600">Home</Link></li>
            <li><Link href="/catalogue" className="hover:text-amber-600">Catalogue</Link></li>
            {/* <li><Link href="/admin" className="hover:text-amber-600">Admin Portal</Link></li> */}
          </ul>
        </div>
        <div className="text-sm">
          <h4 className="font-semibold text-gray-900">Get in touch</h4>
          <a href={buildGeneralWhatsAppUrl(whatsapp)} target="_blank" rel="noopener noreferrer" className="mt-3 inline-flex items-center gap-2 text-emerald-700 hover:underline">
            <MessageCircle className="h-4 w-4" /> {whatsapp.display}
          </a>
          <a
            href="https://maps.app.goo.gl/XTMgYws4g7naY6nw9"
            target="_blank"
            rel="noopener noreferrer"
            className="mt-3 flex items-start gap-2 text-gray-500 hover:text-amber-600"
          >
            <MapPin className="mt-0.5 h-4 w-4 shrink-0" />
            <span className="leading-snug">
              27-20-24, Museum Rd,<br />
              opp. K.L University, Governor Peta,<br />
              Vijayawada, Andhra Pradesh 520002
            </span>
          </a>
        </div>
      </div>
      <div className="border-t border-gray-200 py-4 text-center text-xs text-gray-400">
        © {new Date().getFullYear()} Kedhar Foods. All rights reserved.
      </div>
    </footer>
  )
}
