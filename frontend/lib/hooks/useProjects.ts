import useSWR from 'swr'
import { api } from '../api'
import type {
  PortfolioGroup,
  ProjectListItem,
  ProjectsFilter,
  SavedViewCount,
  TriageItem,
} from '../types'

export function useProjects(filters?: ProjectsFilter) {
  const key = ['/api/projects', filters?.q ?? '', filters?.view ?? 'all', filters?.group_by ?? 'none']
  const { data, error, isLoading, mutate } = useSWR(
    key,
    () => api.projects.list(filters),
    { revalidateOnFocus: false, keepPreviousData: true },
  )
  return {
    projects: (data?.data ?? []) as ProjectListItem[],
    groups: (data?.meta?.groups ?? null) as PortfolioGroup[] | null,
    total: (data?.meta?.total ?? 0) as number,
    error,
    isLoading,
    mutate,
  }
}

export function useViews() {
  const { data, mutate } = useSWR<SavedViewCount[]>(
    '/api/projects/views',
    () => api.projects.views(),
    { revalidateOnFocus: false },
  )
  return { views: data ?? [], mutate }
}

export function useTriage() {
  const { data, isLoading, mutate } = useSWR(
    '/api/triage',
    () => api.triage.list(),
    { revalidateOnFocus: false },
  )
  return {
    items: (data?.data ?? []) as TriageItem[],
    computedAt: (data?.meta?.computed_at ?? null) as string | null,
    nextAt: (data?.meta?.next_at ?? null) as string | null,
    isLoading,
    mutate,
  }
}
