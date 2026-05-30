'use client'
/**
 * FRS Builder View — Stage A state machine.
 *
 * Routes between 6 surfaces:
 *   S0 — readiness blocked (no validated BRD)
 *   S1 — empty (no FRS doc yet) → FrsEmptyState
 *   S3 — generating → FrsConstructionTheater (5-step simulated narrative)
 *   S4 — builder body (rail + module panel) — the 80% experience
 *   S5 — findings drawer (slides over S4)
 *   S6 — Stage 1 approved → S4 + ContinueStageBBanner
 *
 * Header is always present with: Back · status badge · sources/coverage/check-validate
 * The "Resume from here" recovery button lives in the generation theater header.
 */
import { useEffect, useMemo, useState } from 'react'
import useSWR from 'swr'
import {
  AlertTriangle, ArrowLeft, ArrowRight, BookOpen, CheckCircle2, Loader2, RotateCcw, Sparkles,
} from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'
import { useFrsReadiness } from '@/lib/hooks/useFrsReadiness'
import type { FrsFindingsResponse, FrsSpecDecisionRow } from '@/lib/types'

import { FrsEmptyState } from './FrsEmptyState'
import { FrsConstructionTheater } from './FrsConstructionTheater'
import { FrsTwoPhaseGenerationViz } from './FrsTwoPhaseGenerationViz'
import { FrsModuleRail } from './FrsModuleRail'
import { FrsModulePanel } from './FrsModulePanel'
import { FrsSpecPanel } from './FrsSpecPanel'
import { FrsModuleDecisionPrompt } from './FrsModuleDecisionPrompt'
import { FrsModularizeFindings } from './FrsModularizeFindings'
import { FrsFindingsDrawer } from './FrsFindingsDrawer'
import { FrsCoverageGalaxy } from './FrsCoverageGalaxy'
import { FrsExportMenu } from './FrsExportMenu'
import { FrsContinueStageBBanner } from './FrsContinueStageBBanner'
import { FrsBrdEchoStrip } from './FrsBrdEchoStrip'
import { SourceStrip } from '@/app/components/brd/SourceStrip'

interface Props {
  projectId: string
  onBack: () => void
}

