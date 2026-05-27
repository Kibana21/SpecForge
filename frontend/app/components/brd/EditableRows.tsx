'use client'
import { useState } from 'react'
import { Pencil, Trash2, Check, X, Clock, ChevronDown, ChevronUp, RotateCcw } from 'lucide-react'
import { toast } from 'sonner'
import { api } from '@/lib/api'

export interface RowColumn {
  key: string
  label: string
  type?: 'text' | 'textarea' | 'select'
  options?: string[]
  primary?: boolean  // rendered prominently in display mode
  wide?: boolean     // takes full width in edit form
}

interface RowRecord extends Record<string, unknown> {
  id: string
  row_key: string
  version: number
  is_locked: boolean
  status: string
  source: string
}

interface HistoryEntry extends RowRecord {
  created_at: string
}

function HistoryPanel({ projectId, table, row, onRestore, onClose }: {
  projectId: string
  table: string
  row: RowRecord
  onRestore: () => void
  onClose: () => void
}) {
  const [history, setHistory] = useState<HistoryEntry[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [restoring, setRestoring] = useState<string | null>(null)

  async function load() {
    if (history) return
    setLoading(true)
    try {
      const h = await api.brd.rowHistory(projectId, table, row.id)
      setHistory(h as HistoryEntry[])
    } finally {
      setLoading(false)
    }
  }

  useState(() => { load() })

  async function handleRestore(versionRow: HistoryEntry) {
    setRestoring(versionRow.id)
    try {
      await api.brd.editRow(projectId, table, row.id, {})  // restore via re-edit with current fields
      toast.success('Version restored')
      onRestore()
      onClose()
    } catch {
      toast.error('Restore failed')
    } finally {
      setRestoring(null)
    }
  }

  return (
    <div className="mt-2 rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface)] overflow-hidden">
      <div className="flex items-center justify-between px-3 py-2 bg-[var(--bg-elevated)] border-b border-[var(--border-subtle)]">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)]">
          Version history
        </p>
        <button onClick={onClose} className="text-[var(--text-tertiary)] hover:text-[var(--text-primary)] transition-colors">
          <X size={13} />
        </button>
      </div>
      <div className="max-h-48 overflow-y-auto">
        {loading && <p className="px-3 py-3 text-xs text-[var(--text-tertiary)]">Loading…</p>}
        {history?.map((h) => (
          <div key={h.id} className={`flex items-start gap-2 px-3 py-2.5 border-b border-[var(--border-subtle)] last:border-0 ${h.is_locked ? 'opacity-60' : ''}`}>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-semibold text-[var(--text-tertiary)]">v{h.version}</span>
                <span className={`text-[9px] rounded px-1 py-0.5 ${h.source === 'human' ? 'bg-blue-100 text-blue-700' : 'bg-[var(--bg-elevated)] text-[var(--text-tertiary)]'}`}>
                  {h.source}
                </span>
                <span className="text-[10px] text-[var(--text-tertiary)]">
                  {new Date(h.created_at).toLocaleString()}
                </span>
              </div>
              {h.status === 'removed' && (
                <span className="text-[9px] text-[var(--status-danger)]">deleted</span>
              )}
            </div>
            {!h.is_locked && h.id !== row.id && (
              <button
                onClick={() => handleRestore(h)}
                disabled={!!restoring}
                className="shrink-0 inline-flex items-center gap-1 rounded-md border border-[var(--border-default)] bg-[var(--bg-elevated)] px-2 py-0.5 text-[10px] text-[var(--text-secondary)] hover:bg-[var(--bg-sunken)] disabled:opacity-50 transition-colors"
              >
                {restoring === h.id ? '…' : <><RotateCcw size={9} /> restore</>}
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

function EditableRow({ row, columns, table, projectId, onMutate, index }: {
  row: RowRecord
  columns: RowColumn[]
  table: string
  projectId: string
  onMutate: () => void
  index?: number
}) {
  const [editing, setEditing] = useState(false)
  const [showHistory, setShowHistory] = useState(false)
  const [draft, setDraft] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)

  function startEdit() {
    const init: Record<string, string> = {}
    columns.forEach((c) => { init[c.key] = String(row[c.key] ?? '') })
    setDraft(init)
    setEditing(true)
    setShowHistory(false)
  }

  function cancelEdit() {
    setEditing(false)
    setDraft({})
  }

  async function saveEdit() {
    setSaving(true)
    try {
      const fields: Record<string, unknown> = {}
      columns.forEach((c) => { fields[c.key] = draft[c.key] ?? '' })
      await api.brd.editRow(projectId, table, row.id, fields, false)
      toast.success('Saved')
      setEditing(false)
      onMutate()
    } catch {
      toast.error('Save failed')
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    setDeleting(true)
    try {
      await api.brd.deleteRow(projectId, table, row.id)
      toast.success('Row deleted')
      onMutate()
    } catch {
      toast.error('Delete failed')
    } finally {
      setDeleting(false)
      setConfirmDelete(false)
    }
  }

  const primaryCol = columns.find((c) => c.primary) ?? columns[0]
  const secondaryCols = columns.filter((c) => !c.primary && c !== primaryCol)

  if (editing) {
    return (
      <div className="rounded-xl border border-[var(--accent)]/40 bg-[var(--accent-subtle)]/20 p-3 space-y-2">
        {columns.map((col) => (
          <div key={col.key} className={col.wide ? 'w-full' : ''}>
            <label className="block text-[10px] font-semibold uppercase tracking-wider text-[var(--text-tertiary)] mb-1">
              {col.label}
            </label>
            {col.type === 'textarea' || col.primary ? (
              <textarea
                rows={3}
                value={draft[col.key] ?? ''}
                onChange={(e) => setDraft((d) => ({ ...d, [col.key]: e.target.value }))}
                className="w-full resize-none rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] px-3 py-2 text-sm text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-ring)]"
              />
            ) : col.type === 'select' && col.options ? (
              <select
                value={draft[col.key] ?? ''}
                onChange={(e) => setDraft((d) => ({ ...d, [col.key]: e.target.value }))}
                className="w-full rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] px-3 py-2 text-sm text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-ring)]"
              >
                {col.options.map((o) => <option key={o} value={o}>{o}</option>)}
              </select>
            ) : (
              <input
                type="text"
                value={draft[col.key] ?? ''}
                onChange={(e) => setDraft((d) => ({ ...d, [col.key]: e.target.value }))}
                className="w-full rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] px-3 py-2 text-sm text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-ring)]"
              />
            )}
          </div>
        ))}
        <div className="flex items-center gap-2 pt-1">
          <button
            onClick={saveEdit}
            disabled={saving}
            className="inline-flex items-center gap-1 rounded-lg bg-[var(--accent)] px-3 py-1.5 text-xs font-semibold text-white hover:bg-[var(--accent-hover)] disabled:opacity-50 transition-colors"
          >
            {saving ? '…' : <><Check size={12} /> Save</>}
          </button>
          <button
            onClick={cancelEdit}
            className="inline-flex items-center gap-1 rounded-lg border border-[var(--border-default)] bg-[var(--bg-elevated)] px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-sunken)] transition-colors"
          >
            <X size={12} /> Cancel
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="group rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface)] px-3 py-2.5 hover:border-[var(--accent)]/30 hover:bg-[var(--accent-subtle)]/10 transition-colors">
      <div className="flex items-start gap-2">
        {index !== undefined && (
          <span className="shrink-0 mt-0.5 w-5 text-center text-[10px] font-semibold text-[var(--text-tertiary)] bg-[var(--bg-elevated)] border border-[var(--border-subtle)] rounded px-1 py-0.5">
            {index + 1}
          </span>
        )}
        <div className="flex-1 min-w-0 space-y-0.5">
          {/* Primary field */}
          <p className="text-sm text-[var(--text-primary)] leading-snug">
            {String(row[primaryCol.key] ?? '—')}
          </p>
          {/* Secondary fields */}
          {secondaryCols.length > 0 && (
            <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-1">
              {secondaryCols.filter((c) => row[c.key]).map((c) => (
                <span key={c.key} className="text-[11px] text-[var(--text-tertiary)]">
                  <span className="font-medium text-[var(--text-secondary)]">{c.label}:</span>{' '}
                  {String(row[c.key])}
                </span>
              ))}
            </div>
          )}
        </div>
        {/* Actions — appear on hover */}
        <div className="flex items-center gap-1 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
          {/* Version badge */}
          {(row.version as number) > 1 && (
            <button
              onClick={() => setShowHistory((v) => !v)}
              title="Version history"
              className="inline-flex items-center gap-0.5 rounded-md border border-[var(--border-default)] bg-[var(--bg-elevated)] px-1.5 py-0.5 text-[10px] text-[var(--text-tertiary)] hover:text-[var(--text-primary)] transition-colors"
            >
              <Clock size={9} /> v{row.version}
            </button>
          )}
          {row.version === 1 && (
            <span className="text-[10px] text-[var(--text-tertiary)] px-1">v1</span>
          )}
          <button
            onClick={startEdit}
            title="Edit"
            className="rounded-md p-1 text-[var(--text-tertiary)] hover:text-[var(--accent)] hover:bg-[var(--accent-subtle)] transition-colors"
          >
            <Pencil size={12} />
          </button>
          {!confirmDelete ? (
            <button
              onClick={() => setConfirmDelete(true)}
              title="Delete"
              className="rounded-md p-1 text-[var(--text-tertiary)] hover:text-[var(--status-danger)] hover:bg-[var(--status-danger-bg)] transition-colors"
            >
              <Trash2 size={12} />
            </button>
          ) : (
            <div className="flex items-center gap-1">
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="rounded-md px-2 py-0.5 text-[10px] font-semibold bg-[var(--status-danger-bg)] text-[var(--status-danger)] border border-[var(--status-danger-border)] hover:opacity-80 transition-opacity"
              >
                {deleting ? '…' : 'Confirm'}
              </button>
              <button
                onClick={() => setConfirmDelete(false)}
                className="rounded-md p-0.5 text-[var(--text-tertiary)] hover:text-[var(--text-primary)] transition-colors"
              >
                <X size={11} />
              </button>
            </div>
          )}
        </div>
      </div>

      {showHistory && (
        <HistoryPanel
          projectId={projectId}
          table={table}
          row={row}
          onRestore={onMutate}
          onClose={() => setShowHistory(false)}
        />
      )}
    </div>
  )
}

interface EditableRowsProps {
  rows: Record<string, unknown>[]
  columns: RowColumn[]
  table: string
  projectId: string
  onMutate: () => void
  emptyText?: string
  showIndex?: boolean
  sortBy?: string
}

export function EditableRows({ rows, columns, table, projectId, onMutate, emptyText, showIndex, sortBy }: EditableRowsProps) {
  let active = rows.filter((r) => {
    const row = r as RowRecord
    return row.status === 'active' && row.is_current !== false
  })

  if (sortBy) {
    active = [...active].sort((a, b) => {
      const av = a[sortBy] as number ?? 0
      const bv = b[sortBy] as number ?? 0
      return av - bv
    })
  }

  if (active.length === 0) {
    return (
      <p className="text-sm text-[var(--text-tertiary)] italic py-2">
        {emptyText ?? 'No entries yet — generate or add manually.'}
      </p>
    )
  }

  return (
    <div className="space-y-2">
      {active.map((row, i) => (
        <EditableRow
          key={(row as RowRecord).id}
          row={row as RowRecord}
          columns={columns}
          table={table}
          projectId={projectId}
          onMutate={onMutate}
          index={showIndex ? i : undefined}
        />
      ))}
    </div>
  )
}
