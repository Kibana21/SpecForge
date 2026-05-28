'use client'
/**
 * FRS BRD Echo Strip — collapsed-by-default one-line summary of the validated BRD,
 * shown below the SourceStrip. Expanded view shows top objectives/BRs/risks so the
 * FRS author doesn't have to leave the page to remember what they're grounding on.
 *
 * Sibling to CbEchoStrip (used in BRD Builder). Same shape, BRD-flavoured content.
 */
import { useState } from 'react'
import { ChevronDown, ChevronUp, BookOpen, ExternalLink } from 'lucide-react'
import { cn } from '@/lib/utils'

interface BrdSummary {
  br_count: number
  objective_count: number
  risk_count: number
  kpi_count: number
  stakeholder_count: number
}

interface TopRow {
  row_key: string
  text: string
  /** Optional decoration: priority (P0/P1/…), severity, etc. */
  badge?: string
  badgeClass?: string
}

interface Props {
  /** Aggregate counts (from readiness.brd_summary). */
  summary: BrdSummary | null
  /** Optional top BRs (sorted by priority desc). */
  topBrs?: TopRow[]
  /** Optional top objectives. */
  topObjectives?: TopRow[]
  /** Optional top risks. */
  topRisks?: TopRow[]
  /** Click handler for "Open BRD →". */
  onOpenBrd?: () => void
}

export function FrsBrdEchoStrip({
  summary, topBrs = [], topObjectives = [], topRisks = [], onOpenBrd,
}: Props) {
  const [open, setOpen] = useState(false)
  if (!summary) return null

  return (
    <div className="border-b border-[var(--border-subtle)] bg-[var(--bg-elevated)]/40">
      {/* Collapsed: one line */}
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 px-3 py-1.5 text-left hover:bg-[var(--bg-elevated)] transition-colors"
        aria-expanded={open}
        aria-label="Toggle BRD essence summary"
      >
        {open ? (
          <ChevronUp size={11} className="shrink-0 text-[var(--text-tertiary)]" />
        ) : (
          <ChevronDown size={11} className="shrink-0 text-[var(--text-tertiary)]" />
        )}
        <BookOpen size={11} className="shrink-0 text-pink-500" />
        <span className="text-[11px] font-medium text-[var(--text-secondary)]">
          BRD essence
        </span>
        <span className="text-[11px] text-[var(--text-tertiary)]">
          · {summary.br_count} BRs · {summary.objective_count} objectives ·{' '}
          {summary.risk_count} risks · {summary.kpi_count} KPIs
        </span>
        {onOpenBrd && (
          <button
            onClick={(e) => { e.stopPropagation(); onOpenBrd() }}
            className="ml-auto inline-flex items-center gap-0.5 text-[10px] text-[var(--accent)] hover:underline"
          >
            Open BRD <ExternalLink size={9} />
          </button>
        )}
      </button>

      {/* Expanded */}
      {open && (
        <div className="px-3 pb-3 pt-1 space-y-3 text-xs text-[var(--text-secondary)]">
          {topObjectives.length > 0 && (
            <EchoSection title="Top objectives" rows={topObjectives} />
          )}
          {topBrs.length > 0 && (
            <EchoSection title="Top BRs by priority" rows={topBrs} />
          )}
          {topRisks.length > 0 && (
            <EchoSection title="Top risks" rows={topRisks} />
          )}
          {topObjectives.length === 0 && topBrs.length === 0 && topRisks.length === 0 && (
            <p className="text-[var(--text-tertiary)] italic">
              Detailed BRD content unavailable. Open the BRD to view full traceability.
            </p>
          )}
        </div>
      )}
    </div>
  )
}

function EchoSection({ title, rows }: { title: string; rows: TopRow[] }) {
  return (
    <div>
      <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)] mb-1">
        {title}
      </p>
      <ul className="space-y-0.5">
        {rows.slice(0, 5).map((r) => (
          <li key={r.row_key} className="flex items-start gap-2">
            <span className="text-[10px] font-mono text-[var(--text-tertiary)] shrink-0 mt-0.5">
              {r.row_key}
            </span>
            {r.badge && (
              <span
                className={cn(
                  'text-[9px] font-semibold rounded px-1 py-px shrink-0 mt-0.5 border',
                  r.badgeClass ?? 'bg-[var(--bg-elevated)] text-[var(--text-tertiary)] border-[var(--border-default)]',
                )}
              >
                {r.badge}
              </span>
            )}
            <span className="text-[11px] leading-snug">{r.text}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
