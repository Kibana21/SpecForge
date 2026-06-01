'use client'

import { Loader2, Check } from 'lucide-react'
import { NFR_CATEGORIES } from '@/lib/nfr-manifest'
import { cn } from '@/lib/utils'

interface Props {
  unitStatus: Record<string, unknown> | null
}

const STEPS: { key: string; label: string }[] = [
  { key: 'overview', label: 'Context & objectives' },
  ...NFR_CATEGORIES.map((c) => ({ key: c.key, label: `${c.emoji} ${c.label}` })),
  { key: 'governance', label: 'Risks, trade-offs & governance' },
]

export function NfrGenerationTheater({ unitStatus }: Props) {
  const us = unitStatus ?? {}
  const current = (us as Record<string, unknown>)['_current_unit'] as string | undefined
  const currentIdx = STEPS.findIndex((s) => s.key === current)

  return (
    <div className="mx-auto max-w-md py-12">
      <div className="mb-5 text-center">
        <Loader2 className="mx-auto mb-2 animate-spin text-[var(--accent)]" size={26} />
        <h3 className="text-sm font-semibold text-[var(--text-primary)]">Generating non-functional requirements…</h3>
        <p className="text-xs text-[var(--text-tertiary)]">Authoring each quality dimension, then governance.</p>
      </div>
      <ol className="space-y-1.5">
        {STEPS.map((s, i) => {
          const done = !!(us as Record<string, unknown>)[s.key] && (currentIdx === -1 || i < currentIdx || current !== s.key)
          const running = current === s.key
          return (
            <li key={s.key} className={cn('flex items-center gap-2 rounded-md px-3 py-1.5 text-xs',
              running ? 'bg-blue-50 text-blue-700' : done ? 'text-[var(--text-secondary)]' : 'text-[var(--text-tertiary)]')}>
              <span className="w-4">
                {running ? <Loader2 size={12} className="animate-spin" /> : done ? <Check size={12} className="text-emerald-500" /> : <span className="inline-block h-1.5 w-1.5 rounded-full bg-[var(--nfr-radar-grid)]" />}
              </span>
              {s.label}
            </li>
          )
        })}
      </ol>
    </div>
  )
}
