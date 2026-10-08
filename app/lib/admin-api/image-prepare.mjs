// Prepares a picture in the browser: checks it, shrinks it and turns it into a small
// WebP before it is sent. The original photo never leaves the device.

export const MAX_SOURCE_BYTES = 10 * 1024 * 1024
export const MAX_ENCODED_BYTES = 560 * 1024
export const SOURCE_TYPES = ['image/jpeg', 'image/png', 'image/webp']
export const CARD_SIDE = 480
export const MAIN_SIDE = 1200
export const POSTER_SIDE = 1200
export const MAX_PICTURES = 3
const QUALITIES = [0.82, 0.68, 0.5]

export function validateSourceFile(file) {
  if (!file || typeof file.size !== 'number') return 'Please choose a picture.'
  if (!SOURCE_TYPES.includes(file.type)) return 'Only JPEG, PNG or WebP pictures are allowed.'
  if (file.size > MAX_SOURCE_BYTES) return 'The picture is larger than 10 MB. Please choose a smaller one.'
  if (file.size === 0) return 'The picture file is empty.'
  return null
}

export function validateImageUrl(value) {
  const text = String(value ?? '').trim()
  if (!text) return 'Enter the picture web address.'
  let url
  try {
    url = new URL(text)
  } catch {
    return 'Enter a full web address starting with https://'
  }
  if (url.protocol !== 'https:') return 'The web address must start with https://'
  return null
}

// Shrinks to fit inside maxSide on the longest edge; never enlarges.
export function fitSize(width, height, maxSide) {
  const longest = Math.max(width, height)
  if (!(longest > 0)) throw new Error('The picture has no size.')
  if (longest <= maxSide) return { width, height }
  const scale = maxSide / longest
  return {
    width: Math.max(1, Math.round(width * scale)),
    height: Math.max(1, Math.round(height * scale)),
  }
}

// Slot 1 is `image`; slots 2 and 3 are `gallery`. Incomplete entries are skipped.
export function productPictures(product) {
  const entries = [product?.image, ...(Array.isArray(product?.gallery) ? product.gallery : [])]
  return entries
    .slice(0, MAX_PICTURES)
    .filter((e) => e && typeof e.card === 'string' && typeof e.main === 'string')
}

export function mediaUrl(key) {
  return `/${String(key).replace(/^\/+/, '')}`
}

function blobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(new Error('Could not read the picture.'))
    reader.onload = () => resolve(String(reader.result).split(',')[1] ?? '')
    reader.readAsDataURL(blob)
  })
}

async function toWebp(bitmap, maxSide) {
  const { width, height } = fitSize(bitmap.width, bitmap.height, maxSide)
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const context = canvas.getContext('2d')
  if (!context) throw new Error('This browser cannot prepare pictures.')
  context.drawImage(bitmap, 0, 0, width, height)
  for (const quality of QUALITIES) {
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/webp', quality))
    if (!blob || blob.type !== 'image/webp') {
      throw new Error('This browser cannot save WebP pictures. Please use a recent Chrome, Edge, Firefox or Safari.')
    }
    if (blob.size <= MAX_ENCODED_BYTES) return blobToBase64(blob)
  }
  throw new Error('The picture is still too large after shrinking. Please choose a simpler one.')
}

export async function fetchImageFromUrl(url, fetchImpl = globalThis.fetch) {
  const problem = validateImageUrl(url)
  if (problem) throw new Error(problem)
  let response
  try {
    response = await fetchImpl(String(url).trim(), { mode: 'cors', credentials: 'omit' })
  } catch {
    throw new Error('That website does not allow its picture to be used here. Download the picture and upload it instead.')
  }
  if (!response.ok) throw new Error(`The picture could not be downloaded (HTTP ${response.status}).`)
  const blob = await response.blob()
  const problemWithFile = validateSourceFile(blob)
  if (problemWithFile) throw new Error(problemWithFile)
  return blob
}

// source: { file } or { url }. sides: e.g. { card: 480, main: 1200 }.
export async function prepareImages(source, sides) {
  let blob
  if (source.file) {
    const problem = validateSourceFile(source.file)
    if (problem) throw new Error(problem)
    blob = source.file
  } else {
    blob = await fetchImageFromUrl(source.url)
  }
  let bitmap
  try {
    bitmap = await createImageBitmap(blob)
  } catch {
    throw new Error('That file could not be read as a picture.')
  }
  try {
    const result = {}
    for (const [name, side] of Object.entries(sides)) {
      result[name] = await toWebp(bitmap, side)
    }
    return result
  } finally {
    bitmap.close?.()
  }
}
