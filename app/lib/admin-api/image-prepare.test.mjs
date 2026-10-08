import assert from 'node:assert/strict'
import test from 'node:test'

import {
  fetchImageFromUrl,
  fitSize,
  mediaUrl,
  productPictures,
  validateImageUrl,
  validateSourceFile,
} from './image-prepare.mjs'

test('source files must be JPEG, PNG or WebP and at most 10 MB', () => {
  assert.equal(validateSourceFile({ type: 'image/jpeg', size: 2_000_000 }), null)
  assert.equal(validateSourceFile({ type: 'image/png', size: 10 * 1024 * 1024 }), null)
  assert.match(validateSourceFile({ type: 'image/gif', size: 100 }), /JPEG, PNG or WebP/)
  assert.match(validateSourceFile({ type: 'application/pdf', size: 100 }), /JPEG, PNG or WebP/)
  assert.match(validateSourceFile({ type: 'image/jpeg', size: 10 * 1024 * 1024 + 1 }), /10 MB/)
  assert.match(validateSourceFile({ type: 'image/jpeg', size: 0 }), /empty/)
  assert.match(validateSourceFile(null), /choose/)
})

test('picture web addresses must be https', () => {
  assert.equal(validateImageUrl('https://example.com/a.jpg'), null)
  assert.match(validateImageUrl('http://example.com/a.jpg'), /https/)
  assert.match(validateImageUrl('javascript:alert(1)'), /https/)
  assert.match(validateImageUrl('not a url'), /https/)
  assert.match(validateImageUrl('   '), /Enter/)
})

test('fitSize shrinks to the longest edge and never enlarges', () => {
  assert.deepEqual(fitSize(4000, 3000, 1200), { width: 1200, height: 900 })
  assert.deepEqual(fitSize(3000, 4000, 480), { width: 360, height: 480 })
  assert.deepEqual(fitSize(300, 200, 480), { width: 300, height: 200 })
  assert.throws(() => fitSize(0, 0, 480))
})

test('productPictures lists slot 1 then the gallery, skipping broken entries', () => {
  const a = { card: 'media/a-card.webp', main: 'media/a-main.webp' }
  const b = { card: 'media/b-card.webp', main: 'media/b-main.webp' }
  assert.deepEqual(productPictures({ image: a, gallery: [b] }), [a, b])
  assert.deepEqual(productPictures({ image: {}, gallery: [] }), [])
  assert.deepEqual(productPictures({}), [])
  assert.deepEqual(productPictures({ image: a, gallery: [{ card: 1 }, b, a, b] }), [a, b])
  assert.equal(productPictures({ image: a, gallery: [b, b, b] }).length, 3)
})

test('mediaUrl is a same-site path', () => {
  assert.equal(mediaUrl('media/products/x/card.webp'), '/media/products/x/card.webp')
})

test('fetchImageFromUrl explains CORS and HTTP failures and rejects non-pictures', async () => {
  await assert.rejects(
    fetchImageFromUrl('https://x.test/a.jpg', async () => {
      throw new TypeError('blocked')
    }),
    /does not allow/,
  )
  await assert.rejects(
    fetchImageFromUrl('https://x.test/a.jpg', async () => ({ ok: false, status: 404 })),
    /HTTP 404/,
  )
  await assert.rejects(
    fetchImageFromUrl('https://x.test/a.jpg', async () => ({
      ok: true,
      blob: async () => ({ type: 'text/html', size: 50 }),
    })),
    /JPEG, PNG or WebP/,
  )
  await assert.rejects(fetchImageFromUrl('http://x.test/a.jpg', async () => ({})), /https/)
  const good = { type: 'image/png', size: 500 }
  assert.equal(
    await fetchImageFromUrl('https://x.test/a.png', async () => ({ ok: true, blob: async () => good })),
    good,
  )
})
