'use client'
import { useRouter } from 'next/navigation'
import { AlertTriangle, CheckSquare, Clock, HelpCircle, Inbox } from 'lucide-react'
import { motion } from 'framer-motion'
import type { TriageItem } from '@/lib/types'

const KIND_META: Record<string, { icon: typeof Inbox; tint: string }> = {
  review: { icon: CheckSquare, tint: 'text-warning' },
  approval: { icon: AlertTriangle, tint: 'text-accent' },
  stale_impact: { icon: Clock, tint: 'text-danger' },
  low_confidence: { icon: HelpCircle, tint: 'text-info' },
}

function freshness(computedAt: string | null, nextAt: string | null): string {
  if (!computedAt) return 'computing…'
  const ago = Math.max(0, Math.round((Date.now() - new Date(computedAt).getTime()) / 60000))
  const parts = [`updated ${ago}m ago`]
  if (nextAt) {
    const next = Math.round((new Date(nextAt).getTime() - Date.now()) / 60000)
    if (next > 0) parts.push(`next in ${next}m`)
  }
  return parts.join(' · ')
}

interface Props {
  items: TriageItem[]
  computedAt: string | null
  nextAt: string | null
}

export function TriagePanel({ items, computedAt, nextAt }: Props) {
  const router = useRouter()
  if (items.length === 0) return null

  return (
    <div className="mb-5">
      <div className="mb-2 flex items-center justify-between">
        <p className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-tertiary)]">
          Needs your attention
        </p>
        <span className="text-[11px] text-[var(--text-tertiary)]">{freshness(computedAt, nextAt)}</span>
      </div>
      <div className="flex gap-3 overflow-x-auto pb-1">
        {items.map((it) => {
          const meta = KIND_META[it.kind] ?? { icon: Inbox, tint: 'text-[var(--text-secondary)]' }
          const Icon = meta.icon
          return (
            <motion.button
              key={it.id}
              whileHover={{ y: -2 }}
              transition={{ type: 'spring', stiffness: 400, damping: 28 }}
              onClick={() => router.push(it.link)}
              className="card card-hover shrink-0 w-64 text-left p-3 flex items-start gap-2.5"
            >
              <Icon size={15} className={`shrink-0 mt-0.5 ${meta.tint}`} />
              <span className="text-xs text-[var(--text-primary)] leading-snug line-clamp-2">{it.title}</span>
            </motion.button>
          )
        })}
      </div>
    </div>
  )
}
