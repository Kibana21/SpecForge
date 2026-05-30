'use client'
/**
 * LineageMap (E2 provenance) — the intake provenance spine as a three-column
 * graph: Documents → Concepts → Clarifications. Hover any node to highlight its
 * connected path (forward impact + backward provenance). Opened as a modal from
 * the Understanding Studio. Mirrors the FrsCoverageGalaxy SVG approach.
 */
import { useEffect, useMemo, useState } from 'react'
import { X, FileText, Network, AlertTriangle } from 'lucide-react'
import { api } from '@/lib/api'
import type { ProjectLineage } from '@/lib/types'

interface Props {
  projectId: string
  open: boolean
  onClose: () => void
}

const COL_W = 220
const NODE_H = 26
const NODE_GAP = 10
const COL_GAP = 130
const PAD = 24

type NodeKind = 'doc' | 'concept' | 'clarif'
interface LNode { key: string; col: number; idx: number; label: string; kind: NodeKind; resolved?: boolean }

export function LineageMap({ projectId, open, onClose }: Props) {
  const [data, setData] = useState<ProjectLineage | null>(null)
  const [loading, setLoading] = useState(false)
  const [hover, setHover] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    setLoading(true); setData(null)
    api.projects.provenance(projectId)
      .then(setData).catch(() => setData(null)).finally(() => setLoading(false))
  }, [open, projectId])

  const { nodes, edges, height } = useMemo(() => {
    if (!data) return { nodes: [] as LNode[], edges: [] as [string, string][], height: 400 }
    const ns: LNode[] = []
    data.documents.forEach((d, i) => ns.push({ key: `doc:${d.id}`, col: 0, idx: i, label: d.label, kind: 'doc' }))
    data.concepts.forEach((c, i) => ns.push({ key: `con:${c.slug}`, col: 1, idx: i, label: c.title, kind: 'concept' }))
    data.clarifications.forEach((q, i) => ns.push({
      key: `clar:${q.id}`, col: 2, idx: i,
      label: q.question.length > 40 ? q.question.slice(0, 38) + '…' : q.question,
      kind: 'clarif', resolved: q.resolved,
    }))
    const es: [string, string][] = []
    data.concepts.forEach(c => c.doc_ids.forEach(d => es.push([`con:${c.slug}`, `doc:${d}`])))
    data.clarifications.forEach(q => {
      q.concept_slugs.forEach(s => es.push([`clar:${q.id}`, `con:${s}`]))
      q.doc_ids.forEach(d => es.push([`clar:${q.id}`, `doc:${d}`]))
    })
    const maxRows = Math.max(data.documents.length, data.concepts.length, data.clarifications.length, 1)
    return { nodes: ns, edges: es, height: PAD * 2 + maxRows * (NODE_H + NODE_GAP) }
  }, [data])

  if (!open) return null

  const colX = (c: number) => PAD + c * (COL_W + COL_GAP)
  const nodeY = (n: LNode) => PAD + n.idx * (NODE_H + NODE_GAP)
  const byKey = Object.fromEntries(nodes.map(n => [n.key, n])) as Record<string, LNode>

  // Which nodes/edges are in the hovered node's connected path.
  const lit = new Set<string>()
  if (hover) {
    lit.add(hover)
    for (const [a, b] of edges) {
      if (a === hover || b === hover) { lit.add(a); lit.add(b) }
    }
  }
  const width = colX(2) + COL_W + PAD

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-6" onClick={onClose}>
      <div className="bg-[var(--bg-surface)] rounded-2xl shadow-[var(--shadow-lg)] max-w-5xl w-full max-h-[85vh] overflow-hidden flex flex-col"
        onClick={e => e.stopPropagation()}>
        <div className="shrink-0 flex items-center gap-2 px-5 h-12 border-b border-[var(--border-default)]">
          <Network size={15} className="text-[var(--accent)]" />
          <span className="text-sm font-semibold text-[var(--text-primary)]">Provenance — how this understanding was built</span>
          <div className="flex-1" />
          <button onClick={onClose} className="text-[var(--text-tertiary)] hover:text-[var(--text-primary)]"><X size={16} /></button>
        </div>

        <div className="flex items-center gap-6 px-5 py-2 border-b border-[var(--border-subtle)] text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)]">
          <span className="flex items-center gap-1.5" style={{ width: COL_W }}><FileText size={11} /> Documents</span>
          <span className="flex items-center gap-1.5" style={{ width: COL_W }}><Network size={11} /> Concepts</span>
          <span className="flex items-center gap-1.5"><AlertTriangle size={11} /> Clarifications</span>
        </div>

        <div className="flex-1 overflow-auto p-2">
          {loading ? (
            <p className="text-sm text-[var(--text-tertiary)] p-8 text-center">Loading lineage…</p>
          ) : !data || nodes.length === 0 ? (
            <p className="text-sm text-[var(--text-tertiary)] p-8 text-center">
              No lineage yet — upload documents to build the project wiki, then clarifications will connect.
            </p>
          ) : (
            <svg width={width} height={height} className="mx-auto">
              {/* edges */}
              {edges.map(([a, b], i) => {
                const na = byKey[a], nb = byKey[b]
                if (!na || !nb) return null
                // a is the higher-column node (clar/con); b is lower (con/doc).
                const y1 = nodeY(na) + NODE_H / 2
                const y2 = nodeY(nb) + NODE_H / 2
                const fromX = colX(na.col), toX = colX(nb.col) + COL_W
                const mx = (fromX + toX) / 2
                const active = !hover || (lit.has(a) && lit.has(b))
                return (
                  <path key={i}
                    d={`M ${fromX} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${toX} ${y2}`}
                    fill="none"
                    stroke={active ? 'var(--accent)' : 'var(--border-default)'}
                    strokeOpacity={active ? 0.5 : 0.25}
                    strokeWidth={active ? 1.5 : 1} />
                )
              })}
              {/* nodes */}
              {nodes.map(n => {
                const x = colX(n.col), y = nodeY(n)
                const active = !hover || lit.has(n.key)
                const fill = n.kind === 'doc' ? 'var(--status-info-bg)'
                  : n.kind === 'concept' ? 'var(--accent-subtle)'
                  : n.resolved ? 'var(--bg-elevated)' : 'var(--status-warning-bg)'
                const stroke = n.kind === 'doc' ? 'var(--status-info)'
                  : n.kind === 'concept' ? 'var(--accent)'
                  : n.resolved ? 'var(--border-strong)' : 'var(--status-warning)'
                return (
                  <g key={n.key} opacity={active ? 1 : 0.35}
                    onMouseEnter={() => setHover(n.key)} onMouseLeave={() => setHover(null)}
                    style={{ cursor: 'default' }}>
                    <rect x={x} y={y} width={COL_W} height={NODE_H} rx={6}
                      fill={fill} stroke={stroke} strokeWidth={1} />
                    <text x={x + 8} y={y + NODE_H / 2 + 3.5} fontSize={11}
                      fill="var(--text-primary)" className="select-none">
                      {n.label.length > 30 ? n.label.slice(0, 29) + '…' : n.label}
                    </text>
                  </g>
                )
              })}
            </svg>
          )}
        </div>
        <div className="shrink-0 px-5 py-2 border-t border-[var(--border-subtle)] text-[11px] text-[var(--text-tertiary)]">
          Hover any node to trace its connections. Documents ground concepts; clarifications cite the concepts and sources they question.
        </div>
      </div>
    </div>
  )
}
