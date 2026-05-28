'use client'
/**
 * Stage-A Findings Drawer.
 *
 * Right-slide drawer (480px) listing all validator findings grouped by severity:
 *   Critical → Major → Minor → Coverage → Warnings
 *
 * Each group is collapsible; counts shown in the header. Each finding card
 * shows description + suggested fix + optional "Jump to row" and "Accept fix"
 * actions.
 *
 * Two-step validate (mirrors BRD):
 *   1. GET /findings (read-only) populates this drawer
 *   2. "Approve Stage 1" button (footer) only enabled when blocking == 0 —
 *      POST /validate which sets `_stage_a_approved=true` on the document.
 */
import { useState } from 'react'
import { ChevronDown, ChevronRight, Loader2, X, Check, ArrowRight } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'
import { FRS_FINDING_GROUPS } from '@/lib/frs-manifest'
import type { FrsFinding, FrsFindingsResponse } from '@/lib/types'

interface Props {
  projectId: string
  open: boolean
  findings: FrsFindingsResponse | null
  onClose: () => void
  /** Re-fetch findings (used after accept-fix). */
  onRefresh: () => void
  /** Called when validate succeeds (parent transitions to the Continue banner). */
  onApproved: () => void
  /** Called when the user clicks "Jump to row →" on a finding. */
  onJumpToRow?: (rowKey: string) => void
}

