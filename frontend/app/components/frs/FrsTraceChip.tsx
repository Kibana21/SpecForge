'use client'
import { useState } from 'react'
import { cn } from '@/lib/utils'
import { FRS_TRACE_KIND_STYLES, type FrsTraceKind } from '@/lib/frs-manifest'

interface Props {
  /** What kind of source this chip points at — picks the colour family. */
  kind: FrsTraceKind | string
  /** The opaque target id (BR-001, MOD-002, an app fact id, …). */
  targetRef: string
  /** Optional human-readable label shown alongside the kind. */
  targetLabel?: string
  /** AI confidence; low gets a dotted underline + verify hint. */
  confidence?: 'high' | 'medium' | 'low'
  /** Optional click handler (e.g. open the source in a side drawer). */
  onClick?: () => void
  /** Optional inline className override. */
  className?: string
}

/**
 * FRS trace chip — colour-coded by target kind (brd_* = pink to distinguish
 * from CB green; nfr_driver = yellow; app_fact = blue; doc_section = sky;
 * discover_qa = violet; within_frs = gray).
 */
export function FrsTraceChip({ kind, targetRef, targetLabel, confidence = 'high', onClick, className }: Props) {
  const [showPopover, setShowPopover] = useState(false)
  type Style = { bg: string; text: string; border: string; label: string }
  const styles = FRS_TRACE_KIND_STYLES as unknown as Record<string, Style>
  const style: Style = styles[kind] ?? styles.within_frs

  const display = targetLabel ? `${style.label} · ${targetLabel}` : `${style.label} · ${targetRef}`
  const low = confidence === 'low'

  return (
    <span className="relative inline-block">
      <button
        onClick={onClick}
        onMouseEnter={() => setShowPopover(true)}
        onMouseLeave={() => setShowPopover(false)}
        onFocus={() => setShowPopover(true)}
        onBlur={() => setShowPopover(false)}
        aria-label={`Trace to ${kind.replace(/_/g, ' ')} ${targetRef}${targetLabel ? `: ${targetLabel}` : ''}`}
        className={cn(
          'inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium leading-tight',
          'transition-colors select-none',
          style.bg, style.text, style.border,
          low && 'underline decoration-dotted underline-offset-2',
          onClick ? 'cursor-pointer hover:brightness-95' : 'cursor-default',
          className,
        )}
        title={low ? 'AI-inferred trace — verify' : undefined}
      >
        ← {display}
      </button>
      {showPopover && (
        <span
          role="tooltip"
          className="absolute bottom-full left-0 mb-1 z-50 w-72 rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] shadow-[var(--shadow-md)] p-3 text-xs"
        >
          <span className="block font-semibold text-[var(--text-primary)]">
            {style.label} · {targetLabel || targetRef}
          </span>
          <span className="block mt-1 text-[var(--text-secondary)]">
            Kind: <span className="font-mono text-[10px]">{kind.replace(/_/g, ' ')}</span>
          </span>
          <span className="block mt-1 text-[var(--text-secondary)]">
            target_ref: <span className="font-mono text-[10px]">{targetRef}</span>
          </span>
          <span className="block mt-1 text-[var(--text-tertiary)]">
            Confidence:{' '}
            <span
              className={cn(
                confidence === 'high' && 'text-[var(--status-success)]',
                confidence === 'medium' && 'text-[var(--status-warning)]',
                confidence === 'low' && 'text-[var(--status-danger)]',
              )}
            >
              {confidence}
            </span>
          </span>
        </span>
      )}
    </span>
  )
}