export function FrsBuilderView({ projectId, onBack }: Props) {
  const { readiness } = useFrsReadiness(projectId)
  const { data: detail, mutate, isLoading } = useSWR(
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

  // ── State ────────────────────────────────────────────────────────────────
  const [activeModuleKey, setActiveModuleKey] = useState<string | null>(null)
  const [activeSpecRowKey, setActiveSpecRowKey] = useState<string | null>(null)
  const [coverageOpen, setCoverageOpen] = useState(false)
  const [openDecision, setOpenDecision] = useState<FrsSpecDecisionRow | null>(null)
  const [findingsOpen, setFindingsOpen] = useState(false)
  const [findings, setFindings] = useState<FrsFindingsResponse | null>(null)
  const [findingsLoading, setFindingsLoading] = useState(false)
  const [bannerDismissed, setBannerDismissed] = useState(false)
  const [stageBRunning, setStageBRunning] = useState(false)

  // Auto-select first module when modules first appear
  useEffect(() => {
    if (!activeModuleKey && detail?.modules && detail.modules.length > 0) {
      setActiveModuleKey(detail.modules[0].row_key)
    }
  }, [activeModuleKey, detail?.modules])

  // ── Derived ─────────────────────────────────────────────────────────────
  const doc = detail?.document ?? null
  const modules = detail?.modules ?? []
  const status = doc?.status ?? null
  const modularizeStatus = doc?.unit_status?.['modularize'] as { completeness?: number; confidence?: string } | undefined
  const stageAApproved = Boolean(doc?.unit_status?.['_stage_a_approved'])
  const activeModule = modules.find((m) => m.row_key === activeModuleKey) ?? null
  const activeSpec = useMemo(() => {
    if (!activeSpecRowKey) return null
    for (const m of modules) {
      const s = m.backlog?.find((sp) => sp.row_key === activeSpecRowKey)
      if (s) return { spec: s, module: m }
    }
    return null
  }, [activeSpecRowKey, modules])

  const openModuleDecisions: FrsSpecDecisionRow[] = useMemo(() => {
    if (!detail?.decisions || !activeModuleKey) return []
    return detail.decisions.filter(
      (d) => d.resolution_status === 'open' && d.module_row_key === activeModuleKey,
    )
  }, [detail?.decisions, activeModuleKey])

  // ── Findings flow ────────────────────────────────────────────────────────
  async function handleCheckValidate() {
    setFindingsLoading(true)
    try {
      const result = await api.frs.findings(projectId)
      setFindings(result)
      setFindingsOpen(true)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Could not load findings')
    } finally {
      setFindingsLoading(false)
    }
  }

  // ── Actions ──────────────────────────────────────────────────────────────
  async function handleRegenerateModule() {
    if (!activeModuleKey) return
    try {
      await api.frs.designModule(projectId, activeModuleKey)
      toast.success(`Module design queued for ${activeModuleKey}`)
      await mutate()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Regeneration failed')
    }
  }

  async function handleToggleLock(table: string, rowId: string, currentLocked: boolean) {
    try {
      if (currentLocked) {
        await api.frs.unlockRow(projectId, table, rowId)
        toast.success('Unlocked')
      } else {
        await api.frs.editRow(projectId, table, rowId, {}, { lock: true })
        toast.success('Locked — will be preserved on regen')
      }
      mutate()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to toggle lock')
    }
  }

  async function handleDeleteStub(rowId: string) {
    try {
      await api.frs.deleteRow(projectId, 'frs_specs', rowId)
      toast.success('Stub removed')
      mutate()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Delete failed')
    }
  }

  async function handleContinueStageB() {
    setBannerDismissed(true)
    setStageBRunning(true)
    const moduleKeys = modules.map((m) => m.row_key)
    let ok = 0
    for (const key of moduleKeys) {
      try {
        await api.frs.designModule(projectId, key)
        ok++
        await mutate()
      } catch {
        toast.error(`Design failed for module ${key}`)
      }
    }
    setStageBRunning(false)
    if (ok > 0) toast.success(`Stage 2 complete — ${ok} module${ok !== 1 ? 's' : ''} designed`)
    await mutate()
  }

  // ── Render gates ─────────────────────────────────────────────────────────

  // Loading first hit
  if (isLoading) {
    return (
      <div className="flex flex-col h-full items-center justify-center bg-[var(--bg-base)]">
        <Loader2 size={24} className="animate-spin text-[var(--accent)]" />
        <p className="mt-2 text-sm text-[var(--text-tertiary)]">Loading FRS state…</p>
      </div>
    )
  }

  // S3b — Stage B generation in progress (client-driven, mock-mode)
  if (stageBRunning) {
    const coveredBrsB = new Set(modules.flatMap((m) => m.backlog?.flatMap((s) => s.br_refs ?? []) ?? []))
    return (
      <FrsTwoPhaseGenerationViz
        projectId={projectId}
        modules={modules}
        unitStatus={doc?.unit_status}
        brCount={coveredBrsB.size}
        onComplete={() => { setStageBRunning(false); mutate() }}
        onCancel={() => { setStageBRunning(false); mutate() }}
      />
    )
  }

  // S3 — generating WITH real progress signal (recent unit_status update or
  // _current_unit pointer). Without this, a stale 'generating' status from a
  // failed worker would strand the user in the spinner forever.
  const hasGenerationProgress = Boolean(
    doc?.unit_status?.['_current_unit'] ||
    (modularizeStatus?.completeness && modularizeStatus.completeness > 0),
  )
  if (status === 'generating' && hasGenerationProgress) {
    // Stage A approved → Stage B is running; show the two-phase viz with per-module bars.
    // Stage A not yet approved → Stage A modularization is running; show the construction theater.
    if (stageAApproved) {
      const coveredBrsGen = new Set(modules.flatMap((m) => m.backlog?.flatMap((s) => s.br_refs ?? []) ?? []))
      return (
        <FrsTwoPhaseGenerationViz
          projectId={projectId}
          modules={modules}
          unitStatus={doc?.unit_status}
          brCount={coveredBrsGen.size}
          onComplete={() => { setStageBRunning(false); mutate() }}
          onCancel={() => { setStageBRunning(false); mutate() }}
        />
      )
    }
    return (
      <FrsConstructionTheater
        projectId={projectId}
        modularizeCompleteness={modularizeStatus?.completeness}
        docStatus={status}
        readiness={readiness}
        onComplete={() => mutate()}
        onCancel={() => mutate()}
      />
    )
  }

  // S1 — empty state. Shown when:
  //   - No doc exists yet (first visit), OR
  //   - Doc exists but no modules have been produced (stuck/aborted/regen)
  //
  // If status === 'generating' but no progress, we still drop into the empty
  // state with a warning banner so the user can restart cleanly rather than
  // staring at a spinner forever.
  const showEmptyState = !doc || (modules.length === 0 && !stageAApproved)
  if (showEmptyState) {
    return (
      <div className="flex flex-col h-full overflow-hidden bg-[var(--bg-base)]">
        <Header
          projectId={projectId}
          onBack={onBack}
          status={status}
          stageAApproved={false}
          onCheckValidate={() => {}}
          checkBusy={false}
          showActions={false}
        />
        <div className="flex-1 overflow-auto">
          {status === 'generating' && (
            <StalledGenerationBanner
              projectId={projectId}
              onReset={() => mutate()}
            />
          )}
          <FrsEmptyState
            projectId={projectId}
            readiness={readiness}
            onGenerateStarted={() => mutate()}
          />
        </div>
      </div>
    )
  }

  // S4/S6 — builder body
  const moduleCount = modules.length
  const stubCount = modules.reduce((sum, m) => sum + (m.backlog?.length ?? 0), 0)
  const coveredBrs = new Set(modules.flatMap((m) => m.backlog?.flatMap((s) => s.br_refs ?? []) ?? []))

  const showContinueBanner =
    stageAApproved && !bannerDismissed && status === 'in_interview'

  return (
    <div className="flex flex-col h-full overflow-hidden bg-[var(--bg-base)]">
      <Header
        projectId={projectId}
        onBack={onBack}
        status={status}
        stageAApproved={stageAApproved}
        onCheckValidate={handleCheckValidate}
        checkBusy={findingsLoading}
        showActions
        onCoverage={() => setCoverageOpen(true)}
      />

      {/* Body: rail + active surface */}
      <div className="flex flex-1 overflow-hidden">
        <FrsModuleRail
          modules={modules}
          activeModuleKey={activeModuleKey}
          activeSpecRowKey={activeSpecRowKey}
          unitStatus={doc?.unit_status ?? null}
          onSelectModule={(rk) => { setActiveModuleKey(rk); setActiveSpecRowKey(null) }}
          onSelectSpec={(specKey, modKey) => {
            setActiveModuleKey(modKey)
            setActiveSpecRowKey(specKey)
          }}
        />

        <div className="flex-1 overflow-y-auto">
          {/* Source strip + BRD echo */}
          {readiness && (
            <SourceStrip
              projectId={projectId}
              readiness={{
                can_generate: readiness.can_generate,
                blocking_reason: readiness.blocking_reason,
                docs_all_ready: readiness.docs_all_ready,
                cb_ready: readiness.cb_ready,
                cb_status: readiness.cb_status,
                pending_doc_count: readiness.docs_pending_names.length,
                failed_doc_count: readiness.docs_failed_names.length,
                docs: [],
              }}
              cbStatus={readiness.cb_status ?? undefined}
              brdStatus={readiness.brd_status ?? undefined}
              brdCounts={
                readiness.brd_summary
                  ? {
                      brs: readiness.brd_summary.br_count,
                      objectives: readiness.brd_summary.objective_count,
                      risks: readiness.brd_summary.risk_count,
                      kpis: readiness.brd_summary.kpi_count,
                      stakeholders: readiness.brd_summary.stakeholder_count,
                    }
                  : undefined
              }
            />
          )}
          <FrsBrdEchoStrip summary={readiness?.brd_summary ?? null} />

          {/* Active surface: spec panel (Stage B) takes priority, else module panel (Stage A) */}
          <div className="px-4 py-4 pb-32">
            {activeSpec ? (
              <FrsSpecPanel
                projectId={projectId}
                spec={activeSpec.spec}
                module={activeSpec.module}
                onMutate={() => mutate()}
                onBack={() => setActiveSpecRowKey(null)}
              />
            ) : activeModule ? (
              <FrsModulePanel
                projectId={projectId}
                module={activeModule}
                allModules={modules}
                decisions={detail?.decisions ?? []}
                onMutate={() => mutate()}
                onOpenDecision={setOpenDecision}
                onNavigateModule={(rowKey) => setActiveModuleKey(rowKey)}
                onRegenerateModule={handleRegenerateModule}
                onToggleLock={handleToggleLock}
                onDeleteStub={handleDeleteStub}
              />
            ) : (
              <div className="mx-auto max-w-md text-center py-16">
                <p className="text-sm text-[var(--text-tertiary)]">
                  Select a module from the rail to view its contents.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Findings drawer (Stage-B-aware: locks rows + flips status='validated' when clean) */}
      <FrsFindingsDrawer
        projectId={projectId}
        open={findingsOpen}
        findings={findings}
        onClose={() => setFindingsOpen(false)}
        onRefresh={async () => {
          const r = await api.frs.findings(projectId)
          setFindings(r)
        }}
        onValidated={(r) => {
          mutate()
          setBannerDismissed(false)
          if (r.stage_b_validated) {
            toast.success(`FRS validated — ${r.locked_row_count ?? 0} rows locked`)
          }
        }}
        onJumpToRow={(rowKey) => {
          // Spec-level row_key like M001-FRS001 → navigate to that spec
          const specMatch = /^([A-Z]\d+-FRS\d+)/.exec(rowKey)
          if (specMatch) {
            for (const m of modules) {
              const sp = m.backlog.find((s) => s.row_key === specMatch[1])
              if (sp) {
                setActiveModuleKey(m.row_key)
                setActiveSpecRowKey(sp.row_key)
                setFindingsOpen(false)
                return
              }
            }
          }
          // Module-level row_key → just switch modules
          const mod = modules.find((m) => m.row_key === rowKey)
          if (mod) {
            setActiveModuleKey(mod.row_key)
            setActiveSpecRowKey(null)
            setFindingsOpen(false)
            return
          }
          // Otherwise look up which module owns the row
          for (const m of modules) {
            if (m.actors.some((a) => a.row_key === rowKey)
              || m.responsibilities.some((r) => r.row_key === rowKey)
              || m.interfaces.some((i) => i.row_key === rowKey)
              || m.data_entities.some((e) => e.row_key === rowKey)
              || m.backlog.some((s) => s.row_key === rowKey)
              || m.decisions.some((d) => d.row_key === rowKey)) {
              setActiveModuleKey(m.row_key)
              setFindingsOpen(false)
              return
            }
          }
        }}
      />

      {/* Coverage galaxy modal */}
      <FrsCoverageGalaxy
        projectId={projectId}
        open={coverageOpen}
        onClose={() => setCoverageOpen(false)}
        onSelectSpec={(specRowKey) => {
          for (const m of modules) {
            if (m.backlog.some((s) => s.row_key === specRowKey)) {
              setActiveModuleKey(m.row_key)
              setActiveSpecRowKey(specRowKey)
              break
            }
          }
          setCoverageOpen(false)
        }}
      />

      {/* Decision prompt modal */}
      {openDecision && (
        <FrsModuleDecisionPrompt
          projectId={projectId}
          decision={openDecision}
          onClose={() => setOpenDecision(null)}
          onResolved={() => {
            mutate()
            setOpenDecision(null)
          }}
        />
      )}

      {/* Continue to Stage 2 banner */}
      <FrsContinueStageBBanner
        moduleCount={moduleCount}
        stubCount={stubCount}
        brCount={coveredBrs.size}
        open={showContinueBanner}
        onContinue={handleContinueStageB}
        onDismiss={() => setBannerDismissed(true)}
      />
    </div>
  )
}

// ── Header ──────────────────────────────────────────────────────────────────

function Header({
  projectId, onBack, status, stageAApproved, onCheckValidate, checkBusy, showActions,
  onCoverage,
}: {
  projectId: string
  onBack: () => void
  status: 'in_interview' | 'generating' | 'validated' | null
  stageAApproved: boolean
  onCheckValidate: () => void
  checkBusy: boolean
  showActions: boolean
  onCoverage?: () => void
}) {
  const [restarting, setRestarting] = useState(false)

  async function handleRestart() {
    if (!confirm(
      'Restart FRS Modularization?\n\n' +
      'This will:\n' +
      '  • Stop any in-progress generation\n' +
      '  • Return to the empty state\n' +
      '  • Preserve existing modules (use row delete to remove individually)\n\n' +
      'Continue?'
    )) return
    setRestarting(true)
    try {
      await api.frs.resetGenerating(projectId)
      toast.success('Reset — enter a new brief or pick up where you left off')
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Reset failed')
    } finally {
      setRestarting(false)
    }
  }

  return (
    <div className="shrink-0 h-12 flex items-center gap-3 border-b border-[var(--border-default)] bg-[var(--bg-surface)] px-4 z-10">
      <button
        onClick={onBack}
        className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] transition-colors"
      >
        <ArrowLeft size={14} /> Back
      </button>
      <span className="text-sm font-semibold text-[var(--text-primary)] hidden sm:block">
        Functional Specifications
      </span>
      <StatusBadge status={status} stageAApproved={stageAApproved} />
      <div className="flex-1" />
      {/* Restart button — always visible so the user can recover from anywhere */}
      <button
        onClick={handleRestart}
        disabled={restarting}
        title="Restart Stage 1 (preserves existing modules; locked rows verbatim)"
        className={cn(
          'inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs transition-colors',
          'border-[var(--border-default)] bg-[var(--bg-surface)] text-[var(--text-secondary)]',
          'hover:bg-[var(--bg-elevated)] disabled:opacity-50',
        )}
      >
        {restarting ? (
          <Loader2 size={13} className="animate-spin" />
        ) : (
          <RotateCcw size={13} />
        )}
        {restarting ? 'Resetting…' : 'Restart'}
      </button>
      {showActions && onCoverage && (
        <button
          onClick={onCoverage}
          title="BR → FRS coverage map"
          className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] px-2.5 py-1.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] transition-colors"
        >
          <Sparkles size={13} />
          Coverage
        </button>
      )}
      {showActions && <FrsExportMenu projectId={projectId} />}
      {showActions && (
        <button
          onClick={onCheckValidate}
          disabled={checkBusy}
          className={cn(
            'inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs transition-colors',
            'border-[var(--border-default)] bg-[var(--bg-surface)] text-[var(--text-secondary)]',
            'hover:bg-[var(--bg-elevated)] disabled:opacity-50',
          )}
        >
          {checkBusy ? (
            <Loader2 size={13} className="animate-spin" />
          ) : (
            <CheckCircle2 size={13} />
          )}
          Check &amp; Validate
        </button>
      )}
    </div>
  )
}

