import type {
  DocumentRead,
  ExtractedRequirement,
  GapQuestion,
  ProjectDetail,
  ProjectListItem,
  ProjectRead,
  ReviewComment,
  SpecType,
  SpecVersion,
} from './types'

async function apiFetch<T>(url: string, options?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {}
  if (!(options?.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
  }
  const res = await fetch(url, { headers, ...options })
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
      const form = new FormData()
      form.append('file', file)
      const res = await fetch(`/api/projects/${projectId}/documents`, {
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
}
