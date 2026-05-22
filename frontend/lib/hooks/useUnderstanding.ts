import useSWR from 'swr'
import { api } from '../api'
import type { UnderstandingDetail } from '../types'

export function useUnderstanding(projectId: string) {
  const { data, error, isLoading, mutate } = useSWR<UnderstandingDetail>(
    `/api/projects/${projectId}/understanding`,
    () => api.projects.understanding(projectId),
    { revalidateOnFocus: false },
  )
  return { detail: data, error, isLoading, mutate }
}
