import useSWR from 'swr'
import { api } from '../api'
import type { AppListItem, AppsFilter } from '../types'

export function useApps(filters?: AppsFilter) {
  const params = new URLSearchParams()
  if (filters?.q) params.set('q', filters.q)
  if (filters?.tier !== undefined) params.set('tier', String(filters.tier))
  if (filters?.mine) params.set('mine', 'true')
  const qs = params.toString()
  const key = `/api/apps${qs ? `?${qs}` : ''}`

  return useSWR<AppListItem[]>(key, () => api.apps.list(filters), {
    revalidateOnFocus: false,
  })
}
