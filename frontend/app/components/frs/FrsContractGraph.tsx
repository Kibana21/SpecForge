'use client'
/**
 * Cross-Module Contract Mini-Graph + textual equivalent.
 *
 * Layout: the SVG above gives a high-level shape (who-talks-to-whom), the
 * textual list below is the readable source of truth. The list is also the
 * accessible view for screen readers and the fallback when many edges fan out.
 *
 * The active module sits in the middle. Inbound counterparts above (arrows
 * point IN to active), outbound counterparts below (arrows point OUT to them).
 * Arrow strokes are color-coded by transport (rest=blue, event_bus=violet,
 * other=accent). On-canvas labels are intentionally omitted because they
 * overlap badly when several edges meet at the same node — the list below
 * carries that detail.
 *
 * Cycle detection: when an outbound module also has an outbound back to active,
 * both the outgoing and the return arrows render red.
 */
import { useMemo } from 'react'
import { ArrowDownLeft, ArrowUpRight, Network } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { FrsModuleHydrated, FrsModuleInterfaceRow } from '@/lib/types'

const NODE_W = 168
const NODE_H = 40
const SVG_W = 760
const CENTER_X = SVG_W / 2

interface Props {
  module: FrsModuleHydrated
  allModules: FrsModuleHydrated[]
  onNavigateModule?: (rowKey: string) => void
  onEditInterface?: (interfaceRowKey: string) => void
}

interface PositionedNode {
  rowKey: string
  name: string
  x: number
  y: number
  isCenter: boolean
  cycle: boolean
}

interface PositionedEdge {
  ifaceRowKey: string
  fromX: number
  fromY: number
  toX: number
  toY: number
  transport: string
  inbound: boolean
  cycle: boolean
}

