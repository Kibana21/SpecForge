'use client'
/**
 * Test Cases Builder — Module → Spec → Cases workspace.
 *
 * State machine: locked (FRS not validated) → ready (no suites) → generating
 * (theater) → authored (three-pane builder) → validated. Header always present.
 */
import { useEffect, useMemo, useState } from 'react'
import useSWR from 'swr'
import {
  ArrowLeft, CheckCircle2, ChevronDown, ChevronRight, Loader2,
  Lock, Pencil, Plus, RotateCcw, Sparkles, Trash2, Unlock, Network, Target, RefreshCw, Wrench, ClipboardList,
  Clock, AlertTriangle,
} from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'
import { Button } from '@/app/components/ui/button'
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem,
} from '@/app/components/ui/dropdown-menu'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/app/components/ui/dialog'
import {
  TC_TYPE_STYLES, TC_PRIORITY_STYLES, coverageColor,
} from '@/lib/testcases-manifest'
import type {
  TestCasesDetail, TestCasesReadiness, TestCasesCoverage,
  TestPlanRow, TestCaseRow, TestSuiteRow, TestCasesFinding,
} from '@/lib/types'
import { TestCasesTraceChip } from './TestCasesTraceChip'
import { TestCaseEditDialog } from './TestCaseEditDialog'
import { AddTestCaseDialog } from './AddTestCaseDialog'
import { TestCasesCoverageGalaxy } from './TestCasesCoverageGalaxy'
import { TestingOutcomesPanel } from './TestingOutcomesPanel'
import { TestCasesFindingsDrawer } from './TestCasesFindingsDrawer'

interface Props { projectId: string; onBack: () => void }

