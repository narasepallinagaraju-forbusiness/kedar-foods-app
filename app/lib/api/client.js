import { fetchWithTimeout } from './fetch-timeout.mjs'

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export function getApiBaseUrl() {
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.trim()
  if (!baseUrl) {
    throw new Error(
      'NEXT_PUBLIC_API_BASE_URL is not configured. Set it and rebuild the frontend.',
    )
  }

  let parsedUrl
  try {
    parsedUrl = new URL(baseUrl)
  } catch {
    throw new Error('NEXT_PUBLIC_API_BASE_URL must be a valid absolute URL.')
  }

  if (!['http:', 'https:'].includes(parsedUrl.protocol)) {
    throw new Error('NEXT_PUBLIC_API_BASE_URL must use HTTP or HTTPS.')
  }

  return baseUrl.replace(/\/+$/, '')
}

export async function fetchApiJson(path, { signal } = {}) {
  const response = await fetchWithTimeout(`${getApiBaseUrl()}${path}`, {
    headers: { Accept: 'application/json' },
    signal,
  })

  if (!response.ok) {
    throw new ApiError(`API request failed with HTTP ${response.status}`, response.status)
  }

  try {
    return await response.json()
  } catch {
    throw new Error('The API returned an invalid JSON response.')
  }
}
