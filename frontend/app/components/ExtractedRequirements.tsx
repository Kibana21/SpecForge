'use client'
import { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import clsx from 'clsx'
import type { ExtractedRequirement } from '@/lib/types'
import { ConfidenceBadge } from './ConfidenceBadge'

const CATEGORY_LABELS: Record<string, string> = {
  functional: 'Functional',
  non_functional: 'Non-Functional',
  constraint: 'Constraints',
  assumption: 'Assumptions',
  stakeholder: 'Stakeholders',
}

function groupBy<T>(items: T[], key: (item: T) => string): Record<string, T[]> {
  return items.reduce<Record<string, T[]>>((acc, item) => {
    const k = key(item)
    ;(acc[k] ??= []).push(item)
    return acc
  }, {})
}

interface TooltipProps {
  text: string
  children: React.ReactNode
}

function Tooltip({ text, children }: TooltipProps) {
  const [show, setShow] = useState(false)
  return (
    <span
      className="relative inline-block"
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      {children}
      {show && (
        <span className="absolute bottom-full left-0 mb-1 z-10 w-56 rounded-lg border border-[var(--border-default)] bg-[var(--bg-elevated)] p-2 text-[10px] text-[var(--text-secondary)] shadow-xl">
          {text}
        </span>
      )}
    </span>
  )
}

export function ExtractedRequirements({ requirements }: { requirements: ExtractedRequirement[] }) {
  const groups = groupBy(requirements, (r) => r.category)
  const [open, setOpen] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(Object.keys(groups).map((k) => [k, true]))
  )

  const toggle = (key: string) => setOpen((s) => ({ ...s, [key]: !s[key] }))

  return (
    <div className="divide-y divide-[var(--border-subtle)]">
      {Object.entries(groups).map(([cat, reqs]) => (
        <div key={cat}>
          <button
            onClick={() => toggle(cat)}
            className="flex w-full items-center justify-between px-4 py-2.5 text-left hover:bg-[var(--bg-elevated)] transition-colors"
          >
            <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-tertiary)]">
              {CATEGORY_LABELS[cat] ?? cat} ({reqs.length})
            </span>
            {open[cat] ? (
              <ChevronDown size={13} className="text-[var(--text-tertiary)]" />
            ) : (
              <ChevronRight size={13} className="text-[var(--text-tertiary)]" />
            )}
          </button>

          {open[cat] && (
            <ul className="pb-1">
              {reqs.map((req) => (
                <li key={req.id} className="flex items-start gap-2.5 px-4 py-2 hover:bg-[var(--bg-elevated)] transition-colors">
                  <span className="mt-0.5 shrink-0 text-[10px] font-mono text-[var(--text-tertiary)]">
                    {req.ext_id}
                  </span>
                  <span className="flex-1 text-xs text-[var(--text-primary)] leading-relaxed">
                    {req.source_reference ? (
                      <Tooltip text={`Source: "${req.source_reference}"`}>
                        <span className="border-b border-dashed border-[var(--border-default)] cursor-help">
                          {req.text}
                        </span>
                      </Tooltip>
                    ) : (
                      req.text
                    )}
                  </span>
                  <div className="shrink-0">
                    <ConfidenceBadge confidence={req.confidence} />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      ))}
    </div>
  )
}
