'use client'
import { useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import useSWR from 'swr'
import {
  ArrowLeft, Cpu, History, Pencil, FileText, BookOpen, Layers,
  CheckSquare, Sparkles, Lock, ChevronRight, Check, Circle
} from 'lucide-react'
import { useProjectContext } from '@/lib/context/ProjectContext'
import type { ExtractedRequirement, GapQuestion, ReviewComment, SpecType, SpecVersion } from '@/lib/types'
import { api } from '@/lib/api'
import { useProject } from '@/lib/hooks/useProject'
import { useArtifact } from '@/lib/hooks/useArtifact'
import { UploadPanel } from '@/app/components/UploadPanel'
import { DocumentList } from '@/app/components/DocumentList'
import { OutputTabs } from '@/app/components/OutputTabs'
import type { OutputTab } from '@/app/components/OutputTabs'
import { SpecEditor } from '@/app/components/SpecEditor'
import { GapQuestions } from '@/app/components/GapQuestions'
import { ReviewComments } from '@/app/components/ReviewComments'
import { GenerateSpecsButton } from '@/app/components/GenerateSpecsButton'
import { ExportMenu } from '@/app/components/ExportMenu'
import { EmptyState } from '@/app/components/EmptyState'
import { Skeleton } from '@/app/components/Skeleton'
import { EditProjectModal } from '@/app/components/EditProjectModal'
import { ArtifactBuilderPanel } from '@/app/components/ArtifactBuilderPanel'
import { InterviewPanel } from '@/app/components/InterviewPanel'
import { DocumentViewer } from '@/app/components/DocumentViewer'
import type { DocumentRead } from '@/lib/types'

// ── Types ────────────────────────────────────────────────────────────────────

type View = 'interview' | 'concept-brief' | 'brd' | null

// ── NavItem helper ────────────────────────────────────────────────────────────

interface NavItemProps {
  label: string
  sublabel?: string
  icon: React.ReactNode
  active?: boolean
  locked?: boolean
  comingSoon?: boolean
  badge?: React.ReactNode
  onClick?: () => void
  children?: React.ReactNode
}

function NavItem({ label, sublabel, icon, active, locked, comingSoon, badge, onClick, children }: NavItemProps) {
  return (
    <div>
      <button
        onClick={locked || comingSoon ? undefined : onClick}
        disabled={locked || comingSoon}
        className={[
          'flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-xs transition-colors',
          active
            ? 'border-l-2 border-[var(--accent)] bg-[var(--accent-subtle)]/30 text-[var(--accent-deep)] pl-[9px]'
            : locked || comingSoon
            ? 'opacity-50 cursor-not-allowed text-[var(--text-secondary)]'
            : 'hover:bg-[var(--bg-elevated)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]',
        ].join(' ')}
      >
        <span className={`shrink-0 ${active ? 'text-[var(--accent)]' : 'text-[var(--text-tertiary)]'}`}>
          {icon}
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="font-medium leading-none">{label}</span>
            {comingSoon && (
              <span className="rounded bg-[var(--bg-elevated)] px-1 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
                Soon
              </span>
            )}
          </div>
          {sublabel && (
            <span className="mt-0.5 block text-[10px] text-[var(--text-tertiary)] leading-snug truncate">
              {sublabel}
            </span>
          )}
        </div>
        {badge && <span className="shrink-0">{badge}</span>}
        {locked && !comingSoon && <Lock size={11} className="shrink-0 text-[var(--text-tertiary)]" />}
        {!locked && !active && !comingSoon && onClick && (
          <ChevronRight size={11} className="shrink-0 opacity-0 group-hover:opacity-100 text-[var(--text-tertiary)]" />
        )}
      </button>
      {children && <div className="ml-4 mt-0.5 space-y-0.5">{children}</div>}
    </div>
  )
}

interface SubNavItemProps {
  label: string
  active?: boolean
  badge?: React.ReactNode
  onClick?: () => void
}

function SubNavItem({ label, active, badge, onClick }: SubNavItemProps) {
  return (
    <button
      onClick={onClick}
      className={[
        'flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-[11px] transition-colors',
        active
          ? 'bg-[var(--accent-subtle)]/40 text-[var(--accent-deep)] font-semibold'
          : 'text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]',
      ].join(' ')}
    >
      <span className="flex-1">{label}</span>
      {badge && <span className="shrink-0">{badge}</span>}
    </button>
  )
}

// ── Badge helpers ─────────────────────────────────────────────────────────────

function CountBadge({ count, variant = 'default' }: { count: number; variant?: 'default' | 'success' | 'warning' | 'danger' }) {
  const colors: Record<string, string> = {
    default: 'bg-[var(--bg-elevated)] text-[var(--text-tertiary)]',
    success: 'bg-emerald-100 text-emerald-700',
    warning: 'bg-amber-100 text-amber-700',
    danger: 'bg-red-100 text-red-700',
  }
  return (
    <span className={`rounded-full px-1.5 py-0.5 text-[9px] font-bold leading-none ${colors[variant]}`}>
      {count}
    </span>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function WorkspacePage({ params }: { params: { id: string } }) {
  const projectId = params.id
  const router = useRouter()

  const [activeTab, setActiveTab] = useState<OutputTab>('functional')
  const [generatingTab, setGeneratingTab] = useState<SpecType | null>(null)
  const [extracting, setExtracting] = useState(false)
  const [editing, setEditing] = useState(false)
  const [view, setView] = useState<View>(null)
  const [selectedDoc, setSelectedDoc] = useState<DocumentRead | null>(null)

  const { project, isLoading: projectLoading, mutate: mutateProject } = useProject(projectId)
  const { detail: cbDetail } = useArtifact(projectId, 'concept-brief')
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

  // Determine workflow step (kept for future use)
  const currentStep = (() => {
    if (!project) return 'upload' as const
    if (specs?.length) return 'review' as const
    if (requirements?.length) return 'generate' as const
    if (project.documents.length) return 'extract' as const
    return 'upload' as const
  })()
  void currentStep // suppress unused-variable lint

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

  // Badge counts for sidebar
  const unresolvedGaps = gaps?.filter((g) => !g.resolved) ?? []
  const blockerGaps = unresolvedGaps.filter((g) => g.severity === 'blocker')
  const criticalReviews = reviews?.filter((r) => !r.dismissed && (r.severity === 'critical' || r.severity === 'warning')) ?? []

  // ── Loading state ──────────────────────────────────────────────────────────

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

  const ruValidated = project.ru_validated

  // ── Artifact status helpers ────────────────────────────────────────────────

  const cbStatus = cbDetail?.document?.status ?? null
  // 'generating' | 'in_interview' (=generated, chatting) | 'validated' | null (not started)
  function cbStatusBadge() {
    if (!cbStatus) return null
    if (cbStatus === 'generating') return <span className="text-[9px] rounded px-1.5 py-0.5 bg-blue-100 text-blue-700 font-semibold animate-pulse">Generating…</span>
    if (cbStatus === 'validated') return <span className="text-[9px] rounded px-1.5 py-0.5 bg-emerald-100 text-emerald-700 font-semibold">Validated ✓</span>
    return <span className="text-[9px] rounded px-1.5 py-0.5 bg-amber-100 text-amber-700 font-semibold">Draft</span>
  }
  const cbSublabel = !cbStatus ? 'Not started' : cbStatus === 'generating' ? 'Generating…' : cbStatus === 'validated' ? 'Validated' : 'Draft · in progress'

  // ── Artifacts sidebar (always visible, narrow) ────────────────────────────

  const artifactsSidebar = (
    <aside className="w-52 shrink-0 flex flex-col overflow-y-auto border-r border-[var(--border-default)] bg-[var(--bg-surface)]">
      <div className="px-3 pt-4 pb-4 flex-1 space-y-0.5">
        <p className="mb-3 text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)]">
          Artifacts
        </p>

        {/* 1. Requirement Understanding */}
        <NavItem
          label="Req. Understanding"
          sublabel={ruValidated ? 'Validated ✓' : 'Pending interview'}
          icon={<FileText size={14} />}
          active={view === 'interview'}
          badge={
            ruValidated
              ? <span className="text-[9px] rounded px-1.5 py-0.5 bg-emerald-100 text-emerald-700 font-semibold">Done ✓</span>
              : <span className="text-[9px] rounded px-1.5 py-0.5 bg-amber-100 text-amber-700 font-semibold">Pending</span>
          }
          onClick={() => setView('interview')}
        />

        {/* 2. Concept Brief */}
        <NavItem
          label="Concept Brief"
          sublabel={cbSublabel}
          icon={<Sparkles size={14} />}
          active={view === 'concept-brief'}
          badge={cbStatusBadge()}
          onClick={() => setView('concept-brief')}
        />

        {/* 3. BRD */}
        <NavItem
          label="BRD"
          sublabel={ruValidated ? 'Business Requirements' : 'Unlocks after RU'}
          icon={<BookOpen size={14} />}
          active={view === 'brd'}
          locked={!ruValidated}
          onClick={ruValidated ? () => setView('brd') : undefined}
        >
          {view === 'brd' && (
            <>
              {(
                [
                  { key: 'functional' as OutputTab, label: 'Functional' },
                  { key: 'technical' as OutputTab, label: 'Technical' },
                  { key: 'user_stories' as OutputTab, label: 'User Stories' },
                  { key: 'gaps' as OutputTab, label: 'Open Questions' },
                  { key: 'review' as OutputTab, label: 'Review' },
                ] as { key: OutputTab; label: string }[]
              ).map(({ key, label }) => {
                const isSpecTab = key === 'functional' || key === 'technical' || key === 'user_stories'
                const ver = isSpecTab ? versionMap[key as SpecType] : undefined
                const badge =
                  key === 'gaps' && unresolvedGaps.length > 0 ? (
                    <CountBadge count={unresolvedGaps.length} variant={blockerGaps.length > 0 ? 'danger' : 'warning'} />
                  ) : key === 'review' && criticalReviews.length > 0 ? (
                    <CountBadge count={criticalReviews.length} variant="warning" />
                  ) : ver ? (
                    <span className="text-[9px] text-[var(--text-tertiary)]">v{ver}</span>
                  ) : undefined
                return (
                  <SubNavItem
                    key={key}
                    label={label}
                    active={activeTab === key}
                    badge={badge}
                    onClick={() => setActiveTab(key)}
                  />
                )
              })}
            </>
          )}
        </NavItem>

        {/* 4. FRS */}
        <NavItem
          label="FRS"
          sublabel="Coming soon"
          icon={<Layers size={14} />}
          comingSoon
          locked
        />

        {/* 5. Test Cases */}
        <NavItem
          label="Test Cases"
          sublabel="Coming soon"
          icon={<CheckSquare size={14} />}
          comingSoon
          locked
        />
      </div>
    </aside>
  )

  // ── Documents panel (overview only) ───────────────────────────────────────

  const documentsPanel = (
    <div className="w-72 shrink-0 flex flex-col overflow-hidden border-r border-[var(--border-default)] bg-[var(--bg-surface)]">
      <div className="shrink-0 flex items-center justify-between px-4 pt-4 pb-2">
        <span className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)]">
          Documents
        </span>
        {project.documents.length > 0 && (
          <span className="text-[10px] text-[var(--text-tertiary)]">{project.documents.length} file{project.documents.length !== 1 ? 's' : ''}</span>
        )}
      </div>

      {/* Upload zone */}
      <div className="px-3 pb-2 shrink-0">
        <UploadPanel projectId={projectId} onUploaded={() => { mutateProject(); }} />
      </div>

      {/* Document list — scrollable */}
      <div className="flex-1 overflow-y-auto px-3 py-1">
        <DocumentList
          projectId={projectId}
          documents={project.documents}
          selectedId={selectedDoc?.id}
          onSelect={(doc) => setSelectedDoc(prev => prev?.id === doc.id ? null : doc)}
          onDeleted={() => { mutateProject(); setSelectedDoc(null) }}
        />
      </div>

      {/* Footer actions */}
      {project.documents.length > 0 && (
        <div className="shrink-0 border-t border-[var(--border-subtle)] px-3 py-3 space-y-2">
          <button
            onClick={handleExtract}
            disabled={extracting}
            className="flex w-full items-center justify-center gap-1.5 rounded-lg border border-[var(--border-default)] px-3 py-2 text-xs font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:border-[var(--text-tertiary)] disabled:opacity-50 transition-colors"
          >
            <Cpu size={12} className={extracting ? 'animate-pulse' : ''} />
            {extracting ? 'Extracting…' : 'Extract Requirements'}
          </button>
          {requirements && requirements.length > 0 && (
            <p className="text-center text-[10px] text-[var(--text-tertiary)]">
              {requirements.length} requirement{requirements.length !== 1 ? 's' : ''} extracted
            </p>
          )}
        </div>
      )}
    </div>
  )

  // ── Main content ───────────────────────────────────────────────────────────

  const mainContent = (() => {
    if (view === 'interview') {
      return (
        <InterviewPanel
          projectId={projectId}
          onBack={() => setView(null)}
          onValidated={() => { mutateProject(); setView(null) }}
        />
      )
    }

    if (view === 'concept-brief') {
      return (
        <ArtifactBuilderPanel
          projectId={projectId}
          artifactType="concept-brief"
          onBack={() => setView(null)}
        />
      )
    }

    if (view === 'brd') {
      return (
        <div className="flex flex-col h-full">
          <div className="flex items-center justify-between pl-3 pr-4 py-2 border-b border-[var(--border-default)] bg-[var(--bg-surface)]">
            <button
              onClick={() => setView(null)}
              className="inline-flex items-center gap-1 rounded-full border border-[var(--border-default)] bg-[var(--bg-elevated)] px-2.5 py-1 text-[11px] text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:border-[var(--text-tertiary)] transition-colors shrink-0"
            >
              <ArrowLeft size={11} />
              BRD
            </button>
          </div>
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
                disabled={!project?.ru_validated}
                disabledReason="Validate the Requirement Understanding first"
              />
            </div>
          </div>

          {!ruValidated && (
            <button
              onClick={() => setView('interview')}
              className="flex w-full items-center gap-2 border-b border-warning-border bg-warning-bg/40 px-4 py-2 text-left text-xs text-[var(--text-secondary)] hover:bg-warning-bg/60 transition-colors"
            >
              <Cpu size={13} className="text-warning shrink-0" />
              <span>Requirement Understanding not validated — spec generation is locked.</span>
              <span className="ml-auto font-semibold text-[var(--accent-deep)]">Open interview →</span>
            </button>
          )}

          <div className="flex-1 overflow-y-auto">
            {activeTab === 'gaps' ? (
              gaps && gaps.length > 0 ? (
                <GapQuestions projectId={projectId} gaps={gaps} onGapUpdate={() => mutateGaps()} />
              ) : (
                <EmptyState title="No gap questions" description="Upload documents and run 'Extract Requirements' to detect gaps." />
              )
            ) : activeTab === 'review' ? (
              reviews && reviews.length > 0 ? (
                <ReviewComments projectId={projectId} comments={reviews} onCommentUpdate={() => mutateReviews()} />
              ) : (
                <EmptyState title="No review comments" description="Generate all specs first, then the reviewer runs automatically." />
              )
            ) : activeSpec ? (
              <SpecEditor projectId={projectId} spec={activeSpec} onSaved={() => mutateSpecs()} />
            ) : (
              <EmptyState title={`No ${activeTab.replace('_', ' ')} spec yet`} description="Click 'Generate Specs' to create specs from your requirements." />
            )}
          </div>
        </div>
      )
    }

    // view === null → document viewer or project overview
    if (selectedDoc) {
      return (
        <DocumentViewer
          projectId={projectId}
          doc={selectedDoc}
          onClose={() => setSelectedDoc(null)}
        />
      )
    }

    // No doc selected — project overview + progress
    return (
      <div className="flex-1 overflow-y-auto p-8">
        <div className="max-w-xl mx-auto space-y-6">
          <div>
            <h2 className="text-2xl font-bold text-[var(--text-primary)] leading-tight">{project.name}</h2>
            {project.description && (
              <p className="mt-1.5 text-sm text-[var(--text-secondary)] leading-relaxed">{project.description}</p>
            )}
            <div className="mt-3 flex flex-wrap gap-2 text-xs text-[var(--text-tertiary)]">
              {project.business_unit && (
                <span className="rounded-md bg-[var(--bg-elevated)] px-2 py-1">{project.business_unit}</span>
              )}
              {project.go_live_date && (
                <span className="rounded-md bg-[var(--bg-elevated)] px-2 py-1">
                  Go-live: {new Date(project.go_live_date).toLocaleDateString()}
                </span>
              )}
            </div>
          </div>

          {project.apps_in_scope && project.apps_in_scope.length > 0 && (
            <div>
              <p className="mb-2 text-[11px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)]">Apps in scope</p>
              <div className="flex flex-wrap gap-1.5">
                {project.apps_in_scope.map((app) => (
                  <span key={app.app_id} className="rounded-full border border-[var(--border-default)] bg-[var(--bg-surface)] px-3 py-1 text-xs text-[var(--text-secondary)]">
                    {app.name}
                  </span>
                ))}
              </div>
            </div>
          )}

          <div>
            <p className="mb-3 text-[11px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)]">Project Progress</p>
            <div className="space-y-2">
              <ProgressStep
                done={project.documents.length > 0}
                label="Upload source documents"
                sublabel={project.documents.length > 0 ? `${project.documents.length} document${project.documents.length !== 1 ? 's' : ''} uploaded` : 'Use the Documents panel to upload'}
              />
              <ProgressStep
                done={cbStatus === 'validated'}
                inProgress={!!cbStatus && cbStatus !== 'validated'}
                label="Concept Brief"
                sublabel={cbSublabel}
                onClick={() => setView('concept-brief')}
              />
              <ProgressStep
                done={ruValidated}
                inProgress={!ruValidated}
                label="Requirement Understanding"
                sublabel={ruValidated ? 'Validated' : 'Interview required before generating BRD'}
                onClick={() => setView('interview')}
              />
              <ProgressStep
                done={!!specs?.length}
                locked={!ruValidated}
                label="BRD Specs"
                sublabel={!ruValidated ? 'Locked — validate RU first' : specs?.length ? `${specs.length} spec${specs.length !== 1 ? 's' : ''} generated` : 'Ready to generate'}
                onClick={ruValidated ? () => setView('brd') : undefined}
              />
            </div>
          </div>
        </div>
      </div>
    )
  })()

  // ── Render ─────────────────────────────────────────────────────────────────

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
            <div className="flex items-center gap-1.5">
              <h1 className="text-sm font-semibold text-[var(--text-primary)] truncate leading-none">
                {project.name}
              </h1>
              <button
                onClick={() => setEditing(true)}
                title="Edit project"
                className="shrink-0 rounded-md p-1 text-[var(--text-tertiary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]"
              >
                <Pencil size={12} />
              </button>
            </div>
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

      {editing && (
        <EditProjectModal
          project={project}
          canDelete
          onClose={() => setEditing(false)}
          onUpdated={() => mutateProject()}
          onDeleted={() => router.push('/')}
        />
      )}

      {/* Workspace: artifacts sidebar | documents panel (overview only) | main content */}
      <div className="flex flex-1 overflow-hidden">
        {artifactsSidebar}
        {view === null && documentsPanel}
        <main className="flex-1 overflow-hidden bg-[var(--bg-base)] flex flex-col">
          {mainContent}
        </main>
      </div>
    </div>
  )
}

