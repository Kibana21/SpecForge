'use client'
/**
 * Generic row-edit modal for any FRS table row.
 *
 * Driven by a small field-schema descriptor so we don't have to write a
 * dedicated editor per row type. Supported field types: text, textarea, enum,
 * tags (comma-separated string list).
 *
 * Submission POSTs to `api.frs.editRow`, which versions the row and (optionally)
 * locks it. The caller is responsible for re-fetching the FRS detail via the
 * `onSaved` callback.
 */
import { useEffect, useState } from 'react'
import { Loader2, Lock, X } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'

export type FrsRowField =
  | { name: string; label: string; type: 'text'; placeholder?: string }
  | { name: string; label: string; type: 'textarea'; placeholder?: string; rows?: number }
  | { name: string; label: string; type: 'enum'; options: { value: string; label: string }[] }
  | { name: string; label: string; type: 'tags'; placeholder?: string }
  | { name: string; label: string; type: 'bool'; description?: string }
  | { name: string; label: string; type: 'json'; placeholder?: string; rows?: number; description?: string }

interface Props {
  open: boolean
  title: string
  projectId: string
  table: string
  rowId: string
  initialValues: Record<string, unknown>
  fields: FrsRowField[]
  /** Whether the row is currently locked (changes default of the lock checkbox). */
  isLocked?: boolean
  onClose: () => void
  onSaved: () => void
}

export function FrsRowEditDialog({
  open, title, projectId, table, rowId, initialValues, fields,
  isLocked = false, onClose, onSaved,
}: Props) {
  const [values, setValues] = useState<Record<string, unknown>>({})
  const [lock, setLock] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!open) return
    const next: Record<string, unknown> = {}
    for (const f of fields) {
      const raw = initialValues[f.name]
      if (f.type === 'tags') {
        next[f.name] = Array.isArray(raw) ? raw.join(', ') : (raw ?? '')
      } else if (f.type === 'bool') {
        next[f.name] = Boolean(raw)
      } else if (f.type === 'json') {
        // Pretty-print JSON for editing; empty/null becomes "" so the textarea is blank
        if (raw === null || raw === undefined || raw === '') {
          next[f.name] = ''
        } else if (typeof raw === 'string') {
          // Try to parse + re-stringify to pretty-print; fall back to raw if it's not JSON
          try {
            next[f.name] = JSON.stringify(JSON.parse(raw), null, 2)
          } catch {
            next[f.name] = raw
          }
        } else {
          next[f.name] = JSON.stringify(raw, null, 2)
        }
      } else {
        next[f.name] = raw ?? ''
      }
    }
    setValues(next)
    setLock(!isLocked ? true : true)
  }, [open, fields, initialValues, isLocked])

  if (!open) return null

  function setVal(name: string, v: unknown) {
    setValues((prev) => ({ ...prev, [name]: v }))
  }

  async function handleSave() {
    const payload: Record<string, unknown> = {}
    for (const f of fields) {
      const v = values[f.name]
      if (f.type === 'tags') {
        const s = typeof v === 'string' ? v : ''
        payload[f.name] = s.split(',').map((t) => t.trim()).filter(Boolean)
      } else if (f.type === 'bool') {
        payload[f.name] = Boolean(v)
      } else if (f.type === 'json') {
        const s = typeof v === 'string' ? v.trim() : ''
        if (!s) {
          payload[f.name] = null
        } else {
          try {
            payload[f.name] = JSON.parse(s)
          } catch (e) {
            toast.error(`Field "${f.label}" is not valid JSON: ${e instanceof Error ? e.message : 'parse error'}`)
            return
          }
        }
      } else {
        payload[f.name] = v
      }
    }
    setSaving(true)
    try {
      await api.frs.editRow(projectId, table, rowId, payload, { lock })
      toast.success('Saved')
      onSaved()
      onClose()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <div
        className="fixed inset-0 z-40 bg-black/30 backdrop-blur-[2px]"
        onClick={onClose}
        aria-hidden="true"
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="frs-row-edit-title"
        className="fixed inset-0 z-50 flex items-center justify-center p-4"
        onClick={onClose}
      >
        <div
          className="w-full max-w-xl rounded-2xl bg-[var(--bg-surface)] border border-[var(--border-default)] shadow-[var(--shadow-lg)] flex flex-col max-h-[90vh]"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="shrink-0 flex items-start gap-3 px-5 py-4 border-b border-[var(--border-default)]">
            <div className="flex-1">
              <h2 id="frs-row-edit-title" className="text-base font-semibold text-[var(--text-primary)]">
                {title}
              </h2>
              <p className="text-[11px] text-[var(--text-tertiary)] mt-0.5 font-mono">
                {table} · {rowId.slice(0, 8)}…
              </p>
            </div>
            <button
              onClick={onClose}
              className="rounded-md p-1 text-[var(--text-tertiary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-elevated)] transition-colors"
              aria-label="Close"
            >
              <X size={16} />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
            {fields.map((f) => (
              <FieldInput
                key={f.name}
                field={f}
                value={values[f.name]}
                onChange={(v) => setVal(f.name, v)}
              />
            ))}
          </div>

          <div className="shrink-0 border-t border-[var(--border-default)] px-5 py-3 flex items-center gap-3">
            <label className="flex items-center gap-1.5 text-xs text-[var(--text-secondary)] cursor-pointer">
              <input
                type="checkbox"
                checked={lock}
                onChange={(e) => setLock(e.target.checked)}
                className="rounded border-[var(--border-default)]"
              />
              <Lock size={11} />
              Lock after save (preserve on regenerate)
            </label>
            <div className="flex-1" />
            <button
              onClick={onClose}
              disabled={saving}
              className="rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] disabled:opacity-50 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className={cn(
                'inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors',
                'bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)] disabled:opacity-50',
              )}
            >
              {saving && <Loader2 size={12} className="animate-spin" />}
              {saving ? 'Saving…' : 'Save'}
            </button>
          </div>
        </div>
      </div>
    </>
  )
}

