import { fetchWithTimeout } from './fetch-timeout.mjs'

export async function fetchCatalogIndex({ signal } = {}) {
  const response = await fetchWithTimeout('/data/catalog-index.json', {
    headers: { Accept: 'application/json' },
    signal,
  })

  if (!response.ok) {
    throw new Error(`Catalog request failed with HTTP ${response.status}`)
  }

  let catalog
  try {
    catalog = await response.json()
  } catch {
    throw new Error('The catalog endpoint returned invalid JSON.')
  }

  if (!catalog || typeof catalog !== 'object' || !Array.isArray(catalog.items)) {
    throw new Error('The catalog endpoint returned an invalid catalog index.')
  }

  const validItems = catalog.items.every((item) =>
    item &&
    typeof item.id === 'string' &&
    typeof item.sku === 'string' &&
    typeof item.slug === 'string' &&
    typeof item.name === 'string' &&
    typeof item.brand === 'string' &&
    typeof item.category === 'string' &&
    Array.isArray(item.businessType) &&
    Array.isArray(item.quantities) &&
    typeof item.isTrending === 'boolean' &&
    typeof item.searchText === 'string' &&
    Number.isFinite(item.sortRank) &&
    (item.thumbnailKey === undefined || typeof item.thumbnailKey === 'string'),
  )

  if (!validItems) {
    throw new Error('The catalog endpoint returned an invalid product entry.')
  }

  return catalog
}
