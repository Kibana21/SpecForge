import useSWR from 'swr'
import { api } from '../api'
import type { ProjectListItem } from '../types'

export function useProjects() {
  const { data, error, isLoading, mutate } = useSWR<ProjectListItem[]>(
    '/api/projects',
    () => api.projects.list(),
    { revalidateOnFocus: false }
  )
  return { projects: data ?? [], error, isLoading, mutate }
}
