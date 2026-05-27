'use client'
import { CheckCircle2, Clock, AlertTriangle, FileText } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { BrdBundleReadiness } from '@/lib/types'

interface Props {
  readiness: BrdBundleReadiness
}

function StatusIcon({ status }: { status: string }) {
  if (status === 'done')
    return <CheckCircle2 size={13} className="text-[var(--status-success)] shrink-0" />
  if (status === 'error')
    return <AlertTriangle size={13} className="text-[var(--status-danger)] shrink-0" />
  // pending | running
  return <Clock size={13} className="text-[var(--status-warning)] shrink-0 animate-pulse" />
}

export function DocReadinessPanel({ readiness }: Props) {
  const total = readiness.docs?.length ?? 0
  const doneCount = readiness.docs?.filter((d) => d.indexing_status === 'done').length ?? 0
  const pendingCount = readiness.pending_doc_count ?? 0

  if (total === 0) return null

  return (
    <div
      className={cn(
        'rounded-xl border p-3 text-xs',
        readiness.can_generate
          ? 'border-[var(--status-success-border)] bg-[var(--status-success-bg)]'
          : 'border-[var(--status-warning-border)] bg-[var(--status-warning-bg)]',
      )}
    >
      {/* Summary row */}
      <div className="flex items-center gap-2 mb-2">
        {readiness.can_generate ? (
          <CheckCircle2 size={14} className="text-[var(--status-success)] shrink-0" />
        ) : (
          <Clock size={14} className="text-[var(--status-warning)] shrink-0 animate-pulse" />
        )}
        <span
          className={cn(
            'font-semibold',
            readiness.can_generate
              ? 'text-[var(--status-success)]'
              : 'text-[var(--status-warning)]',
          )}
        >
          {readiness.can_generate
            ? 'All sources ready'
            : pendingCount > 0
            ? `${doneCount} of ${total} documents indexed…`
            : readiness.blocking_reason ?? 'Sources not ready'}
        </span>
      </div>

      {/* Doc list */}
      <div className="space-y-1">
        {readiness.docs?.map((doc) => (
          <div
            key={doc.id}
            className="flex items-center gap-2 rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] px-2.5 py-1.5"
          >
            <FileText size={11} className="text-[var(--text-tertiary)] shrink-0" />
            <span className="flex-1 truncate text-[var(--text-primary)]" title={doc.filename}>
              {doc.filename}
            </span>
            {doc.page_count !== null && (
              <span className="text-[10px] text-[var(--text-tertiary)] shrink-0">
                {doc.page_count}p
              </span>
            )}
            <StatusIcon status={doc.indexing_status} />
          </div>
        ))}
      </div>

      {/* Failed doc warning */}
      {readiness.failed_doc_count > 0 && (
        <p className="mt-2 text-[11px] text-[var(--status-danger)]">
          <AlertTriangle size={10} className="inline mr-1" />
          {readiness.failed_doc_count} document{readiness.failed_doc_count !== 1 ? 's' : ''} failed to index — re-upload to fix.
        </p>
      )}
    </div>
  )
}
