'use client'
import { cn } from '@/lib/utils'
import { TC_TRACE_STYLES } from '@/lib/testcases-manifest'
import type { TcTraceRow } from '@/lib/types'

export function TestCasesTraceChip({ trace }: { trace: TcTraceRow }) {
  const style = TC_TRACE_STYLES[trace.target_kind] ?? TC_TRACE_STYLES.within_test_cases
  const isMust = trace.target_kind === 'brd_business_requirement'
  return (
    <span
      title={`${trace.target_kind} · ${trace.target_ref}${trace.target_label ? ` — ${trace.target_label}` : ''} (${trace.confidence})`}
      className={cn(
        'inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium',
        style.bg, style.text,
        isMust && 'ring-1 ring-emerald-400',
      )}
    >
      <span className="opacity-60">{style.label}</span>
      <span className="font-semibold">{trace.target_ref}</span>
    </span>
  )
}
