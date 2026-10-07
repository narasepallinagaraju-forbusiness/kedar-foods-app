'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { ArrowRight, ShieldCheck, Truck, Tag, MessageCircle, ChevronLeft, ChevronRight } from 'lucide-react'
import Header from '@/components/kedar/Header'
import Footer from '@/components/kedar/Footer'
import OfferPromoBlock from '@/components/kedar/OfferPromoBlock'
import OfferPopup from '@/components/kedar/OfferPopup'
import { useCatalogIndex, useSiteConfig } from '@/lib/api/hooks'
import { getSiteCategories, getWhatsAppConfig } from '@/lib/api/site-config'
import { getCatalogImageUrl } from '@/lib/api/catalog.mjs'
import { buildGeneralWhatsAppUrl, buildProductWhatsAppUrl } from '@/lib/api/whatsapp.mjs'
import { TOP_BRANDS } from '@/lib/data'

const STYLES = [
  {
    name: 'For Bakeries',
    emoji: '🧁',
    biz: 'Bakery',
    desc: 'Flour, butter, sugar & chocolate for breads and cakes.',
    image: 'https://images.unsplash.com/photo-1568254183919-78a4f43a2877?w=600&q=80&auto=format&fit=crop',
  },
  {
    name: 'For Cafes',
    emoji: '☕',
    biz: 'Cafe',
    desc: 'Cream, chocolate, syrups & dairy for your counter.',
    image: 'https://images.unsplash.com/photo-1556742393-d75f468bfcb0?w=600&q=80&auto=format&fit=crop',
  },
  {
    name: 'For Restaurants',
    emoji: '🍽️',
    biz: 'Restaurant',
    desc: 'Cheese, flour & essentials for high-volume kitchens.',
    image: 'https://images.unsplash.com/photo-1622021142947-da7dedc7c39a?w=600&q=80&auto=format&fit=crop',
  },
]

function HeroCarousel({ slides, whatsapp }) {
  const [active, setActive] = useState(0)
  const count = slides.length

  useEffect(() => {
    if (count <= 1) return
    const t = setInterval(() => setActive((a) => (a + 1) % count), 3500)
    return () => clearInterval(t)
  }, [count])

  if (count === 0) return null
  const go = (dir) => setActive((a) => (a + dir + count) % count)

  return (
    <div className="relative h-[380px] overflow-hidden rounded-3xl border border-gray-100 bg-gray-900 shadow-xl sm:h-[460px]">
      {slides.map((p, i) => (
        <div
          key={p.id}
          className={`absolute inset-0 transition-opacity duration-700 ease-in-out ${i === active ? 'opacity-100' : 'pointer-events-none opacity-0'}`}
        >
          {getCatalogImageUrl(p.thumbnailKey) ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={getCatalogImageUrl(p.thumbnailKey)} alt={p.name} className="h-full w-full object-cover" />
          ) : (
            <div className="h-full w-full bg-gradient-to-br from-gray-700 to-gray-900" role="img" aria-label="Product image unavailable" />
          )}
          <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/30 to-transparent" />

          <div className="absolute inset-x-0 bottom-0 p-5 text-white sm:p-7">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <span className="rounded-full bg-amber-500 px-2.5 py-1 text-[11px] font-bold uppercase tracking-wide text-white">{p.brand}</span>
              {p.quantities?.[0] && <span className="rounded-full bg-white/15 px-2.5 py-1 text-[11px] font-semibold backdrop-blur">{p.quantities[0]}</span>}
              <span className="rounded-full bg-white/15 px-2.5 py-1 text-[11px] font-semibold backdrop-blur">{p.category}</span>
            </div>
            <h3 className="text-2xl font-extrabold leading-tight sm:text-3xl">
              <a href={`/products/${encodeURIComponent(p.slug)}`} className="hover:text-amber-300">
                {p.name}
              </a>
            </h3>
            <a
              href={buildProductWhatsAppUrl(whatsapp, p)}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-4 inline-flex items-center gap-2 rounded-full bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-700"
            >
              <MessageCircle className="h-4 w-4" /> Enquire on WhatsApp
            </a>
          </div>
        </div>
      ))}

      {/* Arrows */}
      {count > 1 && (
        <>
          <button
            onClick={() => go(-1)}
            aria-label="Previous product"
            className="absolute left-3 top-1/2 flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-full bg-white/80 text-gray-800 shadow transition hover:bg-white"
          >
            <ChevronLeft className="h-5 w-5" />
          </button>
          <button
            onClick={() => go(1)}
            aria-label="Next product"
            className="absolute right-3 top-1/2 flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-full bg-white/80 text-gray-800 shadow transition hover:bg-white"
          >
            <ChevronRight className="h-5 w-5" />
          </button>

          {/* Dots */}
          <div className="absolute left-1/2 top-4 flex -translate-x-1/2 gap-1.5">
            {slides.map((p, i) => (
              <button
                key={p.id}
                onClick={() => setActive(i)}
                aria-label={`Go to slide ${i + 1}`}
                className={`h-2 rounded-full transition-all ${i === active ? 'w-6 bg-amber-400' : 'w-2 bg-white/60 hover:bg-white'}`}
              />
            ))}
          </div>
        </>
      )}
    </div>
  )
}

