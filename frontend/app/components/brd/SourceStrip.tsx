'use client'
import { useState } from 'react'
import { ChevronDown, ChevronUp, CheckCircle2, Clock, AlertTriangle, Brain, FileText, Sparkles, BookOpen } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { BrdBundleReadiness } from '@/lib/types'

interface Props {
  projectId: string
  readiness: BrdBundleReadiness
  cbStatus?: string
  /** When provided, renders a 4th BRD layer row below CB (used by FRS Builder). */
  brdStatus?: string
  brdCounts?: {
    brs?: number
    objectives?: number
    risks?: number
    kpis?: number
    stakeholders?: number
  }
  onManageSources?: () => void
}

interface SourceRowProps {
  label: string
  description: string
  status: 'ready' | 'pending' | 'stale' | 'missing'
  accentColor: string
  icon: React.ReactNode
  expandedContent?: React.ReactNode
}

function SourceRow({ label, description, status, accentColor, icon, expandedContent }: SourceRowProps) {
  const [open, setOpen] = useState(false)

  const statusPill = {
    ready:   { label: '✓ Ready',   cls: 'bg-[var(--status-success-bg)] text-[var(--status-success)] border-[var(--status-success-border)]' },
    pending: { label: '⏳ Indexing', cls: 'bg-[var(--status-warning-bg)] text-[var(--status-warning)] border-[var(--status-warning-border)]' },
    stale:   { label: '⚠ Stale',   cls: 'bg-[var(--stale-bg)] text-[var(--stale)] border-[var(--stale-bg)]' },
    missing: { label: '— None',    cls: 'bg-[var(--bg-elevated)] text-[var(--text-tertiary)] border-[var(--border-default)]' },
  }[status]

  return (
    <div
      className={cn(
        'rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] overflow-hidden',
        'border-l-2',
        accentColor,
      )}
    >
      <button
        onClick={() => expandedContent && setOpen((o) => !o)}
        className={cn(
          'flex w-full items-center gap-2.5 px-3 py-2.5 text-left',
          expandedContent ? 'cursor-pointer hover:bg-[var(--bg-elevated)] transition-colors' : 'cursor-default',
        )}
      >
        <span className="shrink-0 text-[var(--text-secondary)]">{icon}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-semibold text-[var(--text-primary)]">{label}</span>
            <span
              className={cn(
                'inline-flex items-center rounded border px-1.5 py-0.5 text-[10px] font-medium',
                statusPill.cls,
              )}
            >
              {statusPill.label}
            </span>
          </div>
          <p className="text-[11px] text-[var(--text-tertiary)] truncate mt-0.5">{description}</p>
        </div>
        {expandedContent && (
          open ? <ChevronUp size={13} className="shrink-0 text-[var(--text-tertiary)]" /> : <ChevronDown size={13} className="shrink-0 text-[var(--text-tertiary)]" />
        )}
      </button>
      {open && expandedContent && (
        <div className="border-t border-[var(--border-subtle)] px-3 py-2.5">
          {expandedContent}
        </div>
      )}
    </div>
  )
}

const STATUS_DOT: Record<SourceRowProps['status'], string> = {
  ready:   'bg-[var(--status-success)]',
  pending: 'bg-[var(--status-warning)]',
  stale:   'bg-[var(--stale)]',
  missing: 'bg-[var(--text-tertiary)]',
}

function CompactChip({ label, status, icon }: Pick<SourceRowProps, 'label' | 'status' | 'icon'>) {
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-md border border-[var(--border-default)] bg-[var(--bg-surface)] px-2 py-1 text-[11px] text-[var(--text-secondary)]"
      title={`${label}: ${status}`}
    >
      <span className="shrink-0 text-[var(--text-tertiary)]">{icon}</span>
      <span className="font-medium text-[var(--text-primary)]">{label}</span>
      <span className={cn('h-1.5 w-1.5 rounded-full shrink-0', STATUS_DOT[status])} />
    </span>
  )
}

