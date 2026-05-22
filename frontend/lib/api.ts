import type {
  AppCorpusDoc,
  AppCreate,
  AppDetail,
  AppFact,
  AppListItem,
  AppsFilter,
  AppSuggestion,
  AssumptionItem,
  DocumentRead,
  ExtractedRequirement,
  FactsFilter,
  GapQuestion,
  ProjectCreateWizard,
  ProjectDetail,
  ProjectListItem,
  ProjectPriority,
  ProjectRead,
  ProjectsFilter,
  ProjectStatus,
  RequirementUnderstanding,
  ReviewComment,
  SavedViewCount,
  SimilarProject,
  SpecType,
  SpecVersion,
  TriageItem,
  UnderstandingDetail,
} from './types'
import { tokenStore } from './auth/tokenStore'

// Deduplicate concurrent refresh calls so only one request goes out
let refreshInFlight: Promise<string | null> | null = null

export async function refreshAccessToken(): Promise<string | null> {
  if (refreshInFlight) return refreshInFlight
  refreshInFlight = (async () => {
    try {
      const res = await fetch('/api/auth/refresh', {
        method: 'POST',
        credentials: 'include',
      })
      if (!res.ok) return null
      const json = await res.json()
      const token: string | null = json.data?.access_token ?? null
      tokenStore.set(token)
      return token
    } finally {
      refreshInFlight = null
    }
  })()
  return refreshInFlight
}

/**
 * fetch with bearer auth + transparent 401 refresh-and-retry. Returns the raw
 * Response so streaming and file-upload callers can consume it. Use this for ANY
 * authenticated request (not just JSON) so the access token never surfaces a
 * mid-session "unauthorized" — it silently refreshes once and retries.
 */
export async function authedFetch(url: string, options?: RequestInit): Promise<Response> {
  const withAuth = (token: string | null): RequestInit => ({
    credentials: 'include',
    ...options,
    headers: {
      ...(options?.headers as Record<string, string> | undefined),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  })

  let res = await fetch(url, withAuth(tokenStore.get()))
  if (res.status === 401) {
    const newToken = await refreshAccessToken()
    if (newToken) {
      res = await fetch(url, withAuth(newToken))
    } else {
      tokenStore.set(null)
      if (typeof window !== 'undefined') {
        window.location.href = '/login'
      }
      throw new Error('Session expired')
    }
  }
  return res
}

export async function apiFetch<T>(url: string, options?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    ...(options?.headers as Record<string, string> | undefined),
  }
  if (!(options?.body instanceof FormData) && !('Content-Type' in headers)) {
    headers['Content-Type'] = 'application/json'
  }

  const res = await authedFetch(url, { ...options, headers })

  // some endpoints (e.g. file upload) may return a non-JSON response
  const contentType = res.headers.get('content-type') ?? ''
  if (!contentType.includes('application/json')) {
    if (!res.ok) throw new Error(`Request failed: ${res.status}`)
    return undefined as unknown as T
  }

  const json = await res.json()
  if (json.error) {
    throw new Error(json.error.message ?? `Request failed: ${res.status}`)
  }
  return json.data as T
}

/** Like apiFetch but also returns the response `meta` (groups, totals, freshness). */
export async function apiFetchEnvelope<T>(
  url: string, options?: RequestInit,
): Promise<{ data: T; meta: Record<string, unknown> }> {
  const headers: Record<string, string> = { ...(options?.headers as Record<string, string> | undefined) }
  if (!(options?.body instanceof FormData) && !('Content-Type' in headers)) {
    headers['Content-Type'] = 'application/json'
  }
  const res = await authedFetch(url, { ...options, headers })
  const json = await res.json()
  if (json.error) throw new Error(json.error.message ?? `Request failed: ${res.status}`)
  return { data: json.data as T, meta: json.meta ?? {} }
}

