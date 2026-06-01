'use client'

import { X, CheckCircle2 } from 'lucide-react'
import type { NfrFindingsResponse } from '@/lib/types'
import { NFR_FINDING_GROUPS } from '@/lib/nfr-manifest'
import { cn } from '@/lib/utils'

interface Props {
  open: boolean
  findings: NfrFindingsResponse | null
  validating: boolean
  onClose: () => void
  onValidate: () => void
}

export function NfrFindingsDrawer({ open, findings, validating, onClose, onValidate }: Props) {
  if (!open) return null
  const list = findings?.findings ?? []
  const blocking = list.filter((f) => f.group === 'critical' || f.group === 'major').length
  const grouped = NFR_FINDING_GROUPS.map((g) => ({ ...g, items: list.filter((f) => f.group === g.key) }))

  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/20 backdrop-blur-[2px]" onClick={onClose} aria-hidden />
      <aside role="dialog" aria-modal
             className="fixed right-0 top-0 bottom-0 z-50 flex w-[460px] max-w-[100vw] flex-col border-l border-[var(--border-default)] bg-[var(--bg-surface)] shadow-[var(--shadow-lg)]">
        <div className="flex items-start gap-3 border-b border-[var(--border-default)] px-4 py-3">
          <div className="flex-1">
            <h2 className="text-base font-semibold text-[var(--text-primary)]">NFR Findings</h2>
            <p className="mt-0.5 text-[11px] text-[var(--text-tertiary)]">{list.length} total · {blocking} blocking</p>
          </div>
          <button onClick={onClose} className="text-[var(--text-tertiary)] hover:text-[var(--text-primary)]"><X size={16} /></button>
        </div>

        <div className="flex-1 overflow-y-auto p-3">
          {list.length === 0 ? (
            <div className="flex flex-col items-center gap-2 py-12 text-center text-xs text-[var(--text-tertiary)]">
              <CheckCircle2 size={28} className="text-emerald-500" />
              No findings — the NFR document passes all checks.
            </div>
          ) : grouped.filter((g) => g.items.length).map((g) => (
            <div key={g.key} className="mb-3">
              <div className={cn('mb-1 inline-block rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase', g.cls)}>
                {g.label} · {g.items.length}
              </div>
              <div className="space-y-1.5">
                {g.items.map((f, i) => (
                  <div key={i} className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] px-2.5 py-2">
                    <p className="text-xs text-[var(--text-primary)]">{f.description}</p>
                    {f.suggested_fix && <p className="mt-1 text-[10px] text-[var(--text-tertiary)]">→ {f.suggested_fix}</p>}
                    {f.row_key && <span className="mt-1 inline-block font-mono text-[9px] text-[var(--text-tertiary)]">{f.row_key}</span>}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        <div className="border-t border-[var(--border-default)] px-4 py-3">
          <button
            disabled={validating}
            onClick={onValidate}
            className="w-full rounded-md bg-[var(--accent)] px-3 py-2 text-xs font-medium text-white disabled:opacity-50"
          >
            {validating ? 'Validating…' : blocking > 0 ? `Re-check (${blocking} blocking)` : 'Validate NFR ✓'}
          </button>
        </div>
      </aside>
    </>
  )
}
