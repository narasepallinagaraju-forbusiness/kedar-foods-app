import assert from 'node:assert/strict'
import test from 'node:test'

import {
  buildGeneralWhatsAppUrl,
  buildProductWhatsAppUrl,
  buildWhatsAppUrl,
  fillProductMessage,
} from './whatsapp.mjs'

const whatsapp = {
  number: '+91 78423 31013',
  messageTemplate: 'Interested in {name}{pack} (SKU: {sku})?',
  generalMessage: "I'd like to enquire about bulk rates.",
}
const product = { name: 'Amul Butter', sku: 'KF 01' }

test('fills product placeholders with a selected pack size', () => {
  assert.equal(
    fillProductMessage(whatsapp.messageTemplate, product, '500g'),
    'Interested in Amul Butter - Selected Pack Size: 500g (SKU: KF 01)?',
  )
})

test('fills the pack placeholder with an empty string when no pack is selected', () => {
  assert.equal(
    fillProductMessage(whatsapp.messageTemplate, product),
    'Interested in Amul Butter (SKU: KF 01)?',
  )
})

test('preserves replacement values literally and does not expand their placeholders', () => {
  assert.equal(
    fillProductMessage(
      '{name} (SKU: {sku})',
      { name: 'Cake $& Co {sku}', sku: 'Rs$$5' },
    ),
    'Cake $& Co {sku} (SKU: Rs$$5)',
  )
})

test('builds an encoded product WhatsApp URL using configured values', () => {
  const url = buildProductWhatsAppUrl(whatsapp, product, '500g')
  assert.equal(url, 'https://wa.me/917842331013?text=Interested%20in%20Amul%20Butter%20-%20Selected%20Pack%20Size%3A%20500g%20(SKU%3A%20KF%2001)%3F')
})

test('builds the configured general enquiry URL', () => {
  assert.equal(
    buildGeneralWhatsAppUrl(whatsapp),
    "https://wa.me/917842331013?text=I'd%20like%20to%20enquire%20about%20bulk%20rates.",
  )
})

test('requires a WhatsApp number', () => {
  assert.throws(() => buildWhatsAppUrl('', 'Hello'), /phone number is required/)
})
