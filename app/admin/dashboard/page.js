'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { Wheat, LogOut, Pencil, X, Save, Flame, Plus, Megaphone, Eye, EyeOff, AlertCircle, RefreshCw, Search, Upload } from 'lucide-react'
import { BUSINESS_TYPES } from '@/lib/data'
import { useSiteConfig } from '@/lib/api/hooks'
import { getSiteCategories } from '@/lib/api/site-config'
import { clearAdminKey, getAdminKey } from '@/lib/admin-api/admin-key.mjs'
import {
  useAdminOffer,
  useAdminProducts,
  useCreateProduct,
  useRebuildIndex,
  useRemovePoster,
  useRemoveProductPicture,
  useSaveOffer,
  useSetProductVisibility,
  useUpdateProduct,
  useUploadPoster,
  useUploadProductPicture,
} from '@/lib/admin-api/hooks'
import {
  CARD_SIDE,
  MAIN_SIDE,
  MAX_PICTURES,
  POSTER_SIDE,
  prepareImages,
  productPictures,
} from '@/lib/admin-api/image-prepare.mjs'
import PictureSlot from './PictureSlot'
import ImportDialog from './ImportDialog'
import {
  buildOfferPayload,
  buildProductPayload,
  EMPTY_PRODUCT_FORM,
  filterProducts,
  offerStatusLabel,
  productToForm,
  todayInIndia,
  validateOfferForm,
  validateProductForm,
} from '@/lib/admin-api/validation.mjs'

const INPUT = 'w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-amber-400 focus:ring-2 focus:ring-amber-100'

function FieldError({ message }) {
  return message ? <p className="mt-1 text-xs text-red-600">{message}</p> : null
}

