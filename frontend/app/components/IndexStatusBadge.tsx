import { Loader2, CheckCircle2, AlertCircle, Clock } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { IndexStatus } from '@/lib/types'

const CONFIG: Record<IndexStatus, { icon: LucideIcon; label: string; className: string }> = {
  pending: { icon: Clock, label: 'Pending', className: 'text-[var(--text-tertiary)]' },
  running: { icon: Loader2, label: 'Indexing', className: 'text-amber-600 animate-spin' },
  done: { icon: CheckCircle2, label: 'Done', className: 'text-emerald-600' },
  error: { icon: AlertCircle, label: 'Error', className: 'text-rose-600' },
}

export function IndexStatusBadge({ status }: { status: IndexStatus }) {
  const { icon: Icon, label, className } = CONFIG[status]
  return (
    <span className="inline-flex items-center gap-1 text-[10px]">
      <Icon size={11} className={className} />
      <span className={className}>{label}</span>
    </span>
  )
}
