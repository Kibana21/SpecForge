'use client'
import useSWR from 'swr'
import { api } from '@/lib/api'
import type { BrdBundleReadiness } from '@/lib/types'

export function useBrdReadiness(projectId: string, enabled = true) {
  const { data, error, mutate } = useSWR<BrdBundleReadiness>(
    enabled ? `brd-readiness-${projectId}` : null,
    () => api.brd.readiness(projectId),
    {
      refreshInterval: (data) => {
        if (!data) return 3000
        const hasPending = data.docs?.some(
          (d) => d.indexing_status === 'pending' || d.indexing_status === 'running',
        )
        return hasPending ? 3000 : 0
      },
    },
  )
  return { readiness: data, isLoading: !data && !error, error, mutate }
}