export function FrsContractGraph({
  module: active, allModules, onNavigateModule, onEditInterface,
}: Props) {
  const { nodes, edges, svgH, inboundIfaces, outboundIfaces, moduleByKey } = useMemo(
    () => layout(active, allModules),
    [active, allModules],
  )

  const totalCounterparts = nodes.length - 1
  const hasContracts = inboundIfaces.length + outboundIfaces.length > 0

  if (!hasContracts) {
    return (
      <div className="rounded-lg border border-dashed border-[var(--border-default)] bg-[var(--bg-elevated)]/50 px-4 py-6 text-center">
        <Network size={18} className="mx-auto text-[var(--text-tertiary)] mb-1" />
        <p className="text-xs text-[var(--text-tertiary)] italic">
          No cross-module interfaces yet. Inbound and outbound APIs/events will
          appear here once they&apos;re defined.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* ── SVG diagram (overview) ─────────────────────────────── */}
      <div className="rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] p-4 overflow-x-auto">
        <svg
          width="100%"
          height={svgH}
          viewBox={`0 0 ${SVG_W} ${svgH}`}
          preserveAspectRatio="xMidYMid meet"
          className="mx-auto block"
          style={{ minWidth: 320, maxWidth: SVG_W }}
          role="img"
          aria-label={`Cross-module contracts for ${active.name}: ${inboundIfaces.length} inbound, ${outboundIfaces.length} outbound`}
        >
          <defs>
            <marker id="arrow-accent" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--accent)" />
            </marker>
            <marker id="arrow-rest" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#2563EB" />
            </marker>
            <marker id="arrow-event" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#7C3AED" />
            </marker>
            <marker id="arrow-red" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--status-danger)" />
            </marker>
          </defs>

          {/* Edges first so nodes overlap them */}
          {edges.map((e) => {
            const stroke = e.cycle
              ? 'var(--status-danger)'
              : e.transport === 'rest'
                ? '#2563EB'
                : e.transport === 'event_bus' || e.transport === 'event'
                  ? '#7C3AED'
                  : 'var(--accent)'
            const marker = e.cycle
              ? 'arrow-red'
              : e.transport === 'rest'
                ? 'arrow-rest'
                : e.transport === 'event_bus' || e.transport === 'event'
                  ? 'arrow-event'
                  : 'arrow-accent'
            return (
              <g
                key={e.ifaceRowKey}
                className={cn(onEditInterface && 'cursor-pointer')}
                onClick={() => onEditInterface?.(e.ifaceRowKey)}
              >
                <line
                  x1={e.fromX} y1={e.fromY} x2={e.toX} y2={e.toY}
                  stroke={stroke} strokeWidth={1.75} strokeOpacity={0.72}
                  markerEnd={`url(#${marker})`}
                />
              </g>
            )
          })}

          {/* Nodes on top */}
          {nodes.map((n) => (
            <g
              key={n.rowKey}
              className={cn(!n.isCenter && onNavigateModule && 'cursor-pointer')}
              onClick={() => !n.isCenter && onNavigateModule?.(n.rowKey)}
            >
              <rect
                x={n.x - NODE_W / 2}
                y={n.y - NODE_H / 2}
                width={NODE_W}
                height={NODE_H}
                rx={8}
                fill={n.isCenter ? 'var(--accent-subtle)' : 'var(--bg-elevated)'}
                stroke={n.cycle ? 'var(--status-danger)' : n.isCenter ? 'var(--accent)' : 'var(--border-default)'}
                strokeWidth={n.isCenter ? 1.75 : 1}
              />
              <text
                x={n.x}
                y={n.y + 4}
                textAnchor="middle"
                fontSize={n.isCenter ? '12' : '11'}
                fontWeight={n.isCenter ? '600' : '500'}
                fill={n.isCenter ? 'var(--accent)' : 'var(--text-primary)'}
                className="select-none"
              >
                {truncate(n.name, n.isCenter ? 26 : 22)}
              </text>
            </g>
          ))}
        </svg>

        {/* Legend */}
        <div className="mt-3 flex flex-wrap items-center justify-center gap-3 text-[10px] text-[var(--text-tertiary)]">
          <LegendDot color="#2563EB" label="rest" />
          <LegendDot color="#7C3AED" label="event_bus" />
          <LegendDot color="var(--accent)" label="other" />
          <span className="opacity-60">·</span>
          <span>{totalCounterparts} counterpart{totalCounterparts !== 1 ? 's' : ''} · {inboundIfaces.length + outboundIfaces.length} contracts</span>
        </div>
      </div>

      {/* ── Textual contracts list (source of truth) ──────────── */}
      <div className="rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] divide-y divide-[var(--border-subtle)]">
        <ContractsBlock
          title="Inbound"
          icon={<ArrowDownLeft size={12} />}
          tone="accent"
          ifaces={inboundIfaces}
          activeName={active.name}
          moduleByKey={moduleByKey}
          onNavigateModule={onNavigateModule}
          onEditInterface={onEditInterface}
        />
        <ContractsBlock
          title="Outbound"
          icon={<ArrowUpRight size={12} />}
          tone="info"
          ifaces={outboundIfaces}
          activeName={active.name}
          moduleByKey={moduleByKey}
          onNavigateModule={onNavigateModule}
          onEditInterface={onEditInterface}
        />
      </div>
    </div>
  )
}

// ── Subcomponents ────────────────────────────────────────────────────────────

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1">
      <span
        className="inline-block w-2.5 h-0.5 rounded"
        style={{ backgroundColor: color }}
      />
      <span>{label}</span>
    </span>
  )
}

