'use client'
/**
 * Module-Scoped [SPEC-DECISION] MCQ Prompt.
 *
 * Modal dialog presenting a [SPEC-DECISION] question + 2–4 MCQ options.
 * AI's recommended option is marked with ⭐ and rationale shown inline.
 *
 * Three resolution buttons:
 *   - Accept AI recommendation → status='accepted_ai', chosen_index=recommended_index
 *   - Override → choose a different option, status='overridden'
 *     (also triggers re-modularize since the AI's pick is no longer the basis)
 *   - Dismiss → status='dismissed' (not applicable to this decomposition)
 *
 * On submit, the resolved decision row is bumped to a new version with the
 * chosen index + status. The orchestrator picks up the resolved decision on the
 * next modularize re-run via the `resolved_decisions` LLM input.
 */
import { useState } from 'react'
import { Loader2, Sparkles, X } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'
import type { FrsSpecDecisionRow } from '@/lib/types'

interface Props {
  projectId: string
  decision: FrsSpecDecisionRow
  onClose: () => void
  /** Called after the resolution is persisted (parent should re-fetch). */
  onResolved: () => void
}

export function FrsModuleDecisionPrompt({
  projectId, decision, onClose, onResolved,
}: Props) {
  const [chosenIndex, setChosenIndex] = useState<number>(
    decision.recommended_index,
  )
  const [submitting, setSubmitting] = useState(false)

  async function submit(status: 'accepted_ai' | 'overridden' | 'dismissed') {
    setSubmitting(true)
    try {
      await api.frs.resolveDecision(projectId, decision.id, {
        chosen_index: chosenIndex,
        status,
      })
      const flavor =
        status === 'accepted_ai' ? 'Accepted AI recommendation' :
        status === 'overridden'  ? 'Overridden — re-modularization scheduled' :
        'Dismissed'
      toast.success(flavor)
      onResolved()
      onClose()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to resolve decision')
      setSubmitting(false)
    }
  }

  const isAcceptingAi = chosenIndex === decision.recommended_index
  const options = decision.options ?? []

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="decision-prompt-title"
      onClick={onClose}
    >
      <div
        className="w-full max-w-2xl max-h-[90vh] overflow-auto rounded-2xl bg-[var(--bg-surface)] shadow-[var(--shadow-lg)] border border-[var(--border-default)]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start gap-3 px-5 py-4 border-b border-[var(--border-subtle)]">
          <div className="shrink-0 w-9 h-9 rounded-lg bg-amber-50 ring-1 ring-amber-200 flex items-center justify-center">
            <Sparkles size={16} className="text-amber-600" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-amber-700">
              Module-scoped decision
            </p>
            <h2
              id="decision-prompt-title"
              className="mt-0.5 text-base font-semibold text-[var(--text-primary)] leading-snug"
            >
              {decision.question}
            </h2>
            <p className="mt-1 text-[10px] text-[var(--text-tertiary)] font-mono">
              {decision.row_key}
              {decision.module_row_key && ` · ${decision.module_row_key}`}
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-md p-1 text-[var(--text-tertiary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-elevated)] transition-colors"
            aria-label="Close"
          >
            <X size={16} />
          </button>
        </div>

        {/* AI rationale */}
        {decision.recommended_rationale && (
          <div className="mx-5 mt-4 rounded-lg bg-[var(--accent-subtle)]/40 border border-[var(--accent)]/20 px-3 py-2.5">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--accent)]">
              ✦ AI rationale
            </p>
            <p className="mt-1 text-xs text-[var(--text-secondary)] leading-relaxed">
              Recommends <span className="font-semibold">option {decision.recommended_index + 1}</span>.
              {' '}{decision.recommended_rationale}
            </p>
          </div>
        )}

        {/* Options */}
        <div className="px-5 py-4 space-y-2">
          {options.map((opt, idx) => {
            const recommended = idx === decision.recommended_index
            const chosen = idx === chosenIndex
            return (
              <button
                key={idx}
                onClick={() => setChosenIndex(idx)}
                disabled={submitting}
                className={cn(
                  'w-full text-left rounded-xl border px-3 py-3 transition-all',
                  chosen
                    ? 'border-[var(--accent)] bg-[var(--accent-subtle)] shadow-[var(--shadow-sm)]'
                    : 'border-[var(--border-default)] bg-[var(--bg-surface)] hover:border-[var(--accent)]/40',
                  submitting && 'opacity-60 cursor-not-allowed',
                )}
                aria-pressed={chosen}
              >
                <div className="flex items-center gap-2">
                  <div
                    className={cn(
                      'shrink-0 w-4 h-4 rounded-full border-2 flex items-center justify-center',
                      chosen
                        ? 'border-[var(--accent)] bg-[var(--accent)]'
                        : 'border-[var(--border-default)]',
                    )}
                  >
                    {chosen && <div className="w-1.5 h-1.5 rounded-full bg-white" />}
                  </div>
                  <p className="font-semibold text-sm text-[var(--text-primary)]">
                    {opt.label as string}
                  </p>
                  {recommended && (
                    <span className="text-[10px] inline-flex items-center gap-0.5 rounded-full bg-amber-100 text-amber-800 border border-amber-300 px-1.5 py-0.5 font-semibold">
                      ⭐ AI rec
                    </span>
                  )}
                </div>
                {opt.description && (
                  <p className="mt-1 ml-6 text-xs text-[var(--text-secondary)] leading-relaxed">
                    {opt.description as string}
                  </p>
                )}
                {opt.implications && (
                  <p className="mt-1 ml-6 text-[11px] text-[var(--text-tertiary)] italic leading-relaxed">
                    Implications: {opt.implications as string}
                  </p>
                )}
              </button>
            )
          })}
        </div>

        {/* Footer actions */}
        <div className="border-t border-[var(--border-subtle)] px-5 py-3 flex items-center gap-2">
          <button
            onClick={() => submit('dismissed')}
            disabled={submitting}
            className="text-xs text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] underline disabled:opacity-50"
          >
            Dismiss (not applicable)
          </button>
          <div className="flex-1" />
          {isAcceptingAi ? (
            <button
              onClick={() => submit('accepted_ai')}
              disabled={submitting}
              className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] text-white px-4 py-2 text-sm font-semibold hover:bg-[var(--accent-hover)] disabled:opacity-50 transition-colors"
            >
              {submitting ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} />}
              Accept AI recommendation
            </button>
          ) : (
            <button
              onClick={() => submit('overridden')}
              disabled={submitting}
              className="inline-flex items-center gap-1.5 rounded-lg bg-amber-600 text-white px-4 py-2 text-sm font-semibold hover:bg-amber-700 disabled:opacity-50 transition-colors"
            >
              {submitting ? <Loader2 size={13} className="animate-spin" /> : null}
              Override → Option {chosenIndex + 1}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
