'use client'
import React, { useState } from 'react'
import { cn } from '@/lib/utils'
import { TRACE_KIND_STYLES } from '@/lib/brd-manifest'
import type { BrdTraceabilityRow } from '@/lib/types'

interface Props {
  trace: BrdTraceabilityRow
  onUnlink?: (traceId: string) => void
}

export function TraceChip({ trace, onUnlink }: Props) {
  const [showPopover, setShowPopover] = useState(false)
  const style =
    TRACE_KIND_STYLES[trace.target_kind as keyof typeof TRACE_KIND_STYLES] ??
    TRACE_KIND_STYLES.within_brd

  const label = `← ${style.label} · ${trace.target_label || trace.target_ref}`
  const isLowConfidence = trace.confidence === 'low'

  return (
    <div className="relative inline-block">
      <button
        className={cn(
          'inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium',
          'border transition-colors cursor-pointer select-none',
          style.bg,
          style.text,
          isLowConfidence && 'underline decoration-dotted',
        )}
        style={{ borderLeftWidth: '2px', borderLeftStyle: 'solid' }}
        onMouseEnter={() => setShowPopover(true)}
        onMouseLeave={() => setShowPopover(false)}
        title={isLowConfidence ? 'AI inferred this trace — verify' : undefined}
      >
        {label}
      </button>
      {showPopover && (
        <div className="absolute bottom-full left-0 mb-1 z-50 w-72 rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] shadow-[var(--shadow-md)] p-3 text-xs">
          <div className="font-semibold text-[var(--text-primary)] mb-1">
            {style.label}: {trace.target_label || trace.target_ref}
          </div>
          <div className="text-[var(--text-secondary)] mb-2">
            Kind: {trace.target_kind.replace(/_/g, ' ')} · Confidence:{' '}
            <span
              className={
                trace.confidence === 'high'
                  ? 'text-[var(--status-success)]'
                  : trace.confidence === 'low'
                  ? 'text-[var(--status-danger)]'
                  : 'text-[var(--status-warning)]'
              }
            >
              {trace.confidence}
            </span>
          </div>
          {onUnlink && (
            <button
              className="text-[var(--status-danger)] hover:opacity-80 text-[11px] transition-opacity"
              onClick={() => onUnlink(trace.id)}
            >
              unlink trace
            </button>
          )}
        </div>
      )}
    </div>
  )
}
