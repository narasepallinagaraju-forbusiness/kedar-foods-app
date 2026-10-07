import assert from 'node:assert/strict'
import test from 'node:test'

import { safeLink } from './safe-link.mjs'

test('accepts a same-origin relative path', () => {
  assert.equal(safeLink('/offers/spring'), '/offers/spring')
})

test('accepts an HTTPS URL', () => {
  assert.equal(safeLink('https://example.com/offers'), 'https://example.com/offers')
})

test('rejects protocol-relative URLs', () => {
  assert.equal(safeLink('//evil.com'), null)
})

test('rejects backslash-based relative paths', () => {
  assert.equal(safeLink('/\\evil.com'), null)
  assert.equal(safeLink('/\\/evil.com'), null)
})

test('rejects script and non-HTTPS schemes', () => {
  assert.equal(safeLink('javascript:alert(1)'), null)
  assert.equal(safeLink('http://example.com'), null)
})

test('rejects empty and non-string values', () => {
  assert.equal(safeLink(''), null)
  assert.equal(safeLink(null), null)
  assert.equal(safeLink(12), null)
})

test('rejects whitespace and control characters', () => {
  assert.equal(safeLink('/an offer'), null)
  assert.equal(safeLink('https://example.com/\npath'), null)
})