export function TestCasesBuilderView({ projectId, onBack }: Props) {
  const { data: readiness } = useSWR<TestCasesReadiness>(
    `tc-readiness-${projectId}`, () => api.testcases.readiness(projectId),
    { revalidateOnFocus: false },
  )
  const { data: detail, mutate, isLoading } = useSWR<TestCasesDetail>(
    `tc-detail-${projectId}`, () => api.testcases.get(projectId),
    {
      revalidateOnFocus: false,
      refreshInterval: (d) => (d?.document?.status === 'generating' ? 1500 : 0),
    },
  )

  const status = detail?.document?.status ?? null
  const suites = useMemo(() => detail?.suites ?? [], [detail])
  const generating = status === 'generating'
  // A "Fix automatically" (repair) run shows a dedicated, named progress screen
  // instead of the generic generation banner.
  const repairActive = generating && (detail?.document?.unit_status as any)?._repair?.active === true

  const [activeSpec, setActiveSpec] = useState<string | null>(null)
  const [showCoverage, setShowCoverage] = useState(false)
  const [showOutcomes, setShowOutcomes] = useState(false)
  const [showProgress, setShowProgress] = useState(false)
  const [busy, setBusy] = useState(false)
  // Blocking-finding count from the last Validate (drives the "Clean up & fix" CTA).
  const [valBlocking, setValBlocking] = useState(0)
  const [findings, setFindings] = useState<TestCasesFinding[] | null>(null)
  const [showFindings, setShowFindings] = useState(false)
  // When you click a finding, open its feature AND expand that exact test case.
  const [focusCaseKey, setFocusCaseKey] = useState<string | null>(null)
  // The repair screen is non-blocking: clicking any plan minimizes it so you can
  // browse while the fix runs; a slim banner lets you jump back to the progress.
  const [repairMinimized, setRepairMinimized] = useState(false)

  // Coverage drives the modals AND the live gap counts. Fetch once authored —
  // and also while generating IF a modal is open, so Coverage/Outcomes work
  // during a repair run instead of spinning on "Loading…".
  const { data: coverage, mutate: mutateCoverage } = useSWR<TestCasesCoverage>(
    (suites.length > 0 && (!generating || showCoverage || showOutcomes)) ? `tc-coverage-${projectId}` : null,
    () => api.testcases.coverage(projectId),
    { revalidateOnFocus: false },
  )

  // Uncovered-element count per spec + project total (from coverage).
  const gapsBySpec = useMemo(() => {
    const m: Record<string, number> = {}
    for (const mod of coverage?.modules ?? [])
      for (const sp of mod.specs)
        m[sp.spec_row_key] = sp.elements.filter(e => !(e.covered_by?.length)).length
    return m
  }, [coverage])
  const totalGaps = useMemo(() => Object.values(gapsBySpec).reduce((a, b) => a + b, 0), [gapsBySpec])

  // Live per-plan status from unit_status while generating: { 'TP-…': 'authoring'|'done'|'failed' }
  const genStatus = useMemo(() => {
    const us = detail?.document?.unit_status ?? {}
    const m: Record<string, string> = {}
    for (const [k, v] of Object.entries(us)) {
      if (!k.startsWith('_') && v && typeof v === 'object' && (v as any).status) m[k] = (v as any).status
    }
    return m
  }, [detail])

  const allPlans = useMemo(() => suites.flatMap(s => s.plans), [suites])
  const activePlan = useMemo(
    () => allPlans.find(p => p.spec_row_key === activeSpec) ?? allPlans[0] ?? null,
    [allPlans, activeSpec],
  )

  async function doGenerate() {
    setBusy(true)
    try { await api.testcases.generate(projectId); await mutate() }
    catch (e: any) { toast.error(e?.message || 'Generation failed') }
    finally { setBusy(false) }
  }
  async function doValidate() {
    setBusy(true)
    try {
      const res = await api.testcases.validate(projectId)
      setFindings(res.findings ?? [])
      if (res.ok) { toast.success(`Validated ✓ — ${res.locked_row_count ?? 0} rows locked`); setValBlocking(0) }
      else { setValBlocking(res.summary.blocking); setShowFindings(true) }
      await mutate()
    } catch (e: any) { toast.error(e?.message || 'Validation failed') }
    finally { setBusy(false) }
  }
  async function openFindings() {
    setShowFindings(true)
    try {
      const res = await api.testcases.findings(projectId)
      setFindings(res.findings ?? [])
      setValBlocking(res.summary.blocking ?? 0)
    } catch (e: any) { toast.error(e?.message || 'Could not load findings') }
  }
  async function doRepair() {
    setBusy(true)
    setRepairMinimized(false)  // show the progress screen first
    try {
      const res = await api.testcases.repair(projectId)
      const c = res.cleanup
      toast.success(
        `Cleaned ${c.cases_cleaned} case(s) (${c.refs_removed} dead refs) · re-authoring thin specs…`,
      )
      setValBlocking(0)
      await mutate(); await mutateCoverage()
    } catch (e: any) { toast.error(e?.message || 'Clean up & fix failed') }
    finally { setBusy(false) }
  }
  async function doReset() {
    await api.testcases.resetGenerating(projectId); await mutate()
  }
  async function doDesignAll(skipDesigned: boolean, moduleRowKey?: string) {
    setBusy(true)
    try {
      await api.testcases.designAllPlans(projectId, { skipDesigned, moduleRowKey })
      toast.success(
        moduleRowKey ? `Regenerating ${moduleRowKey}…`
          : skipDesigned ? 'Filling empty plans…' : 'Regenerating all test cases…',
      )
      await mutate()
    } catch (e: any) { toast.error(e?.message || 'Failed to start') }
    finally { setBusy(false) }
  }
  async function doRegenPlan(specRowKey: string) {
    setBusy(true)
    try {
      await api.testcases.regeneratePlan(projectId, specRowKey)
      toast.success(`Regenerating ${specRowKey}…`)
      await mutate()
    } catch (e: any) { toast.error(e?.message || 'Failed to start') }
    finally { setBusy(false) }
  }
  async function doGapFill(specRowKey?: string) {
    setBusy(true)
    try {
      await api.testcases.gapFill(projectId, specRowKey)
      toast.success(specRowKey ? `Filling gaps in ${specRowKey}…` : 'Filling all coverage gaps…')
      await mutate(); await mutateCoverage()
    } catch (e: any) { toast.error(e?.message || 'Failed to start') }
    finally { setBusy(false) }
  }

  // ── Locked: FRS not validated ───────────────────────────────────────────
  if (readiness && !readiness.frs_ready) {
    return (
      <div className="flex flex-col h-full">
        <Header onBack={onBack} status={null} />
        <div className="flex-1 grid place-items-center p-8">
          <div className="max-w-md text-center space-y-3">
            <Lock className="mx-auto text-[var(--text-tertiary)]" size={28} />
            <h3 className="text-lg font-semibold">Test cases are locked</h3>
            <p className="text-sm text-[var(--text-tertiary)]">
              Test cases unlock once the FRS is validated. FRS status:{' '}
              <span className="font-medium">{readiness.frs_status ?? 'not started'}</span>.
            </p>
          </div>
        </div>
      </div>
    )
  }

  // ── Ready / empty ─────────────────────────────────────────────────────────
  if (!isLoading && !generating && suites.length === 0) {
    return (
      <div className="flex flex-col h-full">
        <Header onBack={onBack} status={status} />
        <div className="flex-1 grid place-items-center p-8">
          <div className="max-w-lg text-center space-y-4">
            <Sparkles className="mx-auto text-[var(--accent)]" size={28} />
            <h3 className="text-xl font-semibold">Generate a traceable test suite</h3>
            <p className="text-sm text-[var(--text-tertiary)]">
              From your validated FRS{readiness ? ` — ${readiness.frs_module_count} modules · ${readiness.frs_spec_count} specs` : ''}.
              Produces a suite per module and a plan per spec with multi-level cases
              (functional · integration · e2e · negative · edge · responsive) and full BRD→FRS→Test traceability.
            </p>
            <Button onClick={doGenerate} disabled={busy || !readiness?.can_generate}>
              {busy ? <Loader2 className="animate-spin" size={14} /> : <Sparkles size={14} />}
              Generate test cases
            </Button>
            {readiness && !readiness.can_generate && (
              <p className="text-xs text-amber-600">{readiness.blocking_reason}</p>
            )}
          </div>
        </div>
      </div>
    )
  }

  // ── First-run theater: nothing generated yet → full-screen progress ───────
  if (generating && suites.length === 0) {
    return (
      <div className="flex flex-col h-full">
        <Header onBack={onBack} status={status} onReset={doReset} />
        <GenerationTheater unitStatus={detail?.document?.unit_status ?? {}} />
      </div>
    )
  }

  // ── Builder (also shown WHILE generating, with a slim banner on top) ──────
  return (
    <div className="flex flex-col h-full">
      <Header
        onBack={onBack} status={status}
        right={
          <div className="flex items-center gap-2">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm" disabled={busy || generating}
                  title={generating ? 'Generation in progress…' : undefined}>
                  {busy ? <Loader2 className="animate-spin" size={13} /> : <RefreshCw size={13} />} Regenerate
                  <ChevronDown size={12} className="ml-0.5 opacity-60" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-60">
                <DropdownMenuItem onClick={() => doDesignAll(true)}>
                  Fill empty plans
                  <span className="ml-auto text-[10px] text-[var(--text-tertiary)]">only 0-case</span>
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => doDesignAll(false)}>
                  Regenerate all plans
                  <span className="ml-auto text-[10px] text-[var(--text-tertiary)]">whole project</span>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
            {totalGaps > 0 && (
              <Button
                size="sm" onClick={() => doGapFill()} disabled={busy || generating}
                title="Author test cases only for the FRS elements that have no coverage yet (existing cases untouched)"
                className="bg-amber-500 text-white hover:bg-amber-600"
              >
                {busy ? <Loader2 className="animate-spin" size={13} /> : <Sparkles size={13} />} Fill {totalGaps} gap{totalGaps > 1 ? 's' : ''}
              </Button>
            )}
            <Button variant="outline" size="sm" onClick={() => setShowCoverage(true)}><Network size={13} /> Coverage</Button>
            <Button variant="outline" size="sm" onClick={() => setShowOutcomes(true)}><Target size={13} /> Outcomes</Button>
            <Button variant="outline" size="sm" onClick={openFindings} disabled={generating}>
              <ClipboardList size={13} /> Findings
              {valBlocking > 0 && (
                <span className="ml-1 rounded-full bg-red-100 px-1.5 text-[10px] font-semibold text-red-700">{valBlocking}</span>
              )}
            </Button>
            {valBlocking > 0 && !generating && (
              <Button
                size="sm" onClick={doRepair} disabled={busy}
                title="Strip dangling references that point at deleted FRS rows (no AI), then re-author only the specs that still fail validation. Locked & manual cases are preserved."
                className="bg-amber-500 text-white hover:bg-amber-600"
              >
                {busy ? <Loader2 className="animate-spin" size={13} /> : <Wrench size={13} />} Clean up & fix
              </Button>
            )}
            <Button size="sm" onClick={doValidate} disabled={busy || generating}
              title={generating ? 'Wait for generation to finish' : undefined}>
              {busy ? <Loader2 className="animate-spin" size={13} /> : <CheckCircle2 size={13} />} Validate
            </Button>
          </div>
        }
      />
      {generating && !repairActive && (
        <TestCasesGenerationBanner
          unitStatus={detail?.document?.unit_status ?? {}}
          onOpenDetails={() => setShowProgress(true)} onReset={doReset}
        />
      )}
      {repairActive && repairMinimized && (
        <RepairMiniBanner
          unitStatus={detail?.document?.unit_status ?? {}}
          onShow={() => setRepairMinimized(false)}
        />
      )}
      <div className="relative flex-1 flex min-h-0">
        <SuiteRail
          suites={suites} activeSpec={activePlan?.spec_row_key ?? null}
          onSelect={(s) => { setActiveSpec(s); if (repairActive) setRepairMinimized(true) }}
          busy={busy || generating} onRegenModule={(mk) => doDesignAll(false, mk)}
          genStatus={genStatus}
        />
        <div className="flex-1 min-w-0 overflow-y-auto">
          {repairActive && !repairMinimized ? (
            <RepairTheater unitStatus={detail?.document?.unit_status ?? {}} onReset={doReset} />
          ) : activePlan ? (
            <PlanPanel
              projectId={projectId} plan={activePlan}
              onChanged={() => mutate()}
              busy={busy || generating} onRegenPlan={() => doRegenPlan(activePlan.spec_row_key)}
              gapCount={gapsBySpec[activePlan.spec_row_key] ?? 0}
              onGapFill={() => doGapFill(activePlan.spec_row_key)}
              focusCaseKey={focusCaseKey} onFocused={() => setFocusCaseKey(null)}
            />
          ) : (
            <div className="grid place-items-center h-full text-sm text-[var(--text-tertiary)]">Select a plan</div>
          )}
        </div>
        {/* Docked findings panel — stays open while you click through findings. */}
        <TestCasesFindingsDrawer
          open={showFindings} onClose={() => setShowFindings(false)} findings={findings} detail={detail} busy={busy}
          onJump={(rk) => {
            const m = rk.match(/^TP-(.+?)-TC-\d+$/)
            const spec = m ? m[1] : rk.startsWith('TP-') ? rk.slice(3) : rk
            setActiveSpec(spec)
            setFocusCaseKey(m ? rk : null)  // only case-level keys point at a specific test
          }}
          onFix={!generating ? () => { setShowFindings(false); doRepair() } : undefined}
        />
      </div>

      <TestCasesCoverageGalaxy
        coverage={coverage ?? null} open={showCoverage} onClose={() => setShowCoverage(false)}
        onFillGaps={totalGaps > 0 && !generating ? () => { setShowCoverage(false); doGapFill() } : undefined}
      />
      <TestingOutcomesPanel
        coverage={coverage ?? null} open={showOutcomes} onClose={() => setShowOutcomes(false)}
        onFillGaps={totalGaps > 0 && !generating ? () => { setShowOutcomes(false); doGapFill() } : undefined}
      />
      <Dialog open={showProgress} onOpenChange={(o) => !o && setShowProgress(false)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader><DialogTitle>Generation progress</DialogTitle></DialogHeader>
          <ProgressCard unitStatus={detail?.document?.unit_status ?? {}} />
        </DialogContent>
      </Dialog>
    </div>
  )
}

