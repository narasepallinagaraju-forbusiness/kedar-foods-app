'use client'

import { useState } from 'react'
import { X, Upload } from 'lucide-react'
import { useImportProducts } from '@/lib/admin-api/hooks'
import { chunkRows, prepareImport } from '@/lib/admin-api/csv-import.mjs'

const BTN = 'rounded-lg px-4 py-2 text-sm font-semibold'

export default function ImportDialog({ categories, onClose }) {
  const importRows = useImportProducts()
  const [fileName, setFileName] = useState('')
  const [parsed, setParsed] = useState(null)
  const [running, setRunning] = useState(false)
  const [progress, setProgress] = useState('')
  const [summary, setSummary] = useState(null)

  const good = parsed?.rows?.filter((row) => row.errors.length === 0) ?? []
  const bad = parsed?.rows?.filter((row) => row.errors.length > 0) ?? []
  const liveCount = good.filter((row) => row.status === 'PUBLISHED').length

  async function onFile(event) {
    const file = event.target.files?.[0]
    setSummary(null)
    setParsed(null)
    if (!file) return
    setFileName(file.name)
    if (file.size > 1024 * 1024) {
      setParsed({ fileError: 'This file is larger than 1 MB. Split it into smaller files.' })
      return
    }
    setParsed(prepareImport(await file.text(), { categories }))
  }

  async function start() {
    setRunning(true)
    const total = { created: 0, skipped: 0, failed: [], stopped: null, indexFailed: false }
    const batches = chunkRows(good)
    for (let i = 0; i < batches.length; i += 1) {
      setProgress(`Importing batch ${i + 1} of ${batches.length}…`)
      try {
        const result = await importRows.mutateAsync(batches[i].map((row) => row.payload))
        total.created += result.created
        total.skipped += result.skipped
        if (result.indexRebuilt === false) total.indexFailed = true
        result.results
          .filter((r) => r.result === 'failed')
          .forEach((r) => {
            const row = batches[i][r.row]
            total.failed.push(`Line ${row.line} (${row.sku}): ${r.errors.map((e) => e.message).join(' ')}`)
          })
      } catch (error) {
        total.stopped = error?.message || 'The import stopped unexpectedly.'
        break
      }
    }
    setProgress('')
    setRunning(false)
    setSummary(total)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto px-4 py-8">
      <div className="fixed inset-0 bg-black/40" onClick={running ? undefined : onClose} />
      <div className="relative z-10 w-full rounded-2xl bg-white p-6 shadow-xl" style={{ maxWidth: 672 }}>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-bold text-gray-900">Import products from CSV</h2>
          <button onClick={onClose} disabled={running} aria-label="Close">
            <X className="h-5 w-5" />
          </button>
        </div>

        {!summary && (
          <>
            <p className="mb-3 text-sm text-gray-600">
              Choose a CSV file (UTF-8, up to 500 products). Use <b>|</b> between several business
              types or pack sizes. Existing SKUs are skipped, never changed.
            </p>
            <input type="file" accept=".csv,text/csv" onChange={onFile} disabled={running} />
          </>
        )}

        {parsed?.fileError && !summary && (
          <p className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">{parsed.fileError}</p>
        )}

        {parsed?.rows && !summary && (
          <div className="mt-4">
            <p className="text-sm text-gray-700">
              <b>{fileName}</b>: {good.length} ready, {bad.length} with problems.
            </p>
            {liveCount > 0 && (
              <p className="mt-2 rounded-lg bg-amber-50 p-3 text-sm text-amber-800">
                {liveCount} product(s) will go live on the website right away.
              </p>
            )}
            {bad.length > 0 && (
              <div className="mt-3 overflow-y-auto rounded-lg border p-3 text-sm text-red-700" style={{ maxHeight: 224, borderColor: '#fecaca' }}>
                <p className="mb-1 font-semibold">These rows will be left out. Fix them and import again:</p>
                {bad.map((row) => (
                  <p key={row.line} className="mt-1">
                    Line {row.line}{row.sku ? ` (${row.sku})` : ''}: {row.errors.join(' ')}
                  </p>
                ))}
              </div>
            )}
            <div className="mt-4 flex items-center gap-3">
              <button
                onClick={start}
                disabled={running || good.length === 0}
                className={`${BTN} inline-flex items-center gap-2 bg-amber-500 text-white hover:bg-amber-600 disabled:opacity-50`}
              >
                <Upload className="h-4 w-4" /> Import {good.length} product{good.length === 1 ? '' : 's'}
              </button>
              {progress && <span className="text-sm text-gray-500">{progress}</span>}
            </div>
          </div>
        )}

        {summary && (
          <div className="text-sm text-gray-700">
            <p className="rounded-lg p-3" style={{ background: '#f0fdf4', color: '#166534' }}>
              Created {summary.created}, skipped {summary.skipped} existing, {summary.failed.length} rejected
              by the server.
            </p>
            {summary.stopped && (
              <p className="mt-3 rounded-lg bg-red-50 p-3 text-red-700">
                Stopped early: {summary.stopped} Re-importing the same file is safe: products already
                created are skipped.
              </p>
            )}
            {summary.indexFailed && (
              <p className="mt-3 rounded-lg bg-amber-50 p-3" style={{ color: '#92400e' }}>
                Products were saved but the public list could not be refreshed. Open and save any live
                product again to refresh it.
              </p>
            )}
            {summary.failed.map((line) => (
              <p key={line} className="mt-2 text-red-700">{line}</p>
            ))}
            <button onClick={onClose} className={`${BTN} mt-4 bg-gray-900 text-white`}>
              Done
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
