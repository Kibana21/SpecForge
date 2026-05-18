import type { Confidence } from '@/lib/types'
import clsx from 'clsx'

const map: Record<Confidence, { label: string; cls: string }> = {
  high:   { label: 'High', cls: 'bg-emerald-100 text-emerald-700 border-emerald-300' },
  medium: { label: 'Med',  cls: 'bg-amber-100  text-amber-700  border-amber-300'  },
  low:    { label: 'Low',  cls: 'bg-rose-100   text-rose-700   border-rose-300'   },
}

export function ConfidenceBadge({ confidence }: { confidence: Confidence }) {
  const { label, cls } = map[confidence]
  return (
    <span className={clsx('inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold border', cls)}>
      {label}
    </span>
  )
}
