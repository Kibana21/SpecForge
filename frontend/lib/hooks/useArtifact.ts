import useSWR from 'swr'
import { api } from '../api'
import type { ArtifactDetail } from '../types'

export function useArtifact(projectId: string, type: string) {
  const { data, error, isLoading, mutate } = useSWR<ArtifactDetail>(
    `/api/projects/${projectId}/artifacts/${type}`,
    () => api.artifacts.get(projectId, type),
    {
      revalidateOnFocus: false,
      // refreshInterval: poll every 2s while generating, stop otherwise
      refreshInterval: (data) => data?.document?.status === 'generating' ? 2000 : 0,
    },
  )
  return { detail: data, error, isLoading, mutate }
}
