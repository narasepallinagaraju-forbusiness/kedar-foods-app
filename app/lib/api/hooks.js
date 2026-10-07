'use client'

import { useQuery } from '@tanstack/react-query'
import { fetchCatalogIndex } from './catalog'
import { fetchApiJson } from './client'
import { fetchSiteConfig } from './site-config'

const CUSTOMER_QUERY_OPTIONS = {
  staleTime: 60_000,
  refetchOnWindowFocus: false,
  retry: 1,
}

export function useCatalogIndex(enabled = true) {
  return useQuery({
    queryKey: ['customer', 'catalog-index'],
    queryFn: ({ signal }) => fetchCatalogIndex({ signal }),
    enabled,
    ...CUSTOMER_QUERY_OPTIONS,
  })
}

export function useSiteConfig(enabled = true) {
  return useQuery({
    queryKey: ['customer', 'site-config'],
    queryFn: ({ signal }) => fetchSiteConfig({ signal }),
    enabled,
    ...CUSTOMER_QUERY_OPTIONS,
  })
}

export function useProduct(slug) {
  return useQuery({
    queryKey: ['customer', 'product', slug],
    queryFn: ({ signal }) =>
      fetchApiJson(`/products/${encodeURIComponent(slug)}`, { signal }),
    enabled: Boolean(slug),
    ...CUSTOMER_QUERY_OPTIONS,
    retry: (failureCount, error) => error.status !== 404 && failureCount < 1,
  })
}
