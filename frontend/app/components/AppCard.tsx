'use client'
import { motion, useReducedMotion } from 'framer-motion'
import type { AppListItem } from '@/lib/types'
import { Badge } from '@/app/components/ui/badge'

const TIER_VARIANT: Record<number, 'success' | 'info' | 'neutral'> = {
  1: 'success',
  2: 'info',
  3: 'neutral',
}

// Avatar chip tint per tier
const AVATAR_TONE: Record<number, string> = {
  1: 'bg-success-bg text-success',
  2: 'bg-info-bg text-info',
  3: 'bg-[var(--bg-elevated)] text-[var(--text-secondary)]',
}

function initials(name: string): string {
  return name
    .split(/\s+/)
    .map((w) => w[0])
    .join('')
    .toUpperCase()
    .slice(0, 2)
}

function HealthBadge({ app }: { app: AppListItem }) {
  if (!app.is_onboarded) return <Badge variant="neutral">Not Onboarded</Badge>
  if (app.corpus_doc_count === 0) return <Badge variant="neutral">No Corpus</Badge>
  if (app.indexed_doc_count >= app.corpus_doc_count) return <Badge variant="success">Brain Ready</Badge>
  return <Badge variant="warning">Indexing</Badge>
}

// A single metric cell. Pass value=null for an untracked, stylish placeholder.
function Metric({ label, value, danger }: { label: string; value: number | null; danger?: boolean }) {
  const placeholder = value === null
  return (
    <div className="px-3 py-2.5">
      <p className="text-[9px] font-semibold uppercase tracking-wider text-[var(--text-tertiary)]">{label}</p>
      <p
        className={`mt-0.5 text-sm font-bold ${
          placeholder
            ? 'text-[var(--text-tertiary)]'
            : danger && value > 0
              ? 'text-danger'
              : 'text-[var(--text-primary)]'
        }`}
        title={placeholder ? 'Not tracked yet' : undefined}
      >
        {placeholder ? '—' : value}
      </p>
    </div>
  )
}

interface Props {
  app: AppListItem
  onClick: () => void
}

export function AppCard({ app, onClick }: Props) {
  const reduce = useReducedMotion()
  const area = app.domain_area || 'General'

  return (
    <motion.button
      onClick={onClick}
      whileHover={reduce ? undefined : { y: -3 }}
      transition={{ type: 'spring', stiffness: 400, damping: 28 }}
      className="card card-hover text-left w-full overflow-hidden"
    >
      {/* Header */}
      <div className="flex items-start gap-3 p-4">
        <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-xs font-bold ${AVATAR_TONE[app.tier] ?? AVATAR_TONE[3]}`}>
          {initials(app.name)}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-[var(--text-primary)] truncate">{app.name}</h3>
            {app.version ? (
              <span className="shrink-0 rounded border border-[var(--border-default)] px-1 py-0 text-[10px] font-mono text-[var(--text-tertiary)]">
                v{app.version}
              </span>
            ) : (
              <span className="shrink-0 rounded border border-dashed border-[var(--border-default)] px-1 py-0 text-[10px] font-mono text-[var(--text-tertiary)]" title="No version set">
                v—
              </span>
            )}
          </div>
          {/* Subline: real (tier, area) + placeholder owner */}
          <p className="mt-0.5 truncate text-[11px] text-[var(--text-tertiary)]">
            Tier {app.tier} <span className="opacity-50">·</span> {area} <span className="opacity-50">·</span>{' '}
            <span title={app.owner_id ? 'Owner name not available' : 'No owner assigned'}>
              Owner {app.owner_id ? '—' : 'Unassigned'}
            </span>
          </p>
        </div>
        <div className="shrink-0">
          <HealthBadge app={app} />
        </div>
      </div>

      {/* Metrics row */}
      <div className="grid grid-cols-4 divide-x divide-[var(--border-subtle)] border-t border-[var(--border-subtle)]">
        <Metric label="Facts" value={app.fact_count} />
        <Metric label="Indexed Docs" value={app.indexed_doc_count} />
        <Metric label="Live Projects" value={null} />
        <Metric label="Open Qs" value={null} danger />
      </div>
    </motion.button>
  )
}
