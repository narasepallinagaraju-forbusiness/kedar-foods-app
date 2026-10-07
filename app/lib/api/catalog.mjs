export function filterCatalogItems(items, {
  search = '',
  brands = [],
  categories = [],
  businessTypes = [],
} = {}) {
  const query = search.trim().toLowerCase()

  return [...items]
    .filter((item) => {
      const matchesSearch = !query || item.searchText.toLowerCase().includes(query)
      const matchesBrand = brands.length === 0 || brands.includes(item.brand)
      const matchesCategory = categories.length === 0 || categories.includes(item.category)
      const matchesBusinessType =
        businessTypes.length === 0 ||
        item.businessType.some((type) => businessTypes.includes(type))

      return matchesSearch && matchesBrand && matchesCategory && matchesBusinessType
    })
    .sort((left, right) => {
      const trendingOrder = Number(Boolean(right.isTrending)) - Number(Boolean(left.isTrending))
      if (trendingOrder !== 0) return trendingOrder

      const rankOrder = left.sortRank - right.sortRank
      if (rankOrder !== 0) return rankOrder

      return left.name.localeCompare(right.name)
    })
}

export function paginateCatalog(items, page = 0, pageSize = 12) {
  if (!Number.isInteger(page) || page < 0) {
    throw new RangeError('page must be a non-negative integer')
  }
  if (!Number.isInteger(pageSize) || pageSize < 1) {
    throw new RangeError('pageSize must be a positive integer')
  }

  const start = page * pageSize
  return items.slice(start, start + pageSize)
}

export function getRelatedProducts(items, product, limit = 4) {
  return items
    .filter((item) => item.category === product.category && item.id !== product.id)
    .slice(0, limit)
}

export function getCatalogImageUrl(thumbnailKey) {
  return thumbnailKey ? `/${thumbnailKey}` : null
}
