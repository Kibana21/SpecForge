'use client'
import { useMemo } from 'react'
import { api } from '@/lib/api'
import { BrainWiki, type WikiAdapter } from './BrainWiki'

interface Props {
  projectId: string
  initialCompiledAt?: string | null
  initialStatus?: string
  lastIndexedAt?: string | null
  canWrite?: boolean
  /** Open directly on this concept slug (deep-link from the studio rail). */
  initialSlug?: string
}

/**
 * Project Wiki (E2) — the navigable, source-grounded knowledge view of a
 * project's own uploaded documents. Reuses the App Brain wiki UI (BrainWiki)
 * via a project-scoped API adapter, so concepts, "Grounded in" drill-downs,
 * health, and rebuild all work identically.
 */
export function ProjectWiki({
  projectId, initialCompiledAt = null, initialStatus = 'idle',
  lastIndexedAt = null, canWrite = true, initialSlug,
}: Props) {
  const adapter: WikiAdapter = useMemo(() => ({
    label: 'Project Wiki',
    getIndex: () => api.projects.getWiki(projectId),
    getConcept: (slug) => api.projects.getWikiConcept(projectId, slug),
    getSummary: (docId) => api.projects.getWikiSummary(projectId, docId),
    rebuild: () => api.projects.rebuildWiki(projectId),
    checkHealth: () => api.projects.checkWikiHealth(projectId),
    getSection: (docId, nodeId) => api.projects.getSourceSection(projectId, docId, nodeId),
  }), [projectId])

  return (
    <BrainWiki
      adapter={adapter}
      projectId={projectId}
      initialSlug={initialSlug}
      initialCompiledAt={initialCompiledAt}
      initialStatus={initialStatus}
      lastIndexedAt={lastIndexedAt}
      canWrite={canWrite}
    />
  )
}
