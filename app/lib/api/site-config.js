import { CATEGORIES, WHATSAPP_DISPLAY, WHATSAPP_NUMBER } from '@/lib/data'
import { fetchApiJson } from './client'

export const FALLBACK_WHATSAPP = {
  number: WHATSAPP_NUMBER,
  display: WHATSAPP_DISPLAY,
  messageTemplate:
    'Hi Kedar Foods! I am interested in bulk rates for {name}{pack} (SKU: {sku})?',
  generalMessage: "Hi Kedar Foods! I'd like to enquire about bulk wholesale rates.",
}

export async function fetchSiteConfig({ signal } = {}) {
  const config = await fetchApiJson('/site-config', { signal })
  if (!config || typeof config !== 'object') {
    throw new Error('The site-config endpoint returned an invalid response.')
  }
  return config
}

export function getWhatsAppConfig(siteConfig) {
  const configured = siteConfig?.whatsapp ?? {}
  return {
    number: configured.number || FALLBACK_WHATSAPP.number,
    display: configured.display || FALLBACK_WHATSAPP.display,
    messageTemplate: configured.messageTemplate || FALLBACK_WHATSAPP.messageTemplate,
    generalMessage: configured.generalMessage || FALLBACK_WHATSAPP.generalMessage,
  }
}

export function getSiteCategories(siteConfig) {
  if (Array.isArray(siteConfig?.categories) && siteConfig.categories.length > 0) {
    return siteConfig.categories
      .filter((category) => category && category.isActive !== false)
      .sort((left, right) => (left.sortOrder ?? 0) - (right.sortOrder ?? 0))
  }

  return CATEGORIES.map((name, index) => ({
    id: name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, ''),
    name,
    slug: name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, ''),
    sortOrder: index * 10,
    isActive: true,
  }))
}
