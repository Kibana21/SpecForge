'use client'

import { useState } from 'react'
import { toast } from 'sonner'
import { Pencil, Lock, Unlock, Trash2, Plus } from 'lucide-react'
import { api } from '@/lib/api'
import type { NfrRow } from '@/lib/types'
import { NFR_GOVERNANCE_SECTIONS } from '@/lib/nfr-manifest'
import { NfrRowDialog, type NfrField } from './NfrRowDialog'

interface Props {
  projectId: string
  table: string
  rows: NfrRow[]
  onMutate: () => void
}

export function NfrGovernancePanel({ projectId, table, rows, onMutate }: Props) {
  const section = NFR_GOVERNANCE_SECTIONS.find((s) => s.table === table)
  const [dialog, setDialog] = useState<{ mode: 'add' | 'edit'; row?: NfrRow } | null>(null)
  const [busy, setBusy] = useState(false)
  if (!section) return null

  const fields: NfrField[] = section.columns.map((c) => ({
    key: c.key, label: c.label, type: c.wide ? 'textarea' : 'text', wide: c.wide,
  }))
  const sorted = [...rows].sort((a, b) => a.row_key.localeCompare(b.row_key))

  async function act(fn: () => Promise<unknown>, ok: string) {
    setBusy(true)
    try { await fn(); toast.success(ok); onMutate() }
    catch (e) { toast.error(e instanceof Error ? e.message : 'Failed') }
    finally { setBusy(false) }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="mb-2 flex shrink-0 items-center justify-between">
        <h3 className="text-sm font-semibold text-[var(--text-primary)]">{section.emoji} {section.label}</h3>
        <button onClick={() => setDialog({ mode: 'add' })}
                className="inline-flex items-center gap-1 rounded-md border border-[var(--border-default)] px-2 py-1 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]">
          <Plus size={12} /> Add row
        </button>
      </div>

      {sorted.length === 0 ? (
        <p className="py-8 text-center text-xs text-[var(--text-tertiary)]">No {section.label.toLowerCase()} yet.</p>
      ) : (
        <div className="flex-1 overflow-auto rounded-lg border border-[var(--border-subtle)]">
          <table className="w-full table-fixed text-xs">
            <colgroup>
              <col className="w-[88px]" />
              {section.columns.map((c) => <col key={c.key} className={c.wide ? 'w-auto' : 'w-[120px]'} />)}
              <col className="w-[44px]" />
            </colgroup>
            <thead className="sticky top-0 z-10 bg-[var(--bg-elevated)] text-[10px] uppercase tracking-wide text-[var(--text-secondary)] shadow-[0_1px_0_var(--border-subtle)]">
              <tr>
                <th className="px-2 py-1.5 text-left font-bold">Key</th>
                {section.columns.map((c) => <th key={c.key} className="px-2 py-1.5 text-left font-bold">{c.label}</th>)}
                <th />
              </tr>
            </thead>
            <tbody>
              {sorted.map((r) => (
                <tr key={r.id} className="group border-t border-[var(--border-subtle)] align-top">
                  <td className="px-2 py-1.5 font-mono text-[10px] text-[var(--text-secondary)]">
                    {r.row_key}{r.is_locked && <Lock size={9} className="ml-1 inline text-[var(--text-tertiary)]" />}
                  </td>
                  {section.columns.map((c) => <td key={c.key} className="px-2 py-1.5 break-words leading-snug">{String((r as Record<string, unknown>)[c.key] ?? '')}</td>)}
                  <td className="px-2 py-1.5 whitespace-nowrap text-right opacity-0 group-hover:opacity-100">
                    <button title="Edit" onClick={() => setDialog({ mode: 'edit', row: r })} className="p-1 text-[var(--text-tertiary)] hover:text-[var(--text-primary)]"><Pencil size={12} /></button>
                    {r.is_locked
                      ? <button title="Unlock" onClick={() => act(() => api.nfr.unlockRow(projectId, table, r.id), 'Unlocked')} className="p-1 text-[var(--text-tertiary)] hover:text-[var(--text-primary)]"><Unlock size={12} /></button>
                      : <button title="Delete" onClick={() => act(() => api.nfr.deleteRow(projectId, table, r.id), 'Deleted')} className="p-1 text-[var(--text-tertiary)] hover:text-red-600"><Trash2 size={12} /></button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {dialog && (
        <NfrRowDialog
          title={dialog.mode === 'add' ? `Add ${section.label}` : `Edit ${dialog.row?.row_key}`}
          fields={fields}
          initial={dialog.mode === 'edit' ? (dialog.row as Record<string, unknown>) : {}}
          busy={busy}
          onClose={() => setDialog(null)}
          onSubmit={(values) => act(async () => {
            if (dialog.mode === 'add') await api.nfr.addRow(projectId, table, values)
            else await api.nfr.editRow(projectId, table, dialog.row!.id, values)
            setDialog(null)
          }, dialog.mode === 'add' ? 'Row added' : 'Row updated')}
        />
      )}
    </div>
  )
}
