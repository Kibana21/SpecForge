'use client'
/**
 * Module Identity Card — the visual centrepiece at the top of every module panel.
 *
 * Anatomy:
 *   ┌────────────────────────────────────────────────────────────────────┐
 *   │  🏷 Capability icon · Module name        Layer ribbon · row_key   │
 *   │  Summary (2-3 lines)                                                │
 *   │  ┌──────────┬──────────┬──────────┬──────────┐  Covers BRs: chips │
 *   │  │ N backlog│ N actors │ N ifaces │ N data   │                     │
 *   │  └──────────┴──────────┴──────────┴──────────┘                     │
 *   │  [Edit] [Regenerate] [⤴ History] [🔒 Lock]                          │
 *   └────────────────────────────────────────────────────────────────────┘
 *
 * Visual hierarchy by Layer (foundation = amber ribbon, vertical = accent, cross_cutting = sky).
 * Stat counts pulse-animate on change (300ms scale 1 → 1.12 → 1) to telegraph updates.
 */
import { Edit, History, Lock, Loader2, RotateCcw, Unlock } from 'lucide-react'
import { cn } from '@/lib/utils'
import { FRS_LAYER_STYLES, FRS_MODULE_LAYER_LABELS } from '@/lib/frs-manifest'
import type { FrsModuleHydrated } from '@/lib/types'
import { pickCapabilityIcon } from './icons'
import { FrsTraceChip } from './FrsTraceChip'

interface Props {
  module: FrsModuleHydrated
  /** Optional callback when the user wants to inline-edit the module metadata. */
  onEdit?: () => void
  /** Optional regenerate just this module. */
  onRegenerate?: () => void
  /** Optional view history drawer. */
  onHistory?: () => void
  /** Optional lock toggle. */
  onLockToggle?: () => void
  /** Whether a per-module regenerate is currently in flight. */
  regenerating?: boolean
}