export function FrsModularizeFindings({
  projectId, open, findings, onClose, onRefresh, onApproved, onJumpToRow,
}: Props) {
  const [expanded, setExpanded] = useState<Set<string>>(
    new Set(['critical', 'major', 'coverage']),
  )
  const [submitting, setSubmitting] = useState(false)

  if (!open) return null

  const summary = findings?.summary
  const list = findings?.findings ?? []
  const blocking = summary?.blocking ?? 0

  const grouped = FRS_FINDING_GROUPS.map((g) => ({
    ...g,
    items: list.filter((f) => f.group === g.key),
  }))

  function toggleGroup(key: string) {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  async function handleApprove() {
    if (blocking > 0) return
    setSubmitting(true)
    try {
      const result = await api.frs.validate(projectId)
      if (result.ok) {
        toast.success('Stage 1 approved — ready for Stage 2')
        onApproved()
        onClose()
      } else {
        toast.error('Validation failed — refresh findings and try again')
        onRefresh()
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Validation failed')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/20 backdrop-blur-[2px]"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Drawer */}
      <aside
        className="fixed right-0 top-0 bottom-0 z-50 w-[480px] max-w-[100vw] bg-[var(--bg-surface)] border-l border-[var(--border-default)] shadow-[var(--shadow-lg)] flex flex-col"
        role="dialog"
        aria-modal="true"
        aria-labelledby="findings-title"
      >
        {/* Header */}
        <div className="shrink-0 flex items-start gap-3 px-4 py-4 border-b border-[var(--border-default)]">
          <div className="flex-1">
            <h2 id="findings-title" className="text-base font-semibold text-[var(--text-primary)]">
              Stage 1 Findings
            </h2>
            {summary && (
              <p className="text-xs text-[var(--text-tertiary)] mt-0.5">
                {summary.total} finding{summary.total !== 1 ? 's' : ''} ·{' '}
                <span
                  className={cn(
                    'font-semibold',
                    blocking === 0 ? 'text-[var(--status-success)]' : 'text-[var(--status-warning)]',
                  )}
                >
                  {blocking} blocking
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

        {/* Findings list */}
        <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
          {grouped.every((g) => g.items.length === 0) ? (
            <div className="py-10 text-center">
              <div className="w-12 h-12 mx-auto rounded-full bg-emerald-50 ring-1 ring-emerald-200 flex items-center justify-center">
                <Check size={20} className="text-emerald-600" />
              </div>
              <p className="mt-3 text-sm font-semibold text-[var(--text-primary)]">
                All clean
              </p>
              <p className="mt-1 text-xs text-[var(--text-tertiary)]">
                No findings. You can approve Stage 1 to proceed.
              </p>
            </div>
          ) : (
            grouped.map((g) =>
              g.items.length === 0 ? null : (
                <FindingGroup
                  key={g.key}
                  label={g.label}
                  cls={g.cls}
                  items={g.items}
                  expanded={expanded.has(g.key)}
                  onToggle={() => toggleGroup(g.key)}
                  onJumpToRow={onJumpToRow}
                />
              ),
            )
          )}
        </div>

        {/* Footer */}
        <div className="shrink-0 border-t border-[var(--border-default)] px-4 py-3">
          <button
            onClick={handleApprove}
            disabled={blocking > 0 || submitting}
            className={cn(
              'w-full inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition-colors',
              blocking === 0 && !submitting
                ? 'bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)]'
                : 'bg-[var(--bg-elevated)] text-[var(--text-tertiary)] cursor-not-allowed',
            )}
            title={blocking > 0 ? `${blocking} blocking finding(s) must be resolved first` : 'Approve Stage 1 and unlock Stage 2'}
          >
            {submitting ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <ArrowRight size={14} />
            )}
            {blocking > 0
              ? `Approve Stage 1 (${blocking} blocking)`
              : 'Approve Stage 1 → Continue to Stage 2'}
          </button>
        </div>
      </aside>
    </>
  )
}

// ── Group ───────────────────────────────────────────────────────────────────

function FindingGroup({
  label, cls, items, expanded, onToggle, onJumpToRow,
}: {
  label: string
  cls: string
  items: FrsFinding[]
  expanded: boolean
  onToggle: () => void
  onJumpToRow?: (rowKey: string) => void
}) {
  return (
    <div className="rounded-lg border border-[var(--border-default)] overflow-hidden">
      <button
        onClick={onToggle}
        className={cn(
          'w-full flex items-center gap-2 px-3 py-2 text-left text-xs font-semibold',
          cls,
        )}
        aria-expanded={expanded}
      >
        {expanded ? (
          <ChevronDown size={13} className="shrink-0" />
        ) : (
          <ChevronRight size={13} className="shrink-0" />
        )}
        <span>{label}</span>
        <span className="ml-auto rounded-full px-1.5 py-0.5 text-[10px] bg-white/60 border border-current/20">
          {items.length}
        </span>
      </button>
      {expanded && (
        <div className="bg-[var(--bg-surface)] divide-y divide-[var(--border-subtle)]">
          {items.map((f, idx) => (
            <FindingCard
              key={`${f.check_id}-${idx}`}
              finding={f}
              onJumpToRow={onJumpToRow}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function FindingCard({
  finding, onJumpToRow,
}: {
  finding: FrsFinding
  onJumpToRow?: (rowKey: string) => void
}) {
  return (
    <div className="px-3 py-2.5 text-xs">
      <p className="text-[var(--text-primary)] leading-snug">
        {finding.description}
      </p>
      {finding.suggested_fix && (
        <p className="mt-1 text-[var(--text-tertiary)] italic leading-snug">
          Fix: {finding.suggested_fix}
        </p>
      )}
      <div className="mt-1.5 flex items-center gap-2">
        {finding.row_key && (
          <span className="text-[10px] font-mono text-[var(--text-tertiary)]">
            {finding.row_key}
          </span>
        )}
        {finding.target_ref && (
          <span className="text-[10px] font-mono text-[var(--text-tertiary)]">
            → {finding.target_ref}
          </span>
        )}
        <div className="flex-1" />
        {finding.row_key && onJumpToRow && (
          <button
            onClick={() => onJumpToRow(finding.row_key as string)}
            className="text-[10px] text-[var(--accent)] hover:underline"
          >
            Jump to row →
          </button>
        )}
      </div>
    </div>
  )
}
