'use client'
import { useState } from 'react'
import { Zap, Lock, AlertTriangle, Plug, AlertCircle } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { AppFact, FactKind } from '@/lib/types'
import { factKindColor as KIND_COLORS, factConfidenceVariant } from '@/lib/ui/status'
import { Badge } from '@/app/components/ui/badge'

const KIND_ICONS: Record<FactKind, LucideIcon> = {
  capability: Zap,
  constraint: Lock,
  limitation: AlertTriangle,
  integration: Plug,
  gotcha: AlertCircle,
}

const KIND_OPTIONS: Array<FactKind | 'all'> = ['all', 'capability', 'constraint', 'limitation', 'integration', 'gotcha']

interface Props {
  facts: AppFact[]
}

export function FactList({ facts }: Props) {
  const [kindFilter, setKindFilter] = useState<FactKind | 'all'>('all')

  const filtered = kindFilter === 'all' ? facts : facts.filter((f) => f.kind === kindFilter)
  const activeFacts = filtered.filter((f) => f.status === 'active')

  return (
    <div className="space-y-3">
      {/* Kind filter tabs */}
      <div className="flex items-center gap-1 flex-wrap">
        {KIND_OPTIONS.map((k) => (
          <button
            key={k}
            onClick={() => setKindFilter(k)}
            className={`px-2.5 py-1 rounded-full text-[10px] font-medium capitalize transition-colors ${
              kindFilter === k
                ? 'bg-[var(--accent)] text-white'
                : 'bg-[var(--bg-elevated)] text-[var(--text-secondary)] hover:bg-[var(--border-default)]'
            }`}
          >
            {k}
          </button>
        ))}
      </div>

      {activeFacts.length === 0 ? (
        <p className="text-xs text-[var(--text-tertiary)]">No facts found.</p>
      ) : (
        <div className="space-y-2">
          {activeFacts.map((fact) => {
            const Icon = KIND_ICONS[fact.kind]
            return (
              <div
                key={fact.id}
                className="flex gap-2.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-3"
              >
                <Icon size={13} className={`shrink-0 mt-0.5 ${KIND_COLORS[fact.kind]}`} />
                <div className="min-w-0 flex-1">
                  <p className="text-xs text-[var(--text-primary)] leading-relaxed">{fact.text}</p>
                  {fact.source_ref && (
                    <p className="text-[10px] text-[var(--text-tertiary)] mt-1">{fact.source_ref}</p>
                  )}
                </div>
                <Badge variant={factConfidenceVariant[fact.confidence]} className="shrink-0 self-start capitalize">
                  {fact.confidence}
                </Badge>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
