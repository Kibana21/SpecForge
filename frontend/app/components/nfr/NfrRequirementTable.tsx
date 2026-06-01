'use client'

import { useState } from 'react'
import { toast } from 'sonner'
import { Pencil, Lock, Unlock, Trash2, Plus, AlertTriangle } from 'lucide-react'
import { api } from '@/lib/api'
import type { NfrCategory, NfrRow } from '@/lib/types'
import { NFR_PRIORITY_STYLES, NFR_CATEGORY_LABEL } from '@/lib/nfr-manifest'
import { cn } from '@/lib/utils'
import { NfrTraceChip } from './NfrTraceChip'
import { NfrRowDialog, type BrdOption } from './NfrRowDialog'

interface Props {
  projectId: string
  category: NfrCategory
  rows: NfrRow[]
  tracesBySource: Record<string, { target_kind: string; target_ref: string; target_label: string; confidence: string }[]>
  brdOptions: BrdOption[]
  onMutate: () => void
}

const TABLE = 'nfr_requirements'

const PRIORITY_OPTIONS = [
  { value: 'must', label: 'Must' }, { value: 'should', label: 'Should' },
  { value: 'could', label: 'Could' }, { value: 'wont', label: "Won't" },
]
const CATEGORY_OPTIONS = (Object.keys(NFR_CATEGORY_LABEL) as NfrCategory[]).map((k) => ({ value: k, label: NFR_CATEGORY_LABEL[k] }))

const FIELDS = [
  { key: 'category', label: 'Category', type: 'select' as const, options: CATEGORY_OPTIONS },
  { key: 'priority', label: 'Priority', type: 'select' as const, options: PRIORITY_OPTIONS },
  { key: 'attribute', label: 'Attribute', type: 'text' as const },
  { key: 'requirement', label: 'Requirement', type: 'textarea' as const },
  { key: 'measurement', label: 'Measurement (metric + threshold)', type: 'text' as const, wide: true },
  { key: 'rationale', label: 'Rationale', type: 'textarea' as const },
]

export function NfrRequirementTable({ projectId, category, rows, tracesBySource, brdOptions, onMutate }: Props) {
  const [dialog, setDialog] = useState<{ mode: 'add' | 'edit'; row?: NfrRow } | null>(null)
  const [busy, setBusy] = useState(false)
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
        <h3 className="text-sm font-semibold text-[var(--text-primary)]">{NFR_CATEGORY_LABEL[category]}</h3>
        <button onClick={() => setDialog({ mode: 'add' })}
                className="inline-flex items-center gap-1 rounded-md border border-[var(--border-default)] px-2 py-1 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]">
          <Plus size={12} /> Add NFR
        </button>
      </div>

      {sorted.length === 0 ? (
        <p className="py-8 text-center text-xs text-[var(--text-tertiary)]">No requirements yet in this category.</p>
      ) : (
        <div className="flex-1 overflow-auto rounded-lg border border-[var(--border-subtle)]">
          <table className="w-full table-fixed text-xs">
            <colgroup>
              <col className="w-[52px]" />
              <col className="w-[140px]" />
              <col className="w-[34%]" />
              <col className="w-[24%]" />
              <col className="w-[68px]" />
              <col className="w-[120px]" />
              <col className="w-[44px]" />
            </colgroup>
            <thead className="sticky top-0 z-10 bg-[var(--bg-elevated)] text-[10px] uppercase tracking-wide text-[var(--text-secondary)] shadow-[0_1px_0_var(--border-subtle)]">
              <tr>
                <th className="px-2 py-1.5 text-left font-bold">NFR</th>
                <th className="px-2 py-1.5 text-left font-bold">Attribute</th>
                <th className="px-2 py-1.5 text-left font-bold">Requirement</th>
                <th className="px-2 py-1.5 text-left font-bold">Measurement</th>
                <th className="px-2 py-1.5 text-left font-bold">Priority</th>
                <th className="px-2 py-1.5 text-left font-bold">Traces</th>
                <th className="px-2 py-1.5"></th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((r) => {
                const pr = NFR_PRIORITY_STYLES[(r.priority ?? 'should') as keyof typeof NFR_PRIORITY_STYLES]
                const noMeasure = !r.na && !(r.measurement && String(r.measurement).trim())
                const traces = tracesBySource[r.row_key] ?? []
                return (
                  <tr key={r.id} className={cn('group border-t border-[var(--border-subtle)] align-top',
                    noMeasure && 'border-l-2 border-l-amber-400')}>
                    <td className="px-2 py-1.5 font-mono text-[10px] text-[var(--text-secondary)]">
                      {r.row_key}{r.is_locked && <Lock size={9} className="ml-1 inline text-[var(--text-tertiary)]" />}
                    </td>
                    <td className="px-2 py-1.5 break-words">{String(r.attribute ?? '')}</td>
                    <td className="px-2 py-1.5 break-words leading-snug">
                      {r.na ? <em className="text-[var(--text-tertiary)]">N/A — {String(r.rationale ?? '')}</em> : String(r.requirement ?? '')}
                    </td>
                    <td className="px-2 py-1.5 break-words leading-snug text-[var(--text-secondary)]">
                      {String(r.measurement ?? '') || (noMeasure && <span className="inline-flex items-center gap-1 text-amber-600"><AlertTriangle size={10} /> needs metric</span>)}
                    </td>
                    <td className="px-2 py-1.5">
                      {!r.na && <span className={cn('rounded px-1.5 py-0.5 text-[10px] font-medium', pr.bg, pr.text)}>{pr.label}</span>}
                    </td>
                    <td className="px-2 py-1.5">
                      <div className="flex flex-wrap gap-1">
                        {traces.map((t, i) => <NfrTraceChip key={i} kind={t.target_kind} targetRef={t.target_ref} targetLabel={t.target_label} confidence={t.confidence} />)}
                      </div>
                    </td>
                    <td className="px-2 py-1.5 whitespace-nowrap text-right opacity-0 group-hover:opacity-100">
                      <button title="Edit" onClick={() => setDialog({ mode: 'edit', row: r })} className="p-1 text-[var(--text-tertiary)] hover:text-[var(--text-primary)]"><Pencil size={12} /></button>
                      {r.is_locked
                        ? <button title="Unlock" onClick={() => act(() => api.nfr.unlockRow(projectId, TABLE, r.id), 'Unlocked')} className="p-1 text-[var(--text-tertiary)] hover:text-[var(--text-primary)]"><Unlock size={12} /></button>
                        : <button title="Delete" onClick={() => act(() => api.nfr.deleteRow(projectId, TABLE, r.id), 'Deleted')} className="p-1 text-[var(--text-tertiary)] hover:text-red-600"><Trash2 size={12} /></button>}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {dialog && (
        <NfrRowDialog
          title={dialog.mode === 'add' ? 'Add NFR' : `Edit ${dialog.row?.row_key}`}
          fields={FIELDS}
          initial={dialog.mode === 'edit' ? (dialog.row as Record<string, unknown>) : { category }}
          brdOptions={dialog.mode === 'add' ? brdOptions : undefined}
          requireLink={dialog.mode === 'add'}
          busy={busy}
          onClose={() => setDialog(null)}
          onSubmit={(values, links) => act(async () => {
            if (dialog.mode === 'add') await api.nfr.addRow(projectId, TABLE, values, links)
            else await api.nfr.editRow(projectId, TABLE, dialog.row!.id, values)
            setDialog(null)
          }, dialog.mode === 'add' ? 'NFR added' : 'NFR updated')}
        />
      )}
    </div>
  )
}
