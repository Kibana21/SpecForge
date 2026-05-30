'use client'
/**
 * §3.2 Data Entity card — one per `frs_data_entities` row.
 *
 * Header: entity name + store type + expected volume + action cluster.
 * Body (collapsible): meta + Columns (compact table) + Keys/Indexes/Relationships
 * + Access logic text + optional Cache spec + Retention policy.
 * Nested arrays edit via the JSON field on the parent row.
 */
import { useState } from 'react'
import { ChevronDown, ChevronRight, Key } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { FrsDataEntityRow } from '@/lib/types'
import { FrsRowEditDialog, type FrsRowField } from './FrsRowEditDialog'
import { FrsRowActions } from './FrsRowActions'
import { useFrsRowOps } from './useFrsRowOps'

const DATA_ENTITY_FIELDS: FrsRowField[] = [
  { name: 'entity_name', label: 'Entity name', type: 'text' },
  { name: 'data_store_type', label: 'Data store type', type: 'enum', options: [
    { value: 'RDBMS', label: 'RDBMS' },
    { value: 'NoSQL', label: 'NoSQL' },
    { value: 'ObjectStore', label: 'Object store' },
    { value: 'Cache', label: 'Cache' },
    { value: 'FileStorage', label: 'File storage' },
  ]},
  { name: 'description', label: 'Description', type: 'textarea', rows: 3 },
  { name: 'expected_volume', label: 'Expected volume', type: 'text',
    placeholder: '~10k rows/day; ~5M total' },
  { name: 'retention_policy', label: 'Retention policy', type: 'text',
    placeholder: '7 years (compliance)' },
  { name: 'columns', label: 'Columns (JSON array)', type: 'json', rows: 8 },
  { name: 'keys_constraints', label: 'Keys & constraints (JSON)', type: 'json', rows: 5 },
  { name: 'indexes', label: 'Indexes (JSON array)', type: 'json', rows: 5 },
  { name: 'relationships', label: 'Relationships (JSON array)', type: 'json', rows: 5 },
  { name: 'access_logic', label: 'Access logic', type: 'textarea', rows: 4 },
  { name: 'cache_spec', label: 'Cache spec (JSON or null)', type: 'json', rows: 5 },
]

interface Props {
  projectId: string
  entity: FrsDataEntityRow
  onMutate: () => void
}

