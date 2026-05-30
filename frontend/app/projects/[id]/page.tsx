'use client'
import { useState, useCallback } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import useSWR from 'swr'
import {
  AlertTriangle, ArrowLeft, Cpu, History, Pencil, FileText, BookOpen, BookMarked, Layers,
  CheckSquare, Sparkles, Lock, ChevronRight, Check, Circle, X
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
import { BrdBuilderView } from '@/app/components/brd/BrdBuilderView'
import { FrsBuilderView } from '@/app/components/frs/FrsBuilderView'
import { ProjectWiki } from '@/app/components/ProjectWiki'
import type { DocumentRead } from '@/lib/types'

// ── Types ────────────────────────────────────────────────────────────────────

type View = 'interview' | 'wiki' | 'concept-brief' | 'brd' | 'frs' | null

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
            : 'hover:bg-[var(--bg-elevated)] text-[var(--text-primary)] hover:text-[var(--text-primary)]',
        ].join(' ')}
      >
        <span className={`shrink-0 ${active ? 'text-[var(--accent)]' : 'text-[var(--text-secondary)]'}`}>
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
  const searchParams = useSearchParams()

  const [activeTab, setActiveTab] = useState<OutputTab>('functional')
  const [generatingTab, setGeneratingTab] = useState<SpecType | null>(null)
  const [extracting, setExtracting] = useState(false)
  const [editing, setEditing] = useState(false)
  const [view, setView] = useState<View>(() => {
    const v = searchParams.get('view')
    return (v === 'interview' || v === 'wiki' || v === 'concept-brief' || v === 'brd' || v === 'frs') ? v : null
  })
  const [selectedDoc, setSelectedDoc] = useState<DocumentRead | null>(null)
  const [staleBannerDismissed, setStaleBannerDismissed] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false
    return sessionStorage.getItem(`stale-ru-${projectId}`) === '1'
  })

  const { project, isLoading: projectLoading, mutate: mutateProject } = useProject(projectId)
  const { detail: cbDetail } = useArtifact(projectId, 'concept-brief')
  const { data: brdDetail } = useSWR(
    `brd-detail-${projectId}`,
    () => api.brd.get(projectId),
    { revalidateOnFocus: false },
  )
  const { data: frsDetail } = useSWR(
    `frs-detail-${projectId}`,
    () => api.frs.get(projectId),
    {
      revalidateOnFocus: false,
      refreshInterval: (data) => {
        const status = data?.document?.status
        if (status === 'generating') return 2000
        if (data?.document?.unit_status?.['_current_unit']) return 2000
        return 0
      },
    },
  )
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
  const cbValidated = cbDetail?.document?.status === 'validated'

  // ── Artifact status helpers ────────────────────────────────────────────────

  const cbStatus = cbDetail?.document?.status ?? null
  const brdStatus = brdDetail?.document?.status ?? null

  function brdStatusBadge() {
    if (!brdStatus) return null
    if (brdStatus === 'generating') return <span className="text-[9px] rounded px-1.5 py-0.5 bg-blue-100 text-blue-700 font-semibold animate-pulse">Generating…</span>
    if (brdStatus === 'validated') return <span className="text-[9px] rounded px-1.5 py-0.5 bg-emerald-100 text-emerald-700 font-semibold">Validated ✓</span>
    if (brdStatus === 'in_interview') return <span className="text-[9px] rounded px-1.5 py-0.5 bg-amber-100 text-amber-700 font-semibold">Draft</span>
    return null
  }
  const brdSublabel = !brdStatus
    ? (cbValidated ? 'Business Requirements' : 'Unlocks after CB')
    : brdStatus === 'generating' ? 'Generating…'
    : brdStatus === 'validated' ? 'Validated'
    : 'Draft · in progress'

  const brdValidated = brdStatus === 'validated'
  const frsStatus = frsDetail?.document?.status ?? null
  const frsStageAApproved = Boolean(frsDetail?.document?.unit_status?.['_stage_a_approved'])

  function frsStatusBadge() {
    if (!frsStatus) return null
    if (frsStatus === 'generating') return <span className="text-[9px] rounded px-1.5 py-0.5 bg-blue-100 text-blue-700 font-semibold animate-pulse">{frsStageAApproved ? 'Designing…' : 'Generating…'}</span>
    if (frsStatus === 'validated') return <span className="text-[9px] rounded px-1.5 py-0.5 bg-emerald-100 text-emerald-700 font-semibold">Validated ✓</span>
    if (frsStageAApproved) return <span className="text-[9px] rounded px-1.5 py-0.5 bg-emerald-50 text-emerald-700 font-semibold border border-emerald-200">Stage 1 ✓</span>
    if (frsStatus === 'in_interview') return <span className="text-[9px] rounded px-1.5 py-0.5 bg-amber-100 text-amber-700 font-semibold">Draft</span>
    return null
  }
  const frsSublabel = !frsStatus
    ? (brdValidated ? 'Functional Specifications' : 'Unlocks after BRD')
    : frsStatus === 'generating' ? (frsStageAApproved ? 'Designing modules…' : 'Modularizing…')
    : frsStatus === 'validated' ? 'Validated'
    : frsStageAApproved ? 'Stage 1 approved · Stage 2 ready'
    : 'Draft · in progress'

  // 'in_discover' | 'generating' | 'in_interview' (=generated, chatting) | 'validated' | null (not started)
  function cbStatusBadge() {
    if (!cbStatus) return null
    if (cbStatus === 'in_discover') return <span className="text-[9px] rounded px-1.5 py-0.5 bg-violet-100 text-violet-700 font-semibold">Discover</span>
    if (cbStatus === 'generating') return <span className="text-[9px] rounded px-1.5 py-0.5 bg-blue-100 text-blue-700 font-semibold animate-pulse">Generating…</span>
    if (cbStatus === 'validated') return <span className="text-[9px] rounded px-1.5 py-0.5 bg-emerald-100 text-emerald-700 font-semibold">Validated ✓</span>
    return <span className="text-[9px] rounded px-1.5 py-0.5 bg-amber-100 text-amber-700 font-semibold">Draft</span>
  }
  const cbSublabel = !cbStatus ? 'Not started' : cbStatus === 'in_discover' ? 'Discovery in progress' : cbStatus === 'generating' ? 'Generating…' : cbStatus === 'validated' ? 'Validated' : 'Draft · in progress'

  // ── Artifacts sidebar (always visible, narrow) ────────────────────────────

  const artifactsSidebar = (
    <aside className="w-52 shrink-0 flex flex-col overflow-y-auto border-r border-[var(--border-default)] bg-[var(--bg-surface)]">
      <div className="px-3 pt-4 pb-4 flex-1 space-y-0.5">
        <p className="mb-3 text-[10px] font-semibold uppercase tracking-widest text-[var(--text-secondary)]">
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

        {/* Project Wiki — emergent, source-grounded knowledge from uploaded docs */}
        <NavItem
          label="Project Wiki"
          sublabel="Source-grounded knowledge"
          icon={<BookMarked size={14} />}
          active={view === 'wiki'}
          onClick={() => setView('wiki')}
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
          sublabel={brdSublabel}
          icon={<BookOpen size={14} />}
          active={view === 'brd'}
          locked={!cbValidated}
          badge={brdStatusBadge()}
          onClick={cbValidated ? () => setView('brd') : undefined}
        />

        {/* 4. FRS */}
        <NavItem
          label="FRS"
          sublabel={frsSublabel}
          icon={<Layers size={14} />}
          active={view === 'frs'}
          locked={!brdValidated}
          badge={frsStatusBadge()}
          onClick={brdValidated ? () => setView('frs') : undefined}
        />

        {/* 5. Test Cases — unlocks after FRS validated (Stage B complete) */}
        <NavItem
          label="Test Cases"
          sublabel={frsStatus === 'validated' ? 'Coming soon — FRS validated ✓' : 'Coming soon'}
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
        <span className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-secondary)]">
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

    if (view === 'wiki') {
      return (
        <div className="flex flex-col h-full overflow-hidden bg-[var(--bg-base)]">
          <div className="shrink-0 h-12 flex items-center gap-3 border-b border-[var(--border-default)] bg-[var(--bg-surface)] px-4">
            <button
              onClick={() => setView(null)}
              className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] transition-colors"
            >
              ← Back
            </button>
            <span className="text-sm font-semibold text-[var(--text-primary)]">Project Wiki</span>
          </div>
          <div className="flex-1 overflow-hidden p-4">
            <ProjectWiki projectId={projectId} canWrite />
          </div>
        </div>
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
        <BrdBuilderView
          projectId={projectId}
          onBack={() => setView(null)}
        />
      )
    }

    if (view === 'frs') {
      return (
        <FrsBuilderView
          projectId={projectId}
          onBack={() => setView(null)}
        />
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
      <>
        {project.docs_stale_for_ru && !staleBannerDismissed && (
          <div className="shrink-0 flex items-center gap-3 bg-amber-50 border-b border-amber-200 px-4 py-2.5">
            <AlertTriangle size={14} className="shrink-0 text-amber-500" />
            <p className="flex-1 text-xs text-amber-800">
              A document was added after your Requirement Understanding. Regenerate it to incorporate the latest sources.
            </p>
            <button
              onClick={() => setView('interview')}
              className="shrink-0 text-xs font-semibold text-amber-700 hover:text-amber-900 transition-colors"
            >
              Open Interview →
            </button>
            <button
              onClick={() => {
                setStaleBannerDismissed(true)
                sessionStorage.setItem(`stale-ru-${projectId}`, '1')
              }}
              className="shrink-0 rounded p-0.5 text-amber-400 hover:text-amber-700 transition-colors"
              aria-label="Dismiss"
            >
              <X size={12} />
            </button>
          </div>
        )}
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
                done={false}
                locked={!cbValidated}
                label="BRD"
                sublabel={!cbValidated ? 'Unlocks after Concept Brief is validated' : 'Ready to build'}
                onClick={cbValidated ? () => setView('brd') : undefined}
              />
            </div>
          </div>
        </div>
      </div>
      </>
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
              <p className="text-[11px] text-[var(--text-secondary)] mt-0.5 truncate">
                {project.description}
              </p>
            )}
          </div>
        </div>
        <button
          onClick={() => openVersionPanel(`project:${projectId}`)}
          className="flex items-center gap-1.5 rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] px-2.5 py-1.5 text-xs text-[var(--text-primary)] hover:bg-[var(--bg-elevated)] transition-colors"
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
          onUpdated={async () => { await mutateProject() }}
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
