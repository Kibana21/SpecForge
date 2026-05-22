'use client'
import { Badge } from '@/app/components/ui/badge'
import type { AuditEventRead } from '@/lib/types'
import { SEVERITY_VARIANT } from '@/lib/audit'

function target(e: AuditEventRead): string {
  if (e.document_key) return e.document_key
  if (e.app_key) return e.app_key
  if (e.project_id) return `project ${e.project_id.slice(0, 8)}`
  return '—'
}

function when(ts: string): string {
  return new Date(ts).toLocaleString(undefined, {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
}

export function AuditTable({
  events, onRowClick,
}: { events: AuditEventRead[]; onRowClick: (e: AuditEventRead) => void }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface)]">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[var(--border-default)] text-left text-[11px] uppercase tracking-wider text-[var(--text-tertiary)]">
            <th className="px-3 py-2.5 font-semibold">Time</th>
            <th className="px-3 py-2.5 font-semibold">Actor</th>
            <th className="px-3 py-2.5 font-semibold">Event</th>
            <th className="px-3 py-2.5 font-semibold">Target</th>
            <th className="px-3 py-2.5 font-semibold">IP</th>
          </tr>
        </thead>
        <tbody>
          {events.map((e) => (
            <tr
              key={e.id}
              onClick={() => onRowClick(e)}
              className="cursor-pointer border-b border-[var(--border-subtle)] last:border-0 hover:bg-[var(--bg-elevated)] transition-colors"
            >
              <td className="px-3 py-2.5 whitespace-nowrap text-xs text-[var(--text-secondary)]">{when(e.ts)}</td>
              <td className="px-3 py-2.5 whitespace-nowrap">
                <span className="text-[var(--text-primary)]">{e.actor_name ?? '—'}</span>
                {e.actor_role && <span className="text-[var(--text-tertiary)]"> · {e.actor_role}</span>}
              </td>
              <td className="px-3 py-2.5"><Badge variant={SEVERITY_VARIANT[e.severity]}>{e.label}</Badge></td>
              <td className="px-3 py-2.5 font-mono text-[11px] text-[var(--text-secondary)] max-w-[260px] truncate">{target(e)}</td>
              <td className="px-3 py-2.5 font-mono text-[11px] text-[var(--text-tertiary)] whitespace-nowrap">{e.ip ?? '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
