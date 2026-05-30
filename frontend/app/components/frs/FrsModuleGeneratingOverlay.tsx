'use client'
/**
 * Live progress overlay shown inside the module panel content area while a
 * module's specs are being designed by the LLM.
 *
 * Replaces the blank content area between "Regenerate queued" and specs appearing.
 * Data comes entirely from unit_status (polled every 2s by the parent SWR hook)
 * and the module's existing backlog stubs (known upfront from Stage A).
 *
 * Each spec shows one of three states:
 *   ✓  completeness > 0  → done (SWR brought in the designed spec)
 *   ◐  row_key === current_spec_key → currently being sent to the LLM (pulsing row)
 *   ○  otherwise → queued
 */
import { useReducedMotion } from 'framer-motion'
import { CheckCircle2, Circle, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { FrsModuleDesignProgress, FrsModuleHydrated } from '@/lib/types'

const BAR_SEGMENTS = 10

interface Props {
  module: FrsModuleHydrated
  /** Value of unit_status["design_mod_<row_key>"] — updated by SWR every 2s. */
  progress: FrsModuleDesignProgress
}

export function FrsModuleGeneratingOverlay({ module: m, progress }: Props) {
  const reduce = useReducedMotion()
  const stubs = m.backlog ?? []
  const specsDone = progress.specs_done ?? 0
  const specsTotal = progress.specs_total ?? stubs.length
  const currentKey = progress.current_spec_key ?? null
  const filledSegments = specsTotal > 0
    ? Math.max(1, Math.round((specsDone / specsTotal) * BAR_SEGMENTS))
    : 0

  const currentStub = currentKey
    ? stubs.find(s => s.row_key === currentKey)
    : null

  return (
    <div className="rounded-xl border border-blue-200 bg-blue-50/60 p-5 space-y-4">
      {/* Header */}
      <div className="flex items-center gap-2">
        <Loader2
          size={15}
          className={cn('text-blue-600 shrink-0', reduce ? '' : 'animate-spin')}
        />
        <p className="text-sm font-semibold text-[var(--text-primary)]">
          Designing specs for {m.name}
        </p>
      </div>

      {/* Progress bar */}
      <div className="space-y-1.5">
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-px" role="progressbar"
               aria-valuenow={specsDone} aria-valuemin={0} aria-valuemax={specsTotal}>
            {Array.from({ length: BAR_SEGMENTS }, (_, i) => (
              <span
                key={i}
                className={cn(
                  'inline-block w-4 h-2.5 rounded-[2px]',
                  i < filledSegments ? 'bg-blue-500' : 'bg-blue-200',
                )}
              />
            ))}
          </div>
          <span className="text-xs text-[var(--text-secondary)]">
            {specsDone} of {specsTotal} spec{specsTotal !== 1 ? 's' : ''} complete
          </span>
        </div>

        {currentStub && (
          <p className="text-xs text-blue-700">
            Currently writing: <span className="font-medium">{currentStub.title}</span>
          </p>
        )}
        {!currentStub && specsDone === 0 && (
          <p className="text-xs text-[var(--text-tertiary)]">
            Gathering context and sending to AI model…
          </p>
        )}
      </div>

      {/* Per-spec checklist */}
      {stubs.length > 0 && (
        <ul className="space-y-1 border-t border-blue-200 pt-3">
          {stubs.map((s) => {
            const isDone = (s.completeness ?? 0) > 0
            const isActive = s.row_key === currentKey && !isDone
            return (
              <li
                key={s.row_key}
                className={cn(
                  'flex items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-xs transition-colors',
                  isActive && !reduce && 'frs-spec-pulse',
                  isActive && reduce && 'bg-[var(--accent-subtle)]',
                )}
              >
                <span className="shrink-0 w-4 flex justify-center">
                  {isDone ? (
                    <CheckCircle2 size={13} className="text-[var(--accent)]" />
                  ) : isActive ? (
                    <Loader2 size={12} className={cn('text-blue-600', reduce ? '' : 'animate-spin')} />
                  ) : (
                    <Circle size={11} className="text-[var(--text-tertiary)]/40" />
                  )}
                </span>
                <span
                  className={cn(
                    'flex-1 min-w-0 truncate',
                    isDone ? 'text-[var(--text-secondary)] line-through decoration-[var(--text-tertiary)]' : '',
                    isActive ? 'font-medium text-blue-800' : 'text-[var(--text-secondary)]',
                  )}
                >
                  {s.title}
                </span>
                <span className="shrink-0 font-mono text-[10px] text-[var(--text-tertiary)]">
                  {s.row_key}
                </span>
                {isDone && (
                  <span className="shrink-0 text-[10px] text-[var(--accent)] font-medium">
                    {s.completeness}%
                  </span>
                )}
                {isActive && (
                  <span className="shrink-0 text-[10px] text-blue-600">
                    writing…
                  </span>
                )}
                {!isDone && !isActive && (
                  <span className="shrink-0 text-[10px] text-[var(--text-tertiary)]">
                    queued
                  </span>
                )}
              </li>
            )
          })}
        </ul>
      )}

      <p className="text-[11px] text-[var(--text-tertiary)]">
        Each spec takes 30–120 s. The page updates as each one completes.
      </p>
    </div>
  )
}
