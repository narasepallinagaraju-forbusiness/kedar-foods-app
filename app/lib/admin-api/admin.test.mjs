import assert from 'node:assert/strict'
import test from 'node:test'

import { clearAdminKey, getAdminKey, setAdminKey } from './admin-key.mjs'
import { AdminApiError, adminRequest, messageForStatus } from './request.mjs'
import {
  buildOfferPayload,
  buildProductPayload,
  EMPTY_PRODUCT_FORM,
  parseQuantities,
  productToForm,
  validateOfferForm,
  validateProductForm,
} from './validation.mjs'

function fakeStorage() {
  const data = new Map()
  return {
    getItem: (k) => (data.has(k) ? data.get(k) : null),
    setItem: (k, v) => data.set(k, v),
    removeItem: (k) => data.delete(k),
  }
}

function fakeFetch(status, payload, calls = []) {
  return async (url, init) => {
    calls.push({ url, init })
    return {
      ok: status >= 200 && status < 300,
      status,
      json: async () => {
        if (payload === undefined) throw new Error('no body')
        return payload
      },
    }
  }
}

const VALID_FORM = {
  ...EMPTY_PRODUCT_FORM,
  sku: 'kf-12',
  name: ' Fresh Cream ',
  brand: 'Amul',
  category: 'Dairy',
  businessType: ['Cafe'],
  quantities: '500g, 1 kg,',
}

test('admin key lives only in the given storage and can be cleared', () => {
  const storage = fakeStorage()
  assert.equal(getAdminKey(storage), '')
  assert.equal(setAdminKey('secret-value', storage), true)
  assert.equal(getAdminKey(storage), 'secret-value')
  clearAdminKey(storage)
  assert.equal(getAdminKey(storage), '')
})

test('admin key helpers never throw when storage is unavailable', () => {
  const broken = {
    getItem: () => { throw new Error('blocked') },
    setItem: () => { throw new Error('blocked') },
    removeItem: () => { throw new Error('blocked') },
  }
  assert.equal(getAdminKey(broken), '')
  assert.equal(setAdminKey('x', broken), false)
  assert.doesNotThrow(() => clearAdminKey(broken))
  assert.equal(getAdminKey(null), '')
})

test('adminRequest sends the key header, JSON body and method', async () => {
  const calls = []
  const result = await adminRequest({
    baseUrl: 'https://api.example.com',
    adminKey: 'the-key',
    method: 'POST',
    path: '/admin/products',
    body: { name: 'x' },
    fetchImpl: fakeFetch(201, { product: {} }, calls),
  })
  assert.deepEqual(result, { product: {} })
  assert.equal(calls[0].url, 'https://api.example.com/admin/products')
  assert.equal(calls[0].init.method, 'POST')
  assert.equal(calls[0].init.headers['X-Admin-Key'], 'the-key')
  assert.equal(calls[0].init.headers['Content-Type'], 'application/json')
  assert.equal(calls[0].init.body, '{"name":"x"}')
})

test('adminRequest GET sends no body or content type', async () => {
  const calls = []
  await adminRequest({
    baseUrl: 'https://api.example.com',
    adminKey: 'k',
    path: '/admin/products',
    fetchImpl: fakeFetch(200, { products: [] }, calls),
  })
  assert.equal(calls[0].init.body, undefined)
  assert.equal(calls[0].init.headers['Content-Type'], undefined)
})

test('adminRequest without a key fails before any network call', async () => {
  const calls = []
  await assert.rejects(
    adminRequest({
      baseUrl: 'https://api.example.com',
      adminKey: '',
      path: '/admin/products',
      fetchImpl: fakeFetch(200, {}, calls),
    }),
    (error) => error instanceof AdminApiError && error.status === 401,
  )
  assert.equal(calls.length, 0)
})

test('adminRequest maps errors to friendly messages without echoing the key', async () => {
  const run = (status, payload) =>
    adminRequest({
      baseUrl: 'https://a.example',
      adminKey: 'super-secret-key',
      path: '/x',
      fetchImpl: fakeFetch(status, payload),
    }).catch((error) => error)

  const unauthorized = await run(401, { error: 'unauthorized' })
  assert.equal(unauthorized.status, 401)
  assert.match(unauthorized.message, /admin key was rejected/)
  assert.ok(!unauthorized.message.includes('super-secret-key'))

  assert.match((await run(409, { error: 'version_conflict' })).message, /Someone else/)
  assert.match((await run(409, { error: 'duplicate_sku' })).message, /SKU/)
  assert.match((await run(503, undefined)).message, /not ready/)
  assert.match((await run(500, undefined)).message, /HTTP 500/)

  const invalid = await run(400, {
    error: 'validation_failed',
    details: [{ field: 'name', message: 'must be text' }],
  })
  assert.equal(invalid.message, 'name: must be text')
  assert.deepEqual(invalid.details, [{ field: 'name', message: 'must be text' }])
})

test('adminRequest rejects a successful but non-JSON response', async () => {
  await assert.rejects(
    adminRequest({
      baseUrl: 'https://a.example',
      adminKey: 'k',
      path: '/x',
      fetchImpl: fakeFetch(200, undefined),
    }),
    /invalid response/,
  )
})