// ── ProgressStep ──────────────────────────────────────────────────────────────

function ProgressStep({
  done, inProgress, locked, label, sublabel, onClick,
}: {
  done?: boolean
  inProgress?: boolean
  locked?: boolean
  label: string
  sublabel?: string
  onClick?: () => void
}) {
  const iconEl = done
    ? <Check size={11} className="text-white" />
    : locked
    ? <Lock size={10} className="text-[var(--text-tertiary)]" />
    : <Circle size={10} className={inProgress ? 'text-amber-500' : 'text-[var(--border-default)]'} />

  const iconBg = done
    ? 'bg-emerald-500 border-emerald-500'
    : locked
    ? 'bg-[var(--bg-elevated)] border-[var(--border-default)]'
    : inProgress
    ? 'bg-amber-50 border-amber-400'
    : 'bg-[var(--bg-elevated)] border-[var(--border-default)]'

  return (
    <button
      onClick={locked ? undefined : onClick}
      disabled={locked || !onClick}
      className={[
        'flex w-full items-start gap-3 rounded-lg border px-3 py-2.5 text-left transition-colors',
        done
          ? 'border-emerald-100 bg-emerald-50/60'
          : locked
          ? 'border-[var(--border-default)] opacity-50 cursor-not-allowed'
          : onClick
          ? 'border-[var(--border-default)] hover:border-[var(--accent)] hover:bg-[var(--accent-subtle)]/10 cursor-pointer'
          : 'border-[var(--border-default)]',
      ].join(' ')}
    >
      <span className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border ${iconBg}`}>
        {iconEl}
      </span>
      <div className="min-w-0 flex-1">
        <p className={`text-xs font-medium leading-none ${done ? 'text-emerald-700' : 'text-[var(--text-primary)]'}`}>
          {label}
        </p>
        {sublabel && (
          <p className="mt-0.5 text-[10px] text-[var(--text-tertiary)] leading-snug">{sublabel}</p>
        )}
      </div>
      {!locked && onClick && !done && (
        <ChevronRight size={12} className="shrink-0 mt-0.5 text-[var(--text-tertiary)]" />
      )}
    </button>
  )
}
