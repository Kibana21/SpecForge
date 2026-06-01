'use client'

import { useState } from 'react'
import { X, Plus, Trash2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { NfrBrdLink } from '@/lib/types'

export interface NfrField {
  key: string
  label: string
  type?: 'text' | 'textarea' | 'select'
  options?: { value: string; label: string }[]
  wide?: boolean
}

export interface BrdOption { kind: string; ref: string; label: string }

interface Props {
  title: string
  fields: NfrField[]
  initial?: Record<string, unknown>
  /** When provided, shows a BRD-link picker (requirement add). */
  brdOptions?: BrdOption[]
  initialLinks?: NfrBrdLink[]
  requireLink?: boolean
  busy?: boolean
  onClose: () => void
  onSubmit: (values: Record<string, unknown>, links: NfrBrdLink[]) => void
}

export function NfrRowDialog({
  title, fields, initial = {}, brdOptions, initialLinks = [], requireLink = false,
  busy = false, onClose, onSubmit,
}: Props) {
  const [values, setValues] = useState<Record<string, unknown>>(() => {
    const v: Record<string, unknown> = {}
    for (const f of fields) v[f.key] = (initial[f.key] as string) ?? ''
    return v
  })
  const [links, setLinks] = useState<NfrBrdLink[]>(initialLinks)

  const canSubmit = (!requireLink || links.length > 0) && !busy

  function set(k: string, val: string) {
    setValues((p) => ({ ...p, [k]: val }))
  }

  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/20 backdrop-blur-[2px]" onClick={onClose} aria-hidden />
      <div role="dialog" aria-modal
           className="fixed left-1/2 top-1/2 z-50 w-[560px] max-w-[95vw] max-h-[88vh] -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface)] shadow-[var(--shadow-lg)]">
        <div className="flex items-center justify-between border-b border-[var(--border-default)] px-4 py-3">
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">{title}</h2>
          <button onClick={onClose} className="text-[var(--text-tertiary)] hover:text-[var(--text-primary)]"><X size={16} /></button>
        </div>

        <div className="grid grid-cols-2 gap-3 p-4">
          {fields.map((f) => (
            <div key={f.key} className={cn('flex flex-col gap-1', (f.wide || f.type === 'textarea') && 'col-span-2')}>
              <label className="text-[11px] font-medium text-[var(--text-secondary)]">{f.label}</label>
              {f.type === 'textarea' ? (
                <textarea
                  value={String(values[f.key] ?? '')} onChange={(e) => set(f.key, e.target.value)} rows={3}
                  className="rounded-md border border-[var(--border-default)] bg-[var(--bg-elevated)] px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-[var(--accent-ring)]"
                />
              ) : f.type === 'select' ? (
                <select
                  value={String(values[f.key] ?? '')} onChange={(e) => set(f.key, e.target.value)}
                  className="rounded-md border border-[var(--border-default)] bg-[var(--bg-elevated)] px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-[var(--accent-ring)]"
                >
                  <option value="">—</option>
                  {f.options?.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              ) : (
                <input
                  value={String(values[f.key] ?? '')} onChange={(e) => set(f.key, e.target.value)}
                  className="rounded-md border border-[var(--border-default)] bg-[var(--bg-elevated)] px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-[var(--accent-ring)]"
                />
              )}
            </div>
          ))}

          {brdOptions && (
            <div className="col-span-2 flex flex-col gap-1.5">
              <label className="text-[11px] font-medium text-[var(--text-secondary)]">
                Trace to BRD {requireLink && <span className="text-red-500">*</span>}
              </label>
              <div className="flex flex-wrap gap-1.5">
                {links.map((l, i) => (
                  <span key={i} className="inline-flex items-center gap-1 rounded bg-pink-50 px-1.5 py-0.5 text-[10px] text-pink-700">
                    {l.target_ref}
                    <button onClick={() => setLinks((p) => p.filter((_, j) => j !== i))}><Trash2 size={10} /></button>
                  </span>
                ))}
              </div>
              <select
                value=""
                onChange={(e) => {
                  const opt = brdOptions.find((o) => o.ref === e.target.value)
                  if (opt && !links.some((l) => l.target_ref === opt.ref)) {
                    setLinks((p) => [...p, { target_kind: opt.kind as NfrBrdLink['target_kind'], target_ref: opt.ref, target_label: opt.label }])
                  }
                }}
                className="rounded-md border border-[var(--border-default)] bg-[var(--bg-elevated)] px-2 py-1.5 text-xs"
              >
                <option value="">+ Link a BRD objective / requirement…</option>
                {brdOptions.map((o) => <option key={o.ref} value={o.ref}>{o.ref} — {o.label}</option>)}
              </select>
            </div>
          )}
        </div>

        <div className="flex justify-end gap-2 border-t border-[var(--border-default)] px-4 py-3">
          <button onClick={onClose} className="rounded-md px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]">Cancel</button>
          <button
            disabled={!canSubmit}
            onClick={() => onSubmit(values, links)}
            className="inline-flex items-center gap-1 rounded-md bg-[var(--accent)] px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50"
          >
            <Plus size={12} /> Save
          </button>
        </div>
      </div>
    </>
  )
}