test('messageForStatus falls back for unknown statuses', () => {
  assert.equal(messageForStatus(418, null), 'The request failed (HTTP 418).')
})

test('parseQuantities trims and drops empty entries', () => {
  assert.deepEqual(parseQuantities(' 500g, ,1 kg ,'), ['500g', '1 kg'])
  assert.deepEqual(parseQuantities(undefined), [])
})

test('a valid new product passes validation and builds a safe payload', () => {
  assert.deepEqual(validateProductForm(VALID_FORM, { mode: 'create', categories: ['Dairy'] }), {})
  const payload = buildProductPayload(VALID_FORM, { mode: 'create' })
  assert.deepEqual(payload, {
    name: 'Fresh Cream',
    brand: 'Amul',
    category: 'Dairy',
    businessType: ['Cafe'],
    quantities: ['500g', '1 kg'],
    description: '',
    isTrending: false,
    sku: 'KF-12',
    status: 'ARCHIVED',
  })
  assert.ok(!('image' in payload) && !('slug' in payload) && !('productId' in payload))
})

test('update payload carries the version and never the sku or status', () => {
  const payload = buildProductPayload(VALID_FORM, { mode: 'update', version: 4 })
  assert.equal(payload.version, 4)
  assert.ok(!('sku' in payload) && !('status' in payload))
})

test('create can request PUBLISHED explicitly, anything else is hidden', () => {
  assert.equal(
    buildProductPayload({ ...VALID_FORM, status: 'PUBLISHED' }, { mode: 'create' }).status,
    'PUBLISHED',
  )
  assert.equal(
    buildProductPayload({ ...VALID_FORM, status: 'weird' }, { mode: 'create' }).status,
    'ARCHIVED',
  )
})

test('sortRank is sent as a number only when provided', () => {
  assert.equal(
    buildProductPayload({ ...VALID_FORM, sortRank: ' 30 ' }, { mode: 'create' }).sortRank,
    30,
  )
  assert.ok(!('sortRank' in buildProductPayload(VALID_FORM, { mode: 'create' })))
})

test('product validation reports each bad field', () => {
  const errors = validateProductForm(
    {
      ...EMPTY_PRODUCT_FORM,
      sku: 'x',
      name: 'A',
      brand: '',
      category: 'Nope',
      quantities: '1kg, 1kg',
      description: 'x'.repeat(2001),
      sortRank: '1.5',
    },
    { mode: 'create', categories: ['Dairy'] },
  )
  for (const field of ['sku', 'name', 'brand', 'category', 'businessType', 'quantities', 'description', 'sortRank']) {
    assert.ok(errors[field], `expected an error for ${field}`)
  }
})

test('update mode does not validate the sku', () => {
  const errors = validateProductForm({ ...VALID_FORM, sku: '' }, { mode: 'update', categories: [] })
  assert.ok(!errors.sku)
})

test('quantity limits: more than 12 or longer than 20 chars are rejected', () => {
  const many = Array.from({ length: 13 }, (_, i) => `${i}kg`).join(',')
  assert.ok(validateProductForm({ ...VALID_FORM, quantities: many }, { mode: 'update' }).quantities)
  assert.ok(validateProductForm({ ...VALID_FORM, quantities: 'x'.repeat(21) }, { mode: 'update' }).quantities)
})

test('productToForm round-trips editable fields and defaults missing ones', () => {
  const form = productToForm({
    sku: 'KF-01',
    name: 'Butter',
    brand: 'Amul',
    category: 'Dairy',
    businessType: ['Cafe'],
    quantities: ['500g', '1 kg'],
    sortRank: 10,
    status: 'PUBLISHED',
  })
  assert.equal(form.quantities, '500g, 1 kg')
  assert.equal(form.sortRank, '10')
  assert.equal(form.description, '')
  assert.equal(form.status, 'PUBLISHED')
  assert.equal(productToForm({}).sortRank, '')
})

test('offer validation: text required when on, link rule matches customer safeLink', () => {
  assert.deepEqual(validateOfferForm({ enabled: false, text: '', link: '' }), {})
  assert.ok(validateOfferForm({ enabled: true, text: ' ', link: '' }).text)
  assert.ok(validateOfferForm({ enabled: false, text: 'x'.repeat(161), link: '' }).text)
  for (const link of ['//evil.com', '/\\evil.com', 'http://x.com', 'javascript:alert(1)', '/a b']) {
    assert.ok(validateOfferForm({ enabled: true, text: 'Sale', link }).link, link)
  }
  for (const link of ['/catalogue', 'https://example.com/x', '']) {
    assert.deepEqual(validateOfferForm({ enabled: true, text: 'Sale', link }), {})
  }
})

test('offer payload contains only enabled, text and link', () => {
  assert.deepEqual(
    buildOfferPayload({ enabled: true, text: ' Sale ', link: '/catalogue', image: 'x' }),
    { enabled: true, text: 'Sale', link: '/catalogue' },
  )
})
