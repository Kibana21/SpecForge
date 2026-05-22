'use client'
import { motion, useReducedMotion } from 'framer-motion'
import { Sparkles } from 'lucide-react'
import type { AppListItem } from '@/lib/types'
import { Badge } from '@/app/components/ui/badge'

// Rich gradient avatar tint per tier (depth, like the reference cards)
const AVATAR_TONE: Record<number, string> = {
  1: 'bg-gradient-to-br from-[var(--accent)] to-[var(--accent-deep)] text-white',
  2: 'bg-gradient-to-br from-[#B98A3E] to-[#8A6526] text-white',
  3: 'bg-gradient-to-br from-[#697586] to-[#48505E] text-white',
}

function initials(name: string): string {
  return name.split(/\s+/).map((w) => w[0]).join('').toUpperCase().slice(0, 2)
}

function HealthBadge({ app }: { app: AppListItem }) {
  if (!app.is_onboarded) return <Badge variant="neutral">Not onboarded</Badge>
  if (app.corpus_doc_count === 0) return <Badge variant="neutral">No corpus</Badge>
  if (app.indexed_doc_count >= app.corpus_doc_count) return <Badge variant="success">Brain ready</Badge>
  return <Badge variant="warning">Indexing</Badge>
}

function Metric({ label, value, danger }: { label: string; value: number; danger?: boolean }) {
  return (
    <div className="px-3.5 py-3">
      <p className="text-[9px] font-semibold uppercase tracking-wider text-[var(--text-tertiary)]">{label}</p>
      <p className={`mt-1 text-lg font-bold leading-none ${danger && value > 0 ? 'text-danger' : 'text-[var(--text-primary)]'}`}>
        {value}
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
  const meta = [`Tier ${app.tier}`, ...(app.environments ?? [])]

  return (
    <motion.button
      onClick={onClick}
      whileHover={reduce ? undefined : { y: -3 }}
      transition={{ type: 'spring', stiffness: 400, damping: 28 }}
      className="card card-hover text-left w-full overflow-hidden"
    >
      {/* Header */}
      <div className="flex items-start gap-3 p-4">
        <div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-sm font-bold shadow-sm ${AVATAR_TONE[app.tier] ?? AVATAR_TONE[3]}`}>
          {initials(app.name)}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h3 className="text-[15px] font-semibold text-[var(--text-primary)] truncate">{app.name}</h3>
            {app.version && (
              <span className="shrink-0 rounded border border-[var(--border-default)] bg-[var(--bg-base)] px-1.5 py-0.5 text-[10px] font-mono text-[var(--text-secondary)]">
                v{app.version}
              </span>
            )}
          </div>
          {/* Metadata: Tier · environments · Owner team (all real fields) */}
          <p className="mt-1 truncate text-[11px] text-[var(--text-secondary)]">
            {meta.join(' · ')}
            <span className="opacity-50"> · </span>
            Owner <span className="font-semibold text-[var(--text-primary)]">{app.owner_team || 'Unassigned'}</span>
          </p>
        </div>
        <div className="shrink-0">
          {app.open_qs > 0 ? (
            <Badge variant="danger"><Sparkles size={10} /> +{app.open_qs} proposed</Badge>
          ) : (
            <HealthBadge app={app} />
          )}
        </div>
      </div>

      {/* Metrics row */}
      <div className="grid grid-cols-4 divide-x divide-[var(--border-subtle)] border-t border-[var(--border-subtle)]">
        <Metric label="Facts" value={app.fact_count} />
        <Metric label="Indexed docs" value={app.indexed_doc_count} />
        <Metric label="Live projects" value={app.live_project_count} />
        <Metric label="Open Qs" value={app.open_qs} danger />
      </div>
    </motion.button>
  )
}
