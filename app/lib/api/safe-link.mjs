const UNSAFE_CHARACTERS = /[\s\u0000-\u001f\u007f]/

export function safeLink(value) {
  if (
    typeof value !== 'string' ||
    UNSAFE_CHARACTERS.test(value) ||
    value.startsWith('//') ||
    (value.startsWith('/') && value.includes('\\'))
  ) {
    return null
  }

  if (value.startsWith('/') || value.startsWith('https://')) {
    return value
  }

  return null
}
