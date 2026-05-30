'use client'
/**
 * BR ↔ FRS Coverage Galaxy.
 *
 * Modal opened from the FRS header. Two-column SVG: BR nodes left (priority
 * order), FRS nodes right, cubic bezier curves for traced links. Uncovered
 * must-priority BRs render in `--frs-coverage-uncovered` with a pulsing glow
 * halo. Driven by `api.frs.coverage`.
 */
import { useMemo, useState } from 'react'
import useSWR from 'swr'
import { Loader2, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'
import type { FrsCoverage, FrsCoveragePoint } from '@/lib/types'

const NODE_W = 200
const NODE_H = 22
const COL_GAP = 320

interface Props {
  projectId: string
  open: boolean
  onClose: () => void
  /** Called when the user clicks a spec node to navigate to it. */
  onSelectSpec?: (specRowKey: string) => void
}

export function FrsCoverageGalaxy({ projectId, open, onClose, onSelectSpec }: Props) {
  const { data, isLoading } = useSWR<FrsCoverage>(
    open ? `frs-coverage-${projectId}` : null,
    () => api.frs.coverage(projectId),
    { revalidateOnFocus: false },
  )
  const [hoverBr, setHoverBr] = useState<string | null>(null)
  const [hoverSpec, setHoverSpec] = useState<string | null>(null)

  const layout = useMemo(() => {
    if (!data) return null
    return computeLayout(data)
  }, [data])

  if (!open) return null

  return (
    <>
      <div
        className="fixed inset-0 z-40 bg-black/40 backdrop-blur-[2px]"
        onClick={onClose}
        aria-hidden="true"
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="frs-coverage-title"
        className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none"
      >
        <div
          className="pointer-events-auto w-full max-w-4xl max-h-[90vh] rounded-2xl bg-[var(--bg-surface)] border border-[var(--border-default)] shadow-[var(--shadow-lg)] flex flex-col"
        >
          {/* Header */}
          <div className="flex items-start gap-3 px-5 py-3 border-b border-[var(--border-default)]">
            <div className="flex-1">
              <h2 id="frs-coverage-title" className="text-base font-semibold text-[var(--text-primary)]">
                BR → FRS Coverage Map
              </h2>
              {data ? (
                <p className="text-[11px] text-[var(--text-tertiary)] mt-0.5">
                  {data.covered_brs} of {data.total_brs} BRs covered
                  {data.must_uncovered > 0 && (
                    <span className="text-red-600 font-semibold">
                      {' '}· {data.must_uncovered} must-priority uncovered
                    </span>
                  )}
                </p>
              ) : null}
            </div>
            <button
              onClick={onClose}
              className="rounded-md p-1 text-[var(--text-tertiary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-elevated)] transition-colors"
              aria-label="Close"
            >
              <X size={16} />
            </button>
          </div>

          {/* Body */}
          <div className="flex-1 overflow-auto p-4">
            {isLoading && (
              <div className="flex items-center justify-center py-12 text-[var(--text-tertiary)]">
                <Loader2 size={16} className="animate-spin mr-2" /> Loading coverage…
              </div>
            )}
            {!isLoading && layout && (
              <svg
                width="100%"
                height={layout.height}
                viewBox={`0 0 ${layout.width} ${layout.height}`}
                className="block mx-auto"
                role="img"
                aria-label={`Coverage map: ${data?.covered_brs} of ${data?.total_brs} BRs covered`}
              >
                {/* Curves */}
                {layout.edges.map((e) => {
                  const dimmed =
                    (hoverBr !== null && e.brKey !== hoverBr) ||
                    (hoverSpec !== null && e.specKey !== hoverSpec)
                  return (
                    <path
                      key={`${e.brKey}-${e.specKey}`}
                      d={e.d}
                      stroke="var(--frs-coverage-covered)"
                      strokeOpacity={dimmed ? 0.1 : 0.55}
                      strokeWidth={
                        (hoverBr === e.brKey || hoverSpec === e.specKey) ? 2 : 1.25
                      }
                      fill="none"
                    />
                  )
                })}
                {/* BR nodes */}
                {layout.brs.map((n) => {
                  const uncovered = n.coveredBy.length === 0
                  const mustUncovered = uncovered && n.priority === 'must'
                  return (
                    <g
                      key={n.row_key}
                      onMouseEnter={() => setHoverBr(n.row_key)}
                      onMouseLeave={() => setHoverBr(null)}
                      className="cursor-default"
                    >
                      <rect
                        x={n.x} y={n.y}
                        width={NODE_W} height={NODE_H} rx={6}
                        fill={
                          mustUncovered ? 'var(--frs-coverage-uncovered)'
                          : uncovered ? '#FCD34D'
                          : 'var(--bg-elevated)'
                        }
                        stroke={
                          mustUncovered ? 'var(--frs-coverage-uncovered)'
                          : 'var(--border-default)'
                        }
                        strokeWidth={hoverBr === n.row_key ? 1.5 : 1}
                      >
                        {mustUncovered && (
                          <animate
                            attributeName="opacity"
                            values="1;0.5;1"
                            dur="2.2s"
                            repeatCount="indefinite"
                          />
                        )}
                      </rect>
                      <text
                        x={n.x + 8} y={n.y + NODE_H / 2 + 3}
                        fontSize="10"
                        fontWeight="600"
                        fill={mustUncovered ? '#fff' : 'var(--text-primary)'}
                        fontFamily="ui-monospace, monospace"
                        className="select-none"
                      >
                        {n.row_key}
                      </text>
                      <text
                        x={n.x + 76} y={n.y + NODE_H / 2 + 3}
                        fontSize="10"
                        fill={mustUncovered ? '#fff' : 'var(--text-secondary)'}
                        className="select-none"
                      >
                        {truncate(n.title, 22)}
                      </text>
                      <text
                        x={n.x + NODE_W - 4} y={n.y + NODE_H / 2 + 3}
                        fontSize="9"
                        textAnchor="end"
                        fill={mustUncovered ? 'rgba(255,255,255,0.85)' : 'var(--text-tertiary)'}
                        className="select-none"
                      >
                        {n.priority}
                      </text>
                    </g>
                  )
                })}
                {/* Spec nodes */}
                {layout.specs.map((n) => (
                  <g
                    key={n.row_key}
                    onMouseEnter={() => setHoverSpec(n.row_key)}
                    onMouseLeave={() => setHoverSpec(null)}
                    onClick={() => onSelectSpec?.(n.row_key)}
                    className={cn(onSelectSpec && 'cursor-pointer')}
                  >
                    <rect
                      x={n.x} y={n.y}
                      width={NODE_W} height={NODE_H} rx={6}
                      fill="var(--accent-subtle)"
                      stroke="var(--accent)"
                      strokeWidth={hoverSpec === n.row_key ? 1.75 : 1}
                    />
                    <text
                      x={n.x + 8} y={n.y + NODE_H / 2 + 3}
                      fontSize="10"
                      fontWeight="600"
                      fill="var(--accent)"
                      fontFamily="ui-monospace, monospace"
                      className="select-none"
                    >
                      {n.row_key}
                    </text>
                    <text
                      x={n.x + 100} y={n.y + NODE_H / 2 + 3}
                      fontSize="10"
                      fill="var(--text-primary)"
                      className="select-none"
                    >
                      {truncate(n.title, 18)}
                    </text>
                  </g>
                ))}
              </svg>
            )}
            {!isLoading && layout && layout.brs.length === 0 && (
              <div className="text-center py-12 text-[var(--text-tertiary)] text-sm italic">
                No BRs to render — has the BRD been validated?
              </div>
            )}
          </div>

          {/* Footer */}
          {data && (
            <div className="border-t border-[var(--border-default)] px-5 py-2 text-[11px] text-[var(--text-secondary)] flex items-center gap-4">
              <span className="inline-flex items-center gap-1">
                <span className="inline-block w-3 h-3 rounded bg-[var(--accent-subtle)] border border-[var(--accent)]" />
                Covered FRS
              </span>
              <span className="inline-flex items-center gap-1">
                <span className="inline-block w-3 h-3 rounded bg-[var(--frs-coverage-uncovered)]" />
                Must-priority uncovered
              </span>
              <span className="inline-flex items-center gap-1">
                <span className="inline-block w-3 h-3 rounded bg-amber-300 border border-amber-400" />
                Should/Could uncovered
              </span>
            </div>
          )}
        </div>
      </div>
    </>
  )
}

// ── Layout ──────────────────────────────────────────────────────────────────

interface BrNode {
  row_key: string
  title: string
  priority: 'must' | 'should' | 'could' | 'wont'
  coveredBy: string[]
  x: number
  y: number
}
interface SpecNode {
  row_key: string
  title: string
  x: number
  y: number
}
interface Edge {
  brKey: string
  specKey: string
  d: string
}

function computeLayout(data: FrsCoverage) {
  const PRIORITY_ORDER: Record<FrsCoveragePoint['br_priority'], number> = {
    must: 0, should: 1, could: 2, wont: 3,
  }
  const brs = [...data.brs].sort((a, b) =>
    PRIORITY_ORDER[a.br_priority] - PRIORITY_ORDER[b.br_priority]
    || a.br_row_key.localeCompare(b.br_row_key),
  )
  const specs = [...data.specs].sort((a, b) =>
    a.row_key.localeCompare(b.row_key),
  )

  const TOP = 16
  const ROW_H = NODE_H + 8
  const leftX = 16
  const rightX = leftX + COL_GAP

  const brNodes: BrNode[] = brs.map((b, i) => ({
    row_key: b.br_row_key,
    title: b.br_title,
    priority: b.br_priority,
    coveredBy: b.covered_by,
    x: leftX,
    y: TOP + i * ROW_H,
  }))
  const specNodes: SpecNode[] = specs.map((s, i) => ({
    row_key: s.row_key,
    title: s.title,
    x: rightX,
    y: TOP + i * ROW_H,
  }))
  const specByKey = new Map(specNodes.map((s) => [s.row_key, s]))
  const brByKey = new Map(brNodes.map((b) => [b.row_key, b]))

  const edges: Edge[] = []
  for (const b of brNodes) {
    for (const sk of b.coveredBy) {
      const s = specByKey.get(sk)
      if (!s) continue
      const x1 = b.x + NODE_W
      const y1 = b.y + NODE_H / 2
      const x2 = s.x
      const y2 = s.y + NODE_H / 2
      const cx1 = x1 + (x2 - x1) * 0.5
      const cx2 = x2 - (x2 - x1) * 0.5
      edges.push({
        brKey: b.row_key,
        specKey: s.row_key,
        d: `M ${x1} ${y1} C ${cx1} ${y1}, ${cx2} ${y2}, ${x2} ${y2}`,
      })
    }
  }

  const totalRows = Math.max(brNodes.length, specNodes.length, 1)
  const height = TOP + totalRows * ROW_H + 16
  const width = rightX + NODE_W + 16
  return { brs: brNodes, specs: specNodes, edges, width, height, specByKey, brByKey }
}

function truncate(s: string, max: number): string {
  return s.length > max ? `${s.slice(0, max - 1)}…` : s
}