export function SourceStrip({ readiness, cbStatus, brdStatus, brdCounts, onManageSources }: Props) {
  const [expanded, setExpanded] = useState(false)

  const totalDocs = readiness.docs?.length ?? 0
  const readyDocs = readiness.docs?.filter((d) => d.indexing_status === 'done').length ?? 0
  const hasPendingDocs = readiness.pending_doc_count > 0

  const docsStatus: SourceRowProps['status'] =
    totalDocs === 0 ? 'missing' :
    hasPendingDocs ? 'pending' :
    readiness.failed_doc_count > 0 ? 'stale' :
    'ready'

  const cbStatusParsed: SourceRowProps['status'] =
    !cbStatus ? 'missing' :
    cbStatus === 'validated' ? 'ready' :
    cbStatus === 'generating' ? 'pending' :
    'stale'

  // Build the source list once; render as compact chips (default) or full cards.
  const sources: SourceRowProps[] = [
    {
      label: 'App Brain',
      description: 'Application facts & context',
      status: 'ready',
      accentColor: 'border-l-blue-500',
      icon: <Brain size={13} />,
    },
    {
      label: 'Documents',
      description:
        totalDocs === 0 ? 'No documents uploaded'
        : hasPendingDocs ? `${readyDocs}/${totalDocs} indexed…`
        : `${totalDocs} document${totalDocs !== 1 ? 's' : ''} ready`,
      status: docsStatus,
      accentColor: 'border-l-sky-500',
      icon: <FileText size={13} />,
      expandedContent:
        totalDocs > 0 ? (
          <div className="space-y-1">
            {readiness.docs?.map((doc) => (
              <div key={doc.id} className="flex items-center gap-2 text-xs">
                {doc.indexing_status === 'done' ? (
                  <CheckCircle2 size={11} className="text-[var(--status-success)] shrink-0" />
                ) : doc.indexing_status === 'error' ? (
                  <AlertTriangle size={11} className="text-[var(--status-danger)] shrink-0" />
                ) : (
                  <Clock size={11} className="text-[var(--status-warning)] shrink-0" />
                )}
                <span className="flex-1 truncate text-[var(--text-secondary)]" title={doc.filename}>
                  {doc.filename}
                </span>
                {doc.page_count !== null && (
                  <span className="text-[10px] text-[var(--text-tertiary)]">{doc.page_count}p</span>
                )}
              </div>
            ))}
          </div>
        ) : undefined,
    },
    {
      label: 'Concept Brief',
      description:
        !cbStatus ? 'Not yet created' :
        cbStatus === 'validated' ? 'Validated ✓' :
        cbStatus === 'generating' ? 'Generating…' :
        'Draft — not validated',
      status: cbStatusParsed,
      accentColor: 'border-l-green-500',
      icon: <Sparkles size={13} />,
    },
    ...(brdStatus ? [{
      label: 'BRD',
      description:
        brdStatus === 'validated' && brdCounts
          ? `${brdCounts.brs ?? 0} BRs · ${brdCounts.objectives ?? 0} objectives · ${brdCounts.risks ?? 0} risks · ${brdCounts.kpis ?? 0} KPIs`
          : brdStatus === 'generating' ? 'Generating…'
          : brdStatus === 'validated' ? 'Validated ✓'
          : 'Draft — not validated',
      status: (brdStatus === 'validated' ? 'ready'
        : brdStatus === 'generating' ? 'pending' : 'stale') as SourceRowProps['status'],
      accentColor: 'border-l-pink-500',
      icon: <BookOpen size={13} />,
      expandedContent:
        brdStatus === 'validated' && brdCounts ? (
          <div className="space-y-1 text-xs text-[var(--text-secondary)]">
            <p>This FRS will be grounded on every BRD row.</p>
            <p className="text-[var(--text-tertiary)]">Stakeholders: {brdCounts.stakeholders ?? 0}</p>
          </div>
        ) : undefined,
    }] : []),
  ]

  return (
    <div className="border-b border-[var(--border-subtle)] bg-[var(--bg-elevated)] px-3 py-2">
      <div className="flex items-center justify-between gap-2">
        <button
          onClick={() => setExpanded((e) => !e)}
          className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] transition-colors"
        >
          Generation Sources
          {expanded
            ? <ChevronUp size={12} className="shrink-0" />
            : <ChevronDown size={12} className="shrink-0" />}
        </button>
        {onManageSources && (
          <button
            onClick={onManageSources}
            className="text-[10px] text-[var(--accent)] hover:opacity-80 transition-opacity shrink-0"
          >
            Manage →
          </button>
        )}
      </div>

      {expanded ? (
        <div className="space-y-1.5 mt-2">
          {sources.map((s) => (
            <SourceRow key={s.label} {...s} />
          ))}
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-1.5 mt-1.5">
          {sources.map((s) => (
            <CompactChip key={s.label} label={s.label} status={s.status} icon={s.icon} />
          ))}
        </div>
      )}
    </div>
  )
}
