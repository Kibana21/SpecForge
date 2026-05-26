import useSWR from 'swr'
import { api } from '../api'
import type { ProjectDetail } from '../types'

export function useProject(id: string | null) {
  const { data, error, isLoading, mutate } = useSWR<ProjectDetail>(
    id ? `/api/projects/${id}` : null,
    () => api.projects.get(id!),
    {
      revalidateOnFocus: false,
      refreshInterval: (data) =>
        data?.documents.some((d) => d.indexing_status !== 'done') ? 3000 : 0,
    }
  )
  return { project: data, error, isLoading, mutate }
}
