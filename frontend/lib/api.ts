import type {
  AppCorpusDoc,
  AppCreate,
  AppDetail,
  AppFact,
  AppListItem,
  AppsFilter,
  DocumentRead,
  ExtractedRequirement,
  FactsFilter,
  GapQuestion,
  ProjectDetail,
  ProjectListItem,
  ProjectRead,
  ReviewComment,
  SpecType,
  SpecVersion,
} from './types'
import { tokenStore } from './auth/tokenStore'

// Deduplicate concurrent refresh calls so only one request goes out
let refreshInFlight: Promise<string | null> | null = null

async function refreshAccessToken(): Promise<string | null> {
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

export async function apiFetch<T>(url: string, options?: RequestInit): Promise<T> {
  const buildHeaders = (token: string | null): Record<string, string> => {
    const h: Record<string, string> = {}
    if (!(options?.body instanceof FormData)) {
      h['Content-Type'] = 'application/json'
    }
    if (token) {
      h['Authorization'] = `Bearer ${token}`
    }
    return h
  }

  const doFetch = (token: string | null) =>
    fetch(url, {
      credentials: 'include',
      ...options,
      headers: {
        ...buildHeaders(token),
        ...(options?.headers as Record<string, string> | undefined),
      },
    })

  let res = await doFetch(tokenStore.get())

  if (res.status === 401) {
    const newToken = await refreshAccessToken()
    if (newToken) {
      res = await doFetch(newToken)
    } else {
      tokenStore.set(null)
      if (typeof window !== 'undefined') {
        window.location.href = '/login'
      }
      throw new Error('Session expired')
    }
  }

  // document upload returns the raw response — handle non-JSON
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

export const api = {
  projects: {
    list: () => apiFetch<ProjectListItem[]>('/api/projects'),
    create: (data: { name: string; description?: string }) =>
      apiFetch<ProjectRead>('/api/projects', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    get: (id: string) => apiFetch<ProjectDetail>(`/api/projects/${id}`),
    delete: (id: string) =>
      apiFetch<{ id: string }>(`/api/projects/${id}`, { method: 'DELETE' }),
  },

  documents: {
    list: (projectId: string) =>
      apiFetch<DocumentRead[]>(`/api/projects/${projectId}/documents`),
    upload: async (projectId: string, file: File): Promise<DocumentRead> => {
      const token = tokenStore.get()
      const form = new FormData()
      form.append('file', file)
      const res = await fetch(`/api/projects/${projectId}/documents`, {
        method: 'POST',
        credentials: 'include',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
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
    uploadCorpusDoc: async (appId: string, file: File, isPrimary = false): Promise<AppCorpusDoc> => {
      const token = tokenStore.get()
      const form = new FormData()
      form.append('file', file)
      form.append('is_primary', isPrimary ? 'true' : 'false')
      const res = await fetch(`/api/apps/${appId}/corpus`, {
        method: 'POST',
        credentials: 'include',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
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
