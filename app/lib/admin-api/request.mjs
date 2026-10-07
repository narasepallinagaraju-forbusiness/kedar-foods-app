import { fetchWithTimeout } from '../api/fetch-timeout.mjs'

export class AdminApiError extends Error {
  constructor(message, status, details = []) {
    super(message)
    this.name = 'AdminApiError'
    this.status = status
    this.details = details
  }
}

const ERROR_MESSAGES = {
  401: 'The admin key was rejected. Sign in again with the correct key.',
  409: 'Someone else changed this item. The latest version has been reloaded.',
  413: 'The request was too large.',
  429: 'Too many requests. Please wait a moment and try again.',
  503: 'The admin service is not ready (the admin key may not be set up yet).',
}

export function messageForStatus(status, payload) {
  if (status === 409 && payload?.error === 'duplicate_sku') {
    return 'A product with this SKU already exists.'
  }
  if (status === 400 && Array.isArray(payload?.details) && payload.details.length) {
    return payload.details.map((d) => `${d.field}: ${d.message}`).join('; ')
  }
  return ERROR_MESSAGES[status] ?? `The request failed (HTTP ${status}).`
}

export async function adminRequest({
  baseUrl,
  adminKey,
  method = 'GET',
  path,
  body,
  signal,
  fetchImpl = globalThis.fetch,
}) {
  if (!adminKey) {
    throw new AdminApiError(ERROR_MESSAGES[401], 401)
  }

  const headers = { Accept: 'application/json', 'X-Admin-Key': adminKey }
  const init = { method, headers, signal }
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    init.body = JSON.stringify(body)
  }

  const response = await fetchWithTimeout(`${baseUrl}${path}`, init, { fetchImpl })

  let payload = null
  try {
    payload = await response.json()
  } catch {}

  if (!response.ok) {
    throw new AdminApiError(
      messageForStatus(response.status, payload),
      response.status,
      Array.isArray(payload?.details) ? payload.details : [],
    )
  }
  if (payload === null || typeof payload !== 'object') {
    throw new AdminApiError('The API returned an invalid response.', response.status)
  }
  return payload
}