function FieldInput({
  field, value, onChange,
}: {
  field: FrsRowField
  value: unknown
  onChange: (v: unknown) => void
}) {
  const v = typeof value === 'string' ? value : ''
  switch (field.type) {
    case 'text':
      return (
        <div>
          <label className="block text-xs font-semibold text-[var(--text-secondary)] mb-1">
            {field.label}
          </label>
          <input
            type="text"
            value={v}
            placeholder={field.placeholder}
            onChange={(e) => onChange(e.target.value)}
            className="w-full rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/30"
          />
        </div>
      )
    case 'textarea':
      return (
        <div>
          <label className="block text-xs font-semibold text-[var(--text-secondary)] mb-1">
            {field.label}
          </label>
          <textarea
            value={v}
            placeholder={field.placeholder}
            rows={field.rows ?? 4}
            onChange={(e) => onChange(e.target.value)}
            className="w-full rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/30 resize-y leading-relaxed"
          />
        </div>
      )
    case 'enum':
      return (
        <div>
          <label className="block text-xs font-semibold text-[var(--text-secondary)] mb-1">
            {field.label}
          </label>
          <select
            value={v}
            onChange={(e) => onChange(e.target.value)}
            className="w-full rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/30"
          >
            <option value="">—</option>
            {field.options.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
      )
    case 'tags':
      return (
        <div>
          <label className="block text-xs font-semibold text-[var(--text-secondary)] mb-1">
            {field.label}
          </label>
          <input
            type="text"
            value={v}
            placeholder={field.placeholder ?? 'comma, separated, list'}
            onChange={(e) => onChange(e.target.value)}
            className="w-full rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/30 font-mono"
          />
          <p className="mt-1 text-[10px] text-[var(--text-tertiary)]">
            Separate values with commas.
          </p>
        </div>
      )
    case 'bool':
      return (
        <div>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={Boolean(value)}
              onChange={(e) => onChange(e.target.checked)}
              className="rounded border-[var(--border-default)]"
            />
            <span className="text-sm font-semibold text-[var(--text-secondary)]">{field.label}</span>
          </label>
          {field.description && (
            <p className="mt-1 ml-6 text-[10px] text-[var(--text-tertiary)]">
              {field.description}
            </p>
          )}
        </div>
      )
    case 'json':
      return (
        <div>
          <label className="block text-xs font-semibold text-[var(--text-secondary)] mb-1">
            {field.label}
          </label>
          <textarea
            value={v}
            placeholder={field.placeholder ?? '{ }'}
            rows={field.rows ?? 6}
            onChange={(e) => onChange(e.target.value)}
            spellCheck={false}
            className="w-full rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] px-3 py-1.5 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/30 resize-y leading-snug"
          />
          <p className="mt-1 text-[10px] text-[var(--text-tertiary)]">
            {field.description ?? 'JSON — empty or null clears the field.'}
          </p>
        </div>
      )
  }
}
