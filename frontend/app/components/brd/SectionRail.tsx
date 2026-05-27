'use client'
import { useState } from 'react'
import { cn } from '@/lib/utils'
import { BRD_SECTIONS } from '@/lib/brd-manifest'
import type { BrdFinding } from '@/lib/types'

interface Props {
  unitStatus: Record<string, { completeness: number; confidence: string }>
  activeSection: number
  onSectionClick: (num: number) => void
  findings?: BrdFinding[]
}

function StatusDot({
  completeness,
  hasFindings,
  isKeystone,
}: {
  completeness: number | null
  hasFindings: boolean
  isKeystone?: boolean
}) {
  if (hasFindings) {
    return <span className="text-[10px] text-[var(--status-danger)]" title="Has validation findings">⚠</span>
  }
  if (isKeystone && completeness !== null && completeness >= 90) {
    return <span className="text-[10px] text-[var(--accent)]" title="Keystone section — complete">★</span>
  }
  if (isKeystone) {
    return <span className="text-[10px] text-[var(--text-tertiary)]" title="Keystone section">★</span>
  }
  if (completeness === null) {
    return <span className="text-[10px] text-[var(--border-strong)]">○</span>
  }
  if (completeness >= 90) {
    return <span className="text-[10px] text-[var(--status-success)]" title={`${completeness}% complete`}>●</span>
  }
  if (completeness >= 60) {
    return <span className="text-[10px] text-[var(--status-warning)]" title={`${completeness}% complete`}>◐</span>
  }
  return <span className="text-[10px] text-[var(--text-tertiary)]" title={`${completeness}% complete`}>○</span>
}

export function SectionRail({ unitStatus, activeSection, onSectionClick, findings = [] }: Props) {
  const [hoveredNum, setHoveredNum] = useState<number | null>(null)

  const findingsByUnit = findings.reduce<Record<string, BrdFinding[]>>((acc, f) => {
    // Map finding to unit by row_key prefix heuristic — group into check_id prefix
    const key = f.check_id?.split('.')[0] ?? 'misc'
    if (!acc[key]) acc[key] = []
    acc[key].push(f)
    return acc
  }, {})

  return (
    <aside className="sticky top-0 h-[calc(100vh-8rem)] w-14 shrink-0 overflow-y-auto border-r border-[var(--border-subtle)] bg-[var(--bg-surface)] flex flex-col py-2 gap-0.5">
      {BRD_SECTIONS.map((section) => {
        const us = unitStatus[section.unit_key]
        const completeness = us?.completeness ?? null
        const hasFindings = findingsByUnit[section.unit_key]?.length > 0
        const isActive = activeSection === section.num
        const isKeystone = 'isKeystone' in section && section.isKeystone === true

        return (
          <div key={section.num} className="relative">
            <button
              onClick={() => onSectionClick(section.num)}
              onMouseEnter={() => setHoveredNum(section.num)}
              onMouseLeave={() => setHoveredNum(null)}
              className={cn(
                'flex flex-col items-center justify-center w-full py-2 px-1 gap-0.5 transition-colors rounded-md mx-auto text-center',
                isActive
                  ? 'border-l-2 border-[var(--accent)] bg-[var(--accent-subtle)] pl-[3px]'
                  : 'hover:bg-[var(--bg-elevated)] border-l-2 border-transparent',
              )}
              title={section.title}
            >
              <span
                className={cn(
                  'text-[10px] font-semibold leading-none',
                  isActive ? 'text-[var(--accent)]' : 'text-[var(--text-tertiary)]',
                )}
              >
                {section.num}
              </span>
              <StatusDot
                completeness={completeness}
                hasFindings={hasFindings}
                isKeystone={isKeystone}
              />
            </button>

            {/* Hover tooltip */}
            {hoveredNum === section.num && (
              <div className="absolute left-full top-0 ml-2 z-50 whitespace-nowrap rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] shadow-[var(--shadow-md)] px-3 py-2 text-xs pointer-events-none">
                <div className="flex items-center gap-1.5">
                  <span>{section.emoji}</span>
                  <span className="font-semibold text-[var(--text-primary)]">{section.title}</span>
                </div>
                {completeness !== null && (
                  <div className="mt-1 text-[10px] text-[var(--text-tertiary)]">
                    {completeness}% complete
                    {us?.confidence && ` · ${us.confidence} confidence`}
                  </div>
                )}
                {hasFindings && (
                  <div className="mt-0.5 text-[10px] text-[var(--status-danger)]">
                    Has findings — needs attention
                  </div>
                )}
              </div>
            )}
          </div>
        )
      })}
    </aside>
  )
}
