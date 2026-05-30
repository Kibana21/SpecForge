'use client'
/**
 * §1.2 UI Component card — one per `frs_ui_components` row. Compact header
 * (name · type · screen) + expandable JSON sub-blob sections (Definition,
 * Behavior, Validation, Actions, Data mapping). Edit dialog uses JSON field
 * type for each sub-blob.
 */
import { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { FrsUiComponentRow } from '@/lib/types'
import { FrsRowEditDialog, type FrsRowField } from './FrsRowEditDialog'
import { FrsRowActions } from './FrsRowActions'
import { useFrsRowOps } from './useFrsRowOps'

const COMPONENT_TYPE_OPTIONS = [
  'input', 'textarea', 'dropdown', 'multi_select',
  'checkbox', 'radio', 'button', 'link',
  'table', 'card', 'tab', 'modal', 'accordion',
  'date_picker', 'file_upload',
].map(v => ({ value: v, label: v }))

const COMPONENT_FIELDS: FrsRowField[] = [
  { name: 'component_name', label: 'Component name', type: 'text' },
  { name: 'component_type', label: 'Component type', type: 'enum',
    options: COMPONENT_TYPE_OPTIONS },
  { name: 'screen_row_key', label: 'Screen row_key', type: 'text',
    placeholder: 'M001-FRS001-SCR-1' },
  { name: 'definition', label: 'Definition (JSON)', type: 'json', rows: 5 },
  { name: 'behavior', label: 'Behavior (JSON)', type: 'json', rows: 5 },
  { name: 'validation', label: 'Validation (JSON)', type: 'json', rows: 5 },
  { name: 'actions', label: 'Actions (JSON array)', type: 'json', rows: 5 },
  { name: 'data_mapping', label: 'Data mapping (JSON)', type: 'json', rows: 4 },
]

interface Props {
  projectId: string
  component: FrsUiComponentRow
  /** Optional human-readable screen name to render in the header. */
  screenLabel?: string
  onMutate: () => void
}

export function FrsUiComponentCard({ projectId, component: c, screenLabel, onMutate }: Props) {
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState(false)

  const { busy, handleLockToggle, handleDelete } = useFrsRowOps({
    projectId,
    table: 'frs_ui_components',
    rowId: c.id,
    isLocked: c.is_locked,
    lockPayload: {
      component_name: c.component_name,
      component_type: c.component_type,
      screen_row_key: c.screen_row_key,
      definition: c.definition,
      behavior: c.behavior,
      validation: c.validation,
      actions: c.actions,
      data_mapping: c.data_mapping,
    },
    label: `component "${c.component_name}"`,
    onMutate,
  })

  const isMandatory = Boolean(
    (c.definition as Record<string, unknown> | undefined)?.['mandatory'],
  )

  return (
    <div
      className={cn(
        'group rounded-lg border bg-[var(--bg-surface)] transition-colors',
        c.is_locked
          ? 'border-amber-200 ring-1 ring-amber-100/70'
          : 'border-[var(--border-default)] hover:border-[var(--accent)]/40',
      )}
    >
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2">
        <button
          onClick={() => setOpen((v) => !v)}
          className="shrink-0 rounded p-0.5 text-[var(--text-tertiary)] hover:bg-[var(--bg-elevated)] transition-colors"
          aria-label={open ? 'Collapse component' : 'Expand component'}
          aria-expanded={open}
        >
          {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        </button>
        <span className="text-sm font-medium text-[var(--text-primary)] truncate">
          {c.component_name}
        </span>
        <span className="text-[10px] rounded px-1.5 py-0.5 bg-[var(--bg-elevated)] text-[var(--text-tertiary)] font-mono">
          {c.component_type}
        </span>
        {isMandatory && (
          <span className="text-[10px] text-rose-700 bg-rose-50 border border-rose-200 rounded px-1.5 py-0.5">
            mandatory
          </span>
        )}
        {screenLabel && (
          <span className="text-[10px] text-[var(--text-tertiary)] truncate">
            on {screenLabel}
          </span>
        )}
        <div className="flex-1" />
        <FrsRowActions
          isLocked={c.is_locked}
          busy={busy}
          onEdit={() => setEditing(true)}
          onLock={handleLockToggle}
          onDelete={handleDelete}
        />
      </div>

      {open && (
        <div className="px-3 pb-2.5 space-y-1.5 border-t border-[var(--border-subtle)] pt-2">
          <JsonBlock title="Definition" payload={c.definition} />
          <JsonBlock title="Behavior" payload={c.behavior} />
          <JsonBlock title="Validation" payload={c.validation} />
          <JsonBlock title="Actions" payload={c.actions} />
          <JsonBlock title="Data mapping" payload={c.data_mapping} />
        </div>
      )}

      {editing && (
        <FrsRowEditDialog
          open
          title={`Edit component — ${c.component_name}`}
          projectId={projectId}
          table="frs_ui_components"
          rowId={c.id}
          initialValues={{
            component_name: c.component_name,
            component_type: c.component_type,
            screen_row_key: c.screen_row_key,
            definition: c.definition,
            behavior: c.behavior,
            validation: c.validation,
            actions: c.actions,
            data_mapping: c.data_mapping,
          }}
          fields={COMPONENT_FIELDS}
          isLocked={c.is_locked}
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
      <pre className="mt-1 px-2 py-1.5 bg-[var(--bg-elevated)]/60 rounded text-[10px] font-mono overflow-x-auto whitespace-pre-wrap break-words">
        {JSON.stringify(payload, null, 2)}
      </pre>
    </details>
  )
}