function ContractsBlock({
  title, icon, tone, ifaces, activeName, moduleByKey, onNavigateModule, onEditInterface,
}: {
  title: string
  icon: React.ReactNode
  tone: 'accent' | 'info'
  ifaces: FrsModuleInterfaceRow[]
  activeName: string
  moduleByKey: Map<string, FrsModuleHydrated>
  onNavigateModule?: (rowKey: string) => void
  onEditInterface?: (interfaceRowKey: string) => void
}) {
  if (ifaces.length === 0) {
    return (
      <div className="px-3 py-2 flex items-center gap-2 text-[11px] text-[var(--text-tertiary)]">
        <span className={cn(
          'inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 font-semibold uppercase tracking-wide',
          tone === 'accent'
            ? 'bg-[var(--accent-subtle)] text-[var(--accent)]'
            : 'bg-blue-50 text-blue-700',
        )}>
          {icon} {title}
        </span>
        <span className="italic">none</span>
      </div>
    )
  }

  return (
    <div className="px-3 py-2.5">
      <div className="flex items-center gap-2 mb-2">
        <span className={cn(
          'inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide',
          tone === 'accent'
            ? 'bg-[var(--accent-subtle)] text-[var(--accent)]'
            : 'bg-blue-50 text-blue-700',
        )}>
          {icon} {title} contracts
        </span>
        <span className="text-[11px] text-[var(--text-tertiary)]">{ifaces.length}</span>
      </div>
      <ul className="space-y-1">
        {ifaces.map((i) => (
          <ContractRow
            key={i.row_key}
            iface={i}
            activeName={activeName}
            moduleByKey={moduleByKey}
            inbound={title === 'Inbound'}
            onNavigateModule={onNavigateModule}
            onEditInterface={onEditInterface}
          />
        ))}
      </ul>
    </div>
  )
}

function ContractRow({
  iface, activeName, moduleByKey, inbound, onNavigateModule, onEditInterface,
}: {
  iface: FrsModuleInterfaceRow
  activeName: string
  moduleByKey: Map<string, FrsModuleHydrated>
  inbound: boolean
  onNavigateModule?: (rowKey: string) => void
  onEditInterface?: (interfaceRowKey: string) => void
}) {
  const transport = iface.transport ?? iface.interface_kind
  const transportColor =
    transport === 'rest' ? 'text-blue-700 bg-blue-50' :
    transport === 'event_bus' || transport === 'event' ? 'text-violet-700 bg-violet-50' :
    'text-[var(--accent)] bg-[var(--accent-subtle)]'
  const counterpartName = iface.counterpart
    ? moduleByKey.get(iface.counterpart)?.name ?? iface.counterpart
    : '—'

  return (
    <li
      className={cn(
        'group grid items-center gap-2 rounded-md px-2 py-1.5 text-xs hover:bg-[var(--bg-elevated)] transition-colors',
        'grid-cols-[80px,minmax(0,1.2fr),auto,minmax(0,1.4fr),minmax(0,1.6fr)]',
      )}
    >
      <span className={cn('font-mono text-[10px] rounded px-1.5 py-0.5 text-center', transportColor)}>
        {transport}
      </span>
      <span className="font-medium text-[var(--text-primary)] truncate" title={iface.name}>
        {iface.name}
      </span>
      <span className="text-[var(--text-tertiary)] text-[10px]">
        {inbound ? '←' : '→'}
      </span>
      <button
        type="button"
        onClick={() => iface.counterpart && onNavigateModule?.(iface.counterpart)}
        className={cn(
          'text-left truncate',
          iface.counterpart
            ? 'text-[var(--accent)] hover:underline cursor-pointer'
            : 'text-[var(--text-tertiary)] cursor-default',
        )}
        title={counterpartName}
      >
        {inbound
          ? `${counterpartName} → ${activeName}`
          : `${activeName} → ${counterpartName}`}
      </button>
      <div className="flex items-center justify-between gap-2 min-w-0">
        <span className="text-[var(--text-secondary)] truncate" title={iface.purpose}>
          {iface.purpose || <em className="text-[var(--text-tertiary)]">no purpose set</em>}
        </span>
        {onEditInterface && (
          <button
            onClick={(e) => { e.stopPropagation(); onEditInterface(iface.row_key) }}
            className="shrink-0 opacity-0 group-hover:opacity-100 text-[10px] text-[var(--text-tertiary)] hover:text-[var(--accent)] transition-opacity"
            title="Edit interface"
          >
            Edit
          </button>
        )}
      </div>
    </li>
  )
}

// ── Layout algorithm ────────────────────────────────────────────────────────

