'use client'
import { useState } from 'react'
import { ChevronDown, ChevronUp, Sparkles } from 'lucide-react'

interface Props {
  cbSummary?: {
    problem: string
    outcomes: string[]
    capabilities: string[]
  }
}

export function CbEchoStrip({ cbSummary }: Props) {
  const [open, setOpen] = useState(false)

  if (!cbSummary?.problem) return null

  const problemExcerpt = cbSummary.problem.length > 100
    ? cbSummary.problem.slice(0, 100) + '…'
    : cbSummary.problem

  return (
    <div className="border-b border-[var(--border-subtle)] bg-[var(--accent-subtle)]/30">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-[var(--accent-subtle)]/50 transition-colors"
      >
        <Sparkles size={12} className="shrink-0 text-[var(--accent)]" />
        <div className="flex-1 min-w-0">
          <span className="text-[10px] font-semibold text-[var(--accent)] uppercase tracking-wider">
            Concept Brief
          </span>
          {!open && (
            <p className="text-[11px] text-[var(--text-secondary)] truncate mt-0.5">
              {problemExcerpt}
            </p>
          )}
        </div>
        {open ? (
          <ChevronUp size={12} className="shrink-0 text-[var(--text-tertiary)]" />
        ) : (
          <ChevronDown size={12} className="shrink-0 text-[var(--text-tertiary)]" />
        )}
      </button>

      {open && (
        <div className="px-3 pb-3 space-y-3 text-xs">
          {/* Problem */}
          <div>
            <p className="text-[10px] font-semibold text-[var(--text-tertiary)] uppercase tracking-wide mb-1">
              Problem
            </p>
            <p className="text-[var(--text-secondary)] leading-relaxed">{cbSummary.problem}</p>
          </div>

          {/* Outcomes */}
          {cbSummary.outcomes.length > 0 && (
            <div>
              <p className="text-[10px] font-semibold text-[var(--text-tertiary)] uppercase tracking-wide mb-1">
                Expected Outcomes
              </p>
              <ul className="space-y-1">
                {cbSummary.outcomes.map((o, i) => (
                  <li key={i} className="flex items-start gap-1.5 text-[var(--text-secondary)]">
                    <span className="shrink-0 mt-0.5 w-1 h-1 rounded-full bg-[var(--accent)] inline-block" />
                    {o}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Capabilities */}
          {cbSummary.capabilities.length > 0 && (
            <div>
              <p className="text-[10px] font-semibold text-[var(--text-tertiary)] uppercase tracking-wide mb-1">
                Capabilities
              </p>
              <div className="flex flex-wrap gap-1.5">
                {cbSummary.capabilities.map((c, i) => (
                  <span
                    key={i}
                    className="rounded border border-[var(--accent-subtle)] bg-[var(--accent-subtle)] px-2 py-0.5 text-[10px] text-[var(--accent)]"
                  >
                    {c}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
