import useSWR from 'swr'
import { api } from '../api'
import type { ArtifactDetail } from '../types'

export function useArtifact(projectId: string, type: string) {
  const { data, error, isLoading, mutate } = useSWR<ArtifactDetail>(
    `/api/projects/${projectId}/artifacts/${type}`,
    () => api.artifacts.get(projectId, type),
    {
      revalidateOnFocus: false,
      refreshInterval: (data) => {
        const status = data?.document?.status
        if (status === 'generating') return 2000
        // Poll while a section is refining in the background
        if (data?.document?.unit_status?.['_current_unit']) return 2000
        return 0
      },
    },
  )
  return { detail: data, error, isLoading, mutate }
}