function layout(
  active: FrsModuleHydrated,
  allModules: FrsModuleHydrated[],
): {
  nodes: PositionedNode[]
  edges: PositionedEdge[]
  svgH: number
  inboundIfaces: FrsModuleInterfaceRow[]
  outboundIfaces: FrsModuleInterfaceRow[]
  moduleByKey: Map<string, FrsModuleHydrated>
} {
  const moduleByKey = new Map(allModules.map((m) => [m.row_key, m]))

  const inboundIfaces = active.interfaces.filter(
    (i) => i.interface_kind !== 'ui_surface' && i.direction === 'inbound' && i.counterpart,
  )
  const outboundIfaces = active.interfaces.filter(
    (i) => i.interface_kind !== 'ui_surface' && i.direction === 'outbound' && i.counterpart,
  )

  const cycleCounterparts = new Set<string>()
  for (const i of outboundIfaces) {
    const ctr = i.counterpart!
    const target = moduleByKey.get(ctr)
    if (!target) continue
    const back = target.interfaces.some(
      (ti) => ti.direction === 'outbound' && ti.counterpart === active.row_key,
    )
    if (back) cycleCounterparts.add(ctr)
  }

  const inboundCounterparts = uniqueCounterparts(inboundIfaces)
  const outboundCounterparts = uniqueCounterparts(outboundIfaces)

  const topY = 50
  const centerY = inboundCounterparts.length > 0 ? 180 : 70
  const bottomY = centerY + 130
  const svgH = outboundCounterparts.length > 0
    ? bottomY + NODE_H / 2 + 30
    : centerY + NODE_H / 2 + 30

  const nodes: PositionedNode[] = []
  const edges: PositionedEdge[] = []

  nodes.push({
    rowKey: active.row_key,
    name: active.name,
    x: CENTER_X,
    y: centerY,
    isCenter: true,
    cycle: false,
  })

  inboundCounterparts.forEach((ctrKey, idx) => {
    const x = laneX(idx, inboundCounterparts.length)
    const ctrName = moduleByKey.get(ctrKey)?.name ?? ctrKey
    nodes.push({
      rowKey: ctrKey, name: ctrName, x, y: topY, isCenter: false, cycle: false,
    })
    const matching = inboundIfaces.filter((i) => i.counterpart === ctrKey)
    matching.forEach((iface, m) => {
      const offsetX = ((m - (matching.length - 1) / 2)) * 14
      edges.push({
        ifaceRowKey: iface.row_key,
        fromX: x, fromY: topY + NODE_H / 2,
        toX: CENTER_X + offsetX, toY: centerY - NODE_H / 2,
        transport: iface.transport ?? iface.interface_kind,
        inbound: true,
        cycle: false,
      })
    })
  })

  outboundCounterparts.forEach((ctrKey, idx) => {
    const x = laneX(idx, outboundCounterparts.length)
    const ctrName = moduleByKey.get(ctrKey)?.name ?? ctrKey
    const isCycle = cycleCounterparts.has(ctrKey)
    nodes.push({
      rowKey: ctrKey, name: ctrName, x, y: bottomY, isCenter: false, cycle: isCycle,
    })
    const matching = outboundIfaces.filter((i) => i.counterpart === ctrKey)
    matching.forEach((iface, m) => {
      const offsetX = ((m - (matching.length - 1) / 2)) * 14
      edges.push({
        ifaceRowKey: iface.row_key,
        fromX: CENTER_X + offsetX, fromY: centerY + NODE_H / 2,
        toX: x, toY: bottomY - NODE_H / 2,
        transport: iface.transport ?? iface.interface_kind,
        inbound: false,
        cycle: isCycle,
      })
    })
  })

  return { nodes, edges, svgH, inboundIfaces, outboundIfaces, moduleByKey }
}

function uniqueCounterparts(ifaces: FrsModuleInterfaceRow[]): string[] {
  const seen = new Set<string>()
  const out: string[] = []
  for (const i of ifaces) {
    const c = i.counterpart
    if (c && !seen.has(c)) {
      seen.add(c)
      out.push(c)
    }
  }
  return out
}

function laneX(idx: number, count: number): number {
  if (count === 1) return CENTER_X
  const padding = NODE_W / 2 + 16
  const usable = SVG_W - padding * 2
  return padding + (usable * idx) / (count - 1)
}

function truncate(s: string, max: number): string {
  return s.length > max ? `${s.slice(0, max - 1)}…` : s
}
