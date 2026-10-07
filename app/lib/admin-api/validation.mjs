import { safeLink } from '../api/safe-link.mjs'

export const OFFER_TEXT_MAX = 160
export const OFFER_LINK_MAX = 200
const SKU_PATTERN = /^[A-Z0-9][A-Z0-9-]{0,28}[A-Z0-9]$/
const CONTROL_CHARACTERS = /[\u0000-\u001f\u007f]/

export const EMPTY_PRODUCT_FORM = {
  sku: '',
  name: '',
  brand: '',
  category: '',
  businessType: [],
  quantities: '',
  description: '',
  isTrending: false,
  sortRank: '',
  status: 'ARCHIVED',
}

export function parseQuantities(value) {
  return String(value ?? '')
    .split(',')
    .map((part) => part.trim())
    .filter(Boolean)
}

export function productToForm(product) {
  return {
    ...EMPTY_PRODUCT_FORM,
    sku: product.sku ?? '',
    name: product.name ?? '',
    brand: product.brand ?? '',
    category: product.category ?? '',
    businessType: [...(product.businessType ?? [])],
    quantities: (product.quantities ?? []).join(', '),
    description: product.description ?? '',
    isTrending: product.isTrending === true,
    sortRank: Number.isInteger(product.sortRank) ? String(product.sortRank) : '',
    status: product.status ?? 'ARCHIVED',
  }
}

export function validateProductForm(form, { mode, categories = [] }) {
  const errors = {}
  const name = form.name.trim()
  const quantities = parseQuantities(form.quantities)

  if (mode === 'create' && !SKU_PATTERN.test(form.sku.trim().toUpperCase())) {
    errors.sku = 'SKU must be 2-30 characters: letters, numbers and hyphens (e.g. KF-12).'
  }
  if (name.length < 2 || name.length > 120 || CONTROL_CHARACTERS.test(name)) {
    errors.name = 'Name must be 2-120 characters.'
  }
  const brand = form.brand.trim()
  if (brand.length < 1 || brand.length > 60) {
    errors.brand = 'Brand must be 1-60 characters.'
  }
  if (!form.category || (categories.length > 0 && !categories.includes(form.category))) {
    errors.category = 'Choose a category.'
  }
  if (form.businessType.length === 0) {
    errors.businessType = 'Choose at least one business type.'
  }
  if (
    quantities.length < 1 ||
    quantities.length > 12 ||
    new Set(quantities).size !== quantities.length ||
    quantities.some((q) => q.length > 20)
  ) {
    errors.quantities = 'Enter 1-12 different pack sizes (up to 20 characters each).'
  }
  if (form.description.length > 2000) {
    errors.description = 'Description can be up to 2000 characters.'
  }
  if (form.sortRank !== '') {
    const text = String(form.sortRank).trim()
    if (!/^\d+$/.test(text) || Number(text) > 100000) {
      errors.sortRank = 'Display order must be a whole number from 0 to 100000.'
    }
  }
  return errors
}

export function buildProductPayload(form, { mode, version }) {
  const payload = {
    name: form.name.trim(),
    brand: form.brand.trim(),
    category: form.category,
    businessType: [...form.businessType],
    quantities: parseQuantities(form.quantities),
    description: form.description.trim(),
    isTrending: form.isTrending === true,
  }
  if (String(form.sortRank).trim() !== '') {
    payload.sortRank = Number(String(form.sortRank).trim())
  }
  if (mode === 'create') {
    payload.sku = form.sku.trim().toUpperCase()
    payload.status = form.status === 'PUBLISHED' ? 'PUBLISHED' : 'ARCHIVED'
  } else {
    payload.version = version
  }
  return payload
}

export function validateOfferForm(offer) {
  const errors = {}
  const text = offer.text.trim()
  if (text.length > OFFER_TEXT_MAX || CONTROL_CHARACTERS.test(text)) {
    errors.text = `Offer text can be up to ${OFFER_TEXT_MAX} characters.`
  } else if (offer.enabled && !text) {
    errors.text = 'Enter the offer text before turning the offer on.'
  }
  if (offer.link !== '' && (offer.link.length > OFFER_LINK_MAX || safeLink(offer.link) === null)) {
    errors.link = 'Link must start with a single / (e.g. /catalogue) or https://.'
  }
  return errors
}

export function buildOfferPayload(offer) {
  return {
    enabled: offer.enabled === true,
    text: offer.text.trim(),
    link: offer.link,
  }
}
