export function fillProductMessage(template, product, selectedPack = '') {
  const replacements = {
    name: product.name ?? '',
    sku: product.sku ?? '',
    pack: selectedPack ? ` - Selected Pack Size: ${selectedPack}` : '',
  }

  return template.replace(/{(name|sku|pack)}/g, (_placeholder, key) =>
    replacements[key],
  )
}

export function buildWhatsAppUrl(number, message) {
  const normalizedNumber = String(number ?? '').replace(/\D/g, '')
  if (!normalizedNumber) {
    throw new Error('A WhatsApp phone number is required')
  }

  return `https://wa.me/${normalizedNumber}?text=${encodeURIComponent(message)}`
}

export function buildProductWhatsAppUrl(whatsapp, product, selectedPack = '') {
  const message = fillProductMessage(whatsapp.messageTemplate, product, selectedPack)
  return buildWhatsAppUrl(whatsapp.number, message)
}

export function buildGeneralWhatsAppUrl(whatsapp) {
  return buildWhatsAppUrl(whatsapp.number, whatsapp.generalMessage)
}
