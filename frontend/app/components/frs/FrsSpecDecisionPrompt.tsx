'use client'
/**
 * Spec-scoped [SPEC-DECISION] MCQ prompt.
 *
 * Used by `FrsSpecPanel` to surface open `frs_spec_decisions` rows. Layout per
 * Stage B PRD §7.4: the question, AI's recommended option marked with ★, the
 * option cards, then four resolution buttons:
 *   - Accept AI recommendation     → resolve with accepted_ai, no regen
 *   - Override → Option B / C / …  → resolve with overridden, triggers spec regen
 *   - Dismiss — not relevant       → resolve with dismissed, no regen
 *
 * `onResolved(triggeredRegen)` lets the parent kick off the spec regenerate flow.
 */
import { useState } from 'react'
import { Loader2, Sparkles, X } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'
import type { FrsSpecDecisionRow } from '@/lib/types'

interface DecisionOption {
  label: string
  description: string
  implications: string
}

interface Props {
  projectId: string
  decision: FrsSpecDecisionRow
  /** Called after a successful resolve. `triggeredRegen` is true when the user
   *  overrode, so the parent can kick off `api.frs.regenerateSpec`. */
  onResolved: (triggeredRegen: boolean) => void
  /** Called when the user dismisses the prompt UI without resolving. */
  onClose: () => void
}

export function FrsSpecDecisionPrompt({ projectId, decision, onResolved, onClose }: Props) {
  const [busy, setBusy] = useState<'accept' | number | 'dismiss' | null>(null)
  const options = (decision.options ?? []) as unknown as DecisionOption[]
  const recommendedIdx = decision.recommended_index ?? 0

  async function submit(
    action: 'accepted_ai' | 'overridden' | 'dismissed',
    chosenIndex: number,
    label: 'accept' | number | 'dismiss',
  ) {
    setBusy(label)
    try {
      await api.frs.resolveDecision(projectId, decision.id, {
        chosen_index: chosenIndex,
        status: action,
      })
      const triggeredRegen = action === 'overridden'
      toast.success(
        action === 'overridden'
          ? 'Override saved — re-authoring spec…'
          : action === 'dismissed'
            ? 'Decision dismissed'
            : 'AI recommendation accepted',
      )
      onResolved(triggeredRegen)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to resolve decision')
    } finally {
      setBusy(null)
    }
  }

  return (
    <>
      <div
        className="fixed inset-0 z-40 bg-black/30 backdrop-blur-[2px]"
        onClick={onClose}
        aria-hidden="true"
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="spec-decision-title"
        className="fixed inset-0 z-50 flex items-center justify-center p-4"
        onClick={onClose}
      >
        <div
          className="w-full max-w-xl rounded-2xl bg-[var(--bg-surface)] border border-[var(--border-default)] shadow-[var(--shadow-lg)] flex flex-col max-h-[90vh]"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-start gap-3 px-5 py-4 border-b border-[var(--border-default)]">
            <div className="flex-1">
              <p className="text-[10px] font-mono text-[var(--text-tertiary)] mb-0.5">
                {decision.row_key}
              </p>
              <h2 id="spec-decision-title" className="text-base font-semibold text-[var(--text-primary)] leading-snug">
                {decision.question}
              </h2>
              {decision.recommended_rationale && (
                <p className="mt-2 text-xs text-[var(--text-secondary)] leading-relaxed flex items-start gap-1.5">
                  <Sparkles size={11} className="text-amber-500 shrink-0 mt-0.5" />
                  <span>
                    <span className="font-semibold text-[var(--text-primary)]">AI rationale:</span>{' '}
                    {decision.recommended_rationale}
                  </span>
                </p>
              )}
            </div>
            <button
              onClick={onClose}
              className="rounded-md p-1 text-[var(--text-tertiary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-elevated)] transition-colors"
              aria-label="Close"
            >
              <X size={16} />
            </button>
          </div>

          {/* Options */}
          <div className="flex-1 overflow-y-auto px-5 py-4 space-y-2">
            {options.map((opt, i) => (
              <div
                key={i}
                className={cn(
                  'rounded-lg border px-3 py-2.5',
                  i === recommendedIdx
                    ? 'border-amber-300 bg-amber-50/40'
                    : 'border-[var(--border-default)] bg-[var(--bg-surface)]',
                )}
              >
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono text-[var(--text-tertiary)]">
                    Option {String.fromCharCode(65 + i)}
                  </span>
                  <p className="text-sm font-semibold text-[var(--text-primary)] flex-1">
                    {opt.label}
                  </p>
                  {i === recommendedIdx && (
                    <span className="text-[10px] font-semibold inline-flex items-center gap-1 rounded-full px-2 py-0.5 bg-amber-100 text-amber-800">
                      <Sparkles size={9} /> AI pick
                    </span>
                  )}
                </div>
                {opt.description && (
                  <p className="mt-1 text-xs text-[var(--text-secondary)]">{opt.description}</p>
                )}
                {opt.implications && (
                  <p className="mt-1 text-[11px] text-[var(--text-tertiary)] italic">
                    Implications: {opt.implications}
                  </p>
                )}
              </div>
            ))}
          </div>

          {/* Footer — resolution buttons */}
          <div className="border-t border-[var(--border-default)] px-5 py-3 flex flex-col gap-2">
            <button
              onClick={() => submit('accepted_ai', recommendedIdx, 'accept')}
              disabled={busy !== null}
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-[var(--accent)] text-white px-3 py-2 text-sm font-semibold hover:bg-[var(--accent-hover)] disabled:opacity-50 transition-colors"
            >
              {busy === 'accept' ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} />}
              Accept AI recommendation (Option {String.fromCharCode(65 + recommendedIdx)})
            </button>
            <div className="grid grid-cols-2 gap-2">
              {options.map((opt, i) =>
                i === recommendedIdx ? null : (
                  <button
                    key={i}
                    onClick={() => submit('overridden', i, i)}
                    disabled={busy !== null}
                    className="inline-flex items-center justify-center gap-1 rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] px-3 py-1.5 text-xs font-semibold text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] disabled:opacity-50 transition-colors"
                  >
                    {busy === i && <Loader2 size={11} className="animate-spin" />}
                    Override → Option {String.fromCharCode(65 + i)}
                  </button>
                ),
              )}
            </div>
            <button
              onClick={() => submit('dismissed', recommendedIdx, 'dismiss')}
              disabled={busy !== null}
              className="inline-flex items-center justify-center gap-1 rounded-md text-[11px] text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] disabled:opacity-50 transition-colors mt-1"
            >
              {busy === 'dismiss' ? <Loader2 size={10} className="animate-spin" /> : null}
              Dismiss — not relevant
            </button>
          </div>
        </div>
      </div>
    </>
  )
}
