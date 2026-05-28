'use client'
/**
 * Backlog Stub Card — one card per `frs_specs` row in Stage A (stub form).
 *
 * Visual states:
 *   - Stub (completeness=0): dashed border, "Stub awaiting Stage 2" footer + [Design now]
 *   - Designed (completeness>0): solid border, "Designed · vN" footer + [Open spec]
 *   - Locked: amber ring around the card + 🔒 chip in header
 *
 * Header shows row_key + priority pill (P0–P3 colour-coded) + lock chip + action buttons.
 * Body shows title + 1-line stub description + BR trace chips.
 */
import { useState } from 'react'
import { ArrowRight, Check, Clock, Edit, Lock, Trash2, Unlock } from 'lucide-react'
import { cn } from '@/lib/utils'
import { FRS_PRIORITY_STYLES } from '@/lib/frs-manifest'
import type { FrsSpecRow } from '@/lib/types'
import { FrsTraceChip } from './FrsTraceChip'

interface Props {
  stub: FrsSpecRow
  /** Trigger Stage B design for this single stub. */
  onDesignNow?: () => void
  /** Open the spec panel (only meaningful when designed). */
  onOpen?: () => void
  /** Edit title / priority / br_refs inline. */
  onEdit?: () => void
  /** Delete this stub (soft delete). */
  onDelete?: () => void
  /** Toggle lock. */
  onLockToggle?: () => void
  /** Disable action buttons (e.g. during regen). */
  busy?: boolean
}

export function FrsBacklogStubCard({
  stub, onDesignNow, onOpen, onEdit, onDelete, onLockToggle, busy,
}: Props) {
  const [confirmDelete, setConfirmDelete] = useState(false)
  const designed = stub.completeness > 0
  const priorityStyle = FRS_PRIORITY_STYLES[stub.priority]

  return (
    <div
      className={cn(
        'group rounded-xl px-3 py-2.5 transition-all',
        'bg-[var(--bg-surface)]',
        designed
          ? 'border border-[var(--accent)]/30 hover:border-[var(--accent)]/60 shadow-[var(--shadow-sm)]'
          : 'border border-dashed border-[var(--border-default)] hover:border-[var(--accent)]/30 hover:bg-[var(--accent-subtle)]/10',
        stub.is_locked && 'ring-1 ring-amber-300',
      )}
    >
      <div className="flex items-start gap-2">
        {/* Body */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[10px] font-mono font-semibold text-[var(--text-tertiary)]">
              {stub.row_key}
            </span>
            <span
              className={cn(
                'text-[10px] font-semibold rounded px-1.5 py-0.5 border',
                priorityStyle.bg, priorityStyle.text, priorityStyle.border,
              )}
            >
              {priorityStyle.label}
            </span>
            {stub.is_locked && (
              <Lock size={10} className="text-amber-600 shrink-0" aria-label="Locked" />
            )}
          </div>
          <p className="mt-1 text-sm font-medium text-[var(--text-primary)]">
            {stub.title}
          </p>
          {stub.narrative && (
            <p className="mt-1 text-xs text-[var(--text-tertiary)] line-clamp-2 leading-snug">
              {stub.narrative}
            </p>
          )}
          {stub.br_refs.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {stub.br_refs.map((br) => (
                <FrsTraceChip
                  key={br}
                  kind="brd_business_requirement"
                  targetRef={br}
                  confidence="high"
                />
              ))}
            </div>
          )}
        </div>

        {/* Action bar — reveal on hover */}
        <div className="shrink-0 opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition-opacity flex items-center gap-1">
          {onEdit && !stub.is_locked && (
            <button
              onClick={onEdit}
              disabled={busy}
              title="Edit stub"
              className="rounded-md p-1 text-[var(--text-tertiary)] hover:text-[var(--accent)] hover:bg-[var(--accent-subtle)] transition-colors disabled:opacity-40"
            >
              <Edit size={12} />
            </button>
          )}
          {onLockToggle && (
            <button
              onClick={onLockToggle}
              disabled={busy}
              title={stub.is_locked ? 'Unlock stub' : 'Lock stub'}
              className={cn(
                'rounded-md p-1 transition-colors disabled:opacity-40',
                stub.is_locked
                  ? 'text-amber-600 hover:bg-amber-50'
                  : 'text-[var(--text-tertiary)] hover:text-amber-600 hover:bg-amber-50',
              )}
            >
              {stub.is_locked ? <Unlock size={12} /> : <Lock size={12} />}
            </button>
          )}
          {onDelete && !stub.is_locked && (
            !confirmDelete ? (
              <button
                onClick={() => setConfirmDelete(true)}
                disabled={busy}
                title="Delete stub"
                className="rounded-md p-1 text-[var(--text-tertiary)] hover:text-[var(--status-danger)] hover:bg-[var(--status-danger-bg)] transition-colors disabled:opacity-40"
              >
                <Trash2 size={12} />
              </button>
            ) : (
              <div className="flex items-center gap-1">
                <button
                  onClick={() => { onDelete(); setConfirmDelete(false) }}
                  className="rounded-md px-2 py-0.5 text-[10px] font-semibold bg-[var(--status-danger-bg)] text-[var(--status-danger)] border border-[var(--status-danger-border)]"
                >
                  Confirm
                </button>
                <button
                  onClick={() => setConfirmDelete(false)}
                  className="rounded-md p-0.5 text-[var(--text-tertiary)] hover:text-[var(--text-primary)] transition-colors"
                >
                  ✕
                </button>
              </div>
            )
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="mt-2 pt-2 border-t border-[var(--border-subtle)] flex items-center gap-2">
        {designed ? (
          <>
            <span className="inline-flex items-center gap-1 text-[10px] text-[var(--accent)] font-semibold">
              <Check size={9} /> Designed · v{stub.version}
            </span>
            <span className="text-[10px] text-[var(--text-tertiary)]">
              · completeness {stub.completeness}%
            </span>
            <div className="flex-1" />
            {onOpen && (
              <button
                onClick={onOpen}
                className="inline-flex items-center gap-0.5 text-[10px] text-[var(--accent)] hover:underline"
              >
                Open spec <ArrowRight size={9} />
              </button>
            )}
          </>
        ) : (
          <>
            <span className="inline-flex items-center gap-1 text-[10px] text-[var(--text-tertiary)]">
              <Clock size={9} /> Stub awaiting Stage 2
            </span>
            <div className="flex-1" />
            {onDesignNow && (
              <button
                onClick={onDesignNow}
                disabled={busy || stub.is_locked}
                className="inline-flex items-center gap-1 rounded-md bg-[var(--accent)] px-2 py-0.5 text-[11px] font-semibold text-white hover:bg-[var(--accent-hover)] disabled:opacity-50 transition-colors"
              >
                Design now <ArrowRight size={10} />
              </button>
            )}
          </>
        )}
      </div>
    </div>
  )
}
