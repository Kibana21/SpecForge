'use client'

import type { NfrCategory, NfrRow } from '@/lib/types'
import { NFR_CATEGORIES, NFR_GOVERNANCE_SECTIONS } from '@/lib/nfr-manifest'
import { cn } from '@/lib/utils'

export type NfrSection = { kind: 'category'; key: NfrCategory } | { kind: 'governance'; table: string }

interface Props {
  sections: Record<string, NfrRow[]>
  active: NfrSection
  onPick: (s: NfrSection) => void
}

const WEIGHT_COLORS = ['var(--nfr-must)', 'var(--nfr-should)', 'var(--nfr-could)', 'var(--nfr-wont)']

export function NfrCategoryRail({ sections, active, onPick }: Props) {
  const reqs = sections['nfr_requirements'] ?? []
  const byCat: Record<string, NfrRow[]> = {}
  for (const r of reqs) (byCat[(r.category as string) ?? ''] ||= []).push(r)

  return (
    <aside className="w-64 shrink-0 overflow-y-auto border-r border-[var(--border-default)] bg-[var(--bg-surface)]">
      <div className="px-3 py-2 text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)]">Categories</div>
      {NFR_CATEGORIES.map((c) => {
        const rows = byCat[c.key] ?? []
        const counts = { must: 0, should: 0, could: 0, wont: 0 } as Record<string, number>
        for (const r of rows) counts[(r.priority as string) ?? 'should'] = (counts[(r.priority as string) ?? 'should'] ?? 0) + 1
        const thin = rows.length === 0
        const isActive = active.kind === 'category' && active.key === c.key
        return (
          <button key={c.key} onClick={() => onPick({ kind: 'category', key: c.key })}
            className={cn('flex w-full items-center gap-2 px-3 py-2 text-left text-xs transition-colors',
              isActive ? 'border-l-2 border-[var(--accent)] bg-[var(--accent-subtle)]/30 pl-[10px]' : 'hover:bg-[var(--bg-elevated)]')}>
            <span>{c.emoji}</span>
            <span className="flex-1 truncate text-[var(--text-primary)]">{c.label}</span>
            {thin
              ? <span className="rounded bg-amber-50 px-1 text-[9px] text-amber-600">thin</span>
              : <span className="text-[10px] text-[var(--text-tertiary)]">{rows.length}</span>}
            <span className="flex h-1.5 w-10 overflow-hidden rounded-full bg-[var(--nfr-radar-grid)]">
              {(['must', 'should', 'could', 'wont'] as const).map((p, i) =>
                counts[p] ? <span key={p} style={{ background: WEIGHT_COLORS[i], flex: counts[p] }} /> : null)}
            </span>
          </button>
        )
      })}

      <div className="mt-2 px-3 py-2 text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)]">Governance</div>
      {NFR_GOVERNANCE_SECTIONS.map((s) => {
        const rows = sections[s.table] ?? []
        const isActive = active.kind === 'governance' && active.table === s.table
        return (
          <button key={s.table} onClick={() => onPick({ kind: 'governance', table: s.table })}
            className={cn('flex w-full items-center gap-2 px-3 py-2 text-left text-xs transition-colors',
              isActive ? 'border-l-2 border-[var(--accent)] bg-[var(--accent-subtle)]/30 pl-[10px]' : 'hover:bg-[var(--bg-elevated)]')}>
            <span>{s.emoji}</span>
            <span className="flex-1 truncate text-[var(--text-primary)]">{s.label}</span>
            <span className="text-[10px] text-[var(--text-tertiary)]">{rows.length}</span>
          </button>
        )
      })}
    </aside>
  )
}