// ── Stalled generation banner (shown when status=generating but no progress) ─

function StalledGenerationBanner({
  projectId, onReset,
}: { projectId: string; onReset: () => void }) {
  const [resetting, setResetting] = useState(false)

  async function handleReset() {
    setResetting(true)
    try {
      await api.frs.resetGenerating(projectId)
      toast.success('Cleared stuck state — you can start fresh')
      onReset()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Reset failed')
    } finally {
      setResetting(false)
    }
  }

  return (
    <div className="mx-auto max-w-3xl mt-4 px-6">
      <div className="rounded-xl border border-amber-200 bg-amber-50/70 px-4 py-3 flex items-start gap-3">
        <AlertTriangle size={16} className="text-amber-600 shrink-0 mt-0.5" />
        <div className="flex-1">
          <p className="text-sm font-semibold text-amber-900">
            A previous run appears stalled
          </p>
          <p className="text-xs text-amber-700 mt-0.5 leading-relaxed">
            The FRS document is in the <code className="font-mono">generating</code> state but
            no progress has been recorded. This usually means the Celery worker died, or the
            previous run was aborted. Click reset, then enter a fresh brief below.
          </p>
        </div>
        <button
          onClick={handleReset}
          disabled={resetting}
          className="shrink-0 inline-flex items-center gap-1.5 rounded-lg border border-amber-300 bg-white px-3 py-1.5 text-xs font-semibold text-amber-700 hover:bg-amber-100 disabled:opacity-50 transition-colors"
        >
          {resetting ? (
            <Loader2 size={12} className="animate-spin" />
          ) : (
            <RotateCcw size={12} />
          )}
          {resetting ? 'Resetting…' : 'Clear stuck state'}
        </button>
      </div>
    </div>
  )
}

// ── Status badge ────────────────────────────────────────────────────────────

function StatusBadge({
  status, stageAApproved,
}: { status: 'in_interview' | 'generating' | 'validated' | null; stageAApproved: boolean }) {
  if (!status) return null
  if (status === 'generating') {
    return (
      <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold bg-blue-100 text-blue-700 border border-blue-200">
        <Loader2 size={9} className="animate-spin" />
        {stageAApproved ? 'Designing…' : 'Modularizing…'}
      </span>
    )
  }
  if (status === 'validated') {
    return (
      <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold bg-emerald-100 text-emerald-700 border border-emerald-200">
        <CheckCircle2 size={9} /> Validated
      </span>
    )
  }
  if (stageAApproved) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
        <CheckCircle2 size={9} /> Stage 1 approved · Stage 2 ready
      </span>
    )
  }
  return (
    <span className="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold bg-amber-100 text-amber-700 border border-amber-200">
      Draft · Stage 1
    </span>
  )
}
