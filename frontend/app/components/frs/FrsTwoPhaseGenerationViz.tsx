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
import { ArrowLeft, CheckCircle2, Loader2, RotateCcw } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'
import { FRS_MODULE_LAYER_LABELS } from '@/lib/frs-manifest'
import type { FrsModuleHydrated } from '@/lib/types'

const BAR_SEGMENTS = 10

interface Props {
  projectId: string
  /** Modules from Stage A — used to seed the per-module bars. */
  modules: FrsModuleHydrated[]
  /** Document `unit_status` JSONB — keys are 'modularize', 'design_mod_<row_key>', '_current_unit'. */
  unitStatus: Record<string, unknown> | null | undefined
  /** Optional readiness summary for the BR count in the Phase A strip. */
  brCount?: number
  /** Called when all design_mod_* keys reach completeness ≥ 90 + status flips out. */
  onComplete: () => void
  /** Called when user backs out. */
  onCancel: () => void
}

export function FrsTwoPhaseGenerationViz({
  projectId, modules, unitStatus, brCount, onCancel,
}: Props) {
  const reduce = useReducedMotion()
  const [resetting, setResetting] = useState(false)

  const currentUnit = (unitStatus?.['_current_unit'] as string | null | undefined) ?? null

  const rows = useMemo(() => modules.map((m) => {
    const key = `design_mod_${m.row_key}`
    const status = (unitStatus?.[key] as Record<string, unknown> | undefined) ?? null
    const completeness = Number((status?.['completeness'] as number | undefined) ?? 0)
    const specCount = Number((status?.['spec_count'] as number | undefined) ?? 0)
    const totalStubs = m.backlog.length
    const running = currentUnit === key
    const done = completeness > 0
    return {
      key, name: m.name, rowKey: m.row_key, layer: m.layer,
      completeness, specCount, totalStubs, running, done,
    }
  }), [modules, unitStatus, currentUnit])

  const doneCount = rows.filter(r => r.done).length
  const runningCount = rows.filter(r => r.running).length
  const totalStubs = modules.reduce((s, m) => s + m.backlog.length, 0)

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
        <button
          onClick={onCancel}
          className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] transition-colors"
        >
          <ArrowLeft size={14} /> Back
        </button>
        <span className="text-sm font-semibold text-[var(--text-primary)]">Functional Specifications</span>
        <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold bg-blue-100 text-blue-700 border border-blue-200">
          <Loader2 size={9} className={reduce ? '' : 'animate-spin'} />
          Designing modules… (Stage 2 of 2)
        </span>
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

          {/* Phase B title + progress */}
          <div className="mt-6 flex items-baseline justify-between">
            <p className="text-base font-semibold text-[var(--text-primary)]">
              Phase B — Per-module design
            </p>
            <p className="text-xs text-[var(--text-tertiary)]">
              {runningCount > 0 && `${runningCount} of ${modules.length} modules running · `}
              {doneCount}/{modules.length} complete
            </p>
          </div>

          {/* Module bars */}
          <div className="mt-3 space-y-2">
            {rows.map((r, i) => (
              <FrsTwoPhaseModuleBar
                key={r.key}
                index={i}
                name={r.name}
                rowKey={r.rowKey}
                layer={r.layer as keyof typeof FRS_MODULE_LAYER_LABELS}
                completeness={r.completeness}
                specCount={r.specCount}
                totalStubs={r.totalStubs}
                running={r.running}
                done={r.done}
                reduce={!!reduce}
              />
            ))}
          </div>

          <p className="mt-6 text-[11px] text-center text-[var(--text-tertiary)]">
            est. 5–12 minutes total · runs 3 modules in parallel
          </p>
        </div>
      </div>
    </div>
  )
}

// ── Module bar ───────────────────────────────────────────────────────────────

interface BarProps {
  index: number
  name: string
  rowKey: string
  layer: keyof typeof FRS_MODULE_LAYER_LABELS
  completeness: number
  specCount: number
  totalStubs: number
  running: boolean
  done: boolean
  reduce: boolean
}

function FrsTwoPhaseModuleBar({
  index, name, rowKey, layer, completeness, specCount, totalStubs, running, done, reduce,
}: BarProps) {
  const segmentsFilled = done
    ? Math.max(1, Math.round((completeness / 100) * BAR_SEGMENTS))
    : running ? Math.max(1, Math.round((completeness / 100) * BAR_SEGMENTS) || 1) : 0

  const status: 'done' | 'running' | 'queue' =
    done && completeness >= 100 ? 'done'
    : running ? 'running'
    : done ? 'done'
    : 'queue'

  return (
    <motion.div
      initial={reduce ? false : { opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.22, delay: index * 0.05, ease: 'easeOut' }}
      className={cn(
        'flex items-center gap-3 rounded-xl border px-3 py-2.5 transition-colors',
        status === 'done' && 'border-[var(--accent)]/40 bg-[var(--accent-subtle)]/40',
        status === 'running' && 'border-blue-300 bg-blue-50',
        status === 'queue' && 'border-[var(--border-default)] bg-[var(--bg-elevated)] opacity-70',
      )}
    >
      {/* Segmented bar */}
      <div className="shrink-0 flex items-center gap-px" role="progressbar"
           aria-valuenow={completeness} aria-valuemin={0} aria-valuemax={100}>
        {Array.from({ length: BAR_SEGMENTS }, (_, i) => {
          const filled = i < segmentsFilled
          return (
            <span
              key={i}
              className={cn(
                'inline-block w-3 h-3 rounded-[2px]',
                filled
                  ? (status === 'done'
                      ? 'bg-[var(--frs-phase-b-done)]'
                      : 'bg-[var(--frs-phase-b-bar)]')
                  : 'bg-[var(--frs-phase-queue)]',
              )}
            />
          )
        })}
      </div>

      {/* Module name + meta */}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-[var(--text-primary)] truncate">
          <span className="font-mono text-[var(--text-tertiary)] mr-1.5">{rowKey}</span>
          {name}
        </p>
        <p className="text-[10px] text-[var(--text-tertiary)]">
          {FRS_MODULE_LAYER_LABELS[layer]} ·{' '}
          {specCount > 0
            ? `${specCount} of ${totalStubs} specs designed`
            : totalStubs > 0
              ? `${totalStubs} stub${totalStubs !== 1 ? 's' : ''} queued`
              : 'no stubs'}
        </p>
      </div>

      {/* Status icon */}
      <div className="shrink-0">
        {status === 'done' && completeness >= 100 ? (
          <CheckCircle2 size={16} className="text-[var(--accent)]" />
        ) : status === 'running' ? (
          <Loader2 size={14} className={cn('text-blue-600', reduce ? '' : 'animate-spin')} />
        ) : status === 'done' ? (
          <span className="text-[10px] font-semibold text-[var(--accent)]">{completeness}%</span>
        ) : (
          <span className="text-[10px] text-[var(--text-tertiary)]">waiting</span>
        )}
      </div>
    </motion.div>
  )
}
