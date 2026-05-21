'use client'
import type { AppListItem } from '@/lib/types'

const TIER_STYLES: Record<number, string> = {
  1: 'bg-[var(--status-success-bg)] text-[var(--status-success)]',
  2: 'bg-[var(--accent-blue-subtle)] text-[var(--accent-blue)]',
  3: 'bg-[var(--bg-elevated)] text-[var(--text-tertiary)]',
}

function HealthBadge({ app }: { app: AppListItem }) {
  if (!app.is_onboarded) {
    return (
      <span className="rounded px-1.5 py-0.5 text-[10px] font-medium bg-[var(--bg-elevated)] text-[var(--text-tertiary)]">
        Not Onboarded
      </span>
    )
  }
  if (app.corpus_doc_count === 0) {
    return (
      <span className="rounded px-1.5 py-0.5 text-[10px] font-medium bg-[var(--bg-elevated)] text-[var(--text-tertiary)]">
        No Corpus
      </span>
    )
  }
  if (app.indexed_doc_count >= app.corpus_doc_count) {
    return (
      <span className="rounded px-1.5 py-0.5 text-[10px] font-medium bg-emerald-50 text-emerald-700">
        Brain Ready
      </span>
    )
  }
  return (
    <span className="rounded px-1.5 py-0.5 text-[10px] font-medium bg-amber-50 text-amber-700">
      Indexing
    </span>
  )
}

interface Props {
  app: AppListItem
  onClick: () => void
}

export function AppCard({ app, onClick }: Props) {
  return (
    <button
      onClick={onClick}
      className="text-left w-full rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-4 hover:border-[var(--border-strong)] hover:bg-[var(--bg-elevated)] transition-all"
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-[var(--text-primary)] truncate">{app.name}</h3>
          <span className="text-[11px] text-[var(--text-tertiary)] font-mono">{app.short_name}</span>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${TIER_STYLES[app.tier] ?? ''}`}>
            Tier {app.tier}
          </span>
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
    </button>
  )
}
