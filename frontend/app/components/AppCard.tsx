'use client'
import { motion, useReducedMotion } from 'framer-motion'
import type { AppListItem } from '@/lib/types'
import { Badge } from '@/app/components/ui/badge'

const TIER_VARIANT: Record<number, 'success' | 'info' | 'neutral'> = {
  1: 'success',
  2: 'info',
  3: 'neutral',
}

function HealthBadge({ app }: { app: AppListItem }) {
  if (!app.is_onboarded) return <Badge variant="neutral">Not Onboarded</Badge>
  if (app.corpus_doc_count === 0) return <Badge variant="neutral">No Corpus</Badge>
  if (app.indexed_doc_count >= app.corpus_doc_count) return <Badge variant="success">Brain Ready</Badge>
  return <Badge variant="warning">Indexing</Badge>
}

interface Props {
  app: AppListItem
  onClick: () => void
}

export function AppCard({ app, onClick }: Props) {
  const reduce = useReducedMotion()
  return (
    <motion.button
      onClick={onClick}
      whileHover={reduce ? undefined : { y: -3 }}
      transition={{ type: 'spring', stiffness: 400, damping: 28 }}
      className="card card-hover text-left w-full p-4"
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-[var(--text-primary)] truncate">{app.name}</h3>
          <span className="text-[11px] text-[var(--text-tertiary)] font-mono">{app.short_name}</span>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <Badge variant={TIER_VARIANT[app.tier] ?? 'neutral'}>Tier {app.tier}</Badge>
        </div>
      </div>

      {app.description && (
        <p className="text-[11px] text-[var(--text-secondary)] line-clamp-2 mb-3">
          {app.description}
        </p>
      )}

      <div className="flex items-center justify-between mt-auto">
        <div className="flex items-center gap-2">
          <HealthBadge app={app} />
          {app.domain_area && (
            <span className="text-[10px] text-[var(--text-tertiary)]">{app.domain_area}</span>
          )}
        </div>
        <span className="text-[10px] text-[var(--text-tertiary)]">
          {app.fact_count} facts
        </span>
      </div>
    </motion.button>
  )
}