export default function App() {
  const catalogQuery = useCatalogIndex()
  const siteConfigQuery = useSiteConfig()
  const catalogItems = catalogQuery.data?.items ?? []
  const siteConfig = siteConfigQuery.data
  const offerLoaded = !siteConfigQuery.isLoading && !siteConfigQuery.isError
  const offer = siteConfig?.offerBanner
  const whatsapp = getWhatsAppConfig(siteConfig)
  const categories = getSiteCategories(siteConfig)
  const slides = catalogItems.filter((product) => product.isTrending).slice(0, 5)
  const brandLoop = [...TOP_BRANDS, ...TOP_BRANDS]

  return (
    <div className="min-h-screen bg-white">
      <Header />

      {/* Conditional sitewide promo (collapses fully when inactive) */}
      <OfferPromoBlock offer={offer} loaded={offerLoaded} />
      {siteConfigQuery.isError && (
        <div className="mx-auto flex max-w-7xl items-center justify-center gap-3 px-4 py-3 text-center text-sm text-gray-600 sm:px-6" role="status">
          Site settings are unavailable; WhatsApp enquiries use the saved contact details.
          <button onClick={() => siteConfigQuery.refetch()} className="font-semibold text-amber-700 hover:underline">
            Retry
          </button>
        </div>
      )}

      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="mx-auto grid max-w-7xl items-center gap-10 px-4 py-12 sm:px-6 lg:grid-cols-2 lg:py-20">
          <div>
            <span className="inline-flex items-center gap-2 rounded-full bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-700">
              <Tag className="h-3.5 w-3.5" /> Bulk wholesale — enquire for best rates
            </span>
            <h1 className="mt-4 text-4xl font-extrabold leading-tight tracking-tight text-gray-900 sm:text-5xl">
              Quality Raw Materials for <span className="text-amber-600">Bakeries, Cafes &amp; Restaurants</span>
            </h1>
            <p className="mt-4 max-w-lg text-base text-gray-600">
              From premium dairy and flour to chocolate and cream — Kedar Foods keeps your kitchen stocked with dependable, food-grade ingredients at wholesale prices.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <Link href="/catalogue" className="inline-flex items-center gap-2 rounded-full bg-amber-500 px-6 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-amber-600">
                Browse Catalogue <ArrowRight className="h-4 w-4" />
              </Link>
              <a href={buildGeneralWhatsAppUrl(whatsapp)} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 rounded-full border border-gray-200 bg-white px-6 py-3 text-sm font-semibold text-gray-800 transition hover:border-emerald-300 hover:text-emerald-700">
                <MessageCircle className="h-4 w-4" /> Enquire on WhatsApp
              </a>
            </div>
            <div className="mt-8 flex flex-wrap gap-6 text-sm text-gray-600">
              <span className="inline-flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-amber-600" /> Food-grade quality</span>
              <span className="inline-flex items-center gap-2"><Truck className="h-4 w-4 text-amber-600" /> Bulk delivery</span>
              <span className="inline-flex items-center gap-2"><Tag className="h-4 w-4 text-amber-600" /> Wholesale pricing</span>
            </div>
          </div>

          {/* Auto-playing product carousel */}
          {catalogQuery.isLoading ? (
            <div className="flex h-[380px] items-center justify-center rounded-3xl border border-gray-100 bg-gray-100 text-gray-500 shadow-xl sm:h-[460px]" aria-live="polite">
              Loading trending products...
            </div>
          ) : catalogQuery.isError ? (
            <div className="flex h-[380px] flex-col items-center justify-center gap-3 rounded-3xl border border-gray-100 bg-gray-100 px-6 text-center text-gray-600 shadow-xl sm:h-[460px]" role="alert">
              <p>Unable to load products right now.</p>
              <button onClick={() => catalogQuery.refetch()} className="rounded-full bg-amber-500 px-5 py-2 text-sm font-semibold text-white hover:bg-amber-600">
                Retry
              </button>
            </div>
          ) : (
            <HeroCarousel slides={slides} whatsapp={whatsapp} />
          )}
        </div>
      </section>

      {/* Categories from the public site configuration */}
      <section className="mx-auto mt-16 max-w-7xl px-4 sm:px-6">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-gray-900">Shop by Category</h2>
          <p className="mt-2 text-gray-500">Browse our wholesale ingredient ranges.</p>
        </div>
        <div className="mt-6 flex flex-wrap justify-center gap-3">
          {categories.map((category) => (
            <Link
              key={category.id}
              href={`/catalogue?category=${encodeURIComponent(category.name)}`}
              className="rounded-full border border-gray-200 bg-white px-5 py-2.5 text-sm font-semibold text-gray-700 transition hover:border-amber-400 hover:text-amber-700"
            >
              {category.name}
            </Link>
          ))}
        </div>
      </section>

      {/* Shop by business style (promoted) */}
      <section className="mx-auto max-w-7xl px-4 pt-4 sm:px-6 lg:pt-6">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-gray-900">Shop by Business Style</h2>
          <p className="mt-2 text-gray-500">Curated ingredient ranges for how you serve.</p>
        </div>
        <div className="mt-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {STYLES.map((s) => (
            <Link
              key={s.name}
              href={`/catalogue?business=${encodeURIComponent(s.biz)}`}
              className="group relative overflow-hidden rounded-2xl border border-gray-200"
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={s.image} alt={s.name} className="h-56 w-full object-cover transition duration-300 group-hover:scale-105" />
              <div className="absolute inset-0 bg-gradient-to-t from-black/75 via-black/25 to-transparent" />
              <div className="absolute bottom-0 left-0 p-5 text-white">
                <h3 className="flex items-center gap-2 text-xl font-extrabold"><span className="text-2xl">{s.emoji}</span> {s.name}</h3>
                <p className="mt-1 max-w-xs text-sm text-white/80">{s.desc}</p>
                <span className="mt-3 inline-flex items-center gap-1 text-sm font-semibold text-amber-300">
                  Shop now <ArrowRight className="h-4 w-4" />
                </span>
              </div>
            </Link>
          ))}
        </div>
      </section>

      {/* Top Brands We Supply */}
      <section className="mt-16 border-y border-gray-100 bg-gray-50 py-10">
        <h2 className="mb-6 text-center text-xl font-bold text-gray-900">Top Brands We Supply</h2>
        <div className="group relative overflow-hidden">
          <div className="marquee-track flex w-max items-center gap-4 px-4 animate-marquee">
            {brandLoop.map((brand, i) => (
              <span
                key={`${brand}-${i}`}
                className="shrink-0 rounded-full border border-gray-200 bg-white px-6 py-3 text-base font-bold text-gray-700 shadow-sm"
              >
                {brand}
              </span>
            ))}
          </div>
        </div>
      </section>

      <Footer />
      <OfferPopup offer={offer} loaded={offerLoaded} />
    </div>
  )
}
