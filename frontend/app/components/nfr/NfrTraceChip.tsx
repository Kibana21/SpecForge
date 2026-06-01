'use client'

import { NFR_TRACE_STYLES } from '@/lib/nfr-manifest'
import { cn } from '@/lib/utils'

interface Props {
  kind: string
  targetRef: string
  targetLabel?: string
  confidence?: string
  className?: string
}

/** NFR → BRD provenance chip (colour-coded by target kind). */
export function NfrTraceChip({ kind, targetRef, targetLabel, confidence = 'high', className }: Props) {
  const style = NFR_TRACE_STYLES[kind] ?? NFR_TRACE_STYLES.within_nfr
  return (
    <span
      title={`${kind} → ${targetRef}${targetLabel ? ` (${targetLabel})` : ''} · ${confidence}`}
      className={cn(
        'inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium',
        style.bg, style.text, style.border,
        confidence === 'low' && 'underline decoration-dotted',
        className,
      )}
    >
      <span className="font-semibold">{style.label}</span>
      <span className="opacity-80">{targetRef}</span>
    </span>
  )
}
