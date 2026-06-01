import type {
  ArtifactDetail,
  ArtifactSource,
  BrdBundleReadiness,
  BrdCoverageReport,
  BrdDetail,
  BrdFinding,
  BrdFindings,
  CbRow,
  DiscoverEnhanceBriefResult,
  DiscoverQuestion,
  DiscoverStateResponse,
  AppCorpusDoc,
  AppCreate,
  AppDetail,
  AppFact,
  AppListItem,
  AppsFilter,
  AppSuggestion,
  AppWikiConcept,
  AppWikiSummary,
  AskSessionListItem,
  AskSessionMessage,
  AskSessionRead,
  BrainContextResponse,
  DocTreeResponse,
  WikiIndexResponse,
  WikiSectionContent,
  AssumptionItem,
  AuditEventRead,
  AuditFilters,
  AuditSummary,
  DocumentOutline,
  DocumentRead,
  DocumentSection,
  ExtractedRequirement,
  FactsFilter,
  FrsBundleReadiness,
  FrsCoverage,
  FrsDetail,
  FrsFigmaLinkResponse,
  FrsFindingsResponse,
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
  ProjectLineage,
  ResolvedFact,
  TestCasesDetail,
  TestCasesReadiness,
  TestCasesCoverage,
  TestCasesFindingsResponse,
  TestCaseRow,
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

  // 204 No Content — body is empty regardless of what content-type header says
  if (res.status === 204) return undefined as unknown as T

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

function _auditQuery(f?: AuditFilters): string {
  const p = new URLSearchParams()
  if (f?.q) p.set('q', f.q)
  if (f?.event) p.set('event', f.event)
  if (f?.category && f.category !== 'all') p.set('category', f.category)
  if (f?.actor_id) p.set('actor_id', f.actor_id)
  if (f?.project_id) p.set('project_id', f.project_id)
  if (f?.correlation_id) p.set('correlation_id', f.correlation_id)
  if (f?.start) p.set('start', f.start)
  if (f?.end) p.set('end', f.end)
  if (f?.limit !== undefined) p.set('limit', String(f.limit))
  if (f?.offset !== undefined) p.set('offset', String(f.offset))
  const qs = p.toString()
  return qs ? `?${qs}` : ''
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
    answerClarification: (id: string, gqId: string, answer: string) =>
      apiFetch<UnderstandingDetail>(
        `/api/projects/${id}/understanding/clarifications/${gqId}/answer`,
        { method: 'POST', body: JSON.stringify({ answer }) },
      ),
    // ── Project Wiki (E2) ──────────────────────────────────────────────────
    getWiki: (id: string) => apiFetch<WikiIndexResponse>(`/api/projects/${id}/wiki`),
    getWikiConcept: (id: string, slug: string) =>
      apiFetch<AppWikiConcept>(`/api/projects/${id}/wiki/concepts/${slug}`),
    getWikiSummary: (id: string, docId: string) =>
      apiFetch<AppWikiSummary>(`/api/projects/${id}/wiki/summaries/${docId}`),
    rebuildWiki: (id: string) =>
      apiFetch<{ task_id: string | null; status: string }>(
        `/api/projects/${id}/wiki/rebuild`, { method: 'POST' }),
    checkWikiHealth: (id: string) =>
      apiFetch<{ task_id: string | null; status: string }>(
        `/api/projects/${id}/wiki/health`, { method: 'POST' }),
    getSourceSection: (id: string, docId: string, nodeId: string) =>
      apiFetch<WikiSectionContent>(`/api/projects/${id}/sources/${docId}/section/${nodeId}`),
    resolveFact: (id: string, factId: string) =>
      apiFetch<ResolvedFact>(`/api/projects/${id}/facts/${factId}`),
    resolveFactByIndex: (id: string, index: number) =>
      apiFetch<ResolvedFact>(`/api/projects/${id}/facts/by-index/${index}`),
    provenance: (id: string) =>
      apiFetch<ProjectLineage>(`/api/projects/${id}/provenance`),
    // ── Ask the Project (E2 Copilot) ────────────────────────────────────────
    listChatSessions: (id: string) =>
      apiFetch<AskSessionListItem[]>(`/api/projects/${id}/ask/sessions`),
    getChatSession: (id: string, sid: string) =>
      apiFetch<AskSessionRead>(`/api/projects/${id}/ask/sessions/${sid}`),
    saveChatSession: (
      id: string,
      body: { id: string | null; title: string; messages: AskSessionMessage[] },
    ) =>
      apiFetch<{ id: string; updated_at: string }>(
        `/api/projects/${id}/ask/sessions`,
        { method: 'POST', body: JSON.stringify(body) },
      ),
    deleteChatSession: (id: string, sid: string) =>
      apiFetch<void>(`/api/projects/${id}/ask/sessions/${sid}`, { method: 'DELETE' }),
  },

  triage: {
    list: () => apiFetchEnvelope<TriageItem[]>('/api/triage'),
  },

  audit: {
    list: (filters?: AuditFilters) =>
      apiFetchEnvelope<AuditEventRead[]>(`/api/audit${_auditQuery(filters)}`),
    summary: () => apiFetch<AuditSummary>('/api/audit/summary'),
    exportCsv: async (filters?: AuditFilters): Promise<void> => {
      const res = await authedFetch(`/api/audit/export.csv${_auditQuery(filters)}`)
      if (!res.ok) throw new Error(`Export failed: ${res.status}`)
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'audit-log.csv'
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    },
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
    getContent: (projectId: string, docId: string) =>
      apiFetch<{ id: string; filename: string; parse_status: string; text: string | null }>(
        `/api/projects/${projectId}/documents/${docId}/content`
      ),
    getOutline: (projectId: string, docId: string) =>
      apiFetch<DocumentOutline>(`/api/projects/${projectId}/documents/${docId}/outline`),
    getSection: (projectId: string, docId: string, nodeId: string) =>
      apiFetch<DocumentSection>(`/api/projects/${projectId}/documents/${docId}/section/${nodeId}`),
    getFileUrl: (projectId: string, docId: string): string =>
      `/api/projects/${projectId}/documents/${docId}/file`,
    reindex: (projectId: string, docId: string) =>
      apiFetch<DocumentRead>(`/api/projects/${projectId}/documents/${docId}/reindex`, {
        method: 'POST',
      }),
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

  artifacts: {
    get: (projectId: string, type: string) =>
      apiFetch<ArtifactDetail>(`/api/projects/${projectId}/artifacts/${type}`),
    generate: (projectId: string, type: string, body?: { context?: string }) =>
      apiFetch<ArtifactDetail>(`/api/projects/${projectId}/artifacts/${type}/generate`, {
        method: 'POST',
        body: body ? JSON.stringify(body) : undefined,
        headers: body ? { 'Content-Type': 'application/json' } : undefined,
      }),
    generateUnit: (projectId: string, type: string, unitKey: string) =>
      apiFetch<ArtifactDetail>(`/api/projects/${projectId}/artifacts/${type}/units/${unitKey}/generate`, { method: 'POST' }),
    regenerateUnit: (projectId: string, type: string, unitKey: string, directive?: string) =>
      apiFetch<ArtifactDetail>(`/api/projects/${projectId}/artifacts/${type}/units/${unitKey}/regenerate`, {
        method: 'POST', body: JSON.stringify({ directive }),
      }),
    answer: (projectId: string, type: string, answer: string, seq?: number) =>
      apiFetch<ArtifactDetail>(`/api/projects/${projectId}/artifacts/${type}/answer`, {
        method: 'POST', body: JSON.stringify({ answer, seq }),
      }),
    rowHistory: (projectId: string, type: string, unitKey: string, rowKey: string, table: string) =>
      apiFetch<CbRow[]>(`/api/projects/${projectId}/artifacts/${type}/units/${unitKey}/rows/${rowKey}/history?table=${table}`),
    editRow: (projectId: string, type: string, table: string, rowId: string, fields: Record<string, unknown>, lock = true) =>
      apiFetch<CbRow>(`/api/projects/${projectId}/artifacts/${type}/rows/${table}/${rowId}`, {
        method: 'PATCH', body: JSON.stringify({ fields, lock }),
      }),
    restoreRow: (projectId: string, type: string, table: string, rowId: string, version: number) =>
      apiFetch<CbRow>(`/api/projects/${projectId}/artifacts/${type}/rows/${table}/${rowId}/restore`, {
        method: 'POST', body: JSON.stringify({ version }),
      }),
    unlockRow: (projectId: string, type: string, table: string, rowId: string) =>
      apiFetch<CbRow>(`/api/projects/${projectId}/artifacts/${type}/rows/${table}/${rowId}/unlock`, { method: 'POST' }),
    deleteRow: (projectId: string, type: string, table: string, rowId: string) =>
      apiFetch<{ id: string; status: string }>(`/api/projects/${projectId}/artifacts/${type}/rows/${table}/${rowId}`, { method: 'DELETE' }),
    validate: (projectId: string, type: string) =>
      apiFetch<{ ok: boolean; failures: string[] }>(`/api/projects/${projectId}/artifacts/${type}/validate`, { method: 'POST' }),
    exportUrl: (projectId: string, type: string) =>
      `/api/projects/${projectId}/artifacts/${type}/export/markdown`,
    listSources: (projectId: string, type: string) =>
      apiFetch<ArtifactSource[]>(`/api/projects/${projectId}/artifacts/${type}/sources`),
    toggleSource: (projectId: string, type: string, sourceId: string, included: boolean) =>
      apiFetch<{ id: string; included: boolean }>(`/api/projects/${projectId}/artifacts/${type}/sources/${sourceId}`, {
        method: 'PATCH', body: JSON.stringify({ included }),
      }),

    // Discover Phase
    enhanceBrief: (projectId: string, type: string, briefText: string) =>
      apiFetch<DiscoverEnhanceBriefResult>(
        `/api/projects/${projectId}/artifacts/${type}/discover/enhance-brief`,
        { method: 'POST', body: JSON.stringify({ brief_text: briefText }) },
      ),
    analyzeDiscover: (projectId: string, type: string, briefText: string) =>
      apiFetch<{ questions: DiscoverQuestion[]; analyzing: boolean }>(
        `/api/projects/${projectId}/artifacts/${type}/discover/analyze`,
        { method: 'POST', body: JSON.stringify({ brief_text: briefText }) },
      ),
    getDiscover: (projectId: string, type: string) =>
      apiFetch<DiscoverStateResponse>(`/api/projects/${projectId}/artifacts/${type}/discover`),
    answerDiscover: (projectId: string, type: string, questionId: string, answer: string) =>
      apiFetch<DiscoverQuestion>(
        `/api/projects/${projectId}/artifacts/${type}/discover/questions/${questionId}`,
        { method: 'PATCH', body: JSON.stringify({ answer }) },
      ),
    completeDiscover: (projectId: string, type: string) =>
      apiFetch<ArtifactDetail>(
        `/api/projects/${projectId}/artifacts/${type}/discover/complete`,
        { method: 'POST' },
      ),
  },

  brd: {
    get: (projectId: string) =>
      apiFetch<BrdDetail>(`/api/projects/${projectId}/artifacts/brd`),
    readiness: (projectId: string) =>
      apiFetch<BrdBundleReadiness>(`/api/projects/${projectId}/artifacts/brd/readiness`, { method: 'POST' }),
    generate: (projectId: string, body?: { context?: string }) =>
      apiFetch<BrdDetail>(`/api/projects/${projectId}/artifacts/brd/generate`, {
        method: 'POST', body: JSON.stringify(body ?? {}),
      }),
    answer: (projectId: string, body: { answer: string; seq?: number }) =>
      apiFetch<BrdDetail>(`/api/projects/${projectId}/artifacts/brd/answer`, {
        method: 'POST', body: JSON.stringify(body),
      }),
    validate: (projectId: string) =>
      apiFetch<BrdFindings>(`/api/projects/${projectId}/artifacts/brd/validate`, { method: 'POST' }),
    findings: (projectId: string) =>
      apiFetch<BrdFindings>(`/api/projects/${projectId}/artifacts/brd/findings`),
    coverage: (projectId: string) =>
      apiFetch<BrdCoverageReport>(`/api/projects/${projectId}/artifacts/brd/coverage`),
    export: (projectId: string) =>
      authedFetch(`/api/projects/${projectId}/artifacts/brd/export`),
    editRow: (projectId: string, table: string, rowId: string, fields: Record<string, unknown>, lock?: boolean) =>
      apiFetch<unknown>(`/api/projects/${projectId}/artifacts/brd/${table}/${rowId}/edit`, {
        method: 'POST', body: JSON.stringify({ fields, lock }),
      }),
    rowHistory: (projectId: string, table: string, rowId: string) =>
      apiFetch<unknown[]>(`/api/projects/${projectId}/artifacts/brd/${table}/${rowId}/history`),
    deleteRow: (projectId: string, table: string, rowId: string) =>
      apiFetch<{ deleted: boolean; row_key: string }>(`/api/projects/${projectId}/artifacts/brd/${table}/${rowId}/delete`, { method: 'POST' }),
    regenerateUnit: (projectId: string, unitKey: string) =>
      apiFetch<unknown>(`/api/projects/${projectId}/artifacts/brd/units/${unitKey}/regenerate`, { method: 'POST' }),
    resetGenerating: (projectId: string) =>
      apiFetch<{ status: string }>(`/api/projects/${projectId}/artifacts/brd/reset-generating`, { method: 'POST' }),
    discoverAnalyze: (projectId: string) =>
      apiFetch<{ questions: DiscoverQuestion[] }>(`/api/projects/${projectId}/artifacts/brd/discover/analyze`, { method: 'POST' }),
    discoverAnswer: (projectId: string, qKey: string, body: { answer: string }) =>
      apiFetch<DiscoverQuestion>(`/api/projects/${projectId}/artifacts/brd/discover/${qKey}/answer`, {
        method: 'POST', body: JSON.stringify(body),
      }),
    discoverEnhance: (projectId: string, body: { question_key: string; draft: string }) =>
      apiFetch<{ enhanced: string }>(`/api/projects/${projectId}/artifacts/brd/discover/enhance`, {
        method: 'POST', body: JSON.stringify(body),
      }),
  },

  frs: {
    get: (projectId: string) =>
      apiFetch<FrsDetail>(`/api/projects/${projectId}/artifacts/frs`),
    readiness: (projectId: string) =>
      apiFetch<FrsBundleReadiness>(`/api/projects/${projectId}/artifacts/frs/readiness`, { method: 'POST' }),
    generate: (projectId: string, body?: { brief?: string }) =>
      apiFetch<FrsDetail>(`/api/projects/${projectId}/artifacts/frs/generate`, {
        method: 'POST', body: JSON.stringify(body ?? {}),
      }),
    modularize: (projectId: string) =>
      apiFetch<FrsDetail>(`/api/projects/${projectId}/artifacts/frs/modularize`, { method: 'POST' }),
    resetGenerating: (projectId: string) =>
      apiFetch<{ status: string }>(`/api/projects/${projectId}/artifacts/frs/reset-generating`, { method: 'POST' }),
    answer: (projectId: string, body: { answer: string; seq?: number }) =>
      apiFetch<FrsDetail>(`/api/projects/${projectId}/artifacts/frs/answer`, {
        method: 'POST', body: JSON.stringify(body),
      }),
    validate: (projectId: string) =>
      apiFetch<FrsFindingsResponse>(`/api/projects/${projectId}/artifacts/frs/validate`, { method: 'POST' }),
    findings: (projectId: string) =>
      apiFetch<FrsFindingsResponse>(`/api/projects/${projectId}/artifacts/frs/findings`),
    resolveDecision: (
      projectId: string,
      decisionRowId: string,
      body: { chosen_index: number; status: 'accepted_ai' | 'overridden' | 'dismissed' },
    ) =>
      apiFetch<{ row_key: string; resolution_status: string }>(
        `/api/projects/${projectId}/artifacts/frs/decisions/${decisionRowId}/resolve`,
        { method: 'POST', body: JSON.stringify(body) },
      ),
    editRow: (
      projectId: string,
      table: string,
      rowId: string,
      fields: Record<string, unknown>,
      opts?: { lock?: boolean; expected_version?: number },
    ) =>
      apiFetch<{ id: string; row_key: string; version: number }>(
        `/api/projects/${projectId}/artifacts/frs/${table}/${rowId}/edit`,
        { method: 'POST', body: JSON.stringify({ fields, ...opts }) },
      ),
    deleteRow: (projectId: string, table: string, rowId: string) =>
      apiFetch<{ deleted: boolean }>(`/api/projects/${projectId}/artifacts/frs/${table}/${rowId}/delete`, { method: 'POST' }),
    unlockRow: (projectId: string, table: string, rowId: string) =>
      apiFetch<{ unlocked: boolean }>(`/api/projects/${projectId}/artifacts/frs/${table}/${rowId}/unlock`, { method: 'POST' }),
    restoreRow: (projectId: string, table: string, rowId: string) =>
      apiFetch<{ id: string; row_key: string; version: number }>(
        `/api/projects/${projectId}/artifacts/frs/${table}/${rowId}/restore`,
        { method: 'POST' },
      ),
    rowHistory: (projectId: string, table: string, rowId: string) =>
      apiFetch<unknown[]>(`/api/projects/${projectId}/artifacts/frs/${table}/${rowId}/history`),
    discoverAnalyze: (projectId: string) =>
      apiFetch<{ categories: unknown[]; questions: unknown[] }>(
        `/api/projects/${projectId}/artifacts/frs/discover/analyze`,
        { method: 'POST' },
      ),
    discoverAnswer: (projectId: string, qKey: string, body: { answer: string }) =>
      apiFetch<{ q_key: string; answered: boolean }>(
        `/api/projects/${projectId}/artifacts/frs/discover/${qKey}/answer`,
        { method: 'POST', body: JSON.stringify(body) },
      ),
    discoverEnhance: (projectId: string, body: { brief: string }) =>
      apiFetch<{ enhanced: string }>(`/api/projects/${projectId}/artifacts/frs/discover/enhance`, {
        method: 'POST', body: JSON.stringify(body),
      }),
    // ── Stage B ────────────────────────────────────────────────────────────
    designModule: (projectId: string, moduleRowKey: string) =>
      apiFetch<FrsDetail>(
        `/api/projects/${projectId}/artifacts/frs/modules/${moduleRowKey}/design`,
        { method: 'POST' },
      ),
    regenerateSpec: (
      projectId: string, specRowKey: string,
      scope: 'full' | 'ui_only' = 'full',
    ) =>
      apiFetch<FrsDetail>(
        `/api/projects/${projectId}/artifacts/frs/specs/${specRowKey}/regenerate`,
        { method: 'POST', body: JSON.stringify({ scope }) },
      ),
    setFigmaLink: (
      projectId: string, specRowKey: string, body: { link: string },
    ) =>
      apiFetch<FrsFigmaLinkResponse>(
        `/api/projects/${projectId}/artifacts/frs/specs/${specRowKey}/figma-link`,
        { method: 'POST', body: JSON.stringify(body) },
      ),
    skipUiPending: (projectId: string, clearDanglingDeps = true) =>
      apiFetch<{ skipped_ui: number; cleared_deps: number; detail: FrsDetail }>(
        `/api/projects/${projectId}/artifacts/frs/skip-ui-pending`,
        { method: 'POST', body: JSON.stringify({ clear_dangling_deps: clearDanglingDeps }) },
      ),
    coverage: (projectId: string) =>
      apiFetch<FrsCoverage>(`/api/projects/${projectId}/artifacts/frs/coverage`),
    exportBundle: (projectId: string) =>
      authedFetch(`/api/projects/${projectId}/artifacts/frs/export`).then(r => r.blob()),
    designAllModules: (projectId: string, skipDesigned = true) =>
      apiFetch<FrsDetail>(
        `/api/projects/${projectId}/artifacts/frs/design-all-modules`,
        { method: 'POST', body: JSON.stringify({ skip_designed: skipDesigned }) },
      ),
  },

  testcases: {
    get: (projectId: string) =>
      apiFetch<TestCasesDetail>(`/api/projects/${projectId}/artifacts/test_cases`),
    readiness: (projectId: string) =>
      apiFetch<TestCasesReadiness>(`/api/projects/${projectId}/artifacts/test_cases/readiness`, { method: 'POST' }),
    generate: (projectId: string) =>
      apiFetch<TestCasesDetail>(`/api/projects/${projectId}/artifacts/test_cases/generate`, {
        method: 'POST', body: JSON.stringify({}),
      }),
    designAllPlans: (
      projectId: string,
      opts?: { skipDesigned?: boolean; moduleRowKey?: string },
    ) =>
      apiFetch<TestCasesDetail>(`/api/projects/${projectId}/artifacts/test_cases/design-all-plans`, {
        method: 'POST',
        body: JSON.stringify({
          skip_designed: opts?.skipDesigned ?? true,
          module_row_key: opts?.moduleRowKey,
        }),
      }),
    regeneratePlan: (projectId: string, specRowKey: string) =>
      apiFetch<TestCasesDetail>(`/api/projects/${projectId}/artifacts/test_cases/plans/${specRowKey}/regenerate`, { method: 'POST' }),
    gapFill: (projectId: string, specRowKey?: string) =>
      apiFetch<TestCasesDetail>(
        specRowKey
          ? `/api/projects/${projectId}/artifacts/test_cases/plans/${specRowKey}/gap-fill`
          : `/api/projects/${projectId}/artifacts/test_cases/gap-fill`,
        { method: 'POST' },
      ),
    repair: (projectId: string) =>
      apiFetch<{ cleanup: { cases_cleaned: number; refs_removed: number; traces_removed: number }; detail: TestCasesDetail }>(
        `/api/projects/${projectId}/artifacts/test_cases/repair`, { method: 'POST' },
      ),
    resetGenerating: (projectId: string) =>
      apiFetch<{ status: string }>(`/api/projects/${projectId}/artifacts/test_cases/reset-generating`, { method: 'POST' }),
    coverage: (projectId: string) =>
      apiFetch<TestCasesCoverage>(`/api/projects/${projectId}/artifacts/test_cases/coverage`),
    findings: (projectId: string) =>
      apiFetch<TestCasesFindingsResponse>(`/api/projects/${projectId}/artifacts/test_cases/findings`),
    validate: (projectId: string) =>
      apiFetch<TestCasesFindingsResponse>(`/api/projects/${projectId}/artifacts/test_cases/validate`, { method: 'POST' }),
    addCase: (projectId: string, planRowKey: string, body: Record<string, unknown>) =>
      apiFetch<{ row_key: string }>(`/api/projects/${projectId}/artifacts/test_cases/plans/${planRowKey}/cases`, {
        method: 'POST', body: JSON.stringify(body),
      }),
    editRow: (
      projectId: string, table: string, rowId: string,
      fields: Record<string, unknown>, opts?: { lock?: boolean; expected_version?: number },
    ) =>
      apiFetch<{ id: string; row_key: string; version: number }>(
        `/api/projects/${projectId}/artifacts/test_cases/${table}/${rowId}/edit`,
        { method: 'POST', body: JSON.stringify({ fields, ...opts }) },
      ),
    deleteRow: (projectId: string, table: string, rowId: string) =>
      apiFetch<{ deleted: boolean }>(`/api/projects/${projectId}/artifacts/test_cases/${table}/${rowId}/delete`, { method: 'POST' }),
    unlockRow: (projectId: string, table: string, rowId: string) =>
      apiFetch<{ unlocked: boolean }>(`/api/projects/${projectId}/artifacts/test_cases/${table}/${rowId}/unlock`, { method: 'POST' }),
    rowHistory: (projectId: string, table: string, rowId: string) =>
      apiFetch<{ versions: TestCaseRow[] }>(`/api/projects/${projectId}/artifacts/test_cases/${table}/${rowId}/history`),
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
    deleteCorpusDoc: (appId: string, docId: string) =>
      apiFetch<void>(`/api/apps/${appId}/corpus/${docId}`, { method: 'DELETE' }),
    getCorpusDocMarkdown: (appId: string, docId: string) =>
      apiFetch<{ markdown_text: string; provider: string; filename: string; created_at: string }>(
        `/api/apps/${appId}/corpus/${docId}/markdown`
      ),
    reindexDoc: (appId: string, docId: string) =>
      apiFetch<{ task_id: string }>(`/api/apps/${appId}/corpus/${docId}/reindex`, { method: 'POST' }),
    getDocFacts: (appId: string, docId: string) =>
      apiFetch<AppFact[]>(`/api/apps/${appId}/corpus/${docId}/facts`),
    createDocFact: (appId: string, docId: string, body: { kind: string; text: string; confidence: string; source_ref?: string | null }) =>
      apiFetch<AppFact>(`/api/apps/${appId}/corpus/${docId}/facts`, { method: 'POST', body: JSON.stringify(body) }),
    getBrainContext: (appId: string) =>
      apiFetch<BrainContextResponse>(`/api/apps/${appId}/brain-context`),
    synthesizeBrainContext: (appId: string) =>
      apiFetch<{ task_id: string | null; status: string }>(`/api/apps/${appId}/brain-context/synthesize`, { method: 'POST' }),
    getWiki: (appId: string) =>
      apiFetch<WikiIndexResponse>(`/api/apps/${appId}/wiki`),
    getWikiConcept: (appId: string, slug: string) =>
      apiFetch<AppWikiConcept>(`/api/apps/${appId}/wiki/concepts/${slug}`),
    getWikiSummary: (appId: string, docId: string) =>
      apiFetch<AppWikiSummary>(`/api/apps/${appId}/wiki/summaries/${docId}`),
    rebuildWiki: (appId: string) =>
      apiFetch<{ task_id: string | null; status: string }>(`/api/apps/${appId}/wiki/rebuild`, { method: 'POST' }),
    checkWikiHealth: (appId: string) =>
      apiFetch<{ task_id: string | null; status: string }>(`/api/apps/${appId}/wiki/health`, { method: 'POST' }),
    getCorpusSection: (appId: string, docId: string, nodeId: string) =>
      apiFetch<WikiSectionContent>(`/api/apps/${appId}/corpus/${docId}/section/${nodeId}`),
    getDocTree: (appId: string, docId: string) =>
      apiFetch<DocTreeResponse>(`/api/apps/${appId}/corpus/${docId}/tree`),
    listAskSessions: (appId: string) =>
      apiFetch<AskSessionListItem[]>(`/api/apps/${appId}/ask/sessions`),
    getAskSession: (appId: string, sessionId: string) =>
      apiFetch<AskSessionRead>(`/api/apps/${appId}/ask/sessions/${sessionId}`),
    saveAskSession: (appId: string, body: { id: string | null; title: string; messages: AskSessionMessage[] }) =>
      apiFetch<{ id: string; updated_at: string }>(`/api/apps/${appId}/ask/sessions`, { method: 'POST', body: JSON.stringify(body) }),
    deleteAskSession: (appId: string, sessionId: string) =>
      apiFetch<void>(`/api/apps/${appId}/ask/sessions/${sessionId}`, { method: 'DELETE' }),
    extractFacts: (appId: string) =>
      apiFetch<{ task_id: string }>(`/api/apps/${appId}/facts/extract`, { method: 'POST' }),
    listFacts: (appId: string, filters?: FactsFilter) => {
      const params = new URLSearchParams()
      if (filters?.kind) params.set('kind', filters.kind)
      if (filters?.status) params.set('status', filters.status)
      if (filters?.confidence) params.set('confidence', filters.confidence)
      const qs = params.toString()
      return apiFetch<AppFact[]>(`/api/apps/${appId}/facts${qs ? `?${qs}` : ''}`)
    },
    createFact: (appId: string, body: { kind: string; text: string; confidence: string; source_ref?: string | null }) =>
      apiFetch<AppFact>(`/api/apps/${appId}/facts`, { method: 'POST', body: JSON.stringify(body) }),
    updateFact: (appId: string, factId: string, body: Partial<{ kind: string; text: string; confidence: string; source_ref: string | null; status: string }>) =>
      apiFetch<AppFact>(`/api/apps/${appId}/facts/${factId}`, { method: 'PATCH', body: JSON.stringify(body) }),
    deleteFact: (appId: string, factId: string) =>
      apiFetch<void>(`/api/apps/${appId}/facts/${factId}`, { method: 'DELETE' }),
  },
}