export default function AdminDashboardPage() {
  const router = useRouter()
  const [authed, setAuthed] = useState(false)
  const [modalMode, setModalMode] = useState(null) // 'create' | 'edit' | null
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState(EMPTY_PRODUCT_FORM)
  const [formErrors, setFormErrors] = useState({})
  const [notice, setNotice] = useState(null) // { type: 'error' | 'warn' | 'ok', text }
  const [searchText, setSearchText] = useState('')
  const [importOpen, setImportOpen] = useState(false)
  const [offerForm, setOfferForm] = useState(null)
  const [offerErrors, setOfferErrors] = useState({})

  const productsQuery = useAdminProducts(authed)
  const offerQuery = useAdminOffer(authed)
  const siteConfig = useSiteConfig(authed)
  const createProduct = useCreateProduct()
  const updateProduct = useUpdateProduct()
  const setVisibility = useSetProductVisibility()
  const rebuildIndex = useRebuildIndex()
  const saveOffer = useSaveOffer()
  const uploadPicture = useUploadProductPicture()
  const removePicture = useRemoveProductPicture()
  const uploadPoster = useUploadPoster()
  const removePoster = useRemovePoster()
  const products = productsQuery.data ?? []
  const shownProducts = filterProducts(products, searchText)
  const categoryNames = getSiteCategories(siteConfig.data).map((c) => c.name)

  useEffect(() => {
    let ok = false
    try { ok = sessionStorage.getItem('kedar_admin') === '1' } catch {}
    if (!ok || !getAdminKey()) router.replace('/admin')
    // eslint-disable-next-line react-hooks/set-state-in-effect
    else setAuthed(true)
  }, [router])

  // Seed the editable offer form once from the stored offer.
  useEffect(() => {
    if (offerQuery.data && !offerForm) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setOfferForm({
        enabled: offerQuery.data.enabled === true,
        text: offerQuery.data.text ?? '',
        link: offerQuery.data.link ?? '',
        startDate: offerQuery.data.startDate ?? '',
        endDate: offerQuery.data.endDate ?? '',
      })
    }
  }, [offerQuery.data, offerForm])

  // A rejected key on any background read sends the admin back to sign-in.
  const rejected = productsQuery.error?.status === 401 || offerQuery.error?.status === 401
  useEffect(() => {
    if (rejected) {
      clearAdminKey()
      try { sessionStorage.removeItem('kedar_admin') } catch {}
      router.replace('/admin')
    }
  }, [rejected, router])

  const logout = () => {
    clearAdminKey()
    try { sessionStorage.removeItem('kedar_admin') } catch {}
    router.push('/admin')
  }

  const handleError = (error) => {
    if (error?.status === 401) {
      logout()
      return
    }
    setNotice({ type: 'error', text: error?.message || 'Something went wrong.' })
  }

  const reportWrite = (result, okText) => {
    if (result?.indexRebuilt === false) {
      setNotice({ type: 'warn', text: result.message || 'Saved, but the public list was not refreshed.', rebuild: true })
    } else {
      setNotice({ type: 'ok', text: `${okText} Changes reach the public site within about a minute.` })
    }
  }

  const openCreate = () => {
    setForm(EMPTY_PRODUCT_FORM)
    setFormErrors({})
    setEditing(null)
    setModalMode('create')
  }

  const openEdit = (product) => {
    setForm(productToForm(product))
    setFormErrors({})
    setEditing(product)
    setModalMode('edit')
  }

  const closeModal = () => setModalMode(null)

  const toggleBiz = (type) => {
    setForm((f) => ({
      ...f,
      businessType: f.businessType.includes(type)
        ? f.businessType.filter((x) => x !== type)
        : [...f.businessType, type],
    }))
  }

  const saveProduct = async () => {
    const errors = validateProductForm(form, { mode: modalMode, categories: categoryNames })
    setFormErrors(errors)
    if (Object.keys(errors).length > 0) return
    setNotice(null)
    try {
      if (modalMode === 'create') {
        const result = await createProduct.mutateAsync(buildProductPayload(form, { mode: 'create' }))
        reportWrite(result, 'Product added.')
      } else {
        const payload = buildProductPayload(form, { mode: 'update', version: editing.version })
        const result = await updateProduct.mutateAsync({ id: editing.productId, payload })
        reportWrite(result, 'Product saved.')
      }
      closeModal()
    } catch (error) {
      if (error?.status === 409 && modalMode === 'edit') closeModal()
      handleError(error)
    }
  }

  const toggleVisibility = async (product) => {
    setNotice(null)
    try {
      const visible = product.status !== 'PUBLISHED'
      const result = await setVisibility.mutateAsync({ id: product.productId, visible })
      reportWrite(result, visible ? 'Product is now visible.' : 'Product is now hidden.')
    } catch (error) {
      handleError(error)
    }
  }

  const rebuild = async () => {
    try {
      await rebuildIndex.mutateAsync()
      setNotice({ type: 'ok', text: 'Public list refreshed. It can take up to a minute to appear.' })
    } catch (error) {
      handleError(error)
    }
  }

  const submitOffer = async () => {
    const errors = validateOfferForm(offerForm)
    setOfferErrors(errors)
    if (Object.keys(errors).length > 0) return
    setNotice(null)
    try {
      await saveOffer.mutateAsync(buildOfferPayload(offerForm))
      setNotice({ type: 'ok', text: 'Offer saved. It reaches the public site within about a minute.' })
    } catch (error) {
      handleError(error)
    }
  }

  if (!authed) return null

  // Picture actions throw plain Errors so the picture box can show them itself.
  const pictureAction = async (action) => {
    try {
      return await action()
    } catch (error) {
      if (error?.status === 401) {
        logout()
      } else if (error?.status === 409) {
        closeModal()
        setNotice({ type: 'error', text: error.message })
      }
      throw error
    }
  }

  const savePicture = (slot) => (source) =>
    pictureAction(async () => {
      const { card, main } = await prepareImages(source, { card: CARD_SIDE, main: MAIN_SIDE })
      const result = await uploadPicture.mutateAsync({
        id: editing.productId, slot, version: editing.version, card, main,
      })
      setEditing(result.product)
      reportWrite(result, 'Picture saved.')
    })

  const deletePicture = (slot) => () =>
    pictureAction(async () => {
      const result = await removePicture.mutateAsync({
        id: editing.productId, slot, version: editing.version,
      })
      setEditing(result.product)
      reportWrite(result, 'Picture removed.')
    })

  const savePoster = (source) =>
    pictureAction(async () => {
      const { poster } = await prepareImages(source, { poster: POSTER_SIDE })
      await uploadPoster.mutateAsync({ poster })
      setNotice({ type: 'ok', text: 'Poster saved. It reaches the public site within about a minute.' })
    })

  const deletePoster = () =>
    pictureAction(async () => {
      await removePoster.mutateAsync()
      setNotice({ type: 'ok', text: 'Poster removed.' })
    })

  const pictures = modalMode === 'edit' && editing ? productPictures(editing) : []
  const pictureSlots = Math.min(pictures.length + 1, MAX_PICTURES)
  const saving = createProduct.isPending || updateProduct.isPending
  const noticeStyle = {
    error: 'bg-red-50 text-red-700',
    warn: 'bg-amber-50 text-amber-800',
    ok: 'bg-emerald-50 text-emerald-700',
  }

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
        {notice && (
          <div role="status" className={`mb-6 flex flex-wrap items-center justify-between gap-3 rounded-lg px-4 py-3 text-sm ${noticeStyle[notice.type]}`}>
            <span className="flex items-center gap-2">
              {notice.type !== 'ok' && <AlertCircle className="h-4 w-4" />} {notice.text}
            </span>
            <span className="flex items-center gap-3">
              {notice.rebuild && (
                <button onClick={rebuild} disabled={rebuildIndex.isPending} className="inline-flex items-center gap-1.5 rounded-lg border border-current px-3 py-1 text-xs font-semibold disabled:opacity-60">
                  <RefreshCw className="h-3.5 w-3.5" /> {rebuildIndex.isPending ? 'Refreshing…' : 'Rebuild public list'}
                </button>
              )}
              <button onClick={() => setNotice(null)} aria-label="Dismiss"><X className="h-4 w-4" /></button>
            </span>
          </div>
        )}

        {/* Offer banner */}
        <section className="mb-8 rounded-2xl border border-gray-200 bg-white p-5 sm:p-6">
          <div className="flex items-center gap-2">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-100 text-amber-600"><Megaphone className="h-5 w-5" /></span>
            <div>
              <h2 className="text-lg font-extrabold text-gray-900">Offer banner</h2>
              <p className="text-xs text-gray-500">Controls the offer shown on the public site. Optional start and end dates (India time) show and hide it automatically.</p>
            </div>
          </div>

          {offerQuery.isError && (
            <p className="mt-4 text-sm text-red-600">{offerQuery.error?.message}</p>
          )}
          {offerQuery.isLoading && <p className="mt-4 text-sm text-gray-500">Loading offer…</p>}

          {offerForm && (
            <div className="mt-5 grid gap-4 md:grid-cols-2">
              <div className="md:col-span-2">
                <label className="flex cursor-pointer items-center gap-2 text-sm font-semibold text-gray-700">
                  <input type="checkbox" checked={offerForm.enabled} onChange={(e) => setOfferForm({ ...offerForm, enabled: e.target.checked })} className="h-4 w-4 rounded border-gray-300 accent-amber-500" />
                  Show the offer on the site
                </label>
              </div>
              <div>
                <label className="mb-1 block text-xs font-semibold text-gray-600">Offer text (up to 160 characters)</label>
                <textarea value={offerForm.text} onChange={(e) => setOfferForm({ ...offerForm, text: e.target.value })} rows={3} className={INPUT} />
                <FieldError message={offerErrors.text} />
              </div>
              <div>
                <label className="mb-1 block text-xs font-semibold text-gray-600">Link (optional)</label>
                <input value={offerForm.link} onChange={(e) => setOfferForm({ ...offerForm, link: e.target.value })} placeholder="/catalogue or https://..." className={INPUT} />
                <FieldError message={offerErrors.link} />
              </div>
              <div>
                <label className="mb-1 block text-xs font-semibold text-gray-600">Start date (optional)</label>
                <input type="date" value={offerForm.startDate} onChange={(e) => setOfferForm({ ...offerForm, startDate: e.target.value })} className={INPUT} />
                <FieldError message={offerErrors.startDate} />
              </div>
              <div>
                <label className="mb-1 block text-xs font-semibold text-gray-600">End date (optional, last day shown)</label>
                <input type="date" value={offerForm.endDate} onChange={(e) => setOfferForm({ ...offerForm, endDate: e.target.value })} className={INPUT} />
                <FieldError message={offerErrors.endDate} />
              </div>
              <p className="text-xs font-semibold text-gray-600 md:col-span-2">
                Status: <span className="text-amber-700">{offerStatusLabel(offerQuery.data ?? offerForm, todayInIndia())}</span>
                <span className="font-normal text-gray-400"> (as last saved)</span>
              </p>
              <div className="md:col-span-2">
                <PictureSlot
                  label="Poster picture (optional, shown in the home page banner)"
                  currentKey={offerQuery.data?.image}
                  onSave={savePoster}
                  onRemove={deletePoster}
                  disabled={uploadPoster.isPending || removePoster.isPending}
                />
              </div>
              <div className="md:col-span-2">
                <button onClick={submitOffer} disabled={saveOffer.isPending} className="inline-flex items-center gap-2 rounded-lg bg-amber-500 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-600 disabled:opacity-60">
                  <Save className="h-4 w-4" /> {saveOffer.isPending ? 'Saving…' : 'Save offer'}
                </button>
              </div>
            </div>
          )}
        </section>

        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-extrabold text-gray-900">Products</h1>
            <p className="mt-1 text-sm text-gray-500">
              {searchText.trim() ? `${shownProducts.length} of ${products.length} items` : `${products.length} items`} · changes are saved to the live catalogue
            </p>
          </div>
          <div className="flex gap-2">
            <button onClick={() => setImportOpen(true)} className="inline-flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-semibold text-gray-700 hover:bg-gray-50">
              <Upload className="h-4 w-4" /> Import CSV
            </button>
            <button onClick={openCreate} className="inline-flex items-center gap-2 rounded-lg bg-amber-500 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-600">
              <Plus className="h-4 w-4" /> Add Product
            </button>
          </div>
        </div>

        <div className="relative mb-4">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            type="search"
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            placeholder="Search by product name, SKU or brand"
            aria-label="Search products"
            className={`${INPUT} pl-9`}
          />
        </div>

        {productsQuery.isError && (
          <div className="mb-4 flex flex-wrap items-center gap-3 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
            {productsQuery.error?.message}
            <button onClick={() => productsQuery.refetch()} className="rounded-lg border border-current px-3 py-1 text-xs font-semibold">Try again</button>
          </div>
        )}
        {productsQuery.isLoading && <p className="mb-4 text-sm text-gray-500">Loading products…</p>}

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
                  <th className="px-4 py-3">On site</th>
                  <th className="px-4 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {shownProducts.map((p) => {
                  const visible = p.status === 'PUBLISHED'
                  return (
                    <tr key={p.productId} className={visible ? 'hover:bg-gray-50' : 'bg-gray-50/60 hover:bg-gray-50'}>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1.5 font-semibold text-gray-900">{p.name}{p.isTrending && <Flame className="h-3.5 w-3.5 text-amber-500" />}</div>
                        <div className="text-xs text-gray-400">{p.sku}</div>
                      </td>
                      <td className="px-4 py-3 text-gray-700"><span className="text-xs">{(p.quantities || []).join(' · ')}</span></td>
                      <td className="px-4 py-3"><span className="rounded-md bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700">{p.category}</span></td>
                      <td className="px-4 py-3 text-gray-700">{p.brand}</td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-1">
                          {p.businessType?.map((b) => (
                            <span key={b} className="rounded bg-gray-100 px-1.5 py-0.5 text-[11px] text-gray-600">{b}</span>
                          ))}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <button
                          onClick={() => toggleVisibility(p)}
                          disabled={setVisibility.isPending}
                          aria-label={visible ? `Hide ${p.name}` : `Show ${p.name}`}
                          className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold disabled:opacity-60 ${visible ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-gray-200 bg-white text-gray-500'}`}
                        >
                          {visible ? <Eye className="h-3.5 w-3.5" /> : <EyeOff className="h-3.5 w-3.5" />}
                          {visible ? 'Visible' : 'Hidden'}
                        </button>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button onClick={() => openEdit(p)} className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-semibold text-gray-700 hover:border-amber-300 hover:text-amber-600">
                          <Pencil className="h-3.5 w-3.5" /> Edit
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      </main>

      {importOpen && (
        <ImportDialog categories={categoryNames} onClose={() => setImportOpen(false)} />
      )}
      {modalMode && (
        <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto px-4 py-8">
          <div className="absolute inset-0 bg-black/50" onClick={closeModal} />
          <div className="relative w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-base font-bold text-gray-900">{modalMode === 'create' ? 'Add New Product' : `Edit - ${form.sku}`}</h3>
              <button onClick={closeModal} aria-label="Close"><X className="h-5 w-5 text-gray-400" /></button>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="col-span-2">
                <label className="mb-1 block text-xs font-semibold text-gray-600">SKU {modalMode === 'edit' && '(cannot be changed)'}</label>
                <input value={form.sku} onChange={(e) => setForm({ ...form, sku: e.target.value })} disabled={modalMode === 'edit'} placeholder="e.g. KF-12" className={`${INPUT} disabled:bg-gray-50 disabled:text-gray-500`} />
                <FieldError message={formErrors.sku} />
              </div>
              <div className="col-span-2">
                <label className="mb-1 block text-xs font-semibold text-gray-600">Product Name</label>
                <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className={INPUT} />
                <FieldError message={formErrors.name} />
              </div>
              <div className="col-span-2">
                <label className="mb-1 block text-xs font-semibold text-gray-600">Available Quantities / Pack Sizes</label>
                <input value={form.quantities} onChange={(e) => setForm({ ...form, quantities: e.target.value })} placeholder="e.g. 100g, 500g, 1 kg, 5 kg" className={INPUT} />
                <FieldError message={formErrors.quantities} />
              </div>
              <div>
                <label className="mb-1 block text-xs font-semibold text-gray-600">Category</label>
                <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} className={`${INPUT} bg-white`}>
                  <option value="">Select category...</option>
                  {categoryNames.map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
                <FieldError message={formErrors.category} />
              </div>
              <div>
                <label className="mb-1 block text-xs font-semibold text-gray-600">Brand</label>
                <input value={form.brand} onChange={(e) => setForm({ ...form, brand: e.target.value })} className={INPUT} />
                <FieldError message={formErrors.brand} />
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
                <FieldError message={formErrors.businessType} />
              </div>
              <div className="col-span-2">
                <label className="mb-1 block text-xs font-semibold text-gray-600">Description</label>
                <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} rows={2} className={INPUT} />
                <FieldError message={formErrors.description} />
              </div>
              <div>
                <label className="mb-1 block text-xs font-semibold text-gray-600">Display order (optional)</label>
                <input value={form.sortRank} onChange={(e) => setForm({ ...form, sortRank: e.target.value })} inputMode="numeric" placeholder="e.g. 30" className={INPUT} />
                <FieldError message={formErrors.sortRank} />
              </div>
              <div className="flex items-end">
                <label className="flex cursor-pointer items-center gap-2 text-sm font-medium text-gray-700">
                  <input type="checkbox" checked={form.isTrending} onChange={(e) => setForm({ ...form, isTrending: e.target.checked })} className="h-4 w-4 rounded border-gray-300 accent-amber-500" />
                  Trending
                </label>
              </div>
              {modalMode === 'create' && (
                <div className="col-span-2">
                  <label className="flex cursor-pointer items-center gap-2 text-sm font-medium text-gray-700">
                    <input type="checkbox" checked={form.status === 'PUBLISHED'} onChange={(e) => setForm({ ...form, status: e.target.checked ? 'PUBLISHED' : 'ARCHIVED' })} className="h-4 w-4 rounded border-gray-300 accent-amber-500" />
                    Show on the site right away (otherwise it stays hidden)
                  </label>
                </div>
              )}
              {modalMode === 'edit' ? (
                <div className="col-span-2 space-y-2">
                  <p className="text-xs font-semibold text-gray-600">Pictures (up to {MAX_PICTURES}; the first is shown on the product card)</p>
                  {Array.from({ length: pictureSlots }, (_, index) => (
                    <PictureSlot
                      key={`${editing.productId}-${index}-${pictures[index]?.card ?? 'empty'}`}
                      label={`Picture ${index + 1}`}
                      currentKey={pictures[index]?.card}
                      onSave={savePicture(index + 1)}
                      onRemove={deletePicture(index + 1)}
                      disabled={uploadPicture.isPending || removePicture.isPending}
                    />
                  ))}
                  <p className="text-xs text-gray-400">Pictures are saved straight away; you do not need to press &quot;Save changes&quot;.</p>
                </div>
              ) : (
                <p className="col-span-2 text-xs text-gray-400">Save the product first, then edit it to add pictures. Products without a picture show a neutral placeholder.</p>
              )}
            </div>

            <div className="mt-6 flex justify-end gap-2">
              <button onClick={closeModal} className="rounded-lg border border-gray-200 px-4 py-2 text-sm font-semibold text-gray-700 hover:bg-gray-50">Cancel</button>
              <button onClick={saveProduct} disabled={saving} className="inline-flex items-center gap-2 rounded-lg bg-amber-500 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-600 disabled:cursor-not-allowed disabled:opacity-50">
                <Save className="h-4 w-4" /> {saving ? 'Saving…' : modalMode === 'create' ? 'Add Product' : 'Save changes'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
