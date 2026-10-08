import { validateProductForm } from './validation.mjs'

export const IMPORT_MAX_ROWS = 500
export const IMPORT_MAX_BYTES = 1024 * 1024
export const IMPORT_BATCH_SIZE = 50
export const IMPORT_BUSINESS_TYPES = ['Bakery', 'Cafe', 'Restaurant']

const REQUIRED_COLUMNS = ['sku', 'name', 'brand', 'category', 'businessType', 'quantities']
const KNOWN_COLUMNS = [...REQUIRED_COLUMNS, 'description', 'isTrending', 'sortRank', 'status']

// Small RFC 4180 parser: quotes, doubled quotes, commas/newlines inside quotes, BOM.
export function parseCsv(text) {
  const source = String(text ?? '').replace(/^\uFEFF/, '')
  const rows = []
  let row = []
  let field = ''
  let quoted = false
  let touched = false

  for (let i = 0; i < source.length; i += 1) {
    const char = source[i]
    if (quoted) {
      if (char === '"' && source[i + 1] === '"') {
        field += '"'
        i += 1
      } else if (char === '"') {
        quoted = false
      } else {
        field += char
      }
    } else if (char === '"') {
      quoted = true
      touched = true
    } else if (char === ',') {
      row.push(field)
      field = ''
      touched = true
    } else if (char === '\n' || char === '\r') {
      if (char === '\r' && source[i + 1] === '\n') i += 1
      if (touched || field !== '') {
        row.push(field)
        rows.push(row)
      }
      row = []
      field = ''
      touched = false
    } else {
      field += char
      touched = true
    }
  }
  if (quoted) throw new Error('A quoted value is never closed. Check for a stray " in the file.')
  if (touched || field !== '') {
    row.push(field)
    rows.push(row)
  }
  return rows
}

function canonical(value, allowed) {
  const wanted = value.trim().toLowerCase()
  return allowed.find((item) => item.toLowerCase() === wanted)
}

function parseBoolean(value) {
  const text = value.trim().toLowerCase()
  if (text === '') return false
  if (['true', 'yes', 'y', '1'].includes(text)) return true
  if (['false', 'no', 'n', '0'].includes(text)) return false
  return null
}

function splitList(value) {
  return value
    .split('|')
    .map((part) => part.trim())
    .filter(Boolean)
}

function buildRow(cells, columns, categories, lineNumber) {
  const get = (name) => (cells[columns.indexOf(name)] ?? '').trim()
  const errors = []

  const sku = get('sku').toUpperCase()
  const category = canonical(get('category'), categories) ?? get('category')
  const businessType = []
  for (const part of splitList(get('businessType'))) {
    const match = canonical(part, IMPORT_BUSINESS_TYPES)
    if (match) {
      if (!businessType.includes(match)) businessType.push(match)
    } else {
      errors.push(`Business type "${part}" is not allowed (use Bakery, Cafe or Restaurant).`)
    }
  }
  const trending = parseBoolean(get('isTrending'))
  if (trending === null) errors.push('isTrending must be true or false.')

  const statusText = get('status').toUpperCase()
  if (statusText !== '' && statusText !== 'PUBLISHED' && statusText !== 'ARCHIVED') {
    errors.push('status must be PUBLISHED or ARCHIVED (or blank for PUBLISHED).')
  }

  const quantities = splitList(get('quantities'))
  const form = {
    sku,
    name: get('name'),
    brand: get('brand'),
    category,
    businessType,
    quantities: quantities.join(', '),
    description: get('description'),
    isTrending: trending === true,
    sortRank: get('sortRank'),
    status: 'ARCHIVED',
  }
  const formErrors = validateProductForm(form, { mode: 'create', categories })
  errors.push(...Object.values(formErrors))

  const payload = {
    sku,
    name: form.name,
    brand: form.brand,
    category,
    businessType,
    quantities,
    description: form.description,
    isTrending: trending === true,
    status: statusText === 'ARCHIVED' ? 'ARCHIVED' : 'PUBLISHED',
  }
  if (form.sortRank !== '') payload.sortRank = Number(form.sortRank)
  return { line: lineNumber, sku, name: form.name, payload, errors, status: payload.status }
}

// Returns { fileError } or { rows } where each row is { line, sku, name, payload, errors, status }.
export function prepareImport(text, { categories = [] } = {}) {
  if (new Blob([String(text ?? '')]).size > IMPORT_MAX_BYTES) {
    return { fileError: 'This file is larger than 1 MB. Split it into smaller files.' }
  }
  let table
  try {
    table = parseCsv(text)
  } catch (error) {
    return { fileError: error.message }
  }
  if (table.length === 0) return { fileError: 'The file is empty.' }

  const columns = table[0].map((name) => name.trim())
  const missing = REQUIRED_COLUMNS.filter((name) => !columns.includes(name))
  if (missing.length > 0) {
    return { fileError: `Missing column(s): ${missing.join(', ')}. Use the sample file header.` }
  }
  const unknown = columns.filter((name) => !KNOWN_COLUMNS.includes(name))
  if (unknown.length > 0) {
    return { fileError: `Unknown column(s): ${unknown.join(', ')}. Use the sample file header.` }
  }
  if (new Set(columns).size !== columns.length) {
    return { fileError: 'A column name appears twice in the header.' }
  }
  const dataRows = table.slice(1)
  if (dataRows.length === 0) return { fileError: 'The file has a header but no products.' }
  if (dataRows.length > IMPORT_MAX_ROWS) {
    return {
      fileError: `The file has ${dataRows.length} products; the limit is ${IMPORT_MAX_ROWS} per file.`,
    }
  }

  const seen = new Map()
  const rows = dataRows.map((cells, index) => {
    const row = buildRow(cells, columns, categories, index + 2)
    if (row.sku) {
      if (seen.has(row.sku)) {
        row.errors.push(`SKU is repeated (first used on line ${seen.get(row.sku)}).`)
      } else {
        seen.set(row.sku, row.line)
      }
    }
    return row
  })
  return { rows }
}

export function chunkRows(rows, size = IMPORT_BATCH_SIZE) {
  const chunks = []
  for (let i = 0; i < rows.length; i += size) chunks.push(rows.slice(i, i + size))
  return chunks
}
