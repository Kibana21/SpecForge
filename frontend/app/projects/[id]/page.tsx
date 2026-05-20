'use client'
import { useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import useSWR from 'swr'
import { ArrowLeft, Cpu, History } from 'lucide-react'
import { useProjectContext } from '@/lib/context/ProjectContext'
import type { ExtractedRequirement, GapQuestion, ReviewComment, SpecType, SpecVersion } from '@/lib/types'
import { api } from '@/lib/api'
import { useProject } from '@/lib/hooks/useProject'
import { ThreePanel } from '@/app/components/ThreePanel'
import { WorkflowSteps } from '@/app/components/WorkflowSteps'
import { UploadPanel } from '@/app/components/UploadPanel'
import { DocumentList } from '@/app/components/DocumentList'
import { ExtractedRequirements } from '@/app/components/ExtractedRequirements'
import { OutputTabs } from '@/app/components/OutputTabs'
import type { OutputTab } from '@/app/components/OutputTabs'
import { SpecEditor } from '@/app/components/SpecEditor'
import { GapQuestions } from '@/app/components/GapQuestions'
import { ReviewComments } from '@/app/components/ReviewComments'
import { GenerateSpecsButton } from '@/app/components/GenerateSpecsButton'
import { ExportMenu } from '@/app/components/ExportMenu'
import { EmptyState } from '@/app/components/EmptyState'
import { Skeleton } from '@/app/components/Skeleton'

export default function WorkspacePage({ params }: { params: { id: string } }) {
  const projectId = params.id
  const router = useRouter()

  const [activeTab, setActiveTab] = useState<OutputTab>('functional')
  const [generatingTab, setGeneratingTab] = useState<SpecType | null>(null)
  const [extracting, setExtracting] = useState(false)

  const { project, isLoading: projectLoading, mutate: mutateProject } = useProject(projectId)
  const { openVersionPanel } = useProjectContext()

  const { data: specs, mutate: mutateSpecs } = useSWR<SpecVersion[]>(
    `/api/projects/${projectId}/specs`,
    () => api.specs.list(projectId),
    { revalidateOnFocus: false }
  )

  const { data: requirements, mutate: mutateReqs } = useSWR<ExtractedRequirement[]>(
    `/api/projects/${projectId}/requirements`,
    () => api.documents.listRequirements(projectId),
    { revalidateOnFocus: false }
  )

  const { data: gaps, mutate: mutateGaps } = useSWR<GapQuestion[]>(
    `/api/projects/${projectId}/gaps`,
    () => api.documents.listGaps(projectId),
    { revalidateOnFocus: false }
  )

  const { data: reviews, mutate: mutateReviews } = useSWR<ReviewComment[]>(
    `/api/projects/${projectId}/reviews`,
    () => api.reviews.list(projectId),
    { revalidateOnFocus: false }
  )

  const handleGenerating = useCallback((tab: SpecType | null) => {
    setGeneratingTab(tab)
    if (tab) setActiveTab(tab)
  }, [])

  const handleGenerateComplete = useCallback(() => {
    mutateSpecs()
    mutateReviews()
    mutateProject()
  }, [mutateSpecs, mutateReviews, mutateProject])

  async function handleExtract() {
    setExtracting(true)
    try {
      await api.documents.extract(projectId)
      await api.documents.detectGaps(projectId)
      mutateReqs()
      mutateGaps()
    } finally {
      setExtracting(false)
    }
  }

  // Determine workflow step
  const currentStep = (() => {
    if (!project) return 'upload' as const
    if (specs?.length) return 'review' as const
    if (requirements?.length) return 'generate' as const
    if (project.documents.length) return 'extract' as const
    return 'upload' as const
  })()

  // Build version map from latest specs per type
  const versionMap: Partial<Record<SpecType, number>> = {}
  if (specs) {
    for (const s of specs) {
      if (!versionMap[s.spec_type] || s.version_number > (versionMap[s.spec_type] ?? 0)) {
        versionMap[s.spec_type] = s.version_number
      }
    }
  }

  // Active spec for editable tabs
  const isEditableTab = activeTab === 'functional' || activeTab === 'technical' || activeTab === 'user_stories'
  const activeSpec = isEditableTab && specs
    ? specs
        .filter((s) => s.spec_type === activeTab)
        .sort((a, b) => b.version_number - a.version_number)[0]
    : undefined

  const loadingTabs: Partial<Record<OutputTab, boolean>> = {}
  if (generatingTab) loadingTabs[generatingTab] = true

  // Right panel context
  const criticalReviews = reviews?.filter((r) => !r.dismissed && (r.severity === 'critical' || r.severity === 'warning'))
  const blockerGaps = gaps?.filter((g) => !g.resolved && g.severity === 'blocker')

  if (projectLoading || !project) {
    return (
      <div className="flex flex-col h-screen">
        <header className="h-14 flex items-center px-4 border-b border-[var(--border-default)] bg-[var(--bg-surface)]">
          <Skeleton className="h-4 w-48" />
        </header>
        <div className="p-6 space-y-3">
          <Skeleton className="h-4 w-64" />
          <Skeleton className="h-4 w-40" />
        </div>
      </div>
    )
  }

  /* ── Left Panel ── */
  const leftPanel = (
    <div className="flex flex-col">
      <WorkflowSteps current={currentStep} />

      <div className="border-t border-[var(--border-subtle)]">
        <p className="px-4 pt-3 pb-1 text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)]">
          Documents
        </p>
        <DocumentList
          projectId={projectId}
          documents={project.documents}
          onDeleted={() => mutateProject()}
        />
        <UploadPanel projectId={projectId} onUploaded={() => mutateProject()} />
      </div>

      {project.documents.length > 0 && (
        <div className="border-t border-[var(--border-subtle)] p-3">
          <button
            onClick={handleExtract}
            disabled={extracting}
            className="flex w-full items-center justify-center gap-2 rounded-lg border border-[var(--border-default)] px-3 py-2 text-xs font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:border-[var(--text-tertiary)] disabled:opacity-50 transition-colors"
          >
            <Cpu size={13} className={extracting ? 'animate-pulse' : ''} />
            {extracting ? 'Extracting…' : 'Extract Requirements'}
          </button>
        </div>
      )}

      {requirements && requirements.length > 0 && (
        <div className="border-t border-[var(--border-subtle)]">
          <p className="px-4 pt-3 pb-1 text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)]">
            Requirements ({requirements.length})
          </p>
          <ExtractedRequirements requirements={requirements} />
        </div>
      )}
    </div>
  )

  /* ── Center Panel ── */
  const centerPanel = (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between pl-0 pr-4 pt-0 border-b border-[var(--border-default)]">
        <OutputTabs
          activeTab={activeTab}
          onTabChange={setActiveTab}
          loadingTabs={loadingTabs}
          versionMap={versionMap}
        />
        <div className="flex items-center gap-2 shrink-0 pb-3 pt-3">
          <ExportMenu projectId={projectId} />
          <GenerateSpecsButton
            projectId={projectId}
            onGenerating={handleGenerating}
            onComplete={handleGenerateComplete}
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {activeTab === 'gaps' ? (
          gaps && gaps.length > 0 ? (
            <GapQuestions
              projectId={projectId}
              gaps={gaps}
              onGapUpdate={() => mutateGaps()}
            />
          ) : (
            <EmptyState
              title="No gap questions"
              description="Upload documents and run 'Extract Requirements' to detect gaps."
            />
          )
        ) : activeTab === 'review' ? (
          reviews && reviews.length > 0 ? (
            <ReviewComments
              projectId={projectId}
              comments={reviews}
              onCommentUpdate={() => mutateReviews()}
            />
          ) : (
            <EmptyState
              title="No review comments"
              description="Generate all specs first, then the reviewer runs automatically."
            />
          )
        ) : activeSpec ? (
          <SpecEditor
            projectId={projectId}
            spec={activeSpec}
            onSaved={() => mutateSpecs()}
          />
        ) : (
          <EmptyState
            title={`No ${activeTab.replace('_', ' ')} spec yet`}
            description="Click 'Generate Specs' to create specs from your requirements."
          />
        )}
      </div>
    </div>
  )

  /* ── Right Panel ── */
  const rightPanel = (
    <div className="p-4 space-y-5">
      {activeTab === 'gaps' ? (
        <>
          <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)]">
            Gap Summary
          </p>
          {gaps && gaps.length > 0 ? (
            <div className="space-y-1.5">
              {(['blocker', 'major', 'minor'] as const).map((sev) => {
                const total = gaps.filter((g) => g.severity === sev).length
                const done = gaps.filter((g) => g.severity === sev && g.resolved).length
                if (!total) return null
                return (
                  <div key={sev} className="flex items-center justify-between">
                    <span className="text-xs capitalize text-[var(--text-secondary)]">{sev}</span>
                    <span className="text-xs text-[var(--text-tertiary)]">{done}/{total} resolved</span>
                  </div>
                )
              })}
            </div>
          ) : (
            <p className="text-xs text-[var(--text-tertiary)]">No gaps detected yet.</p>
          )}
        </>
      ) : activeTab === 'review' ? (
        <>
          <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)]">
            Unresolved Blockers
          </p>
          {blockerGaps && blockerGaps.length > 0 ? (
            <ul className="space-y-2">
              {blockerGaps.slice(0, 5).map((g) => (
                <li key={g.id} className="text-[11px] text-rose-600 leading-relaxed">{g.question}</li>
              ))}
              {blockerGaps.length > 5 && (
                <li className="text-[10px] text-[var(--text-tertiary)]">+{blockerGaps.length - 5} more</li>
              )}
            </ul>
          ) : (
            <p className="text-xs text-[var(--text-tertiary)]">No blocker gaps.</p>
          )}
        </>
      ) : (
        <>
          <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)]">
            Issues
          </p>
          {criticalReviews && criticalReviews.length > 0 ? (
            <ul className="space-y-2.5">
              {criticalReviews.slice(0, 6).map((r) => (
                <li key={r.id} className="text-[11px] leading-relaxed">
                  <span className={r.severity === 'critical' ? 'text-rose-600' : 'text-amber-600'}>
                    [{r.section}]
                  </span>
                  <span className="text-[var(--text-secondary)] ml-1">{r.comment}</span>
                </li>
              ))}
              {criticalReviews.length > 6 && (
                <li className="text-[10px] text-[var(--text-tertiary)]">+{criticalReviews.length - 6} more</li>
              )}
            </ul>
          ) : (
            <p className="text-xs text-[var(--text-tertiary)]">No critical issues.</p>
          )}
        </>
      )}
    </div>
  )

  return (
    <div className="flex flex-col h-screen overflow-hidden">
      {/* Project header */}
      <header className="h-14 shrink-0 flex items-center justify-between px-4 border-b border-[var(--border-default)] bg-[var(--bg-surface)]">
        <div className="flex items-center gap-3 min-w-0">
          <button
            onClick={() => router.push('/')}
            className="shrink-0 p-1.5 rounded-lg text-[var(--text-tertiary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-elevated)] transition-colors"
            aria-label="Back to dashboard"
          >
            <ArrowLeft size={16} />
          </button>
          <div className="min-w-0">
            <h1 className="text-sm font-semibold text-[var(--text-primary)] truncate leading-none">
              {project.name}
            </h1>
            {project.description && (
              <p className="text-[11px] text-[var(--text-tertiary)] mt-0.5 truncate">
                {project.description}
              </p>
            )}
          </div>
        </div>
        <button
          onClick={() => openVersionPanel(`project:${projectId}`)}
          className="flex items-center gap-1.5 rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] px-2.5 py-1.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] transition-colors"
          title="Version history"
        >
          <History size={12} />
          History
        </button>
      </header>

      <ThreePanel left={leftPanel} center={centerPanel} right={rightPanel} />
    </div>
  )
}
