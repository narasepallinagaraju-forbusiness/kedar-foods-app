const PRODUCT_PATH = /^\/products(?:\/(.*))?$/
const VALID_SLUG = /^[a-z0-9]+(-[a-z0-9]+)*$/

export function parseProductSlug(pathname) {
  const match = PRODUCT_PATH.exec(pathname)
  if (!match || !match[1]) return null

  const encodedSegment = match[1].replace(/\/+$/, '')
  if (!encodedSegment || encodedSegment.includes('/')) return null

  let slug
  try {
    slug = decodeURIComponent(encodedSegment).toLowerCase()
  } catch {
    return null
  }

  return VALID_SLUG.test(slug) ? slug : null
}

export function productApiPath(pathname) {
  const slug = parseProductSlug(pathname)
  return slug ? `/products/${encodeURIComponent(slug)}` : null
}
