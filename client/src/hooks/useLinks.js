import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'

export function useLinks() {
  return useQuery({
    queryKey: ['links'],
    queryFn: () => api.get('/links'),
  })
}

export function useLink(id) {
  return useQuery({
    queryKey: ['links', id],
    queryFn: () => api.get(`/links/${id}`),
    enabled: !!id,
  })
}

export function useCreateLink() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data) => api.post('/links', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['links'] })
    },
  })
}

export function useDeleteLink() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id) => api.delete(`/links/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['links'] })
    },
  })
}