// ── Header ──────────────────────────────────────────────────────────────────

function Header({ onBack, status, right, onReset }: {
  onBack: () => void; status: string | null; right?: React.ReactNode; onReset?: () => void
}) {
  return (
    <div className="shrink-0 flex items-center justify-between border-b border-[var(--border-default)] px-4 py-2.5 bg-[var(--bg-surface)]">
      <div className="flex items-center gap-3">
        <button onClick={onBack} className="text-[var(--text-tertiary)] hover:text-[var(--text-primary)]"><ArrowLeft size={16} /></button>
        <span className="font-semibold text-sm">Test Cases</span>
        {status === 'validated' && <span className="text-[10px] rounded px-1.5 py-0.5 bg-emerald-100 text-emerald-700 font-semibold">Validated ✓</span>}
        {status === 'generating' && <span className="text-[10px] rounded px-1.5 py-0.5 bg-blue-100 text-blue-700 font-semibold animate-pulse">Generating…</span>}
        {status === 'in_interview' && <span className="text-[10px] rounded px-1.5 py-0.5 bg-amber-100 text-amber-700 font-semibold">Draft</span>}
      </div>
      <div className="flex items-center gap-2">
        {onReset && <Button variant="outline" size="sm" onClick={onReset}><RotateCcw size={13} /> Reset</Button>}
        {right}
      </div>
    </div>
  )
}

