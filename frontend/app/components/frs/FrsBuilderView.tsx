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
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import useSWR from 'swr'
import {
  AlertTriangle, ArrowLeft, CheckCircle2, Loader2, RotateCcw, Sparkles,
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
import { FrsStageActionBar } from './FrsStageActionBar'
import { FrsModuleGeneratingOverlay } from './FrsModuleGeneratingOverlay'
import { FrsGenerationBanner } from './FrsGenerationBanner'
import { FrsBrdEchoStrip } from './FrsBrdEchoStrip'
import { SourceStrip } from '@/app/components/brd/SourceStrip'

interface Props {
  projectId: string
  onBack: () => void
}

export function FrsBuilderView({ projectId, onBack }: Props) {
  const { readiness } = useFrsReadiness(projectId)
  // True while the user has optimistically triggered regens that the poll hasn't
  // yet confirmed/completed — keeps SWR polling through the optimistic gap.
  const pendingPollRef = useRef(false)
  const { data: detail, mutate, isLoading } = useSWR(
    `frs-detail-${projectId}`,
    () => api.frs.get(projectId),
    {
      revalidateOnFocus: false,
      refreshInterval: (data) => {
        const status = data?.document?.status
        if (status === 'generating') return 1500
        if (data?.document?.unit_status?.['_current_unit']) return 1500
        if (pendingPollRef.current) return 1500
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
  const [stageBMode, setStageBMode] = useState<'parallel' | 'sequential' | null>(null)
  const [seqPaused, setSeqPaused] = useState(false)
  const seqDispatchedKey = useRef<string | null>(null)
  // Whether the optional full "watch generation" overlay is open (user choice).
  const [vizOpen, setVizOpen] = useState(false)
  // Modules the user optimistically triggered (single regens). Bridges the gap
  // between click and the poll confirming the run started, then completed.
  const [pendingRegens, setPendingRegens] = useState<Set<string>>(new Set())
  const confirmedRunning = useRef<Set<string>>(new Set())
  const regenTriggeredAt = useRef<Map<string, number>>(new Map())
  // Spec-level optimistic regens (single-spec Regenerate in the spec panel).
  const [pendingSpecRegens, setPendingSpecRegens] = useState<Set<string>>(new Set())
  const specConfirmedWriting = useRef<Set<string>>(new Set())
  const specRegenVersion = useRef<Map<string, number>>(new Map())
  const specRegenAt = useRef<Map<string, number>>(new Map())

  // Auto-select first module when modules first appear
  useEffect(() => {
    if (!activeModuleKey && detail?.modules && detail.modules.length > 0) {
      setActiveModuleKey(detail.modules[0].row_key)
    }
  }, [activeModuleKey, detail?.modules])

  // Sequential mode: detect when the dispatched module finishes, then pause
  useEffect(() => {
    if (stageBMode !== 'sequential' || seqPaused || !seqDispatchedKey.current) return
    const key = seqDispatchedKey.current
    const us = detail?.document?.unit_status
    const currentUnit = us?.['_current_unit'] as string | undefined
    const modProgress = us?.[`design_mod_${key}`] as { completeness?: number } | undefined
    if (!currentUnit && (modProgress?.completeness ?? 0) > 0) {
      setSeqPaused(true)
    }
  }, [detail?.document?.unit_status, stageBMode, seqPaused])

  // Reconcile optimistic regens with the polled unit_status: confirm started
  // (via _current_unit), then mark done; stale-guard a worker that never picks up.
  useEffect(() => {
    if (pendingRegens.size === 0) return
    const cu = detail?.document?.unit_status?.['_current_unit'] as string | undefined
    const next = new Set(pendingRegens)
    let changed = false
    for (const key of Array.from(pendingRegens)) {
      const unitKey = `design_mod_${key}`
      if (cu === unitKey) {
        confirmedRunning.current.add(key)
      } else if (confirmedRunning.current.has(key)) {
        confirmedRunning.current.delete(key)
        regenTriggeredAt.current.delete(key)
        next.delete(key); changed = true
      } else {
        const t = regenTriggeredAt.current.get(key) ?? 0
        if (t && Date.now() - t > 90_000) {
          regenTriggeredAt.current.delete(key)
          next.delete(key); changed = true
          toast.error(`Generation didn't start for ${key} — is the worker running?`)
        }
      }
    }
    if (changed) setPendingRegens(next)
  }, [detail?.document?.unit_status, pendingRegens])

  // Reconcile optimistic SPEC regens: confirm started (current_spec_key), then
  // mark done when the module's current spec moves on or the spec's version bumps.
  useEffect(() => {
    if (pendingSpecRegens.size === 0) return
    const us = detail?.document?.unit_status
    const mods = detail?.modules ?? []
    const next = new Set(pendingSpecRegens)
    let changed = false
    for (const sk of Array.from(pendingSpecRegens)) {
      let stub: { version?: number } | undefined
      let modKey: string | undefined
      for (const m of mods) {
        const s = m.backlog?.find((x) => x.row_key === sk)
        if (s) { stub = s; modKey = m.row_key; break }
      }
      const mu = modKey ? (us?.[`design_mod_${modKey}`] as { current_spec_key?: string } | undefined) : undefined
      if (mu?.current_spec_key === sk) {
        specConfirmedWriting.current.add(sk)
      } else if (specConfirmedWriting.current.has(sk)) {
        specConfirmedWriting.current.delete(sk); specRegenAt.current.delete(sk); specRegenVersion.current.delete(sk)
        next.delete(sk); changed = true
      } else {
        const startV = specRegenVersion.current.get(sk)
        if (stub && startV != null && (stub.version ?? 0) > startV) {
          specRegenAt.current.delete(sk); specRegenVersion.current.delete(sk)
          next.delete(sk); changed = true
        } else {
          const t = specRegenAt.current.get(sk) ?? 0
          if (t && Date.now() - t > 120_000) {
            specRegenAt.current.delete(sk); specRegenVersion.current.delete(sk)
            next.delete(sk); changed = true
            toast.error(`Regeneration didn't start for ${sk} — is the worker running?`)
          }
        }
      }
    }
    if (changed) setPendingSpecRegens(next)
  }, [detail?.document?.unit_status, detail?.modules, pendingSpecRegens])

  // Keep the SWR poll alive through the optimistic gap
  useEffect(() => {
    pendingPollRef.current = pendingRegens.size > 0 || pendingSpecRegens.size > 0
  }, [pendingRegens, pendingSpecRegens])

  // Snapshot of "is anything actually generating right now" for the self-heal.
  const activityRef = useRef<{ active: boolean }>({ active: false })
  useEffect(() => {
    activityRef.current.active = Boolean(
      detail?.document?.unit_status?.['_current_unit'] ||
      pendingRegens.size > 0 || pendingSpecRegens.size > 0,
    )
  }, [detail?.document?.unit_status, pendingRegens, pendingSpecRegens])

  // Self-heal a stuck 'generating' status: if the doc says generating but no
  // module/spec is in flight for several seconds (worker died, broker was down,
  // or a no-op design-all), clear it so the UI doesn't show "Designing" forever.
  const healAttempted = useRef(false)
  const docStatus = detail?.document?.status ?? null
  useEffect(() => {
    if (docStatus !== 'generating') { healAttempted.current = false; return }
    let idleTicks = 0
    const id = setInterval(() => {
      if (activityRef.current.active) { idleTicks = 0; return }
      idleTicks += 1
      if (idleTicks >= 2 && !healAttempted.current) {   // ~6s with no activity
        healAttempted.current = true
        api.frs.resetGenerating(projectId).then(() => mutate()).catch(() => {})
      }
    }, 3000)
    return () => clearInterval(id)
  }, [docStatus, projectId, mutate])

  // Auto-close the watch overlay when a parallel bulk run finishes (status flips
  // back to in_interview and nothing is in flight). Sequential mode stays open
  // for its pause card.
  useEffect(() => {
    if (!vizOpen || stageBMode === 'sequential') return
    const st = detail?.document?.status
    const cu = detail?.document?.unit_status?.['_current_unit']
    if (st !== 'generating' && !cu && pendingRegens.size === 0 && stageBMode === 'parallel') {
      setVizOpen(false)
      setStageBMode(null)
    }
  }, [detail?.document?.status, detail?.document?.unit_status, vizOpen, stageBMode, pendingRegens])

  // ── Derived ─────────────────────────────────────────────────────────────
  const doc = detail?.document ?? null
  const modules = useMemo(() => detail?.modules ?? [], [detail?.modules])
  const status = doc?.status ?? null
  const modularizeStatus = doc?.unit_status?.['modularize'] as { completeness?: number; confidence?: string } | undefined
  const stageAApproved = Boolean(doc?.unit_status?.['_stage_a_approved'])
  const bulkActive = status === 'generating' && stageAApproved
  const activeModule = modules.find((m) => m.row_key === activeModuleKey) ?? null

  // Per-module generation state — single source of truth for "is it designing".
  // "done" means every backlog stub is actually designed (completeness > 0), not
  // merely that the module's design loop finished (which can leave specs missing).
  const moduleGenState = useCallback(
    (key: string): 'done' | 'running' | 'partial' | 'queued' | 'idle' => {
      const m = modules.find((mm) => mm.row_key === key)
      const stubs = m?.backlog ?? []
      const total = stubs.length
      const designed = stubs.filter((s) => (s.completeness ?? 0) > 0).length
      const fullyDone = total > 0 && designed === total
      const isCurrentUnit = doc?.unit_status?.['_current_unit'] === `design_mod_${key}`
      if (pendingRegens.has(key) || isCurrentUnit) return 'running'
      if (fullyDone) return 'done'
      if (bulkActive) return 'queued'
      if (designed > 0) return 'partial'   // loop finished but some specs missing
      return 'idle'
    },
    [doc?.unit_status, pendingRegens, bulkActive, modules],
  )

  // Per-SPEC state — drives the "Now writing" view and the spec-panel banner.
  const specGenState = useCallback(
    (moduleKey: string, stub: { row_key: string; completeness?: number }):
      'done' | 'writing' | 'queued' | 'incomplete' | 'pending' => {
      const mu = doc?.unit_status?.[`design_mod_${moduleKey}`] as
        | { current_spec_key?: string } | undefined
      if (pendingSpecRegens.has(stub.row_key) || mu?.current_spec_key === stub.row_key) {
        return 'writing'
      }
      if ((stub.completeness ?? 0) > 0) return 'done'
      const ms = moduleGenState(moduleKey)
      if (ms === 'running' || ms === 'queued') return 'queued'
      if (ms === 'partial') return 'incomplete'
      return 'pending'
    },
    [doc?.unit_status, pendingSpecRegens, moduleGenState],
  )
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

  /** Optimistically mark a module as regenerating: overlay + rail spinner mount
   *  instantly; the run is fired without blocking the UI. pendingRegens stays
   *  set (bridging the Celery-pickup gap) until the reconcile effect clears it. */
  function triggerModuleRegen(key: string) {
    setPendingRegens(prev => new Set(prev).add(key))
    regenTriggeredAt.current.set(key, Date.now())
    pendingPollRef.current = true
    api.frs.designModule(projectId, key)
      .then(() => mutate())
      .catch((e) => {
        setPendingRegens(prev => { const n = new Set(prev); n.delete(key); return n })
        regenTriggeredAt.current.delete(key)
        toast.error(e instanceof Error ? e.message : 'Regeneration failed')
      })
  }

  function handleRegenerateModule(moduleRowKey?: string) {
    // Guard: onClick handlers pass a MouseEvent as the first arg — ignore it
    const key = (typeof moduleRowKey === 'string' ? moduleRowKey : null) ?? activeModuleKey
    if (!key) return
    toast.message(`Designing ${key}…`, { description: 'Specs appear as they complete.' })
    triggerModuleRegen(key)
  }

  /** Optimistic single-spec regenerate. The spec panel + "Now writing" view
   *  show progress instantly; pendingSpecRegens clears when the run completes. */
  function handleRegenerateSpec(specRowKey: string, moduleRowKey: string, scope: 'full' | 'ui_only' = 'full') {
    let v = 0
    for (const m of modules) {
      const s = m.backlog?.find((x) => x.row_key === specRowKey)
      if (s) { v = s.version ?? 0; break }
    }
    setPendingSpecRegens(prev => new Set(prev).add(specRowKey))
    specRegenVersion.current.set(specRowKey, v)
    specRegenAt.current.set(specRowKey, Date.now())
    pendingPollRef.current = true
    toast.message(`Re-authoring ${specRowKey}…`, { description: 'Sections update when the model finishes.' })
    api.frs.regenerateSpec(projectId, specRowKey, scope)
      .then(() => mutate())
      .catch((e) => {
        setPendingSpecRegens(prev => { const n = new Set(prev); n.delete(specRowKey); return n })
        specRegenAt.current.delete(specRowKey); specRegenVersion.current.delete(specRowKey)
        toast.error(e instanceof Error ? e.message : 'Regenerate failed')
      })
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

  async function handleDesignAll(sequential: boolean) {
    if (sequential) {
      const firstUndesigned = modules.find(
        m => !((doc?.unit_status?.[`design_mod_${m.row_key}`] as { completeness?: number } | undefined)?.completeness),
      )
      if (!firstUndesigned) return
      setStageBMode('sequential')
      setSeqPaused(false)
      setVizOpen(true)
      seqDispatchedKey.current = firstUndesigned.row_key
      triggerModuleRegen(firstUndesigned.row_key)
    } else {
      // Bulk parallel — open the "watch" overlay; the run sets status='generating'
      // so the ambient banner shows too once the overlay is dismissed.
      setStageBMode('parallel')
      setVizOpen(true)
      try {
        await api.frs.designAllModules(projectId, true)
        await mutate()
      } catch (e) {
        toast.error(e instanceof Error ? e.message : 'Failed to start generation')
        setStageBMode(null)
        setVizOpen(false)
      }
    }
  }

  function handleDesignNext() {
    const nextUndesigned = modules.find(
      m => !((doc?.unit_status?.[`design_mod_${m.row_key}`] as { completeness?: number } | undefined)?.completeness),
    )
    if (!nextUndesigned) {
      setStageBMode(null)
      setSeqPaused(false)
      return
    }
    setSeqPaused(false)
    seqDispatchedKey.current = nextUndesigned.row_key
    triggerModuleRegen(nextUndesigned.row_key)
  }

  async function handleDesignAllRemaining() {
    setStageBMode('parallel')
    setSeqPaused(false)
    try {
      await api.frs.designAllModules(projectId, true)
      await mutate()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to start generation')
      setStageBMode(null)
    }
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

  // S3 — Stage A first-run theater. Full-screen ONLY while there is genuinely no
  // builder to show yet (modularization producing the very first modules). Every
  // Stage B run is ambient (banner + overlays) and never blocks the builder.
  const hasModularizeProgress = Boolean(
    doc?.unit_status?.['_current_unit'] === 'modularize' ||
    (modularizeStatus?.completeness && modularizeStatus.completeness > 0),
  )
  if (status === 'generating' && !stageAApproved && modules.length === 0 && hasModularizeProgress) {
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
          onRegenModule={handleRegenerateModule}
          genStateOf={moduleGenState}
        />

        <div className="flex-1 overflow-y-auto">
          {/* Ambient generation banner — non-blocking, opens the full viz on demand */}
          <FrsGenerationBanner
            modules={modules}
            unitStatus={doc?.unit_status ?? null}
            bulkActive={bulkActive}
            pendingCount={pendingRegens.size}
            onOpenDetails={() => setVizOpen(true)}
          />

          {/* Stage B action bar — inline, visible while specs are pending and idle */}
          {!bulkActive && pendingRegens.size === 0 && (
            <FrsStageActionBar
              projectId={projectId}
              modules={modules}
              unitStatus={doc?.unit_status ?? null}
              stageAApproved={stageAApproved}
              docStatus={status}
              onDesignAll={handleDesignAll}
            />
          )}

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
                onRegenerate={(scope) => handleRegenerateSpec(activeSpec.spec.row_key, activeSpec.module.row_key, scope)}
                regenerating={specGenState(activeSpec.module.row_key, activeSpec.spec) === 'writing'}
              />
            ) : activeModule ? (() => {
              const modDesigning = moduleGenState(activeModule.row_key) === 'running'
              const modProgress =
                (doc?.unit_status?.[`design_mod_${activeModule.row_key}`] as
                  Record<string, unknown> | undefined) ?? {}
              return modDesigning ? (
                <FrsModuleGeneratingOverlay
                  module={activeModule}
                  progress={modProgress}
                />
              ) : (
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
              )
            })() : (
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

      {/* Optional full "watch generation" overlay — opened on demand, dismissible.
          Generation keeps running ambiently when minimized. */}
      {vizOpen && (
        <div className="fixed inset-0 z-50 bg-[var(--bg-base)]">
          <FrsTwoPhaseGenerationViz
            projectId={projectId}
            modules={modules}
            unitStatus={doc?.unit_status}
            brCount={coveredBrs.size}
            bulkActive={bulkActive}
            specStateOf={specGenState}
            onComplete={() => { setVizOpen(false); setStageBMode(null); mutate() }}
            onCancel={() => { setVizOpen(false); setStageBMode(null); setSeqPaused(false); mutate() }}
            onMinimize={() => setVizOpen(false)}
            onSelectSpec={(specRowKey, moduleRowKey) => {
              setActiveModuleKey(moduleRowKey)
              setActiveSpecRowKey(specRowKey)
              setVizOpen(false)
            }}
            sequential={stageBMode === 'sequential'}
            pausedAfterModule={seqPaused ? (seqDispatchedKey.current ?? null) : null}
            onReviewAndContinue={() => { setVizOpen(false); setStageBMode(null); setSeqPaused(false); mutate() }}
            onDesignNext={handleDesignNext}
            onDesignAllRemaining={handleDesignAllRemaining}
          />
        </div>
      )}
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
