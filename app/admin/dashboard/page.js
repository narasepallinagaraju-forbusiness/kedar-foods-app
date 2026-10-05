'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { Wheat, LogOut, Pencil, RotateCcw, X, Save, Flame, Plus, Download, Upload, Camera, Megaphone, Link2 } from 'lucide-react'
import { useProducts } from '@/lib/useProducts'
import { useSiteOffer } from '@/lib/useSiteOffer'
import { BUSINESS_TYPES, CATEGORIES, generateDataJsFile } from '@/lib/data'

const EMPTY = {
  id: '', name: '', quantities: '', category: '', brand: '',
  businessType: [], description: '', image: '', isTrending: false,
}

export default function AdminDashboardPage() {
  const router = useRouter()
  const { products, addProduct, updateProduct, resetProducts } = useProducts()
  const { offer, loaded: offerLoaded, updateOffer, resetOffer } = useSiteOffer()
  const [authed, setAuthed] = useState(false)
  const [modalMode, setModalMode] = useState(null) // 'add' | 'edit' | null
  const [form, setForm] = useState(EMPTY)
  const [offerForm, setOfferForm] = useState(null)
  const [offerSaved, setOfferSaved] = useState(false)

  // Sync the editable offer form once the stored offer has loaded.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (offerLoaded && !offerForm) setOfferForm(offer)
  }, [offerLoaded, offer, offerForm])

  // Master toggle persists instantly.
  const toggleOffer = () => {
    const next = !(offerForm?.isActive)
    setOfferForm((f) => ({ ...f, isActive: next }))
    updateOffer({ isActive: next })
  }

  const onOfferFile = (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => setOfferForm((f) => ({ ...f, image: reader.result }))
    reader.readAsDataURL(file)
  }

  const saveOffer = () => {
    updateOffer(offerForm)
    setOfferSaved(true)
    setTimeout(() => setOfferSaved(false), 2000)
  }

  useEffect(() => {
    let ok = false
    try { ok = sessionStorage.getItem('kedar_admin') === '1' } catch {}
    if (!ok) router.replace('/admin')
    // eslint-disable-next-line react-hooks/set-state-in-effect
    else setAuthed(true)
  }, [router])

  const nextSku = () => {
    const nums = products
      .map((p) => parseInt(String(p.id).replace(/[^0-9]/g, ''), 10))
      .filter((n) => !Number.isNaN(n))
    const max = nums.length ? Math.max(...nums) : 0
    return `KF-${String(max + 1).padStart(2, '0')}`
  }

  const openAdd = () => {
    setForm({ ...EMPTY, id: nextSku() })
    setModalMode('add')
  }

  const openEdit = (p) => {
    setForm({ ...EMPTY, ...p, quantities: (p.quantities || []).join(', ') })
    setModalMode('edit')
  }

  const toggleBiz = (b) => {
    setForm((f) => ({
      ...f,
      businessType: f.businessType.includes(b)
        ? f.businessType.filter((x) => x !== b)
        : [...f.businessType, b],
    }))
  }

  const onFile = (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => setForm((f) => ({ ...f, image: reader.result }))
    reader.readAsDataURL(file)
  }

  const save = () => {
    const quantities = String(form.quantities)
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
    const payload = { ...form, quantities }
    if (modalMode === 'add') addProduct(payload)
    else updateProduct(form.id, payload)
    setModalMode(null)
  }

  const handleExport = () => {
    const content = generateDataJsFile(products)
    const blob = new Blob([content], { type: 'text/javascript' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'data.js'
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  }

  const logout = () => {
    try { sessionStorage.removeItem('kedar_admin') } catch {}
    router.push('/admin')
  }

  if (!authed) return null

  const valid = form.name.trim() && form.brand.trim() && form.category.trim()

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6">
          <Link href="/" className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-500 text-white"><Wheat className="h-4 w-4" /></span>
            <span className="font-extrabold text-gray-900">Kedar Foods <span className="text-gray-400">/ Admin</span></span>
          </Link>
          <button onClick={logout} className="inline-flex items-center gap-2 rounded-lg border border-gray-200 px-3 py-2 text-sm font-semibold text-gray-700 hover:bg-gray-50">
            <LogOut className="h-4 w-4" /> Logout
          </button>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
        {/* Manage Promotions & Offers */}
        <section className="mb-8 rounded-2xl border border-gray-200 bg-white p-5 sm:p-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-100 text-amber-600"><Megaphone className="h-5 w-5" /></span>
              <div>
                <h2 className="text-lg font-extrabold text-gray-900">Manage Promotions &amp; Offers</h2>
                <p className="text-xs text-gray-500">Controls the homepage promo block and first-visit popup.</p>
              </div>
            </div>
            {/* Master toggle */}
            <button
              onClick={toggleOffer}
              className="flex items-center gap-3 rounded-full border border-gray-200 px-3 py-1.5"
            >
              <span className={`text-sm font-semibold ${offerForm?.isActive ? 'text-emerald-600' : 'text-gray-400'}`}>
                {offerForm?.isActive ? 'Offer ON' : 'Offer OFF'}
              </span>
              <span className={`relative h-6 w-11 rounded-full transition ${offerForm?.isActive ? 'bg-emerald-500' : 'bg-gray-300'}`}>
                <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all ${offerForm?.isActive ? 'left-[22px]' : 'left-0.5'}`} />
              </span>
            </button>
          </div>

          {offerForm && (
            <div className="mt-5 grid gap-5 md:grid-cols-2">
              {/* Image controls */}
              <div>
                <label className="mb-1 block text-xs font-semibold text-gray-600">Offer Poster Image</label>
                <div className="relative mb-2">
                  <Link2 className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
                  <input
                    value={offerForm.image?.startsWith('data:') ? '' : offerForm.image}
                    onChange={(e) => setOfferForm({ ...offerForm, image: e.target.value })}
                    placeholder="Paste image URL..."
                    className="w-full rounded-lg border border-gray-200 py-2 pl-9 pr-3 text-sm outline-none focus:border-amber-400 focus:ring-2 focus:ring-amber-100"
                  />
                </div>
                <div className="flex flex-wrap gap-2">
                  <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-semibold text-gray-700 hover:bg-gray-50">
                    <Upload className="h-3.5 w-3.5" /> Upload file
                    <input type="file" accept="image/*" onChange={onOfferFile} className="hidden" />
                  </label>
                  <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-semibold text-gray-700 hover:bg-gray-50">
                    <Camera className="h-3.5 w-3.5" /> Camera
                    <input type="file" accept="image/*" capture="environment" onChange={onOfferFile} className="hidden" />
                  </label>
                </div>
                {offerForm.image && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={offerForm.image} alt="offer preview" className="mt-3 max-h-48 w-full rounded-lg bg-gray-50 object-contain" />
                )}
              </div>

              {/* Text controls */}
              <div className="flex flex-col">
                <label className="mb-1 block text-xs font-semibold text-gray-600">Headline</label>
                <input
                  value={offerForm.headline}
                  onChange={(e) => setOfferForm({ ...offerForm, headline: e.target.value })}
                  className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-amber-400 focus:ring-2 focus:ring-amber-100"
                />
                <label className="mb-1 mt-4 block text-xs font-semibold text-gray-600">Description</label>
                <textarea
                  value={offerForm.description}
                  onChange={(e) => setOfferForm({ ...offerForm, description: e.target.value })}
                  rows={3}
                  className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-amber-400 focus:ring-2 focus:ring-amber-100"
                />
                <p className="mt-1 text-[11px] text-gray-400">Separate discount tiers with | to show them as bullet points.</p>

                <div className="mt-auto flex flex-wrap gap-2 pt-4">
                  <button onClick={saveOffer} className="inline-flex items-center gap-2 rounded-lg bg-amber-500 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-600">
                    <Save className="h-4 w-4" /> {offerSaved ? 'Saved!' : 'Save Offer'}
                  </button>
                  <button onClick={() => { resetOffer(); setOfferForm(null) }} className="inline-flex items-center gap-2 rounded-lg border border-gray-200 px-4 py-2 text-sm font-semibold text-gray-600 hover:bg-gray-50">
                    <RotateCcw className="h-4 w-4" /> Reset to default
                  </button>
                </div>
              </div>
            </div>
          )}
        </section>

        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-extrabold text-gray-900">Products</h1>
            <p className="mt-1 text-sm text-gray-500">{products.length} items · edits are saved to this browser</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button onClick={handleExport} className="inline-flex items-center gap-2 rounded-lg border border-gray-200 px-3 py-2 text-sm font-semibold text-gray-700 hover:bg-gray-50">
              <Download className="h-4 w-4" /> Export data.js
            </button>
            <button onClick={resetProducts} className="inline-flex items-center gap-2 rounded-lg border border-gray-200 px-3 py-2 text-sm font-semibold text-gray-600 hover:bg-gray-50">
              <RotateCcw className="h-4 w-4" /> Reset
            </button>
            <button onClick={openAdd} className="inline-flex items-center gap-2 rounded-lg bg-amber-500 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-600">
              <Plus className="h-4 w-4" /> Add Product
            </button>
          </div>
        </div>

        <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[820px] text-left text-sm">
              <thead className="bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
                <tr>
                  <th className="px-4 py-3">Product</th>
                  <th className="px-4 py-3">Qty</th>
                  <th className="px-4 py-3">Category</th>
                  <th className="px-4 py-3">Brand</th>
                  <th className="px-4 py-3">Business Type</th>
                  <th className="px-4 py-3">Description</th>
                  <th className="px-4 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {products.map((p) => (
                  <tr key={p.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img src={p.image} alt={p.name} className="h-10 w-10 rounded-lg object-cover" />
                        <div>
                          <div className="flex items-center gap-1.5 font-semibold text-gray-900">{p.name}{p.isTrending && <Flame className="h-3.5 w-3.5 text-amber-500" />}</div>
                          <div className="text-xs text-gray-400">{p.id}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-gray-700"><span className="text-xs">{(p.quantities || []).join(' \u00b7 ')}</span></td>
                    <td className="px-4 py-3"><span className="rounded-md bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700">{p.category}</span></td>
                    <td className="px-4 py-3 text-gray-700">{p.brand}</td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1">
                        {p.businessType?.map((b) => (
                          <span key={b} className="rounded bg-gray-100 px-1.5 py-0.5 text-[11px] text-gray-600">{b}</span>
                        ))}
                      </div>
                    </td>
                    <td className="max-w-[220px] px-4 py-3"><p className="line-clamp-2 text-xs text-gray-500">{p.description}</p></td>
                    <td className="px-4 py-3 text-right">
                      <button onClick={() => openEdit(p)} className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-semibold text-gray-700 hover:border-amber-300 hover:text-amber-600">
                        <Pencil className="h-3.5 w-3.5" /> Edit
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </main>

      {/* Add / Edit modal */}
      {modalMode && (
        <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto px-4 py-8">
          <div className="absolute inset-0 bg-black/50" onClick={() => setModalMode(null)} />
          <div className="relative w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-base font-bold text-gray-900">{modalMode === 'add' ? 'Add New Product' : `Edit — ${form.id}`}</h3>
              <button onClick={() => setModalMode(null)}><X className="h-5 w-5 text-gray-400" /></button>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="col-span-2">
                <label className="mb-1 block text-xs font-semibold text-gray-600">Product Name</label>
                <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-amber-400 focus:ring-2 focus:ring-amber-100" />
              </div>
              <div className="col-span-2">
                <label className="mb-1 block text-xs font-semibold text-gray-600">Available Quantities / Pack Sizes</label>
                <input value={form.quantities} onChange={(e) => setForm({ ...form, quantities: e.target.value })} placeholder="e.g. 100g, 500g, 1 kg, 5 kg" className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-amber-400 focus:ring-2 focus:ring-amber-100" />
                <p className="mt-1 text-[11px] text-gray-400">Comma-separated. These appear as the pack-size dropdown on the product card.</p>
              </div>
              <div>
                <label className="mb-1 block text-xs font-semibold text-gray-600">Category</label>
                <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm outline-none focus:border-amber-400 focus:ring-2 focus:ring-amber-100">
                  <option value="">Select category...</option>
                  {CATEGORIES.map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs font-semibold text-gray-600">Brand</label>
                <input value={form.brand} onChange={(e) => setForm({ ...form, brand: e.target.value })} className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-amber-400 focus:ring-2 focus:ring-amber-100" />
              </div>
              <div className="col-span-2">
                <label className="mb-1 block text-xs font-semibold text-gray-600">Business Type</label>
                <div className="flex flex-wrap gap-3">
                  {BUSINESS_TYPES.map((b) => (
                    <label key={b} className="flex cursor-pointer items-center gap-1.5 text-sm text-gray-700">
                      <input type="checkbox" checked={form.businessType.includes(b)} onChange={() => toggleBiz(b)} className="h-4 w-4 rounded border-gray-300 accent-amber-500" />
                      {b}
                    </label>
                  ))}
                </div>
              </div>
              <div className="col-span-2">
                <label className="mb-1 block text-xs font-semibold text-gray-600">Description</label>
                <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} rows={2} className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-amber-400 focus:ring-2 focus:ring-amber-100" />
              </div>

              <div className="col-span-2">
                <label className="mb-1 block text-xs font-semibold text-gray-600">Product Image</label>
                <input value={form.image?.startsWith('data:') ? '' : form.image} onChange={(e) => setForm({ ...form, image: e.target.value })} placeholder="Paste image URL..." className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-amber-400 focus:ring-2 focus:ring-amber-100" />
                <div className="mt-2 flex flex-wrap gap-2">
                  <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-semibold text-gray-700 hover:bg-gray-50">
                    <Upload className="h-3.5 w-3.5" /> Upload file
                    <input type="file" accept="image/*" onChange={onFile} className="hidden" />
                  </label>
                  <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-semibold text-gray-700 hover:bg-gray-50">
                    <Camera className="h-3.5 w-3.5" /> Camera
                    <input type="file" accept="image/*" capture="environment" onChange={onFile} className="hidden" />
                  </label>
                </div>
                {form.image && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={form.image} alt="preview" className="mt-2 h-24 w-full rounded-lg object-cover" />
                )}
              </div>

              <div className="col-span-2">
                <label className="flex cursor-pointer items-center gap-2 text-sm font-medium text-gray-700">
                  <input type="checkbox" checked={form.isTrending} onChange={(e) => setForm({ ...form, isTrending: e.target.checked })} className="h-4 w-4 rounded border-gray-300 accent-amber-500" />
                  Mark as trending (shows in hero &amp; top picks)
                </label>
              </div>
            </div>

            <div className="mt-6 flex justify-end gap-2">
              <button onClick={() => setModalMode(null)} className="rounded-lg border border-gray-200 px-4 py-2 text-sm font-semibold text-gray-700 hover:bg-gray-50">Cancel</button>
              <button onClick={save} disabled={!valid} className="inline-flex items-center gap-2 rounded-lg bg-amber-500 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-600 disabled:cursor-not-allowed disabled:opacity-50">
                <Save className="h-4 w-4" /> {modalMode === 'add' ? 'Add Product' : 'Save changes'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