// ── Generation theater ────────────────────────────────────────────────────

// ── Repair ("Fix automatically") progress screen — named, live, neat ─────────

type RepairItem = { key: string; spec: string; title: string; module: string; status: string; cases: number }

function RepairTheater({ unitStatus, onReset }: { unitStatus: Record<string, any>; onReset: () => void }) {
  const specs = (unitStatus['_repair_specs'] as RepairItem[]) || []
  const items: RepairItem[] = specs.map(s => ({
    ...s,
    status: (unitStatus[s.key]?.status as string) || 'pending',
    cases: (unitStatus[s.key]?.cases_authored as number) || 0,
  }))
  const working = items.filter(i => i.status === 'authoring')
  const pending = items.filter(i => i.status === 'pending')
  const done = items.filter(i => i.status === 'done')
  const failed = items.filter(i => i.status === 'failed')
  const total = items.length || ((unitStatus['_repair']?.total as number) ?? 0)
  const finished = done.length + failed.length
  const pct = total ? Math.round((finished / total) * 100) : 0
  const casesAuthored = done.reduce((a, i) => a + i.cases, 0)
  const starting = total === 0

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-6">
      {/* Hero */}
      <div className="flex items-start gap-3">
        <div className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-amber-100 text-amber-600">
          <Wrench size={20} />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">Fixing your tests</h2>
          <p className="text-sm text-[var(--text-secondary)]">
            Re-writing the tests that didn’t fully prove the result — richer steps, clear checks, proper links.
            This can take a few minutes and updates live; you don’t need to wait here.
          </p>
        </div>
      </div>

      {/* Overall progress */}
      <div className="rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-4 shadow-[var(--shadow-card)]">
        <div className="mb-1.5 flex items-baseline justify-between">
          <span className="text-sm font-medium text-[var(--text-primary)]">
            {starting ? 'Starting…' : `${finished} of ${total} features done`}
          </span>
          <span className="text-sm font-bold text-amber-600">{pct}%</span>
        </div>
        <div className="h-2.5 overflow-hidden rounded-full bg-[var(--bg-sunken)]">
          <div className="h-full bg-amber-500 transition-all duration-700" style={{ width: `${starting ? 6 : pct}%` }} />
        </div>
        <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
          <RepairStat icon={<Loader2 size={12} className="animate-spin" />} n={working.length} label="working now" cls="bg-amber-50 text-amber-700" />
          <RepairStat icon={<Clock size={12} />} n={pending.length} label="up next" cls="bg-[var(--bg-elevated)] text-[var(--text-secondary)]" />
          <RepairStat icon={<CheckCircle2 size={12} />} n={done.length} label="done" cls="bg-emerald-50 text-emerald-700" />
          {failed.length > 0 && <RepairStat icon={<AlertTriangle size={12} />} n={failed.length} label="need another pass" cls="bg-red-50 text-red-700" />}
          {casesAuthored > 0 && <span className="ml-auto self-center font-semibold text-[var(--text-secondary)]">{casesAuthored} cases written</span>}
        </div>
      </div>

      {working.length > 0 && (
        <RepairGroup title="Working on now" count={working.length}>
          {working.map(i => (
            <div key={i.key} className="flex items-center gap-3 rounded-lg border border-amber-300 bg-amber-50/70 px-3 py-2.5">
              <Loader2 size={16} className="shrink-0 animate-spin text-amber-600" />
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium text-[var(--text-primary)]">{i.title}</div>
                <div className="text-[11px] text-amber-700">Writing rich test cases…</div>
              </div>
            </div>
          ))}
        </RepairGroup>
      )}

      {pending.length > 0 && (
        <RepairGroup title="Up next" count={pending.length}>
          {pending.map((i, idx) => (
            <div key={i.key} className="flex items-center gap-3 rounded-lg border border-[var(--border-subtle)] px-3 py-2">
              <span className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-[var(--bg-elevated)] text-[10px] font-semibold text-[var(--text-tertiary)]">{idx + 1}</span>
              <div className="min-w-0 flex-1 truncate text-sm text-[var(--text-secondary)]">{i.title}</div>
              <span className="shrink-0 text-[11px] text-[var(--text-tertiary)]">waiting</span>
            </div>
          ))}
        </RepairGroup>
      )}

      {done.length > 0 && (
        <RepairGroup title="Done" count={done.length}>
          {done.map(i => (
            <div key={i.key} className="flex items-center gap-3 rounded-lg border border-emerald-200 bg-emerald-50/50 px-3 py-2">
              <CheckCircle2 size={15} className="shrink-0 text-emerald-600" />
              <div className="min-w-0 flex-1 truncate text-sm text-[var(--text-primary)]">{i.title}</div>
              <span className="shrink-0 rounded-full bg-white/80 px-2 py-0.5 text-[10px] font-medium text-emerald-700">{i.cases} cases</span>
            </div>
          ))}
        </RepairGroup>
      )}

      {failed.length > 0 && (
        <RepairGroup title="Need another pass" count={failed.length}>
          {failed.map(i => (
            <div key={i.key} className="flex items-center gap-3 rounded-lg border border-red-300 bg-red-50/60 px-3 py-2">
              <AlertTriangle size={15} className="shrink-0 text-red-600" />
              <div className="min-w-0 flex-1 truncate text-sm text-[var(--text-primary)]">{i.title}</div>
              <span className="shrink-0 text-[11px] text-red-700">retry from its feature</span>
            </div>
          ))}
        </RepairGroup>
      )}

      <button onClick={onReset} className="text-[11px] text-[var(--text-tertiary)] underline-offset-2 hover:underline">
        Taking too long? Stop the run
      </button>
    </div>
  )
}

