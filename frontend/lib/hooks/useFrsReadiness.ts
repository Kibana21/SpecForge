'use client'
import useSWR from 'swr'
import { api } from '@/lib/api'
import type { FrsBundleReadiness } from '@/lib/types'

/**
 * Polls FRS readiness while any doc is still pending.
 * 4-layer check: App Brain · Documents · CB · BRD (BRD must be validated).
 */
export function useFrsReadiness(projectId: string, enabled = true) {
  const { data, error, mutate } = useSWR<FrsBundleReadiness>(
    enabled ? `frs-readiness-${projectId}` : null,
    () => api.frs.readiness(projectId),
    {
      refreshInterval: (data) => {
        if (!data) return 3000
        // Poll while any doc indexing is pending
        if (data.docs_pending_names && data.docs_pending_names.length > 0) return 3000
        return 0
      },
      revalidateOnFocus: false,
    },
  )
  return { readiness: data, isLoading: !data && !error, error, mutate }
}