export function FrsModuleIdentityCard({
  module: m, onEdit, onRegenerate, onHistory, onLockToggle, regenerating,
}: Props) {
  const Icon = pickCapabilityIcon(m.slug)
  const layerStyle = FRS_LAYER_STYLES[m.layer]

  // Aggregate "Covers BRs" across all backlog stubs in this module
  const coveredBrs = Array.from(
    new Set(m.backlog?.flatMap((s) => s.br_refs ?? []) ?? []),
  )

  const stats: Array<{ label: string; value: number }> = [
    { label: 'backlog', value: m.backlog?.length ?? 0 },
    { label: 'actors', value: m.actors?.length ?? 0 },
    { label: 'interfaces', value: m.interfaces?.length ?? 0 },
    { label: 'data', value: m.data_entities?.length ?? 0 },
  ]

  return (
    <div
      className={cn(
        'relative rounded-xl border bg-[var(--bg-surface)] shadow-[var(--shadow-card)]',
        'overflow-hidden',
      )}
      style={{ borderColor: 'var(--border-default)' }}
    >
      {/* Layer accent ribbon down the left edge */}
      <div
        className="absolute left-0 top-0 bottom-0 w-1"
        style={{ background: layerStyle.accent }}
        aria-hidden="true"
      />

      <div className="pl-5 pr-4 py-4 space-y-3">
        {/* Top row: icon · name · row_key · layer ribbon · lock chip */}
        <div className="flex items-start gap-3">
          <div
            className="shrink-0 w-10 h-10 rounded-lg flex items-center justify-center"
            style={{ background: layerStyle.bg }}
          >
            <Icon size={20} style={{ color: layerStyle.accent }} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="text-base font-semibold text-[var(--text-primary)] truncate">
                {m.name}
              </h2>
              <span
                className={cn(
                  'text-[10px] font-medium rounded px-1.5 py-0.5 border whitespace-nowrap',
                  layerStyle.ribbon,
                )}
              >
                {FRS_MODULE_LAYER_LABELS[m.layer]}
              </span>
              {m.is_locked && (
                <span className="inline-flex items-center gap-0.5 text-[10px] font-medium rounded px-1.5 py-0.5 bg-amber-50 text-amber-700 border border-amber-200">
                  <Lock size={9} /> Locked
                </span>
              )}
            </div>
            <p className="text-[11px] text-[var(--text-tertiary)] font-mono mt-0.5">
              {m.row_key} · v{m.version}
              {m.completeness > 0 && (
                <span className="ml-2 text-[var(--text-tertiary)]">
                  · completeness {m.completeness}% · {m.confidence}
                </span>
              )}
            </p>
          </div>

          {/* Action bar */}
          <div className="shrink-0 flex items-center gap-1">
            {onRegenerate && (
              <button
                onClick={onRegenerate}
                disabled={regenerating || m.is_locked}
                title={
                  m.is_locked
                    ? 'Unlock the module before regenerating'
                    : 'Regenerate this module'
                }
                className={cn(
                  'inline-flex items-center gap-1 rounded-md p-1.5 text-[var(--text-tertiary)]',
                  'hover:text-[var(--accent)] hover:bg-[var(--accent-subtle)] transition-colors',
                  'disabled:opacity-40 disabled:cursor-not-allowed',
                )}
              >
                {regenerating ? <Loader2 size={13} className="animate-spin" /> : <RotateCcw size={13} />}
              </button>
            )}
            {onEdit && (
              <button
                onClick={onEdit}
                disabled={m.is_locked}
                title="Edit module metadata"
                className="rounded-md p-1.5 text-[var(--text-tertiary)] hover:text-[var(--accent)] hover:bg-[var(--accent-subtle)] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <Edit size={13} />
              </button>
            )}
            {onHistory && (
              <button
                onClick={onHistory}
                title="View version history"
                className="rounded-md p-1.5 text-[var(--text-tertiary)] hover:text-[var(--accent)] hover:bg-[var(--accent-subtle)] transition-colors"
              >
                <History size={13} />
              </button>
            )}
            {onLockToggle && (
              <button
                onClick={onLockToggle}
                title={m.is_locked ? 'Unlock module' : 'Lock module (preserve through regen)'}
                className={cn(
                  'rounded-md p-1.5 transition-colors',
                  m.is_locked
                    ? 'text-amber-600 hover:bg-amber-50'
                    : 'text-[var(--text-tertiary)] hover:text-amber-600 hover:bg-amber-50',
                )}
              >
                {m.is_locked ? <Unlock size={13} /> : <Lock size={13} />}
              </button>
            )}
          </div>
        </div>

        {/* Summary */}
        {m.summary && (
          <p className="text-sm text-[var(--text-secondary)] leading-relaxed">
            {m.summary}
          </p>
        )}

        {/* Stat grid */}
        <div className="grid grid-cols-4 gap-2">
          {stats.map((s) => (
            <div
              key={s.label}
              className="rounded-lg bg-[var(--bg-elevated)] px-3 py-2 text-center"
            >
              <p className="text-base font-semibold text-[var(--text-primary)] tabular-nums">
                {s.value}
              </p>
              <p className="text-[10px] uppercase tracking-wider text-[var(--text-tertiary)]">
                {s.label}
              </p>
            </div>
          ))}
        </div>

        {/* Covers BRs */}
        {coveredBrs.length > 0 && (
          <div>
            <p className="text-[10px] uppercase tracking-widest text-[var(--text-tertiary)] mb-1">
              Covers BRs
            </p>
            <div className="flex flex-wrap gap-1">
              {coveredBrs.slice(0, 8).map((br) => (
                <FrsTraceChip
                  key={br}
                  kind="brd_business_requirement"
                  targetRef={br}
                  confidence="high"
                />
              ))}
              {coveredBrs.length > 8 && (
                <span className="inline-flex items-center text-[10px] text-[var(--text-tertiary)] px-1">
                  +{coveredBrs.length - 8} more
                </span>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
