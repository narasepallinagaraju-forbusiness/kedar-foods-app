import assert from 'node:assert/strict'
import test from 'node:test'

import {
  filterCatalogItems,
  getCatalogImageUrl,
  getRelatedProducts,
  paginateCatalog,
} from './catalog.mjs'

const products = [
  {
    id: 'p2',
    name: 'Amul Butter',
    brand: 'Amul',
    category: 'Dairy',
    businessType: ['Bakery', 'Cafe'],
    isTrending: true,
    searchText: 'amul butter amul dairy',
    sortRank: 20,
    thumbnailKey: 'media/p2.webp',
  },
  {
    id: 'p1',
    name: 'Amul Cream',
    brand: 'Amul',
    category: 'Dairy',
    businessType: ['Restaurant'],
    isTrending: false,
    searchText: 'amul cream amul dairy',
    sortRank: 10,
  },
  {
    id: 'p3',
    name: 'Callebaut Chocolate',
    brand: 'Callebaut',
    category: 'Chocolate',
    businessType: ['Cafe'],
    isTrending: true,
    searchText: 'callebaut chocolate callebaut chocolate',
    sortRank: 10,
    thumbnailKey: 'media/p3.webp',
  },
]

test('search trims input and matches only the index searchText case-insensitively', () => {
  assert.deepEqual(
    filterCatalogItems(products, { search: '  BUTTER  ' }).map((item) => item.id),
    ['p2'],
  )
})

test('search ignores name and brand text that is absent from searchText', () => {
  const items = [{ ...products[0], searchText: 'something else' }]
  assert.deepEqual(filterCatalogItems(items, { search: 'butter' }), [])
})

test('selected categories OR within the category group', () => {
  assert.deepEqual(
    filterCatalogItems(products, { categories: ['Dairy', 'Chocolate'] }).map((item) => item.id),
    ['p3', 'p2', 'p1'],
  )
})

test('selected values OR within groups while active groups combine with AND', () => {
  const result = filterCatalogItems(products, {
    brands: ['Amul', 'Callebaut'],
    categories: ['Dairy'],
    businessTypes: ['Bakery', 'Restaurant'],
  })

  assert.deepEqual(result.map((item) => item.id), ['p2', 'p1'])
})

test('orders trending products first, then rank, then name deterministically', () => {
  const ties = [
    { ...products[0], id: 'z', name: 'Zulu', sortRank: 1 },
    { ...products[0], id: 'a', name: 'Alpha', sortRank: 1 },
  ]

  assert.deepEqual(filterCatalogItems([...products, ...ties]).map((item) => item.id), [
    'a',
    'z',
    'p3',
    'p2',
    'p1',
  ])
})

test('pagination returns consecutive pages and does not mutate the source', () => {
  const items = Array.from({ length: 25 }, (_, index) => index)

  assert.deepEqual(paginateCatalog(items).length, 12)
  assert.deepEqual(paginateCatalog(items, 1), Array.from({ length: 12 }, (_, i) => i + 12))
  assert.deepEqual(paginateCatalog(items, 2), [24])
  assert.equal(items[0], 0)
})

test('related products share category, exclude the current item, and cap at four', () => {
  const related = Array.from({ length: 7 }, (_, index) => ({
    id: `p${index}`,
    category: 'Dairy',
  }))
  const result = getRelatedProducts(related, { id: 'p0', category: 'Dairy' })

  assert.equal(result.length, 4)
  assert.ok(result.every((item) => item.id !== 'p0'))
})

test('related products exclude other categories', () => {
  const items = [
    { id: 'a', category: 'Dairy' },
    { id: 'b', category: 'Chocolate' },
    { id: 'c', category: 'Dairy' },
  ]
  const result = getRelatedProducts(items, { id: 'a', category: 'Dairy' })

  assert.deepEqual(result.map((item) => item.id), ['c'])
})

test('catalog image URLs use the final key and missing keys have no URL', () => {
  assert.equal(getCatalogImageUrl('media/products/p1/card.webp'), '/media/products/p1/card.webp')
  assert.equal(getCatalogImageUrl(undefined), null)
})