function _projectsQuery(f?: ProjectsFilter): string {
  const p = new URLSearchParams()
  if (f?.q) p.set('q', f.q)
  if (f?.view && f.view !== 'all') p.set('view', f.view)
  if (f?.group_by && f.group_by !== 'none') p.set('group_by', f.group_by)
  const qs = p.toString()
  return qs ? `?${qs}` : ''
}

export const api = {
  projects: {
    list: (filters?: ProjectsFilter) =>
      apiFetchEnvelope<ProjectListItem[]>(`/api/projects${_projectsQuery(filters)}`),
    views: () => apiFetch<SavedViewCount[]>('/api/projects/views'),
    create: (data: ProjectCreateWizard) =>
      apiFetch<ProjectRead>('/api/projects', { method: 'POST', body: JSON.stringify(data) }),
    get: (id: string) => apiFetch<ProjectDetail>(`/api/projects/${id}`),
    update: (id: string, data: Partial<{
      name: string; description: string; business_unit: string; app_scope: string;
      priority: ProjectPriority; status: ProjectStatus; go_live_date: string | null
    }>) => apiFetch<ProjectRead>(`/api/projects/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
    delete: (id: string) =>
      apiFetch<{ id: string }>(`/api/projects/${id}`, { method: 'DELETE' }),
    similar: (id: string) => apiFetch<SimilarProject[]>(`/api/projects/${id}/similar`),
    assumptions: (id: string) => apiFetch<AssumptionItem[]>(`/api/projects/${id}/assumptions`),
    patchAssumption: (id: string, aid: string, status: string) =>
      apiFetch<AssumptionItem>(`/api/projects/${id}/assumptions/${aid}`, {
        method: 'PATCH', body: JSON.stringify({ status }),
      }),
    understanding: (id: string) => apiFetch<UnderstandingDetail>(`/api/projects/${id}/understanding`),
    generateUnderstanding: (id: string) =>
      apiFetch<UnderstandingDetail>(`/api/projects/${id}/understanding/generate`, { method: 'POST' }),
    answerUnderstanding: (id: string, answer: string, seq?: number) =>
      apiFetch<UnderstandingDetail>(`/api/projects/${id}/understanding/answer`, {
        method: 'POST', body: JSON.stringify({ answer, seq }),
      }),
    validateUnderstanding: (id: string) =>
      apiFetch<{ ru_validated: boolean; understanding: RequirementUnderstanding }>(
        `/api/projects/${id}/understanding/validate`, { method: 'POST' },
      ),
  },

  triage: {
    list: () => apiFetchEnvelope<TriageItem[]>('/api/triage'),
  },

  documents: {
    list: (projectId: string) =>
      apiFetch<DocumentRead[]>(`/api/projects/${projectId}/documents`),
    upload: async (projectId: string, file: File): Promise<DocumentRead> => {
      const form = new FormData()
      form.append('file', file)
      const res = await authedFetch(`/api/projects/${projectId}/documents`, {
        method: 'POST',
        body: form,
      })
      const json = await res.json()
      if (json.error) throw new Error(json.error.message)
      return json.data as DocumentRead
    },
    delete: (projectId: string, docId: string) =>
      apiFetch<{ id: string }>(`/api/projects/${projectId}/documents/${docId}`, {
        method: 'DELETE',
      }),
    extract: (projectId: string) =>
      apiFetch<ExtractedRequirement[]>(`/api/projects/${projectId}/extract`, {
        method: 'POST',
      }),
    listRequirements: (projectId: string) =>
      apiFetch<ExtractedRequirement[]>(`/api/projects/${projectId}/requirements`),
    detectGaps: (projectId: string) =>
      apiFetch<GapQuestion[]>(`/api/projects/${projectId}/detect-gaps`, {
        method: 'POST',
      }),
    listGaps: (projectId: string) =>
      apiFetch<GapQuestion[]>(`/api/projects/${projectId}/gaps`),
  },

  specs: {
    generate: (projectId: string, specType: SpecType) => {
      const path = specType === 'user_stories' ? 'user-stories' : specType
      return apiFetch<SpecVersion>(`/api/projects/${projectId}/specs/${path}`, {
        method: 'POST',
      })
    },
    review: (projectId: string) =>
      apiFetch<SpecVersion>(`/api/projects/${projectId}/review`, { method: 'POST' }),
    list: (projectId: string) =>
      apiFetch<SpecVersion[]>(`/api/projects/${projectId}/specs`),
    patch: (
      projectId: string,
      versionId: string,
      data: { content_markdown?: string }
    ) =>
      apiFetch<SpecVersion>(`/api/projects/${projectId}/specs/${versionId}`, {
        method: 'PATCH',
        body: JSON.stringify(data),
      }),
    exportUrl: (projectId: string, specType: string) =>
      `/api/projects/${projectId}/export/markdown?spec_type=${specType}`,
  },

  gaps: {
    resolve: (
      projectId: string,
      gapId: string,
      data: { resolved: boolean; resolution_text?: string | null }
    ) =>
      apiFetch<GapQuestion>(`/api/projects/${projectId}/gaps/${gapId}`, {
        method: 'PATCH',
        body: JSON.stringify(data),
      }),
  },

  reviews: {
    list: (projectId: string) =>
      apiFetch<ReviewComment[]>(`/api/projects/${projectId}/reviews`),
    dismiss: (projectId: string, commentId: string, dismissed: boolean) =>
      apiFetch<ReviewComment>(`/api/projects/${projectId}/reviews/${commentId}`, {
        method: 'PATCH',
        body: JSON.stringify({ dismissed }),
      }),
  },

  apps: {
    suggest: (params: { project_id?: string; q?: string }) => {
      const p = new URLSearchParams()
      if (params.project_id) p.set('project_id', params.project_id)
      if (params.q) p.set('q', params.q)
      return apiFetch<AppSuggestion[]>(`/api/apps/suggest?${p.toString()}`)
    },
    list: (filters?: AppsFilter) => {
      const params = new URLSearchParams()
      if (filters?.q) params.set('q', filters.q)
      if (filters?.tier !== undefined) params.set('tier', String(filters.tier))
      if (filters?.mine) params.set('mine', 'true')
      const qs = params.toString()
      return apiFetch<AppListItem[]>(`/api/apps${qs ? `?${qs}` : ''}`)
    },
    create: (data: AppCreate) =>
      apiFetch<AppDetail>('/api/apps', { method: 'POST', body: JSON.stringify(data) }),
    get: (id: string) => apiFetch<AppDetail>(`/api/apps/${id}`),
    update: (id: string, data: Partial<AppCreate>) =>
      apiFetch<AppDetail>(`/api/apps/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
    delete: (id: string) => apiFetch<{ id: string }>(`/api/apps/${id}`, { method: 'DELETE' }),
    uploadCorpusDoc: async (appId: string, file: File, isPrimary = false): Promise<AppCorpusDoc> => {
      const form = new FormData()
      form.append('file', file)
      form.append('is_primary', isPrimary ? 'true' : 'false')
      const res = await authedFetch(`/api/apps/${appId}/corpus`, {
        method: 'POST',
        body: form,
      })
      const json = await res.json()
      if (json.error) throw new Error(json.error.message)
      return json.data as AppCorpusDoc
    },
    reindex: (appId: string) =>
      apiFetch<{ task_id: string }>(`/api/apps/${appId}/reindex`, { method: 'POST' }),
    listFacts: (appId: string, filters?: FactsFilter) => {
      const params = new URLSearchParams()
      if (filters?.kind) params.set('kind', filters.kind)
      if (filters?.status) params.set('status', filters.status)
      if (filters?.confidence) params.set('confidence', filters.confidence)
      const qs = params.toString()
      return apiFetch<AppFact[]>(`/api/apps/${appId}/facts${qs ? `?${qs}` : ''}`)
    },
  },
}
