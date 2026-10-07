import { getApiBaseUrl } from '../api/client'
import { adminRequest } from './request.mjs'
import { getAdminKey } from './admin-key.mjs'

export function adminFetch(options) {
  return adminRequest({
    baseUrl: getApiBaseUrl(),
    adminKey: getAdminKey(),
    ...options,
  })
}
