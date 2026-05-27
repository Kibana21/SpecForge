'use client'
import { useState } from 'react'
import { ChevronDown, ChevronUp, CheckCircle2, Clock, AlertTriangle, Brain, FileText, Sparkles } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { BrdBundleReadiness } from '@/lib/types'

interface Props {
  projectId: string
  readiness: BrdBundleReadiness
  cbStatus?: string
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

export function SourceStrip({ readiness, cbStatus, onManageSources }: Props) {
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

  return (
    <div className="border-b border-[var(--border-subtle)] bg-[var(--bg-elevated)] px-3 py-2.5 space-y-1.5">
      <div className="flex items-center justify-between mb-1">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)]">
          Generation Sources
        </p>
        {onManageSources && (
          <button
            onClick={onManageSources}
            className="text-[10px] text-[var(--accent)] hover:opacity-80 transition-opacity"
          >
            Manage →
          </button>
        )}
      </div>

      {/* App Brain — always show */}
      <SourceRow
        label="App Brain"
        description="Application facts & context"
        status="ready"
        accentColor="border-l-blue-500"
        icon={<Brain size={13} />}
      />

      {/* Documents */}
      <SourceRow
        label="Documents"
        description={
          totalDocs === 0
            ? 'No documents uploaded'
            : hasPendingDocs
            ? `${readyDocs}/${totalDocs} indexed…`
            : `${totalDocs} document${totalDocs !== 1 ? 's' : ''} ready`
        }
        status={docsStatus}
        accentColor="border-l-sky-500"
        icon={<FileText size={13} />}
        expandedContent={
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
          ) : undefined
        }
      />

      {/* Concept Brief */}
      <SourceRow
        label="Concept Brief"
        description={
          !cbStatus ? 'Not yet created' :
          cbStatus === 'validated' ? 'Validated ✓' :
          cbStatus === 'generating' ? 'Generating…' :
          'Draft — not validated'
        }
        status={cbStatusParsed}
        accentColor="border-l-green-500"
        icon={<Sparkles size={13} />}
      />
    </div>
  )
}
