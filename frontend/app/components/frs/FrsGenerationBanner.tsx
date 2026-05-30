'use client'
/**
 * FrsGenerationBanner — a slim, persistent FRS progress strip at the top of the
 * builder body. It is the always-available entry point to the full spec-level
 * overview (FrsTwoPhaseGenerationViz), and an at-a-glance status:
 *
 *   • designing  → blue + spinner   "Designing 23/34 specs"
 *   • complete   → green + check     "34/34 specs designed · 7 modules complete"
 *   • partial    → amber + warning   "30/34 specs designed · 4 incomplete"
 *
 * Deliberately NON-blocking. Renders only once Stage B has produced specs (or a
 * run is active) — before that, FrsStageActionBar owns the call-to-action.
 */
import { useMemo } from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import { CheckCircle2, ChevronRight, Loader2, TriangleAlert } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { FrsModuleHydrated } from '@/lib/types'

interface Props {
  modules: FrsModuleHydrated[]
  unitStatus: Record<string, unknown> | null | undefined
  /** True when a bulk Stage B run is in progress (status === 'generating'). */
  bulkActive: boolean
  /** Count of modules the user optimistically triggered (single regens). */
  pendingCount: number
  /** Opens the full spec overview overlay. */
  onOpenDetails: () => void
}

export function FrsGenerationBanner({
  modules, unitStatus, bulkActive, pendingCount, onOpenDetails,
}: Props) {
  const reduce = useReducedMotion()

  const { designedSpecs, totalSpecs, doneModules, totalModules, runningName, active } = useMemo(() => {
    let designed = 0
    let total = 0
    let done = 0
    let runningLabel: string | null = null
    const currentUnit = unitStatus?.['_current_unit'] as string | undefined
    for (const m of modules) {
      const stubs = m.backlog ?? []
      total += stubs.length
      const designedHere = stubs.filter(s => (s.completeness ?? 0) > 0).length
      designed += designedHere
      if (stubs.length > 0 && designedHere === stubs.length) done += 1
      const isCurrent = currentUnit === `design_mod_${m.row_key}`
      if (isCurrent && designedHere < stubs.length) runningLabel = `${m.row_key} ${m.name}`
    }
    return {
      designedSpecs: designed,
      totalSpecs: total,
      doneModules: done,
      totalModules: modules.length,
      runningName: runningLabel,
      active: bulkActive || pendingCount > 0 || runningLabel != null,
    }
  }, [modules, unitStatus, bulkActive, pendingCount])

  // Show once Stage B has produced anything, or while a run is active.
  if (totalSpecs === 0 || (designedSpecs === 0 && !active)) return null

  const pct = totalSpecs > 0 ? Math.round((designedSpecs / totalSpecs) * 100) : 0
  const allDone = designedSpecs === totalSpecs
  const mode: 'designing' | 'complete' | 'partial' =
    active ? 'designing' : allDone ? 'complete' : 'partial'

  const theme = {
    designing: {
      wrap: 'border-blue-200 bg-gradient-to-r from-blue-50 to-[var(--bg-surface)]',
      edge: 'bg-blue-500', text: 'text-blue-800', sub: 'text-blue-700',
      bar: 'bg-blue-500', track: 'bg-blue-100', pctText: 'text-blue-600', btn: 'text-blue-700 hover:bg-blue-100',
    },
    complete: {
      wrap: 'border-[var(--accent)]/30 bg-gradient-to-r from-[var(--accent-subtle)] to-[var(--bg-surface)]',
      edge: 'bg-[var(--accent)]', text: 'text-[var(--accent-deep)]', sub: 'text-[var(--accent)]',
      bar: 'bg-[var(--accent)]', track: 'bg-[var(--accent-subtle)]', pctText: 'text-[var(--accent)]',
      btn: 'text-[var(--accent)] hover:bg-[var(--accent-subtle)]',
    },
    partial: {
      wrap: 'border-amber-200 bg-gradient-to-r from-amber-50 to-[var(--bg-surface)]',
      edge: 'bg-amber-500', text: 'text-amber-800', sub: 'text-amber-700',
      bar: 'bg-amber-400', track: 'bg-amber-100', pctText: 'text-amber-600', btn: 'text-amber-700 hover:bg-amber-100',
    },
  }[mode]

  return (
    <motion.div
      initial={reduce ? false : { opacity: 0, y: -6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, ease: 'easeOut' }}
      className={cn('relative flex items-center gap-3 h-9 px-4 border-b overflow-hidden', theme.wrap)}
    >
      <div className={cn('absolute left-0 top-0 bottom-0 w-0.5', theme.edge)} />

      {mode === 'designing'
        ? <Loader2 size={13} className={cn('shrink-0', theme.sub, reduce ? '' : 'animate-spin')} />
        : mode === 'complete'
          ? <CheckCircle2 size={13} className={cn('shrink-0', theme.sub)} />
          : <TriangleAlert size={13} className={cn('shrink-0', theme.sub)} />}

      <span className={cn('shrink-0 text-xs font-semibold', theme.text)}>
        {mode === 'designing' && `Designing ${designedSpecs}/${totalSpecs} specs`}
        {mode === 'complete' && `${designedSpecs}/${totalSpecs} specs designed · ${doneModules}/${totalModules} modules complete`}
        {mode === 'partial' && `${designedSpecs}/${totalSpecs} specs designed · ${totalSpecs - designedSpecs} incomplete`}
      </span>

      {runningName && mode === 'designing' && (
        <>
          <span className="text-blue-300">·</span>
          <span className={cn('text-xs truncate min-w-0', theme.sub)}>{runningName}</span>
        </>
      )}

      {/* Thin progress bar */}
      <div className="hidden sm:flex flex-1 min-w-0 items-center gap-2">
        <div className={cn('flex-1 h-1.5 rounded-full overflow-hidden', theme.track)}>
          <motion.div
            className={cn('h-full rounded-full', theme.bar)}
            initial={false}
            animate={{ width: `${pct}%` }}
            transition={{ duration: reduce ? 0 : 0.5, ease: 'easeOut' }}
          />
        </div>
        <span className={cn('shrink-0 text-[10px] font-medium tabular-nums', theme.pctText)}>{pct}%</span>
      </div>

      <button
        onClick={onOpenDetails}
        className={cn('shrink-0 inline-flex items-center gap-0.5 rounded-md px-2 py-1 text-xs font-medium transition-colors', theme.btn)}
      >
        View details <ChevronRight size={12} />
      </button>
    </motion.div>
  )
}
