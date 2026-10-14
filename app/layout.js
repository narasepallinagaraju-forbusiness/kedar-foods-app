import './globals.css'
import Script from 'next/script'
import { Providers } from './providers'

export const metadata = {
  title: 'Kedhar Foods | Wholesale Raw Materials for Bakeries, Cafes & Restaurants',
  description:
    'Kedhar Foods supplies quality wholesale raw materials — dairy, flour, chocolate, coffee and more — to bakeries, cafes and restaurants. Enquire for bulk rates on WhatsApp.',
}

export default function RootLayout({ children }) {
  return (
    <html lang="en" className="dark-theme">
      <head>
        <script dangerouslySetInnerHTML={{__html:'window.addEventListener("error",function(e){if(e.error instanceof DOMException&&e.error.name==="DataCloneError"&&e.message&&e.message.includes("PerformanceServerTiming")){e.stopImmediatePropagation();e.preventDefault()}},true);'}} />
        <Script
          id="google-analytics"
          strategy="afterInteractive"
        >{`
          window.dataLayer = window.dataLayer || [];
          function gtag(){window.dataLayer.push(arguments);}
          gtag('js', new Date());
          gtag('config', 'G-SGT0587M4L');
        `}</Script>
        <Script
          src="https://www.googletagmanager.com/gtag/js?id=G-SGT0587M4L"
          strategy="afterInteractive"
        />
      </head>
      <body className="bg-white text-gray-900 antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
