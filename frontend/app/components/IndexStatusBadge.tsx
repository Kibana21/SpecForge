import { Loader2, CheckCircle2, AlertCircle, Clock } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { IndexStatus } from '@/lib/types'
import { indexStatusColor } from '@/lib/ui/status'

const CONFIG: Record<IndexStatus, { icon: LucideIcon; label: string; spin?: boolean }> = {
  pending: { icon: Clock, label: 'Pending' },
  running: { icon: Loader2, label: 'Indexing', spin: true },
  done: { icon: CheckCircle2, label: 'Done' },
  error: { icon: AlertCircle, label: 'Error' },
}

export function IndexStatusBadge({ status }: { status: IndexStatus }) {
  const { icon: Icon, label, spin } = CONFIG[status]
  const color = indexStatusColor[status]
  return (
    <span className="inline-flex items-center gap-1 text-[10px]">
      <Icon size={11} className={`${color}${spin ? ' animate-spin' : ''}`} />
      <span className={color}>{label}</span>
    </span>
  )
}