export function FrsDataEntityCard({ projectId, entity: e, onMutate }: Props) {
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState(false)

  const { busy, handleLockToggle, handleDelete } = useFrsRowOps({
    projectId,
    table: 'frs_data_entities',
    rowId: e.id,
    isLocked: e.is_locked,
    lockPayload: {
      entity_name: e.entity_name,
      data_store_type: e.data_store_type,
      description: e.description,
      expected_volume: e.expected_volume,
      columns: e.columns,
      keys_constraints: e.keys_constraints,
      indexes: e.indexes,
      relationships: e.relationships,
      access_logic: e.access_logic,
      cache_spec: e.cache_spec,
      retention_policy: e.retention_policy,
    },
    label: `entity "${e.entity_name}"`,
    onMutate,
  })

  const primaryKeys = (e.keys_constraints?.['primary'] as string[] | undefined) ?? []

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
          aria-label={open ? 'Collapse entity' : 'Expand entity'}
          aria-expanded={open}
        >
          {open ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
        </button>
        <code className="text-sm text-[var(--text-primary)] font-mono">
          {e.entity_name}
        </code>
        <span className="text-[10px] rounded px-1.5 py-0.5 bg-[var(--bg-elevated)] text-[var(--text-tertiary)]">
          {e.data_store_type}
        </span>
        {e.expected_volume && (
          <span className="text-[10px] text-[var(--text-tertiary)] truncate">
            {e.expected_volume}
          </span>
        )}
        <div className="flex-1" />
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
        <div className="px-3 py-2.5 space-y-3 text-xs">
          {e.description && (
            <p className="text-[var(--text-secondary)] leading-relaxed">{e.description}</p>
          )}

          {/* Columns table */}
          <section>
            <p className="text-[10px] font-semibold uppercase tracking-wide text-[var(--text-tertiary)] mb-1">
              Columns ({e.columns?.length ?? 0})
            </p>
            {e.columns?.length ? (
              <div className="overflow-x-auto rounded border border-[var(--border-subtle)]">
                <table className="w-full text-[10px]">
                  <thead className="bg-[var(--bg-elevated)]/70">
                    <tr>
                      <th className="text-left px-2 py-1 font-semibold text-[var(--text-secondary)]">Name</th>
                      <th className="text-left px-2 py-1 font-semibold text-[var(--text-secondary)]">Type</th>
                      <th className="text-left px-2 py-1 font-semibold text-[var(--text-secondary)]">Nullable</th>
                      <th className="text-left px-2 py-1 font-semibold text-[var(--text-secondary)]">Sensitivity</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border-subtle)]">
                    {e.columns.map((col, i) => {
                      const c = col as Record<string, unknown>
                      const name = (c['name'] as string) ?? '—'
                      const type = (c['type'] as string) ?? '—'
                      const length = c['length']
                      const nullable = c['nullable']
                      const sensitivity = c['sensitivity'] as string | undefined
                      const pk = primaryKeys.includes(name)
                      return (
                        <tr key={i}>
                          <td className="px-2 py-1 font-mono text-[var(--text-primary)]">
                            <span className="inline-flex items-center gap-1">
                              {pk && <Key size={9} className="text-amber-600" />}
                              {name}
                            </span>
                          </td>
                          <td className="px-2 py-1 font-mono text-[var(--text-secondary)]">
                            {type}{length ? `(${length})` : ''}
                          </td>
                          <td className="px-2 py-1 text-[var(--text-secondary)]">
                            {nullable === true ? 'yes' : nullable === false ? 'no' : '—'}
                          </td>
                          <td className="px-2 py-1 text-[var(--text-secondary)]">
                            {sensitivity ?? '—'}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-[10px] text-[var(--text-tertiary)] italic">(no columns defined)</p>
            )}
          </section>

          <JsonBlock title="Keys & constraints" payload={e.keys_constraints} />
          <JsonBlock title="Indexes" payload={e.indexes} />
          <JsonBlock title="Relationships" payload={e.relationships} />

          {e.access_logic && (
            <section>
              <p className="text-[10px] font-semibold uppercase tracking-wide text-[var(--text-tertiary)] mb-1">
                Access logic
              </p>
              <p className="text-[var(--text-secondary)] leading-relaxed whitespace-pre-line">
                {e.access_logic}
              </p>
            </section>
          )}
          <JsonBlock title="Cache spec" payload={e.cache_spec} />
          {e.retention_policy && (
            <section>
              <p className="text-[10px] font-semibold uppercase tracking-wide text-[var(--text-tertiary)] mb-1">
                Retention
              </p>
              <p className="text-[var(--text-secondary)]">{e.retention_policy}</p>
            </section>
          )}
        </div>
      )}

      {editing && (
        <FrsRowEditDialog
          open
          title={`Edit entity — ${e.entity_name}`}
          projectId={projectId}
          table="frs_data_entities"
          rowId={e.id}
          initialValues={{
            entity_name: e.entity_name,
            data_store_type: e.data_store_type,
            description: e.description,
            expected_volume: e.expected_volume,
            columns: e.columns,
            keys_constraints: e.keys_constraints,
            indexes: e.indexes,
            relationships: e.relationships,
            access_logic: e.access_logic,
            cache_spec: e.cache_spec,
            retention_policy: e.retention_policy,
          }}
          fields={DATA_ENTITY_FIELDS}
          isLocked={e.is_locked}
          onClose={() => setEditing(false)}
          onSaved={() => { setEditing(false); onMutate() }}
        />
      )}
    </div>
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
