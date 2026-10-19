import { WHATSAPP_NUMBER } from '@/lib/data'

export const metadata = {
  title: 'Kedhar Foods – Connect with us',
  description: 'WhatsApp, Instagram, website, contact, map and reviews for Kedhar Foods.',
}

const LINKS = [
  { label: 'WhatsApp', href: `https://wa.me/${WHATSAPP_NUMBER}`, icon: '/whatsapp.png' },
  { label: 'Instagram', href: 'https://www.instagram.com/kedhar_foods', icon: '/instagram.png' },
  { label: 'Website', href: 'https://kedharfoods.in', icon: '/website.png' },
  {
    label: 'Contacts',
    href: 'https://drive.google.com/file/d/1updRANe8255sb1KISry4X9f0O-ZnCjAk/view?usp=drive_link',
    icon: '/contacts.png',
  },
  { label: 'Google Map', href: 'https://maps.app.goo.gl/XTMgYws4g7naY6nw9', icon: '/google-maps.png' },
  { label: 'Google Review', href: 'https://g.page/r/CQMyhg1xMTkMEAE/review', icon: '/rating.png' },
]

export default function BioPage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col items-center bg-white px-6 py-10">
      <img src="/logo.png" alt="Kedhar Foods" className="h-28 w-28 object-contain" />
      <h1 className="mt-4 w-full rounded-lg bg-red-600 px-4 py-3 text-center text-2xl font-extrabold text-white">
        KEDHAR FOODS
      </h1>
      <ul className="mt-8 grid w-full grid-cols-2 gap-6">
        {LINKS.map((l) => (
          <li key={l.label}>
            <a
              href={l.href}
              target="_blank"
              rel="noopener noreferrer"
              className="flex flex-col items-center gap-2 rounded-xl p-3 transition hover:bg-gray-50"
            >
              <img src={l.icon} alt="" width={64} height={64} style={{ width: 64, height: 64, objectFit: 'contain' }} />
              <span className="text-sm font-semibold text-gray-800">{l.label}</span>
            </a>
          </li>
        ))}
      </ul>
    </main>
  )
}
