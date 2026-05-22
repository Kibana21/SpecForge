'use client'
import { GitBranch } from 'lucide-react'
import { Badge } from '@/app/components/ui/badge'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/app/components/ui/dialog'
import type { AuditEventRead } from '@/lib/types'
import { SEVERITY_VARIANT } from '@/lib/audit'

interface Props {
  event: AuditEventRead | null
  onClose: () => void
  onShowRelated: (correlationId: string) => void
}

function Row({ k, v, mono }: { k: string; v: string; mono?: boolean }) {
  return (
    <div className="flex gap-3 border-b border-[var(--border-subtle)] py-1.5 last:border-0">
      <span className="w-28 shrink-0 text-xs font-medium text-[var(--text-tertiary)]">{k}</span>
      <span className={`min-w-0 break-words text-sm text-[var(--text-primary)] ${mono ? 'font-mono text-xs' : ''}`}>{v}</span>
    </div>
  )
}

function Json({ label, value }: { label: string; value: Record<string, unknown> }) {
  if (!value || Object.keys(value).length === 0) return null
  return (
    <div>
      <p className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-[var(--text-tertiary)]">{label}</p>
      <pre className="overflow-x-auto rounded-lg bg-[var(--bg-sunken)] p-2.5 text-[11px] text-[var(--text-secondary)]">
        {JSON.stringify(value, null, 2)}
      </pre>
    </div>
  )
}

export function AuditDetailDialog({ event, onClose, onShowRelated }: Props) {
  if (!event) return null
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-lg max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Badge variant={SEVERITY_VARIANT[event.severity]}>{event.label}</Badge>
            <span className="font-mono text-xs font-normal text-[var(--text-tertiary)]">{event.event}</span>
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-0">
          <Row k="When" v={new Date(event.ts).toLocaleString()} />
          <Row k="Actor" v={`${event.actor_name ?? '—'}${event.actor_email ? ` (${event.actor_email})` : ''}`} />
          <Row k="Role" v={event.actor_role ?? '—'} />
          <Row k="Category" v={event.category} />
          {event.action && <Row k="Action" v={event.action} />}
          {event.project_id && <Row k="Project" v={event.project_id} mono />}
          {event.document_key && <Row k="Document" v={event.document_key} mono />}
          {event.app_key && <Row k="App" v={event.app_key} mono />}
          <Row k="IP" v={event.ip ?? '—'} mono />
          <Row k="User agent" v={event.user_agent ?? '—'} />
          {event.correlation_id && <Row k="Correlation" v={event.correlation_id} mono />}
        </div>

        {event.correlation_id && (
          <button
            onClick={() => onShowRelated(event.correlation_id!)}
            className="inline-flex items-center gap-1.5 self-start rounded-lg border border-[var(--border-default)] px-2.5 py-1.5 text-xs text-[var(--accent-deep)] hover:bg-[var(--bg-elevated)] transition-colors"
          >
            <GitBranch size={13} /> Show related events
          </button>
        )}

        {event.metadata && <Json label="Metadata" value={event.metadata} />}
        {event.affected_sections && <Json label="Affected sections" value={event.affected_sections} />}
      </DialogContent>
    </Dialog>
  )
}