// Slim strip shown when the repair screen is minimized (you've clicked into a
// plan). Keeps the live progress in view + a one-click jump back to the screen.
function RepairMiniBanner({ unitStatus, onShow }: { unitStatus: Record<string, any>; onShow: () => void }) {
  const specs = (unitStatus['_repair_specs'] as RepairItem[]) || []
  const done = specs.filter(s => unitStatus[s.key]?.status === 'done').length
  const working = specs.filter(s => unitStatus[s.key]?.status === 'authoring').length
  const total = specs.length || ((unitStatus['_repair']?.total as number) ?? 0)
  return (
    <div className="relative flex h-9 shrink-0 items-center gap-3 overflow-hidden border-b border-amber-300/40 bg-gradient-to-r from-amber-50 to-[var(--bg-surface)] px-4">
      <div className="absolute inset-y-0 left-0 w-0.5 bg-amber-500" />
      <Wrench size={13} className="shrink-0 text-amber-600" />
      <span className="shrink-0 text-xs font-semibold text-amber-700">Fixing your tests · {done}/{total || '…'}</span>
      {working > 0 && <span className="shrink-0 text-xs text-amber-700/80">· {working} working now</span>}
      <button onClick={onShow} className="ml-auto shrink-0 rounded-md border border-amber-300 bg-white px-2 py-0.5 text-xs font-medium text-amber-700 hover:bg-amber-50">
        View progress
      </button>
    </div>
  )
}

function RepairStat({ icon, n, label, cls }: { icon: React.ReactNode; n: number; label: string; cls: string }) {
  return (
    <span className={cn('inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-medium', cls)}>
      {icon} {n} {label}
    </span>
  )
}

function RepairGroup({ title, count, children }: { title: string; count: number; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <div className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">{title} · {count}</div>
      <div className="space-y-1.5">{children}</div>
    </div>
  )
}

function GenerationTheater({ unitStatus }: { unitStatus: Record<string, any> }) {
  return (
    <div className="flex-1 grid place-items-center p-8">
      <div className="w-full max-w-2xl rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] shadow-[var(--shadow-card)] p-6">
        <ProgressCard unitStatus={unitStatus} />
      </div>
    </div>
  )
}

