'use client'
/**
 * §2.2 Endpoint card — one per `frs_endpoints` row.
 *
 * Header: HTTP method chip + URL + sync/async/idempotent badges + action cluster.
 * Body (collapsible): 5 JSON sub-blob sections (Request, Response, Errors,
 * Security, Operational). Service overview metadata sits between header + body.
 */
import { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'
import { FRS_HTTP_METHOD_STYLES } from '@/lib/frs-manifest'
import type { FrsEndpointRow, FrsHttpMethod } from '@/lib/types'
import { FrsRowEditDialog, type FrsRowField } from './FrsRowEditDialog'
import { FrsRowActions } from './FrsRowActions'
import { useFrsRowOps } from './useFrsRowOps'

const ENDPOINT_FIELDS: FrsRowField[] = [
  { name: 'service_name', label: 'Service name', type: 'text' },
  { name: 'endpoint_name', label: 'Endpoint name', type: 'text' },
  { name: 'url', label: 'URL', type: 'text', placeholder: '/api/v1/…' },
  { name: 'protocol', label: 'Protocol', type: 'text', placeholder: 'HTTPS / gRPC / AMQP' },
  { name: 'method', label: 'HTTP method', type: 'enum', options: [
    { value: 'GET', label: 'GET' },
    { value: 'POST', label: 'POST' },
    { value: 'PUT', label: 'PUT' },
    { value: 'PATCH', label: 'PATCH' },
    { value: 'DELETE', label: 'DELETE' },
  ]},
  { name: 'sync_async', label: 'Sync / Async', type: 'enum', options: [
    { value: 'sync', label: 'sync' },
    { value: 'async', label: 'async' },
  ]},
  { name: 'idempotent', label: 'Idempotent', type: 'bool',
    description: 'Safe to retry without side effects' },
  { name: 'integration_target', label: 'Integration target', type: 'text',
    placeholder: 'External system name (or leave empty)' },
  { name: 'request_spec', label: 'Request spec (JSON)', type: 'json', rows: 6 },
  { name: 'response_spec', label: 'Response spec (JSON)', type: 'json', rows: 6 },
  { name: 'error_handling', label: 'Error handling (JSON)', type: 'json', rows: 6 },
  { name: 'security', label: 'Security (JSON)', type: 'json', rows: 5 },
  { name: 'operational', label: 'Operational (JSON)', type: 'json', rows: 5 },
]

interface Props {
  projectId: string
  endpoint: FrsEndpointRow
  onMutate: () => void
}

export function FrsEndpointCard({ projectId, endpoint: e, onMutate }: Props) {
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState(false)

  const { busy, handleLockToggle, handleDelete } = useFrsRowOps({
    projectId,
    table: 'frs_endpoints',
    rowId: e.id,
    isLocked: e.is_locked,
    lockPayload: {
      service_name: e.service_name,
      endpoint_name: e.endpoint_name,
      url: e.url,
      protocol: e.protocol,
      method: e.method,
      sync_async: e.sync_async,
      idempotent: e.idempotent,
      request_spec: e.request_spec,
      response_spec: e.response_spec,
      error_handling: e.error_handling,
      security: e.security,
      operational: e.operational,
      integration_target: e.integration_target,
    },
    label: `endpoint "${e.method} ${e.url}"`,
    onMutate,
  })

  const methodStyle = FRS_HTTP_METHOD_STYLES[e.method as FrsHttpMethod] ?? FRS_HTTP_METHOD_STYLES.GET

  return (
    <div
      className={cn(
        'group rounded-xl border bg-[var(--bg-surface)] transition-colors',
        e.is_locked
          ? 'border-amber-200 ring-1 ring-amber-100/70'
          : 'border-[var(--border-default)] hover:border-[var(--accent)]/40',
      )}
    >
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2.5 border-b border-[var(--border-subtle)]">
        <button
          onClick={() => setOpen((v) => !v)}
          className="shrink-0 rounded p-0.5 text-[var(--text-tertiary)] hover:bg-[var(--bg-elevated)] transition-colors"
          aria-label={open ? 'Collapse endpoint' : 'Expand endpoint'}
          aria-expanded={open}
        >
          {open ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
        </button>
        <span
          className={cn(
            'shrink-0 text-[10px] font-mono font-semibold rounded px-1.5 py-0.5 border',
            methodStyle.bg, methodStyle.color, methodStyle.border,
          )}
        >
          {e.method}
        </span>
        <code className="flex-1 text-xs text-[var(--text-primary)] font-mono truncate">
          {e.url}
        </code>
        <div className="flex items-center gap-1 text-[10px] text-[var(--text-tertiary)] shrink-0">
          <span>{e.sync_async}</span>
          <span>·</span>
          <span title="Idempotent">{e.idempotent ? 'idempotent' : 'non-idempotent'}</span>
        </div>
        <FrsRowActions
          isLocked={e.is_locked}
          busy={busy}
          onEdit={() => setEditing(true)}
          onLock={handleLockToggle}
          onDelete={handleDelete}
        />
      </div>

      {/* Body */}
      {open && (
        <div className="px-3 py-2.5 space-y-2 text-xs">
          <div className="grid grid-cols-[110px,1fr] gap-2 text-[var(--text-secondary)]">
            <Meta label="Service" value={e.service_name} />
            <Meta label="Endpoint" value={e.endpoint_name} />
            <Meta label="Protocol" value={e.protocol} />
            {e.integration_target && (
              <Meta label="Integration" value={e.integration_target} />
            )}
          </div>
          <JsonBlock title="Request" payload={e.request_spec} />
          <JsonBlock title="Response" payload={e.response_spec} />
          <JsonBlock title="Errors" payload={e.error_handling} />
          <JsonBlock title="Security" payload={e.security} />
          <JsonBlock title="Operational" payload={e.operational} />
        </div>
      )}

      {editing && (
        <FrsRowEditDialog
          open
          title={`Edit endpoint — ${e.method} ${e.url}`}
          projectId={projectId}
          table="frs_endpoints"
          rowId={e.id}
          initialValues={{
            service_name: e.service_name,
            endpoint_name: e.endpoint_name,
            url: e.url,
            protocol: e.protocol,
            method: e.method,
            sync_async: e.sync_async,
            idempotent: e.idempotent,
            request_spec: e.request_spec,
            response_spec: e.response_spec,
            error_handling: e.error_handling,
            security: e.security,
            operational: e.operational,
            integration_target: e.integration_target,
          }}
          fields={ENDPOINT_FIELDS}
          isLocked={e.is_locked}
          onClose={() => setEditing(false)}
          onSaved={() => { setEditing(false); onMutate() }}
        />
      )}
    </div>
  )
}

function Meta({ label, value }: { label: string; value: string | null }) {
  return (
    <>
      <span className="text-[10px] uppercase tracking-wide text-[var(--text-tertiary)] font-semibold pt-0.5">
        {label}
      </span>
      <span className="leading-snug">{value || '—'}</span>
    </>
  )
}

function JsonBlock({ title, payload }: { title: string; payload: unknown }) {
  const isEmpty =
    payload == null
    || (Array.isArray(payload) && payload.length === 0)
    || (typeof payload === 'object' && payload !== null && Object.keys(payload as object).length === 0)

  if (isEmpty) {
    return (
      <p className="text-[10px] text-[var(--text-tertiary)]">
        <span className="font-semibold">{title}:</span> <em>(empty)</em>
      </p>
    )
  }
  return (
    <details className="text-[10px]">
      <summary className="cursor-pointer text-[var(--text-secondary)] font-semibold py-0.5 hover:text-[var(--accent)] transition-colors">
        {title}
      </summary>
      <pre className="mt-1 px-2 py-1.5 bg-[var(--bg-elevated)]/60 rounded font-mono overflow-x-auto whitespace-pre-wrap break-words">
        {JSON.stringify(payload, null, 2)}
      </pre>
    </details>
  )
}
