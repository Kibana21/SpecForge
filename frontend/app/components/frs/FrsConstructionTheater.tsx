'use client'
/**
 * Construction Theater — the hero generation surface for Stage A.
 *
 * Instead of a single spinner, this view simulates the 5 sub-steps the LLM is
 * internally executing:
 *   1. Identifying bounded contexts
 *   2. Validating module boundaries
 *   3. Mapping cross-module contracts
 *   4. Generating FRS backlog
 *   5. Hoisting cross-cutting rules
 *
 * Mechanics:
 *   - Frontend timer ticks through the steps on a budget schedule.
 *   - When the real LLM finishes early (mock mode ≈ 1s), the remaining steps
 *     cascade to ✓ in 600ms total for a satisfying "snap to done" finish.
 *   - When the LLM takes longer, the last visible step pulses indefinitely
 *     until completion or the 90s server-side timeout aborts.
 *   - "Resume from here" recovery button is always visible — a worker-crash
 *     safety hatch (calls /reset-generating).
 *
 * Reduced-motion fallback: spinner replaced with static icon; cascade animations
 * skipped; step transitions are instant.
 */
import { useEffect, useRef, useState } from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import { AlertTriangle, ArrowLeft, Check, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'
import type { FrsBundleReadiness } from '@/lib/types'

const STEPS = [
  { key: 'identify',  label: 'Identifying bounded contexts',   budget: 5_000 },
  { key: 'validate',  label: 'Validating module boundaries',   budget: 8_000 },
  { key: 'contracts', label: 'Mapping cross-module contracts', budget: 12_000 },
  { key: 'backlog',   label: 'Generating FRS backlog',         budget: 12_000 },
  { key: 'crosscut',  label: 'Hoisting cross-cutting rules',   budget: 5_000 },
] as const

const TOTAL_BUDGET_MS = STEPS.reduce((a, s) => a + s.budget, 0)

interface Props {
  projectId: string
  /** Modularize unit completion percentage (>0 means done). */
  modularizeCompleteness: number | undefined
  /** Document status — when in_interview, we transition out. */
  docStatus: 'generating' | 'in_interview' | 'validated' | null
  /** Counts from readiness for the "grounded in" subtitle. */
  readiness: FrsBundleReadiness | null | undefined
  /** Called when status flips from 'generating' → 'in_interview'. */
  onComplete: () => void
  /** Called when the user backs out / resets. */
  onCancel: () => void
}

export function FrsConstructionTheater({
  projectId, modularizeCompleteness, docStatus, readiness, onComplete, onCancel,
}: Props) {
  const reduce = useReducedMotion()
  const [stepIdx, setStepIdx] = useState(0)
  const [resetting, setResetting] = useState(false)
  const completedRef = useRef(false)

  // Drive the theatrical timer while generating
  useEffect(() => {
    if (docStatus !== 'generating') return
    const timers: number[] = []
    let cumulative = 0
    for (let i = 0; i < STEPS.length; i++) {
      cumulative += STEPS[i].budget
      timers.push(window.setTimeout(() => setStepIdx((cur) => Math.max(cur, i + 1)), cumulative))
    }
    return () => timers.forEach(clearTimeout)
  }, [docStatus])

  // Detect actual completion (status flipped to in_interview + modularize completeness > 0)
  useEffect(() => {
    if (completedRef.current) return
    const done =
      docStatus === 'in_interview' &&
      (modularizeCompleteness ?? 0) > 0
    if (!done) return
    completedRef.current = true
    // Cascade remaining steps to ✓ in 600ms total
    const remaining = STEPS.length - stepIdx
    if (remaining <= 0) {
      // already at the end — short pause then transition
      setTimeout(onComplete, 350)
      return
    }
    const stepDelay = Math.max(80, Math.floor(600 / remaining))
    for (let i = 1; i <= remaining; i++) {
      setTimeout(() => setStepIdx(stepIdx + i), i * stepDelay)
    }
    setTimeout(onComplete, remaining * stepDelay + 350)
  }, [docStatus, modularizeCompleteness, stepIdx, onComplete])

  async function handleReset() {
    setResetting(true)
    try {
      await api.frs.resetGenerating(projectId)
      toast.success('Reset to in_interview — you can resume from here')
      onCancel()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Reset failed')
    } finally {
      setResetting(false)
    }
  }

  const currentStep = stepIdx < STEPS.length ? STEPS[stepIdx] : null
  const brd = readiness?.brd_summary

  return (
    <div className="flex flex-col h-full bg-[var(--frs-theater-bg)]">
      {/* Header */}
      <div className="shrink-0 h-12 flex items-center gap-3 border-b border-[var(--border-default)] bg-[var(--bg-surface)] px-4">
        <button
          onClick={onCancel}
          className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] transition-colors"
        >
          <ArrowLeft size={14} /> Back
        </button>
        <span className="text-sm font-semibold text-[var(--text-primary)]">FRS Builder</span>
        <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold bg-blue-100 text-blue-700 border border-blue-200">
          <Loader2 size={9} className={reduce ? '' : 'animate-spin'} />
          Modularizing… (Stage 1 of 2)
        </span>
        <div className="flex-1" />
        <button
          onClick={handleReset}
          disabled={resetting}
          title="If generation appears stuck, click to recover. Existing modules are preserved."
          className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-default)] bg-[var(--bg-elevated)] px-3 py-1 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-sunken)] disabled:opacity-50 transition-colors"
        >
          <AlertTriangle size={12} className="text-amber-500" />
          {resetting ? 'Resetting…' : 'Resume from here'}
        </button>
      </div>

      {/* Stage */}
      <div className="flex-1 overflow-auto px-6 py-10">
        <div className="mx-auto max-w-2xl">
          <p className="text-center text-2xl font-semibold text-[var(--text-primary)]">
            Modularizing your BRD…
          </p>
          <p className="mt-2 text-center text-sm text-[var(--text-tertiary)]">
            est. {Math.round(TOTAL_BUDGET_MS / 1000)} s &nbsp;·&nbsp; Stage 1 of 2
          </p>

          {/* Steps */}
          <div className="mt-10 space-y-2.5">
            {STEPS.map((step, i) => {
              const state: 'done' | 'current' | 'queue' =
                i < stepIdx ? 'done' : i === stepIdx ? 'current' : 'queue'
              return (
                <FrsTheaterStep
                  key={step.key}
                  number={i + 1}
                  label={step.label}
                  state={state}
                  reduce={!!reduce}
                />
              )
            })}
          </div>

          {/* Right-now card */}
          <div className="mt-8 rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface)] px-4 py-3">
            <div className="flex items-center gap-3">
              {reduce ? (
                <Loader2 size={14} className="text-blue-600" />
              ) : (
                <Loader2 size={14} className="text-blue-600 animate-spin" />
              )}
              <p className="text-sm text-[var(--text-secondary)]">
                {currentStep ? (
                  <>
                    Right now: <span className="font-semibold">{currentStep.label.toLowerCase()}…</span>
                  </>
                ) : (
                  <>Finalising and persisting modules…</>
                )}
              </p>
            </div>
            {brd && (
              <p className="mt-1 ml-7 text-[11px] text-[var(--text-tertiary)]">
                Grounded in: {brd.br_count} BRs · {brd.objective_count} objectives ·
                {' '}{brd.risk_count} risks · {brd.kpi_count} KPIs
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Step row ────────────────────────────────────────────────────────────────

function FrsTheaterStep({
  number, label, state, reduce,
}: {
  number: number
  label: string
  state: 'done' | 'current' | 'queue'
  reduce: boolean
}) {
  return (
    <motion.div
      initial={reduce ? false : { opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.22, ease: 'easeOut' }}
      className={cn(
        'flex items-center gap-3 rounded-xl border px-4 py-3 transition-colors',
        state === 'done' && 'border-[var(--accent)] bg-[var(--accent-subtle)]',
        state === 'current' && 'border-blue-300 bg-blue-50',
        state === 'queue' && 'border-[var(--border-default)] bg-[var(--bg-elevated)] opacity-60',
      )}
    >
      <motion.div
        animate={
          reduce
            ? undefined
            : state === 'done'
            ? { scale: [1, 1.12, 1] }
            : undefined
        }
        transition={{ duration: 0.3, ease: 'easeOut' }}
        className={cn(
          'w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold shrink-0',
          state === 'done' && 'bg-[var(--accent)] text-white',
          state === 'current' && 'bg-blue-600 text-white',
          state === 'queue' && 'bg-[var(--bg-sunken)] text-[var(--text-tertiary)]',
        )}
      >
        {state === 'done' ? (
          <Check size={12} />
        ) : state === 'current' ? (
          reduce ? '●' : <Loader2 size={12} className="animate-spin" />
        ) : (
          number
        )}
      </motion.div>
      <p
        className={cn(
          'text-sm font-medium',
          state === 'done' && 'text-[var(--text-primary)]',
          state === 'current' && 'text-blue-900',
          state === 'queue' && 'text-[var(--text-tertiary)]',
        )}
      >
        {label}
      </p>
    </motion.div>
  )
}