function ProgressCard({ unitStatus }: { unitStatus: Record<string, any> }) {
  const current = unitStatus['_current_unit'] as string | undefined
  const modProgress = (unitStatus['_module_progress'] as Record<string, { specs_total: number; specs_done: number }>) || {}
  const mods = Object.entries(modProgress)
  const phase = mods.length === 0 || current === 'plan_journeys' ? 1 : 2

  // Per-plan entries: { status: 'authoring'|'done'|'failed', module, cases_authored }
  const planEntries = Object.entries(unitStatus).filter(([k]) => !k.startsWith('_')) as [string, any][]
  const inFlight = planEntries.filter(([, v]) => v?.status === 'authoring')
  const inFlightByMod: Record<string, number> = {}
  for (const [, v] of inFlight) inFlightByMod[v.module] = (inFlightByMod[v.module] || 0) + 1
  const inFlightSpecs = inFlight.map(([k]) => k.replace(/^TP-/, ''))

  const specsTotal = mods.reduce((a, [, p]) => a + (p.specs_total || 0), 0)
  const specsDone = mods.reduce((a, [, p]) => a + (p.specs_done || 0), 0)
  const overallPct = specsTotal ? Math.round((specsDone / specsTotal) * 100) : 0
  const casesAuthored = planEntries.reduce((a, [, v]) => a + (typeof v?.cases_authored === 'number' ? v.cases_authored : 0), 0)

  return (
      <div className="space-y-6">
        {/* Phase steps */}
        <div className="flex items-center gap-3">
          <span className={cn('flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold',
            phase === 1 ? 'bg-[var(--accent-subtle)] text-[var(--accent)]' : 'bg-emerald-50 text-emerald-700')}>
            {phase === 1 ? <Loader2 className="animate-spin" size={12} /> : <CheckCircle2 size={12} />} 1 · Plan journeys
          </span>
          <ChevronRight size={14} className="text-[var(--text-tertiary)]" />
          <span className={cn('flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold',
            phase === 2 ? 'bg-[var(--accent-subtle)] text-[var(--accent)]' : 'bg-[var(--bg-elevated)] text-[var(--text-tertiary)]')}>
            {phase === 2 ? <Loader2 className="animate-spin" size={12} /> : <span className="w-3" />} 2 · Author cases
          </span>
          <span className="ml-auto text-xs text-[var(--text-tertiary)]">Phase {phase}/2</span>
        </div>

        <div>
          <div className="flex items-baseline justify-between mb-1.5">
            <h3 className="text-lg font-semibold">
              {phase === 1 ? 'Planning test journeys…' : 'Authoring test cases…'}
            </h3>
            {specsTotal > 0 && (
              <span className="text-sm font-semibold text-[var(--accent)]">{specsDone}/{specsTotal} specs · {overallPct}%</span>
            )}
          </div>
          <div className="h-2 rounded-full bg-[var(--bg-sunken)] overflow-hidden">
            <div className="h-full bg-[var(--accent)] transition-all duration-500" style={{ width: `${phase === 1 ? 8 : overallPct}%` }} />
          </div>
          <p className="mt-2 text-xs text-[var(--text-tertiary)]">
            {phase === 1
              ? 'Mapping each FRS module to a user-journey test suite and a plan per spec…'
              : 'Authoring functional, integration, e2e, negative, edge & responsive cases per spec, with full traceability.'}
          </p>
        </div>

        {/* Per-module bars (all modules) — solid = done, striped pulse = in-flight */}
        {mods.length > 0 && (
          <div className="space-y-2.5 max-h-64 overflow-y-auto pr-1">
            {mods.map(([mk, p]) => {
              const total = p.specs_total || 1
              const donePct = Math.round((p.specs_done / total) * 100)
              const active = inFlightByMod[mk] || 0
              const activePct = Math.round((active / total) * 100)
              const dn = p.specs_done >= total
              return (
                <div key={mk} className="space-y-1">
                  <div className="flex justify-between text-[11px]">
                    <span className={cn('font-mono', dn ? 'text-emerald-600' : 'text-[var(--text-secondary)]')}>
                      {dn ? '✓ ' : ''}{mk}
                    </span>
                    <span className="text-[var(--text-tertiary)]">
                      {p.specs_done}/{p.specs_total}{active > 0 && <span className="text-[var(--accent)]"> · {active} authoring</span>}
                    </span>
                  </div>
                  <div className="h-1.5 rounded bg-[var(--bg-sunken)] overflow-hidden flex">
                    <div className={cn('h-full transition-all duration-500', dn ? 'bg-emerald-500' : 'bg-[var(--accent)]')} style={{ width: `${donePct}%` }} />
                    {active > 0 && (
                      <div className="h-full bg-[var(--accent)] opacity-40 animate-pulse" style={{ width: `${activePct}%` }} />
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}

        <div className="flex items-center justify-between border-t border-[var(--border-subtle)] pt-4 text-xs">
          <span className="text-[var(--text-tertiary)]">
            {inFlight.length > 0
              ? <>Authoring <span className="font-semibold text-[var(--accent)]">{inFlight.length}</span> spec{inFlight.length > 1 ? 's' : ''} in parallel
                  {inFlightSpecs.length > 0 && <span className="font-mono"> · {inFlightSpecs.slice(0, 3).join(', ')}{inFlightSpecs.length > 3 ? '…' : ''}</span>}</>
              : phase === 1 ? 'Planning…' : 'Preparing next batch…'}
          </span>
          {casesAuthored > 0 && <span className="font-semibold text-[var(--text-secondary)]">{casesAuthored} cases authored</span>}
        </div>
      </div>
  )
}

// ── Slim generation banner (non-blocking, single clean strip; mirrors FRS) ───

function TestCasesGenerationBanner({ unitStatus, onOpenDetails, onReset }: {
  unitStatus: Record<string, any>; onOpenDetails: () => void; onReset: () => void
}) {
  const modProgress = (unitStatus['_module_progress'] as Record<string, { specs_total: number; specs_done: number }>) || {}
  const mods = Object.entries(modProgress)
  const planEntries = Object.entries(unitStatus).filter(([k]) => !k.startsWith('_')) as [string, any][]
  const inFlight = planEntries.filter(([, v]) => v?.status === 'authoring').length
  const specsTotal = mods.reduce((a, [, p]) => a + (p.specs_total || 0), 0)
  const specsDone = mods.reduce((a, [, p]) => a + (p.specs_done || 0), 0)
  const pct = specsTotal ? Math.round((specsDone / specsTotal) * 100) : 0
  const cases = planEntries.reduce((a, [, v]) => a + (typeof v?.cases_authored === 'number' ? v.cases_authored : 0), 0)

  return (
    <div className="relative shrink-0 flex items-center gap-3 h-9 px-4 border-b border-[var(--accent)]/30 bg-gradient-to-r from-[var(--accent-subtle)] to-[var(--bg-surface)] overflow-hidden">
      <div className="absolute left-0 top-0 bottom-0 w-0.5 bg-[var(--accent)]" />
      <Loader2 size={13} className="shrink-0 animate-spin text-[var(--accent)]" />
      <span className="shrink-0 text-xs font-semibold text-[var(--accent)]">
        Authoring {specsDone}/{specsTotal} specs
      </span>
      {inFlight > 0 && (
        <>
          <span className="text-[var(--accent)]/40">·</span>
          <span className="shrink-0 text-xs text-[var(--accent)]">{inFlight} in parallel</span>
        </>
      )}
      <div className="hidden sm:flex flex-1 min-w-0 items-center gap-2">
        <div className="flex-1 h-1.5 rounded-full overflow-hidden bg-[var(--accent-subtle)]">
          <div className="h-full rounded-full bg-[var(--accent)] transition-all duration-500" style={{ width: `${pct}%` }} />
        </div>
        <span className="shrink-0 text-[10px] font-medium tabular-nums text-[var(--accent)]">{pct}%</span>
      </div>
      {cases > 0 && <span className="shrink-0 text-[10px] text-[var(--text-tertiary)]">{cases} cases</span>}
      <button
        onClick={onOpenDetails}
        className="shrink-0 inline-flex items-center gap-0.5 rounded-md px-2 py-1 text-xs font-medium text-[var(--accent)] hover:bg-[var(--accent-subtle)] transition-colors"
      >
        View details <ChevronRight size={12} />
      </button>
      <button onClick={onReset} title="Reset (recovery)" className="shrink-0 text-[var(--text-tertiary)] hover:text-[var(--text-primary)]">
        <RotateCcw size={12} />
      </button>
    </div>
  )
}

// ── Suite rail ─────────────────────────────────────────────────────────────

function SuiteRail({ suites, activeSpec, onSelect, busy, onRegenModule, genStatus }: {
  suites: TestSuiteRow[]; activeSpec: string | null; onSelect: (spec: string) => void
  busy: boolean; onRegenModule: (moduleRowKey: string) => void
  genStatus: Record<string, string>
}) {
  return (
    <aside className="w-72 shrink-0 border-r border-[var(--border-default)] overflow-y-auto bg-[var(--bg-surface)]">
      {suites.map(s => (
        <div key={s.row_key} className="border-b border-[var(--border-subtle)]">
          <div className="px-3 pt-3 pb-1.5 group/suite">
            <div className="flex items-center gap-1.5">
              <div className="text-xs font-semibold flex-1 min-w-0 truncate">{s.title}</div>
              <button
                title={`Regenerate all test cases in ${s.module_row_key}`}
                disabled={busy}
                onClick={() => onRegenModule(s.module_row_key)}
                className="opacity-0 group-hover/suite:opacity-100 transition text-[var(--text-tertiary)] hover:text-[var(--accent)] disabled:opacity-30"
              >
                <RefreshCw size={12} />
              </button>
            </div>
            {s.journey_overview && <div className="text-[11px] text-[var(--text-tertiary)] line-clamp-2 mt-0.5">{s.journey_overview}</div>}
          </div>
          <div className="pb-2">
            {s.plans.map(p => {
              const caseCount = p.cases.length
              const negCount = p.cases.filter(c => c.test_type === 'negative').length
              const st = genStatus[p.row_key]   // 'authoring' | 'done' | 'failed' while generating
              return (
                <button key={p.row_key} onClick={() => onSelect(p.spec_row_key)}
                  className={cn('w-full text-left px-3 py-1.5 flex items-center gap-2 hover:bg-[var(--bg-elevated)] transition',
                    activeSpec === p.spec_row_key && 'bg-[var(--accent-subtle)]',
                    st === 'authoring' && 'bg-[var(--accent-subtle)]/50')}>
                  <span className="text-xs w-3 flex justify-center">
                    {st === 'authoring' ? <Loader2 size={11} className="animate-spin text-[var(--accent)]" />
                      : st === 'failed' ? <span className="text-red-500" title="Authoring failed — regenerate">⚠</span>
                      : <span className={caseCount ? 'text-emerald-600' : 'text-[var(--text-tertiary)]'}>{caseCount ? '✓' : '○'}</span>}
                  </span>
                  <span className="flex-1 min-w-0">
                    <span className="block text-xs truncate">{p.title}</span>
                    <span className="block text-[10px] text-[var(--text-tertiary)] font-mono">
                      {st === 'authoring' ? <span className="text-[var(--accent)]">authoring…</span>
                        : <>{p.spec_row_key} · {caseCount} cases · {negCount} neg</>}
                    </span>
                  </span>
                  <span className={cn('text-[10px] font-semibold rounded px-1', TC_PRIORITY_STYLES[p.priority]?.text)}>{p.priority}</span>
                </button>
              )
            })}
          </div>
        </div>
      ))}
    </aside>
  )
}

// ── Plan panel ─────────────────────────────────────────────────────────────

function PlanPanel({ projectId, plan, onChanged, busy, onRegenPlan, gapCount, onGapFill, focusCaseKey, onFocused }: {
  projectId: string; plan: TestPlanRow; onChanged: () => void
  busy: boolean; onRegenPlan: () => void
  gapCount: number; onGapFill: () => void
  focusCaseKey?: string | null; onFocused?: () => void
}) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [editCase, setEditCase] = useState<TestCaseRow | null>(null)
  const [adding, setAdding] = useState(false)
  const [typeFilter, setTypeFilter] = useState<string>('all')
  const [highlight, setHighlight] = useState<string | null>(null)

  function toggle(rk: string) {
    setExpanded(prev => { const n = new Set(prev); n.has(rk) ? n.delete(rk) : n.add(rk); return n })
  }

  // Jumped here from the Findings drawer: clear filters so the test is visible,
  // expand it, scroll to it, and flash a highlight. Then clear the request.
  useEffect(() => {
    if (!focusCaseKey || !plan.cases.some(c => c.row_key === focusCaseKey)) return
    setTypeFilter('all')
    setExpanded(prev => new Set(prev).add(focusCaseKey))
    setHighlight(focusCaseKey)
    const t1 = setTimeout(() => {
      document.getElementById(`tc-row-${focusCaseKey}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }, 60)
    const t2 = setTimeout(() => setHighlight(null), 2200)
    onFocused?.()
    return () => { clearTimeout(t1); clearTimeout(t2) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusCaseKey, plan.row_key])
  async function del(c: TestCaseRow) {
    if (c.is_locked) { toast.error('Unlock the row first'); return }
    try { await api.testcases.deleteRow(projectId, 'test_cases', c.id); toast.success('Deleted'); onChanged() }
    catch (e: any) { toast.error(e?.message || 'Delete failed') }
  }
  async function toggleLock(c: TestCaseRow) {
    try {
      if (c.is_locked) await api.testcases.unlockRow(projectId, 'test_cases', c.id)
      else await api.testcases.editRow(projectId, 'test_cases', c.id, {}, { lock: true })
      onChanged()
    } catch (e: any) { toast.error(e?.message || 'Failed') }
  }

  const cases = typeFilter === 'all' ? plan.cases : plan.cases.filter(c => c.test_type === typeFilter)

  return (
    <div className="p-5 space-y-4">
      <div>
        <div className="flex items-center gap-2">
          <h2 className="text-base font-semibold">{plan.title}</h2>
          <span className="text-[10px] font-mono text-[var(--text-tertiary)]">{plan.spec_row_key}</span>
          <span className={cn('text-[10px] font-semibold rounded px-1.5 py-0.5 border', TC_PRIORITY_STYLES[plan.priority]?.bg, TC_PRIORITY_STYLES[plan.priority]?.text, TC_PRIORITY_STYLES[plan.priority]?.border)}>{plan.priority}</span>
        </div>
        {plan.outcomes_summary && (
          <div className="mt-1 text-xs text-[var(--text-secondary)]"><span className="text-[var(--text-tertiary)]">Proves ▸ </span>{plan.outcomes_summary}</div>
        )}
        {plan.preconditions && (
          <div className="mt-1 text-[11px] text-[var(--text-tertiary)]">Preconditions: {plan.preconditions}</div>
        )}
      </div>

      <div className="flex items-center gap-1.5 flex-wrap">
        <FilterChip label="All" active={typeFilter === 'all'} onClick={() => setTypeFilter('all')} />
        {Object.entries(TC_TYPE_STYLES).map(([t, s]) => (
          plan.cases.some(c => c.test_type === t) &&
          <FilterChip key={t} label={s.label} active={typeFilter === t} onClick={() => setTypeFilter(t)} />
        ))}
        {gapCount > 0 && (
          <Button
            size="sm" className="ml-auto bg-amber-500 text-white hover:bg-amber-600"
            disabled={busy} onClick={onGapFill}
            title="Author cases only for this spec's uncovered elements (existing cases kept)"
          >
            {busy ? <Loader2 className="animate-spin" size={13} /> : <Sparkles size={13} />} Fill {gapCount} gap{gapCount > 1 ? 's' : ''}
          </Button>
        )}
        <Button variant="outline" size="sm" className={gapCount > 0 ? '' : 'ml-auto'} disabled={busy} onClick={onRegenPlan}>
          {busy ? <Loader2 className="animate-spin" size={13} /> : <RefreshCw size={13} />} Regenerate plan
        </Button>
        <Button variant="outline" size="sm" onClick={() => setAdding(true)}><Plus size={13} /> Add test case</Button>
      </div>

      <div className="space-y-1.5">
        {cases.map(c => {
          const ts = TC_TYPE_STYLES[c.test_type]
          const isOpen = expanded.has(c.row_key)
          return (
            <div key={c.row_key} id={`tc-row-${c.row_key}`}
              className={cn('rounded-lg border bg-[var(--bg-surface)] transition-shadow',
                highlight === c.row_key ? 'border-amber-400 ring-2 ring-amber-300' : 'border-[var(--border-default)]',
                c.is_locked && 'opacity-70')}>
              <div className="flex items-center gap-2 px-3 py-2 cursor-pointer" onClick={() => toggle(c.row_key)}>
                {isOpen ? <ChevronDown size={14} className="text-[var(--text-tertiary)]" /> : <ChevronRight size={14} className="text-[var(--text-tertiary)]" />}
                <span className="font-mono text-[10px] text-[var(--text-tertiary)]">{c.row_key.split('-TC-')[1] ? `TC-${c.row_key.split('-TC-')[1]}` : c.row_key}</span>
                <span className="flex-1 min-w-0 truncate text-xs font-medium">{c.title}</span>
                <span className={cn('rounded px-1.5 py-0.5 text-[10px] font-medium', ts?.bg, ts?.text)}>{ts?.label}</span>
                {c.source === 'human' && <span className="text-[9px] rounded bg-blue-50 px-1 text-blue-600">manual</span>}
                <div className="flex items-center gap-1" onClick={e => e.stopPropagation()}>
                  <button title="Edit" onClick={() => setEditCase(c)} className="p-1 text-[var(--text-tertiary)] hover:text-[var(--text-primary)]"><Pencil size={12} /></button>
                  <button title={c.is_locked ? 'Unlock' : 'Lock'} onClick={() => toggleLock(c)} className="p-1 text-[var(--text-tertiary)] hover:text-[var(--text-primary)]">{c.is_locked ? <Lock size={12} /> : <Unlock size={12} />}</button>
                  <button title="Delete" onClick={() => del(c)} className="p-1 text-[var(--text-tertiary)] hover:text-red-600"><Trash2 size={12} /></button>
                </div>
              </div>
              {isOpen && <CaseDetail c={c} />}
            </div>
          )
        })}
        {cases.length === 0 && <div className="text-xs text-[var(--text-tertiary)] py-6 text-center">No test cases yet.</div>}
      </div>

      {editCase && (
        <TestCaseEditDialog projectId={projectId} testCase={editCase} open onClose={() => setEditCase(null)} onSaved={onChanged} />
      )}
      <AddTestCaseDialog projectId={projectId} plan={plan} open={adding} onClose={() => setAdding(false)} onAdded={onChanged} />
    </div>
  )
}

function FilterChip({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick} className={cn('rounded border px-2 py-0.5 text-[11px] font-medium transition',
      active ? 'border-[var(--accent)] bg-[var(--accent-subtle)] text-[var(--accent)]' : 'border-[var(--border-default)] text-[var(--text-tertiary)] hover:border-[var(--border-strong)]')}>
      {label}
    </button>
  )
}

function CaseDetail({ c }: { c: TestCaseRow }) {
  return (
    <div className="border-t border-[var(--border-subtle)] px-3 py-3 space-y-2.5 text-xs">
      <div className="flex flex-wrap gap-2 text-[11px] text-[var(--text-tertiary)]">
        {c.source_ref && <span>Source: <span className="font-mono">{c.source_ref}</span></span>}
        {c.auth_role && <span>· Auth: {c.auth_role}</span>}
        {c.viewports.length > 0 && <span>· Viewports: {c.viewports.join(', ')}</span>}
      </div>
      {(c.given || c.when || c.then) && (
        <div className="space-y-0.5 font-mono text-[11px] bg-[var(--bg-elevated)] rounded p-2">
          {c.given && <div><span className="text-[var(--accent)]">Given</span> {c.given}</div>}
          {c.when && <div><span className="text-[var(--accent)]">When</span> {c.when}</div>}
          {c.then && <div><span className="text-[var(--accent)]">Then</span> {c.then}</div>}
        </div>
      )}
      {c.key_assertions.length > 0 && (
        <div>
          <div className="font-semibold text-[11px] mb-0.5">Key assertions</div>
          <ul className="space-y-0.5">
            {c.key_assertions.map((a, i) => <li key={i} className="flex gap-1.5"><span className="text-emerald-600">☑</span>{a}</li>)}
          </ul>
        </div>
      )}
      {c.expected_observability.length > 0 && (
        <div className="text-[11px] text-[var(--text-secondary)]">
          <span className="text-[var(--text-tertiary)]">Observability ▸ </span>
          {c.expected_observability.map((o, i) => <span key={i}>{o.kind}: {o.signal} — {o.assertion}; </span>)}
        </div>
      )}
      {c.expected_result && (
        <div className="text-[11px]"><span className="text-[var(--text-tertiary)]">Expected ▸ </span><span className="font-medium">{c.expected_result}</span></div>
      )}
      {c.traceability && c.traceability.length > 0 && (
        <div className="flex flex-wrap gap-1 pt-1">
          {c.traceability.map((t, i) => <TestCasesTraceChip key={i} trace={t} />)}
        </div>
      )}
    </div>
  )
}
