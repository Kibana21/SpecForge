'use client'
/**
 * Two-phase generation viz.
 *
 * Shown when the FRS pipeline is in Phase B (per-module design). Mirrors the
 * layout from PRD §4.7 of the Stage B plan: a Stage A summary strip at the top
 * (5 modules · 18 stubs · 14 BRs ✓) followed by a stack of per-module bars
 * that fill in parallel as the `design_mod_<row_key>` keys in `unit_status`
 * tick upward.
 *
 * Driven by SWR polling on the FRS detail. The parent passes:
 *   - modules: list of FrsModule rows (for names + row_keys + backlog counts)
 *   - unitStatus: the document's unit_status JSONB (read fresh each tick)
 *   - currentUnit: the active `_current_unit` so we can spin the right bar
 *
 * "Resume from here" always visible — if the pipeline dies mid-flight the user
 * can recover by clearing the stuck state.
 */
import { useMemo, useState } from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import {
  AlertTriangle, ArrowLeft, CheckCircle2, ChevronDown, ChevronRight, Circle,
  Loader2, RotateCcw, Zap,
} from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'
import { FRS_MODULE_LAYER_LABELS } from '@/lib/frs-manifest'
import type { FrsModuleHydrated } from '@/lib/types'

interface Props {
  projectId: string
  /** Modules from Stage A — used to seed the per-module bars. */
  modules: FrsModuleHydrated[]
  /** Document `unit_status` JSONB — keys are 'modularize', 'design_mod_<row_key>', '_current_unit'. */
  unitStatus: Record<string, unknown> | null | undefined
  /** Optional readiness summary for the BR count in the Phase A strip. */
  brCount?: number
  /** True while a bulk run is in progress — distinguishes queued vs incomplete. */
  bulkActive?: boolean
  /** Resolves a spec's live state (centralised in FrsBuilderView). */
  specStateOf?: (moduleKey: string, stub: { row_key: string; completeness?: number }) =>
    'done' | 'writing' | 'queued' | 'incomplete' | 'pending'
  /** Jump to a spec (closes the overlay and opens it in the builder). */
  onSelectSpec?: (specRowKey: string, moduleRowKey: string) => void
  /** Called when all design_mod_* keys reach completeness ≥ 90 + status flips out. */
  onComplete: () => void
  /** Called when user backs out. */
  onCancel: () => void
  // ── Sequential mode extras ───────────────────────────────────────────────
  sequential?: boolean
  /** row_key of the module that just completed — triggers pause card. */
  pausedAfterModule?: string | null
  /** User clicks "← Review specs" on the pause card. */
  onReviewAndContinue?: () => void
  /** User clicks "Design next" — dispatches the next module. */
  onDesignNext?: () => void
  /** User clicks "⚡ Design all remaining" — switches to parallel. */
  onDesignAllRemaining?: () => void
  /** When provided, the viz is a dismissible overlay: the top-left button
   *  becomes "Continue in builder" and closes the overlay WITHOUT resetting
   *  generation (which keeps running ambiently underneath). */
  onMinimize?: () => void
}

