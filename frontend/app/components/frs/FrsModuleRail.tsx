'use client'
/**
 * FRS Module Rail — the navigation primitive for Stage A.
 *
 * Left sidebar (288px) grouped by Layer (Foundation → Vertical → Cross-cutting).
 * Each row shows:
 *   - Capability icon (auto-picked from slug)
 *   - Module name + row_key
 *   - Stub count badge (colour by completeness: red 0, amber 1 or >15, neutral 2-15)
 *   - Lock chip if is_locked
 *
 * When module count > 8, a filter+search bar appears.
 * Hover reveals a "glance" tooltip with summary + quick actions.
 */
import { useMemo, useState } from 'react'
import { Lock, Plus, Search, Filter } from 'lucide-react'
import { cn } from '@/lib/utils'
import { FRS_MODULE_LAYER_LABELS, FRS_LAYER_STYLES } from '@/lib/frs-manifest'
import type { FrsLayer, FrsModuleHydrated } from '@/lib/types'
import { pickCapabilityIcon } from './icons'

interface Props {
  modules: FrsModuleHydrated[]
  activeModuleKey: string | null
  onSelectModule: (rowKey: string) => void
  onAddModule?: () => void
}

const LAYER_ORDER: FrsLayer[] = ['foundation', 'vertical', 'cross_cutting']

export function FrsModuleRail({
  modules, activeModuleKey, onSelectModule, onAddModule,
}: Props) {
  const [filter, setFilter] = useState('')
  const [layerFilter, setLayerFilter] = useState<'all' | FrsLayer>('all')
  const showFilter = modules.length > 8

  const grouped = useMemo(() => {
    const q = filter.toLowerCase()
    const filtered = modules.filter((m) => {
      const matchesText =
        !q ||
        m.name.toLowerCase().includes(q) ||
        m.slug.toLowerCase().includes(q) ||
        m.row_key.toLowerCase().includes(q)
      const matchesLayer = layerFilter === 'all' || m.layer === layerFilter
      return matchesText && matchesLayer
    })
    const byLayer: Record<FrsLayer, FrsModuleHydrated[]> = {
      foundation: [], vertical: [], cross_cutting: [],
    }
    for (const m of filtered) byLayer[m.layer]?.push(m)
    return byLayer
  }, [modules, filter, layerFilter])

  const totalStubs = modules.reduce((sum, m) => sum + (m.backlog?.length ?? 0), 0)
  const totalBRs = new Set(
    modules.flatMap((m) => m.backlog?.flatMap((s) => s.br_refs ?? []) ?? []),
  ).size

  return (
    <aside className="w-72 shrink-0 flex flex-col border-r border-[var(--border-default)] bg-[var(--bg-surface)] overflow-hidden">
      {/* Header */}
      <div className="shrink-0 px-3 py-3 border-b border-[var(--border-subtle)]">
        <div className="flex items-center justify-between">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)]">
            Modules
          </p>
          <p className="text-[10px] text-[var(--text-tertiary)]">
            {modules.length} · {totalStubs} stubs · {totalBRs} BRs
          </p>
        </div>

        {showFilter && (
          <>
            <div className="mt-2 relative">
              <Search size={11} className="absolute left-2 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)]" />
              <input
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                placeholder="Filter modules…"
                className="w-full rounded-md border border-[var(--border-default)] bg-[var(--bg-elevated)] pl-6 pr-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-[var(--accent-ring)]"
              />
            </div>
            <div className="mt-2 flex gap-1 text-[10px]">
              {(['all', 'foundation', 'vertical', 'cross_cutting'] as const).map((l) => (
                <button
                  key={l}
                  onClick={() => setLayerFilter(l)}
                  className={cn(
                    'rounded-full px-2 py-0.5 transition-colors',
                    layerFilter === l
                      ? 'bg-[var(--accent-subtle)] text-[var(--accent)] font-semibold'
                      : 'bg-[var(--bg-elevated)] text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]',
                  )}
                >
                  {l === 'all' ? 'All' : FRS_MODULE_LAYER_LABELS[l]}
                </button>
              ))}
            </div>
          </>
        )}
      </div>

      {/* Module list grouped by layer */}
      <div className="flex-1 overflow-y-auto py-2">
        {LAYER_ORDER.map((layer) => {
          const rows = grouped[layer]
          if (rows.length === 0) return null
          return (
            <div key={layer} className="mb-3">
              <p className="px-3 mb-1 text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)]">
                {FRS_MODULE_LAYER_LABELS[layer]}
              </p>
              {rows.map((m) => (
                <FrsModuleRailItem
                  key={m.row_key}
                  module={m}
                  active={m.row_key === activeModuleKey}
                  onClick={() => onSelectModule(m.row_key)}
                />
              ))}
            </div>
          )
        })}

        {/* Empty state when filter has no matches */}
        {LAYER_ORDER.every((l) => grouped[l].length === 0) && (
          <p className="px-3 py-4 text-xs text-[var(--text-tertiary)] italic">
            {modules.length === 0
              ? 'No modules yet. Click Generate to start.'
              : 'No modules match the filter.'}
          </p>
        )}
      </div>

      {/* Footer */}
      {onAddModule && (
        <div className="shrink-0 px-3 py-3 border-t border-[var(--border-subtle)]">
          <button
            onClick={onAddModule}
            className="w-full inline-flex items-center justify-center gap-1.5 rounded-lg border border-dashed border-[var(--border-default)] py-2 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] hover:border-[var(--accent)]/40 transition-colors"
          >
            <Plus size={13} /> Add Module
          </button>
        </div>
      )}
    </aside>
  )
}

