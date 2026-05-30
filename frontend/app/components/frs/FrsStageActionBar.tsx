'use client'
/**
 * Inline persistent CTA bar shown at the top of the FRS builder content area
 * while Stage B specs are pending. Replaces FrsContinueStageBBanner (which was
 * a floating bottom element that could be dismissed and never returned).
 *
 * Three render states:
 *   1. All modules undesigned → "Design All" + "one by one" choice
 *   2. Partial (some done, some not) → "Design Remaining" compact strip
 *   3. All designed OR not yet Stage A approved → null (unmounts)
 *
 * The "×" on the partial strip hides it for the session only (sessionStorage).
 * It reappears on the next page load until all modules are designed.
 */
import { useState } from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import { ChevronRight, Layers, RotateCcw, X, Zap } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { FrsModuleHydrated } from '@/lib/types'

interface Props {
  projectId: string
  modules: FrsModuleHydrated[]
  unitStatus: Record<string, unknown> | null | undefined
  stageAApproved: boolean
  docStatus: string | null
  /** Called when user wants to design all/remaining. sequential=true → one by one. */
  onDesignAll: (sequential: boolean) => void
}

export function FrsStageActionBar({
  projectId, modules, unitStatus, stageAApproved, docStatus, onDesignAll,
}: Props) {
  const reduce = useReducedMotion()
  const [partialDismissed, setPartialDismissed] = useState(() => {
    if (typeof window === 'undefined') return false
    return sessionStorage.getItem(`frs-action-bar-dismissed-${projectId}`) === '1'
  })

  if (!stageAApproved || docStatus === 'validated' || docStatus === 'generating') {
    return null
  }

  // A module counts as designed only when every backlog stub has a spec — a
  // module whose loop finished with some specs missing still needs work.
  const designedCount = modules.filter((m) => {
    const stubs = m.backlog ?? []
    return stubs.length > 0 && stubs.every(s => (s.completeness ?? 0) > 0)
  }).length
  const totalCount = modules.length
  const pendingCount = totalCount - designedCount

  if (pendingCount === 0) return null

  const isFirstRun = designedCount === 0

  if (isFirstRun) {
    return (
      <motion.div
        initial={reduce ? false : { opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.22, ease: 'easeOut' }}
        className="mx-4 mt-3 mb-1 rounded-xl border border-[var(--accent)]/30 bg-gradient-to-br from-[var(--accent-subtle)] to-emerald-50 p-4"
      >
        <div className="flex items-start gap-3">
          <div className="shrink-0 w-9 h-9 rounded-lg bg-[var(--accent)] flex items-center justify-center">
            <Layers size={16} className="text-white" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-[var(--text-primary)]">
              Stage 2 ready — {totalCount} module{totalCount !== 1 ? 's' : ''}, {modules.reduce((s, m) => s + (m.backlog?.length ?? 0), 0)} specs to design
            </p>
            <p className="text-xs text-[var(--text-secondary)] mt-0.5">
              How would you like to proceed?
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                onClick={() => onDesignAll(false)}
                className={cn(
                  'inline-flex items-center gap-1.5 rounded-lg px-3.5 py-2 text-xs font-semibold',
                  'bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)] transition-colors shadow-sm',
                )}
              >
                <Zap size={12} />
                Design All — parallel
              </button>
              <button
                onClick={() => onDesignAll(true)}
                className={cn(
                  'inline-flex items-center gap-1.5 rounded-lg px-3.5 py-2 text-xs font-semibold',
                  'border border-[var(--accent)]/40 bg-white text-[var(--accent)]',
                  'hover:bg-[var(--accent-subtle)] transition-colors',
                )}
              >
                <ChevronRight size={12} />
                Design one by one
              </button>
            </div>
            <p className="mt-2 text-[11px] text-[var(--text-tertiary)]">
              Parallel: all {totalCount} modules at once, fastest (~5–12 min) ·
              One by one: design one module, review it, then continue
            </p>
          </div>
        </div>
      </motion.div>
    )
  }

  // Partial state
  if (partialDismissed) return null

  return (
    <motion.div
      initial={reduce ? false : { opacity: 0, y: -4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.18, ease: 'easeOut' }}
      className="mx-4 mt-3 mb-1 rounded-lg border border-amber-200 bg-amber-50/70 px-3.5 py-2.5 flex items-center gap-3"
    >
      <RotateCcw size={13} className="shrink-0 text-amber-600" />
      <p className="flex-1 text-xs text-amber-800">
        <span className="font-semibold">{pendingCount} of {totalCount} module{totalCount !== 1 ? 's' : ''}</span>
        {' '}still need{pendingCount === 1 ? 's' : ''} specs designed.
      </p>
      <button
        onClick={() => onDesignAll(false)}
        className="shrink-0 inline-flex items-center gap-1 rounded-md border border-amber-300 bg-white px-2.5 py-1 text-xs font-semibold text-amber-700 hover:bg-amber-100 transition-colors"
      >
        Design Remaining
      </button>
      <button
        onClick={() => {
          sessionStorage.setItem(`frs-action-bar-dismissed-${projectId}`, '1')
          setPartialDismissed(true)
        }}
        className="shrink-0 rounded p-0.5 text-amber-500 hover:text-amber-700 hover:bg-amber-100 transition-colors"
        aria-label="Dismiss"
      >
        <X size={13} />
      </button>
    </motion.div>
  )
}
