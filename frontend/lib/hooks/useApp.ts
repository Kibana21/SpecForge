import useSWR from 'swr'
import { api } from '../api'
import type { AppDetail } from '../types'

export function useApp(id: string | null) {
  const { data, mutate, isLoading, error } = useSWR<AppDetail>(
    id ? `/api/apps/${id}` : null,
    () => api.apps.get(id!),
    {
      revalidateOnFocus: false,
      refreshInterval: (data) => {
        if (!data) return 0
        return data.pipeline_summary.pending_docs > 0 ? 5000 : 0
      },
    }
  )
  return { app: data, mutate, isLoading, error }
}
