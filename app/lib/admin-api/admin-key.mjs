export const ADMIN_KEY_STORAGE = 'kedar_admin_key'

function defaultStorage() {
  try {
    return globalThis.sessionStorage ?? null
  } catch {
    return null
  }
}

export function getAdminKey(storage = defaultStorage()) {
  try {
    return storage?.getItem(ADMIN_KEY_STORAGE) || ''
  } catch {
    return ''
  }
}

export function setAdminKey(key, storage = defaultStorage()) {
  try {
    storage?.setItem(ADMIN_KEY_STORAGE, key)
    return true
  } catch {
    return false
  }
}

export function clearAdminKey(storage = defaultStorage()) {
  try {
    storage?.removeItem(ADMIN_KEY_STORAGE)
  } catch {}
}
