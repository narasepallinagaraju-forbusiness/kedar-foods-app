import ProductShell from '../../../scripts/product-shell.js'

export const dynamicParams = false

export function generateStaticParams() {
  return [{ slug: '_shell' }]
}

export default function ProductShellPage() {
  return <ProductShell />
}
