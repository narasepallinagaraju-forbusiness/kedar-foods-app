import assert from 'node:assert/strict'
import test from 'node:test'

import { parseProductSlug, productApiPath } from './slug.mjs'

test('parses a normal product route', () => {
  assert.equal(parseProductSlug('/products/amul-unsalted-butter'), 'amul-unsalted-butter')
  assert.equal(productApiPath('/products/amul-unsalted-butter'), '/products/amul-unsalted-butter')
})

test('removes a trailing slash and lowercases the slug', () => {
  assert.equal(parseProductSlug('/products/Amul-Unsalted-Butter/'), 'amul-unsalted-butter')
})

test('decodes an encoded slug before validating', () => {
  assert.equal(parseProductSlug('/products/Amul%2DUnsalted%2DButter'), 'amul-unsalted-butter')
})

test('empty product paths produce no API path', () => {
  let apiCalls = 0
  for (const pathname of ['/products/', '/products']) {
    const apiPath = productApiPath(pathname)
    if (apiPath) apiCalls += 1
    assert.equal(apiPath, null)
  }
  assert.equal(apiCalls, 0)
})

test('invalid slugs produce not-found input without an API request path', () => {
  let apiCalls = 0
  const apiPath = productApiPath('/products/not_a_valid_slug')
  if (apiPath) apiCalls += 1

  assert.equal(apiPath, null)
  assert.equal(apiCalls, 0)
})

test('rejects malformed encoding and extra path segments', () => {
  assert.equal(parseProductSlug('/products/%E0%A4%A'), null)
  assert.equal(parseProductSlug('/products/amul/butter'), null)
})
