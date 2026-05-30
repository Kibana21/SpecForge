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
import { useEffect, useMemo, useState } from 'react'
import {
  CheckCircle2, ChevronDown, ChevronRight, Filter, Loader2, Lock, Plus, Search,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { FRS_MODULE_LAYER_LABELS, FRS_LAYER_STYLES } from '@/lib/frs-manifest'
import type { FrsLayer, FrsModuleHydrated } from '@/lib/types'
import { pickCapabilityIcon } from './icons'

interface Props {
  modules: FrsModuleHydrated[]
  activeModuleKey: string | null
  /** Active spec row_key when a spec panel is open. */
  activeSpecRowKey?: string | null
  /** unit_status from the document — used to render per-spec progress indicators. */
  unitStatus?: Record<string, unknown> | null
  onSelectModule: (rowKey: string) => void
  /** Called when a nested spec row is clicked (Stage B). */
  onSelectSpec?: (specRowKey: string, moduleRowKey: string) => void
  onAddModule?: () => void
}

const LAYER_ORDER: FrsLayer[] = ['foundation', 'vertical', 'cross_cutting']

export function FrsModuleRail({
  modules, activeModuleKey, activeSpecRowKey, unitStatus,
  onSelectModule, onSelectSpec, onAddModule,
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
                  activeSpecRowKey={activeSpecRowKey ?? null}
                  unitStatus={unitStatus ?? null}
                  onClick={() => onSelectModule(m.row_key)}
                  onSelectSpec={onSelectSpec}
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
  module: m, active, activeSpecRowKey, unitStatus, onClick, onSelectSpec,
}: {
  module: FrsModuleHydrated
  active: boolean
  activeSpecRowKey: string | null
  unitStatus: Record<string, unknown> | null
  onClick: () => void
  onSelectSpec?: (specRowKey: string, moduleRowKey: string) => void
}) {
  const [hover, setHover] = useState(false)
  // Default-expanded when the module is active OR contains the active spec
  const stubs = m.backlog ?? []
  const containsActiveSpec = !!activeSpecRowKey && stubs.some(s => s.row_key === activeSpecRowKey)
  const [expanded, setExpanded] = useState<boolean>(active || containsActiveSpec)

  // Auto-expand when this module becomes active or contains the active spec
  useEffect(() => {
    if (active || containsActiveSpec) setExpanded(true)
  }, [active, containsActiveSpec])

  const Icon = pickCapabilityIcon(m.slug)
  const stubCount = stubs.length
  const layerStyle = FRS_LAYER_STYLES[m.layer]

  const stubBadgeCls =
    stubCount === 0
      ? 'bg-red-100 text-red-700'
      : stubCount > 15
      ? 'bg-amber-100 text-amber-700'
      : stubCount < 2
      ? 'bg-amber-50 text-amber-600'
      : 'bg-[var(--bg-elevated)] text-[var(--text-tertiary)]'

  const moduleUnit = (unitStatus?.[`design_mod_${m.row_key}`] as
    Record<string, unknown> | undefined) ?? null
  const currentUnit = unitStatus?.['_current_unit'] as string | undefined
  const moduleDesigning = currentUnit === `design_mod_${m.row_key}`

  return (
    <div
      className="relative"
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      <div
        className={cn(
          'group w-full flex items-center gap-1 px-1 py-2 transition-colors',
          'border-l-2',
          active
            ? 'bg-[var(--frs-rail-active-bg)] border-[var(--frs-rail-active-border)]'
            : 'border-transparent hover:bg-[var(--frs-rail-hover-bg)]',
        )}
      >
        {/* Chevron toggle */}
        <button
          onClick={(e) => { e.stopPropagation(); setExpanded(v => !v) }}
          className="shrink-0 rounded p-0.5 text-[var(--text-tertiary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-elevated)] transition-colors"
          aria-label={expanded ? 'Collapse module' : 'Expand module'}
          aria-expanded={expanded}
        >
          {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        </button>

        {/* Module body — clicking selects the module */}
        <button
          onClick={onClick}
          className="flex-1 flex items-center gap-2 min-w-0 text-left"
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
          {moduleDesigning && (
            <Loader2
              size={11}
              className="shrink-0 text-blue-600 animate-spin"
              aria-label="Designing"
            />
          )}
        </button>
      </div>

      {/* Nested spec rows */}
      {expanded && stubs.length > 0 && onSelectSpec && (
        <ul className="ml-6 mb-1 border-l border-[var(--border-subtle)]">
          {stubs.map((s) => {
            const isActive = s.row_key === activeSpecRowKey
            const designed = (s.completeness ?? 0) > 0
            const designing = moduleDesigning && !designed
            return (
              <li key={s.row_key}>
                <button
                  onClick={() => onSelectSpec(s.row_key, m.row_key)}
                  className={cn(
                    'group/spec w-full flex items-center gap-2 pl-3 pr-2 py-1 text-left text-xs transition-colors',
                    isActive
                      ? 'bg-[var(--frs-rail-active-bg)]/60 font-medium text-[var(--text-primary)]'
                      : 'text-[var(--text-secondary)] hover:bg-[var(--frs-rail-hover-bg)]',
                  )}
                  aria-current={isActive ? 'location' : undefined}
                >
                  <span className="shrink-0 w-3 flex justify-center">
                    {designed && (s.completeness ?? 0) >= 90 ? (
                      <CheckCircle2 size={10} className="text-[var(--accent)]" />
                    ) : designed ? (
                      <span className="w-1.5 h-1.5 rounded-full bg-[var(--accent)]" />
                    ) : designing ? (
                      <Loader2 size={10} className="text-blue-600 animate-spin" />
                    ) : (
                      <span className="w-1.5 h-1.5 rounded-full bg-[var(--text-tertiary)]/40" />
                    )}
                  </span>
                  <span className="flex-1 min-w-0 truncate">{s.title}</span>
                  {designed && (
                    <span className="shrink-0 text-[10px] text-[var(--text-tertiary)]">
                      {s.completeness}%
                    </span>
                  )}
                  {s.is_locked && (
                    <Lock size={9} className="shrink-0 text-amber-600" />
                  )}
                </button>
              </li>
            )
          })}
        </ul>
      )}

      {/* Glance card — slides out to right on hover */}
      {hover && !expanded && <FrsModuleGlanceCard module={m} />}
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