// ── Module row ──────────────────────────────────────────────────────────────

function FrsModuleRailItem({
  module: m, active, onClick,
}: {
  module: FrsModuleHydrated
  active: boolean
  onClick: () => void
}) {
  const [hover, setHover] = useState(false)
  const Icon = pickCapabilityIcon(m.slug)
  const stubCount = m.backlog?.length ?? 0
  const layerStyle = FRS_LAYER_STYLES[m.layer]

  const stubBadgeCls =
    stubCount === 0
      ? 'bg-red-100 text-red-700'
      : stubCount > 15
      ? 'bg-amber-100 text-amber-700'
      : stubCount < 2
      ? 'bg-amber-50 text-amber-600'
      : 'bg-[var(--bg-elevated)] text-[var(--text-tertiary)]'

  return (
    <div
      className="relative"
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      <button
        onClick={onClick}
        className={cn(
          'group w-full flex items-center gap-2 px-3 py-2 text-left transition-colors',
          'border-l-2',
          active
            ? 'bg-[var(--frs-rail-active-bg)] border-[var(--frs-rail-active-border)]'
            : 'border-transparent hover:bg-[var(--frs-rail-hover-bg)]',
        )}
        aria-current={active ? 'location' : undefined}
      >
        <span
          className={cn(
            'shrink-0 transition-colors',
            active ? 'text-[var(--accent)]' : 'text-[var(--text-secondary)]',
          )}
          style={{ color: active ? undefined : layerStyle.accent }}
        >
          <Icon size={14} />
        </span>
        <div className="flex-1 min-w-0">
          <p
            className={cn(
              'text-sm truncate',
              active
                ? 'font-semibold text-[var(--text-primary)]'
                : 'text-[var(--text-secondary)]',
            )}
          >
            {m.name}
          </p>
          <p className="text-[10px] text-[var(--text-tertiary)] truncate font-mono">
            {m.row_key}
          </p>
        </div>
        <span
          className={cn(
            'shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold',
            stubBadgeCls,
          )}
          title={`${stubCount} backlog stub(s)`}
        >
          {stubCount}
        </span>
        {m.is_locked && (
          <Lock
            size={11}
            className="shrink-0 text-amber-600"
            aria-label="Locked"
          />
        )}
      </button>

      {/* Glance card — slides out to right on hover */}
      {hover && <FrsModuleGlanceCard module={m} />}
    </div>
  )
}

// ── Glance card ─────────────────────────────────────────────────────────────

function FrsModuleGlanceCard({ module: m }: { module: FrsModuleHydrated }) {
  const Icon = pickCapabilityIcon(m.slug)
  const layerStyle = FRS_LAYER_STYLES[m.layer]
  const coveredBrs = new Set(m.backlog?.flatMap((s) => s.br_refs ?? []) ?? [])

  return (
    <div
      className={cn(
        'absolute left-full top-0 ml-1 w-72 z-50',
        'rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface)]',
        'shadow-[var(--shadow-md)] p-3 text-xs',
        'pointer-events-none', // visual-only so leaving the row doesn't get stuck
      )}
    >
      <div className="flex items-center gap-2 mb-1">
        <span style={{ color: layerStyle.accent }}><Icon size={14} /></span>
        <span className="font-semibold text-[var(--text-primary)] truncate">
          {m.name}
        </span>
        <span
          className={cn(
            'text-[9px] rounded px-1.5 py-0.5 border font-medium',
            layerStyle.ribbon,
          )}
        >
          {FRS_MODULE_LAYER_LABELS[m.layer]}
        </span>
      </div>
      <p className="text-[var(--text-tertiary)] mb-2 line-clamp-3">
        {m.summary || 'No summary provided.'}
      </p>
      <div className="flex flex-wrap gap-1.5 text-[10px]">
        <span className="rounded-full bg-[var(--bg-elevated)] text-[var(--text-secondary)] px-2 py-0.5">
          {m.backlog?.length ?? 0} backlog
        </span>
        <span className="rounded-full bg-[var(--bg-elevated)] text-[var(--text-secondary)] px-2 py-0.5">
          {m.actors?.length ?? 0} actors
        </span>
        <span className="rounded-full bg-[var(--bg-elevated)] text-[var(--text-secondary)] px-2 py-0.5">
          {m.interfaces?.length ?? 0} interfaces
        </span>
        <span className="rounded-full bg-[var(--bg-elevated)] text-[var(--text-secondary)] px-2 py-0.5">
          {m.data_entities?.length ?? 0} data
        </span>
      </div>
      {coveredBrs.size > 0 && (
        <p className="mt-2 text-[10px] text-[var(--text-tertiary)]">
          Covers BRs:{' '}
          <span className="font-mono">
            {Array.from(coveredBrs).slice(0, 5).join(', ')}
            {coveredBrs.size > 5 ? ` +${coveredBrs.size - 5} more` : ''}
          </span>
        </p>
      )}
    </div>
  )
}
