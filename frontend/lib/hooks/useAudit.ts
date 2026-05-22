import useSWR from 'swr'
import { api } from '../api'
import type { AuditEventRead, AuditFilters, AuditSummary } from '../types'

export function useAudit(filters?: AuditFilters) {
  const key = [
    '/api/audit', filters?.q ?? '', filters?.event ?? '', filters?.category ?? 'all',
    filters?.start ?? '', filters?.end ?? '', filters?.limit ?? 50, filters?.offset ?? 0,
  ]
  const { data, error, isLoading, mutate } = useSWR(
    key,
    () => api.audit.list(filters),
    { revalidateOnFocus: false, keepPreviousData: true },
  )
  return {
    events: (data?.data ?? []) as AuditEventRead[],
    total: (data?.meta?.total ?? 0) as number,
    error,
    isLoading,
    mutate,
  }
}

export function useAuditSummary() {
  const { data, mutate } = useSWR<AuditSummary>(
    '/api/audit/summary',
    () => api.audit.summary(),
    { revalidateOnFocus: false },
  )
  return { summary: data, mutate }
}
