'use client'

import { useState } from 'react'
import { Camera, ImagePlus, Link2, Trash2, Upload } from 'lucide-react'
import { mediaUrl, validateImageUrl } from '@/lib/admin-api/image-prepare.mjs'

const BUTTON = 'inline-flex items-center gap-1.5 rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-semibold text-gray-700 hover:border-amber-300 hover:text-amber-600 disabled:opacity-50'

// One picture. The owner picks ONE source: a file/camera photo, or a web address.
// onSave({ file } | { url }) and onRemove() are async and may throw an Error.
export default function PictureSlot({ label, currentKey, onSave, onRemove, disabled }) {
  const [source, setSource] = useState(null) // null | 'file' | 'url'
  const [url, setUrl] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const run = async (action) => {
    setError('')
    setBusy(true)
    try {
      await action()
      setSource(null)
      setUrl('')
    } catch (e) {
      setError(e?.message || 'Something went wrong.')
    } finally {
      setBusy(false)
    }
  }

  const onFile = (event) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (file) run(() => onSave({ file }))
  }

  const submitUrl = () => {
    const problem = validateImageUrl(url)
    if (problem) {
      setError(problem)
      return
    }
    run(() => onSave({ url }))
  }

  const off = disabled || busy

  return (
    <div className="rounded-lg border border-gray-200 p-3">
      <div className="flex items-start gap-3">
        <div className="flex shrink-0 items-center justify-center overflow-hidden rounded-lg bg-gray-100 text-gray-300" style={{ width: 64, height: 64 }}>
          {currentKey ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={mediaUrl(currentKey)} alt={label} style={{ width: 64, height: 64, objectFit: 'cover' }} />
          ) : (
            <ImagePlus className="h-6 w-6" />
          )}
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold text-gray-700">{label}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            <label className={`${BUTTON} cursor-pointer ${off ? 'pointer-events-none opacity-50' : ''}`} onClick={() => setSource('file')}>
              <Upload className="h-3.5 w-3.5" /> Upload picture
              <input type="file" accept="image/jpeg,image/png,image/webp" className="hidden" onChange={onFile} disabled={off} />
            </label>
            <label className={`${BUTTON} cursor-pointer ${off ? 'pointer-events-none opacity-50' : ''}`} onClick={() => setSource('file')}>
              <Camera className="h-3.5 w-3.5" /> Take photo
              <input type="file" accept="image/*" capture="environment" className="hidden" onChange={onFile} disabled={off} />
            </label>
            <button type="button" onClick={() => setSource(source === 'url' ? null : 'url')} disabled={off} className={BUTTON}>
              <Link2 className="h-3.5 w-3.5" /> Use web address
            </button>
            {currentKey && (
              <button type="button" onClick={() => run(onRemove)} disabled={off} className={BUTTON} style={{ color: "#dc2626" }}>
                <Trash2 className="h-3.5 w-3.5" /> Remove
              </button>
            )}
          </div>
          {source === 'url' && (
            <div className="mt-2 flex gap-2">
              <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://..." className="w-full rounded-lg border border-gray-200 px-3 py-1.5 text-sm outline-none focus:border-amber-400" />
              <button type="button" onClick={submitUrl} disabled={off} className="rounded-lg bg-amber-500 px-3 py-1.5 text-xs font-semibold text-white hover:bg-amber-600 disabled:opacity-50">Use</button>
            </div>
          )}
          {busy && <p className="mt-2 text-xs text-gray-500">Preparing and saving the picture…</p>}
          {error && <p role="alert" className="mt-2 text-xs text-red-600">{error}</p>}
        </div>
      </div>
    </div>
  )
}
