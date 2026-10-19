'use client'

import Link from 'next/link'
import { Wheat, MessageCircle, MapPin } from 'lucide-react'
import { getWhatsAppConfig } from '@/lib/api/site-config'
import { useSiteConfig } from '@/lib/api/hooks'
import { buildGeneralWhatsAppUrl } from '@/lib/api/whatsapp.mjs'

export default function Footer({ configEnabled = true }) {
  const { data: siteConfig } = useSiteConfig(configEnabled)
  const whatsapp = getWhatsAppConfig(siteConfig)
  const SOCIAL_LINKS = [
  { label: 'Instagram', href: 'https://www.instagram.com/kedhar_foods', icon: '/instagram.png' },
  { label: 'Google Reviews', href: 'https://g.page/r/CQMyhg1xMTkMEAE/review', icon: '/rating.png' },
]

  return (
    <footer className="mt-16 border-t border-gray-200 bg-gray-50">
      <div className="mx-auto grid max-w-7xl gap-8 px-4 py-10 sm:px-6 md:grid-cols-4">
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
            <li><Link href="/bio" className="hover:text-amber-600">Bio</Link></li>
            {/* <li><Link href="/admin" className="hover:text-amber-600">Admin Portal</Link></li> */}
          </ul>
        </div>
        <div className="text-sm">
          <h4 className="font-semibold text-gray-900">Social Media Links</h4>
          <div className="mt-3" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            {SOCIAL_LINKS.map((item) => (
              <a
                key={item.label}
                href={item.href}
                target="_blank"
                rel="noopener noreferrer"
                aria-label={item.label}
                title={item.label}
                className="transition hover:-translate-y-0.5 hover:opacity-80"
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={item.icon}
                  alt=""
                  width={36}
                  height={36}
                  style={{ width: 36, height: 36, objectFit: 'contain' }}
                />
              </a>
            ))}
          </div>
        </div>
        <div className="text-sm">
          <h4 className="font-semibold text-gray-900">Get in touch</h4>
          <a href={buildGeneralWhatsAppUrl(whatsapp)} target="_blank" rel="noopener noreferrer" className="mt-3 inline-flex items-center gap-2 text-emerald-700 hover:underline">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/whatsapp.png" alt="" width={20} height={20} style={{ width: 20, height: 20, objectFit: 'contain', flexShrink: 0 }}    />
            {whatsapp.display}
          </a>
          <a href="https://maps.app.goo.gl/XTMgYws4g7naY6nw9" target="_blank" rel="noopener noreferrer" className="mt-3 flex items-start gap-2 text-gray-500 hover:text-amber-600">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/google-maps.png" alt="" width={20} height={20} style={{ width: 20, height: 20, objectFit: 'contain', flexShrink: 0, marginTop: 2 }} />
            <span className="leading-snug">
              29-36-39,Meghana Enterprises, Museum Rd,<br />
              opp. K.L University, Governar Peta,<br />
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