export function FrsTwoPhaseGenerationViz({
  projectId, modules, unitStatus, brCount, bulkActive, specStateOf, onSelectSpec, onCancel,
  sequential, pausedAfterModule, onReviewAndContinue, onDesignNext, onDesignAllRemaining,
  onMinimize,
}: Props) {
  const reduce = useReducedMotion()
  const [resetting, setResetting] = useState(false)
  const [filter, setFilter] = useState<'all' | 'writing' | 'incomplete' | 'queued' | 'done'>('all')
  // Modules whose expand state the user flipped from the default (active = open).
  const [toggled, setToggled] = useState<Set<string>>(new Set())

  const currentUnit = (unitStatus?.['_current_unit'] as string | null | undefined) ?? null

  // Resolve a spec's state — parent-provided resolver, with a safe fallback.
  const stubState = (moduleKey: string, stub: { row_key: string; completeness?: number }) =>
    specStateOf
      ? specStateOf(moduleKey, stub)
      : ((stub.completeness ?? 0) > 0 ? 'done' : 'pending')

  // Flat list of specs currently being written, across all modules.
  const nowWriting = useMemo(() => {
    const out: Array<{ moduleKey: string; moduleName: string; title: string; rowKey: string }> = []
    for (const m of modules) {
      for (const s of m.backlog ?? []) {
        if (stubState(m.row_key, s) === 'writing') {
          out.push({ moduleKey: m.row_key, moduleName: m.name, title: s.title, rowKey: s.row_key })
        }
      }
    }
    return out
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [modules, unitStatus, specStateOf])

  // Spec counts per state — drives the filter chips.
  const stateCounts = useMemo(() => {
    const c = { writing: 0, incomplete: 0, queued: 0, done: 0, pending: 0 }
    for (const m of modules) {
      for (const s of m.backlog ?? []) c[stubState(m.row_key, s)] += 1
    }
    return c
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [modules, unitStatus, specStateOf, bulkActive])

  // Progress is measured by ACTUAL specs designed (backlog stubs with
  // completeness > 0) — the ground truth — not the stale module-level aggregate.
  const totalStubs = modules.reduce((s, m) => s + (m.backlog?.length ?? 0), 0)
  const designedStubs = modules.reduce(
    (s, m) => s + (m.backlog?.filter(x => (x.completeness ?? 0) > 0).length ?? 0), 0,
  )
  const doneCount = modules.filter(
    m => (m.backlog?.length ?? 0) > 0 && m.backlog.every(x => (x.completeness ?? 0) > 0),
  ).length

  async function handleReset() {
    setResetting(true)
    try {
      await api.frs.resetGenerating(projectId)
      toast.success('Cleared generation state — you can start fresh')
      onCancel()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Reset failed')
    } finally {
      setResetting(false)
    }
  }

  return (
    <div className="flex flex-col h-full overflow-hidden bg-[var(--frs-theater-bg)]">
      {/* Header */}
      <div className="shrink-0 h-12 flex items-center gap-3 border-b border-[var(--border-default)] bg-[var(--bg-surface)] px-4">
        {onMinimize ? (
          <button
            onClick={onMinimize}
            title="Generation keeps running in the background"
            className="inline-flex items-center gap-1.5 rounded-md border border-[var(--border-default)] bg-[var(--bg-elevated)] px-2.5 py-1 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-sunken)] hover:text-[var(--text-primary)] transition-colors"
          >
            <ArrowLeft size={13} /> Continue in builder
          </button>
        ) : (
          <button
            onClick={onCancel}
            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] transition-colors"
          >
            <ArrowLeft size={14} /> Back
          </button>
        )}
        <span className="text-sm font-semibold text-[var(--text-primary)]">Functional Specifications</span>
        {(() => {
          const allDone = totalStubs > 0 && designedStubs === totalStubs
          const designing = !!currentUnit || nowWriting.length > 0
          if (allDone) {
            return (
              <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold bg-[var(--accent-subtle)] text-[var(--accent)] border border-[var(--accent)]/30">
                <CheckCircle2 size={9} /> All specs designed
              </span>
            )
          }
          if (designing) {
            return (
              <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold bg-blue-100 text-blue-700 border border-blue-200">
                <Loader2 size={9} className={reduce ? '' : 'animate-spin'} />
                Designing… (Stage 2 of 2)
              </span>
            )
          }
          return (
            <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold bg-amber-100 text-amber-700 border border-amber-200">
              <AlertTriangle size={9} /> {totalStubs - designedStubs} specs incomplete
            </span>
          )
        })()}
        <div className="flex-1" />
        <button
          onClick={handleReset}
          disabled={resetting}
          title="Recover from a stuck pipeline — preserves existing modules"
          className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-default)] bg-[var(--bg-elevated)] px-3 py-1 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-sunken)] disabled:opacity-50 transition-colors"
        >
          {resetting ? <Loader2 size={12} className="animate-spin" /> : <RotateCcw size={12} />}
          {resetting ? 'Resetting…' : 'Resume from here'}
        </button>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-auto px-6 py-10">
        <div className="mx-auto max-w-2xl">
          {/* Phase A summary */}
          <div className="rounded-2xl border border-[var(--border-default)] bg-[var(--frs-phase-a-bg)] px-5 py-4">
            <div className="flex items-center gap-2">
              <CheckCircle2 size={16} className="text-[var(--accent)]" />
              <p className="text-sm font-semibold text-[var(--text-primary)]">
                Phase A — Modularization
              </p>
              <span className="ml-auto text-xs text-[var(--accent)] font-semibold">✓ Complete</span>
            </div>
            <p className="mt-1 text-xs text-[var(--text-secondary)]">
              {modules.length} module{modules.length !== 1 ? 's' : ''} ·{' '}
              {totalStubs} backlog stub{totalStubs !== 1 ? 's' : ''}
              {brCount !== undefined && ` · ${brCount} BR${brCount !== 1 ? 's' : ''} covered`}
            </p>
          </div>

          {/* Phase B header — aggregate + progress bar */}
          <div className="mt-6">
            <div className="flex items-baseline justify-between">
              <p className="text-base font-semibold text-[var(--text-primary)]">
                Phase B — Functional design
              </p>
              <p className="text-xs text-[var(--text-tertiary)]">
                {designedStubs}/{totalStubs} specs · {doneCount}/{modules.length} modules done
              </p>
            </div>
            <div className="mt-2 flex items-center gap-2">
              <div className="flex-1 h-2 rounded-full bg-[var(--bg-sunken)] overflow-hidden">
                <motion.div
                  className="h-full rounded-full bg-[var(--accent)]"
                  initial={false}
                  animate={{ width: `${totalStubs > 0 ? Math.round((designedStubs / totalStubs) * 100) : 0}%` }}
                  transition={{ duration: reduce ? 0 : 0.5, ease: 'easeOut' }}
                />
              </div>
              <span className="shrink-0 text-xs font-semibold text-[var(--accent)] tabular-nums">
                {totalStubs > 0 ? Math.round((designedStubs / totalStubs) * 100) : 0}%
              </span>
            </div>
          </div>

          {/* Filter chips */}
          <div className="mt-3 flex flex-wrap items-center gap-1.5">
            {([
              ['all', 'All', totalStubs],
              ['writing', 'Writing', stateCounts.writing],
              ['incomplete', 'Incomplete', stateCounts.incomplete],
              ['queued', 'Queued', stateCounts.queued],
              ['done', 'Done', stateCounts.done],
            ] as const).map(([key, label, count]) => (
              <button
                key={key}
                onClick={() => setFilter(key)}
                className={cn(
                  'inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-medium transition-colors',
                  filter === key
                    ? 'bg-[var(--text-primary)] text-white'
                    : 'bg-[var(--bg-elevated)] text-[var(--text-secondary)] hover:bg-[var(--bg-sunken)]',
                  key === 'writing' && count > 0 && filter !== key && 'text-blue-700',
                  key === 'incomplete' && count > 0 && filter !== key && 'text-amber-700',
                )}
              >
                {label}
                <span className={cn('tabular-nums', filter === key ? 'opacity-80' : 'opacity-60')}>{count}</span>
              </button>
            ))}
          </div>

          {/* Now writing spotlight */}
          {nowWriting.length > 0 && (
            <div className="mt-4 rounded-xl border border-blue-200 bg-blue-50/60 p-3">
              <p className="text-[10px] font-semibold uppercase tracking-widest text-blue-700 mb-2">
                Now writing · {nowWriting.length}
              </p>
              <div className="space-y-1.5">
                {nowWriting.map((w) => (
                  <button
                    key={w.rowKey}
                    onClick={() => onSelectSpec?.(w.rowKey, w.moduleKey)}
                    className="group w-full flex items-center gap-2.5 rounded-lg bg-white/70 px-2.5 py-1.5 text-left hover:bg-white transition-colors"
                  >
                    <Loader2 size={13} className={cn('shrink-0 text-blue-600', reduce ? '' : 'animate-spin')} />
                    <span className="flex-1 min-w-0 truncate text-xs font-medium text-[var(--text-primary)]">
                      {w.title}
                    </span>
                    <span className="shrink-0 font-mono text-[10px] text-[var(--text-tertiary)]">{w.rowKey}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Module accordion with spec rows */}
          <div className="mt-4 space-y-1.5">
            {modules.map((m, i) => (
              <FrsModuleSpecGroup
                key={m.row_key}
                index={i}
                module={m}
                filter={filter}
                stubState={stubState}
                isCurrentModule={currentUnit === `design_mod_${m.row_key}`}
                toggledOpen={toggled.has(m.row_key)}
                onToggle={() => setToggled(prev => {
                  const n = new Set(prev); n.has(m.row_key) ? n.delete(m.row_key) : n.add(m.row_key); return n
                })}
                onSelectSpec={onSelectSpec}
                reduce={!!reduce}
              />
            ))}
          </div>

          {/* Sequential pause card */}
          {sequential && pausedAfterModule && (() => {
            const pausedMod = modules.find(m => m.row_key === pausedAfterModule)
            const remaining = modules.filter((m) => {
              const total = m.backlog.length
              const designed = m.backlog.filter(s => (s.completeness ?? 0) > 0).length
              return total === 0 || designed < total
            }).length
            return (
              <motion.div
                initial={reduce ? false : { opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.22, ease: 'easeOut' }}
                className="mt-4 rounded-xl border border-[var(--accent)]/30 bg-[var(--accent-subtle)]/60 p-4"
              >
                <div className="flex items-center gap-2 mb-1">
                  <CheckCircle2 size={14} className="text-[var(--accent)]" />
                  <p className="text-sm font-semibold text-[var(--text-primary)]">
                    {pausedMod?.name ?? pausedAfterModule} designed
                  </p>
                </div>
                <p className="text-xs text-[var(--text-secondary)] mb-3">
                  Review the specs in the panel, then continue when ready.
                  {remaining > 0 && ` ${remaining} module${remaining !== 1 ? 's' : ''} remaining.`}
                </p>
                <div className="flex flex-wrap gap-2">
                  {onReviewAndContinue && (
                    <button
                      onClick={onReviewAndContinue}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-default)] bg-white px-3 py-1.5 text-xs font-semibold text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] transition-colors"
                    >
                      <ArrowLeft size={11} /> Review specs
                    </button>
                  )}
                  {onDesignNext && remaining > 0 && (
                    <button
                      onClick={onDesignNext}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--accent)]/40 bg-white px-3 py-1.5 text-xs font-semibold text-[var(--accent)] hover:bg-[var(--accent-subtle)] transition-colors"
                    >
                      <ChevronRight size={11} /> Design next module
                    </button>
                  )}
                  {onDesignAllRemaining && remaining > 1 && (
                    <button
                      onClick={onDesignAllRemaining}
                      className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-1.5 text-xs font-semibold text-white hover:bg-[var(--accent-hover)] transition-colors"
                    >
                      <Zap size={11} /> Design all remaining
                    </button>
                  )}
                </div>
              </motion.div>
            )
          })()}

          {!sequential && (!!currentUnit || nowWriting.length > 0) && (
            <p className="mt-6 text-[11px] text-center text-[var(--text-tertiary)]">
              est. 5–12 minutes total · runs 3 modules in parallel
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Module spec group (accordion) ─────────────────────────────────────────────

type SpecState = 'done' | 'writing' | 'queued' | 'incomplete' | 'pending'

function SpecStateIcon({ state, reduce }: { state: SpecState; reduce: boolean }) {
  if (state === 'done') return <CheckCircle2 size={13} className="text-[var(--accent)]" />
  if (state === 'writing') return <Loader2 size={12} className={cn('text-blue-600', reduce ? '' : 'animate-spin')} />
  if (state === 'incomplete') return <AlertTriangle size={12} className="text-amber-600" />
  if (state === 'queued') return <Circle size={10} className="text-blue-400" />
  return <Circle size={10} className="text-[var(--text-tertiary)]/40" />
}

function FrsModuleSpecGroup({
  index, module: m, filter, stubState, isCurrentModule, toggledOpen, onToggle, onSelectSpec, reduce,
}: {
  index: number
  module: FrsModuleHydrated
  filter: 'all' | 'writing' | 'incomplete' | 'queued' | 'done'
  stubState: (moduleKey: string, stub: { row_key: string; completeness?: number }) => SpecState
  isCurrentModule: boolean
  toggledOpen: boolean
  onToggle: () => void
  onSelectSpec?: (specRowKey: string, moduleRowKey: string) => void
  reduce: boolean
}) {
  const stubs = m.backlog ?? []
  const total = stubs.length
  const designed = stubs.filter(s => (s.completeness ?? 0) > 0).length
  const fullyDone = total > 0 && designed === total
  const anyWriting = stubs.some(s => stubState(m.row_key, s) === 'writing')

  const visibleStubs = filter === 'all'
    ? stubs
    : stubs.filter(s => stubState(m.row_key, s) === filter)

  // When a filter is active, hide modules with no matching specs.
  if (filter !== 'all' && visibleStubs.length === 0) return null

  // Default: active modules open, fully-done modules collapsed. User toggle flips it.
  const defaultOpen = !fullyDone
  const open = filter !== 'all' ? true : (toggledOpen ? !defaultOpen : defaultOpen)

  const pct = total > 0 ? Math.round((designed / total) * 100) : 0
  const barColor = fullyDone ? 'bg-[var(--accent)]' : anyWriting ? 'bg-blue-500' : designed > 0 ? 'bg-amber-400' : 'bg-[var(--border-strong)]'

  return (
    <motion.div
      initial={reduce ? false : { opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, delay: Math.min(index * 0.03, 0.3), ease: 'easeOut' }}
      className="rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface)] overflow-hidden"
    >
      {/* Module header */}
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-2.5 px-3 py-2.5 text-left hover:bg-[var(--bg-elevated)] transition-colors"
      >
        <span className="shrink-0 text-[var(--text-tertiary)]">
          {open ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
        </span>
        <span className="font-mono text-[11px] text-[var(--text-tertiary)] shrink-0">{m.row_key}</span>
        <span className="flex-1 min-w-0 truncate text-sm font-medium text-[var(--text-primary)]">{m.name}</span>

        {/* Mini progress */}
        <span className="hidden sm:block w-16 h-1.5 rounded-full bg-[var(--bg-sunken)] overflow-hidden shrink-0">
          <span className={cn('block h-full rounded-full', barColor)} style={{ width: `${pct}%` }} />
        </span>
        <span className="shrink-0 text-[11px] tabular-nums text-[var(--text-tertiary)] w-9 text-right">{designed}/{total}</span>
        <span className="shrink-0 w-4 flex justify-center">
          {fullyDone ? (
            <CheckCircle2 size={15} className="text-[var(--accent)]" />
          ) : (isCurrentModule || anyWriting) ? (
            <Loader2 size={13} className={cn('text-blue-600', reduce ? '' : 'animate-spin')} />
          ) : designed > 0 ? (
            <AlertTriangle size={13} className="text-amber-500" />
          ) : (
            <Circle size={10} className="text-[var(--text-tertiary)]/40" />
          )}
        </span>
      </button>

      {/* Spec rows */}
      {open && visibleStubs.length > 0 && (
        <ul className="border-t border-[var(--border-subtle)] divide-y divide-[var(--border-subtle)]">
          {visibleStubs.map((s) => {
            const st = stubState(m.row_key, s)
            return (
              <li key={s.row_key}>
                <button
                  onClick={() => onSelectSpec?.(s.row_key, m.row_key)}
                  className={cn(
                    'group w-full flex items-center gap-2.5 pl-9 pr-3 py-1.5 text-left text-xs transition-colors hover:bg-[var(--bg-elevated)]',
                    st === 'writing' && !reduce && 'frs-spec-pulse',
                  )}
                >
                  <span className="shrink-0 w-4 flex justify-center">
                    <SpecStateIcon state={st} reduce={reduce} />
                  </span>
                  <span className={cn(
                    'flex-1 min-w-0 truncate',
                    st === 'done' ? 'text-[var(--text-secondary)]' : 'text-[var(--text-primary)]',
                    st === 'writing' && 'font-medium text-blue-800',
                  )}>
                    {s.title}
                  </span>
                  <span className={cn(
                    'shrink-0 text-[10px] font-medium',
                    st === 'writing' && 'text-blue-600',
                    st === 'incomplete' && 'text-amber-600',
                    st === 'queued' && 'text-blue-400',
                    st === 'done' && 'text-[var(--accent)]',
                    st === 'pending' && 'text-[var(--text-tertiary)]',
                  )}>
                    {st === 'writing' ? 'writing…'
                      : st === 'incomplete' ? 'incomplete'
                      : st === 'queued' ? 'queued'
                      : st === 'done' ? `${s.completeness ?? 0}%`
                      : 'pending'}
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </motion.div>
  )
}
