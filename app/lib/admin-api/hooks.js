'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { adminFetch } from './client'

const PRODUCTS_KEY = ['admin', 'products']
const OFFER_KEY = ['admin', 'offer']

const ADMIN_QUERY_OPTIONS = {
  staleTime: 0,
  refetchOnWindowFocus: false,
  retry: (failureCount, error) =>
    ![400, 401, 404, 409, 503].includes(error?.status) && failureCount < 1,
}

export function useAdminProducts(enabled = true) {
  return useQuery({
    queryKey: PRODUCTS_KEY,
    queryFn: ({ signal }) => adminFetch({ path: '/admin/products', signal }),
    select: (data) => data.products ?? [],
    enabled,
    ...ADMIN_QUERY_OPTIONS,
  })
}

export function useAdminOffer(enabled = true) {
  return useQuery({
    queryKey: OFFER_KEY,
    queryFn: ({ signal }) => adminFetch({ path: '/admin/site-config', signal }),
    select: (data) => data.offerBanner ?? {},
    enabled,
    ...ADMIN_QUERY_OPTIONS,
  })
}

function useProductMutation(request) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: request,
    // On a conflict or any failure, reload so the table shows the truth.
    onSettled: () => queryClient.invalidateQueries({ queryKey: PRODUCTS_KEY }),
  })
}

export function useCreateProduct() {
  return useProductMutation((payload) =>
    adminFetch({ method: 'POST', path: '/admin/products', body: payload }),
  )
}

export function useUpdateProduct() {
  return useProductMutation(({ id, payload }) =>
    adminFetch({
      method: 'PUT',
      path: `/admin/products/${encodeURIComponent(id)}`,
      body: payload,
    }),
  )
}

export function useSetProductVisibility() {
  return useProductMutation(({ id, visible }) =>
    adminFetch({
      method: 'POST',
      path: `/admin/products/${encodeURIComponent(id)}/${visible ? 'restore' : 'archive'}`,
    }),
  )
}

export function useRebuildIndex() {
  return useMutation({
    mutationFn: () =>
      adminFetch({ method: 'POST', path: '/admin/catalog-index/rebuild' }),
  })
}

export function useSaveOffer() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload) =>
      adminFetch({ method: 'PUT', path: '/admin/site-config/offer', body: payload }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: OFFER_KEY })
      queryClient.invalidateQueries({ queryKey: ['customer', 'site-config'] })
    },
  })
}

export function useImportProducts() {
  return useProductMutation((rows) =>
    adminFetch({ method: 'POST', path: '/admin/products/import', body: { rows } }),
  )
}

export function useUploadProductPicture() {
  return useProductMutation(({ id, slot, version, card, main }) =>
    adminFetch({
      method: 'PUT',
      path: `/admin/products/${encodeURIComponent(id)}/images/${slot}`,
      body: { version, card, main },
    }),
  )
}

export function useRemoveProductPicture() {
  return useProductMutation(({ id, slot, version }) =>
    adminFetch({
      method: 'POST',
      path: `/admin/products/${encodeURIComponent(id)}/images/${slot}/remove`,
      body: { version },
    }),
  )
}

function useOfferImageMutation(request) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: request,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: OFFER_KEY })
      queryClient.invalidateQueries({ queryKey: ['customer', 'site-config'] })
    },
  })
}

export function useUploadPoster() {
  return useOfferImageMutation(({ poster }) =>
    adminFetch({ method: 'PUT', path: '/admin/site-config/offer/image', body: { poster } }),
  )
}

export function useRemovePoster() {
  return useOfferImageMutation(() =>
    adminFetch({ method: 'POST', path: '/admin/site-config/offer/image/remove', body: {} }),
  )
}
