'use client'
import { useState, useEffect, useCallback } from 'react'
import ReactFlow, {
  Background, Controls, MiniMap, Handle, Position,
  useNodesState, useEdgesState, type Node, type Edge, type NodeProps, BackgroundVariant,
} from 'reactflow'
import 'reactflow/dist/style.css'
import dagre from 'dagre'
import { FileText, Network, X, BookOpen, RefreshCw } from 'lucide-react'
import { Markdown } from './Markdown'
import { api } from '@/lib/api'
import type { DocTreeResponse, DocTreeNode, WikiSectionContent } from '@/lib/types'

const NODE_W = 220
const NODE_H = 64

// Depth → accent ramp (root = strong accent, deeper = lighter/cooler)
const DEPTH_BG = ['var(--accent)', '#6366f1', '#8b5cf6', '#0ea5e9', '#14b8a6']
function depthColor(depth: number): string {
  return DEPTH_BG[Math.min(depth, DEPTH_BG.length - 1)]
}

// ── Custom nodes ────────────────────────────────────────────────────────────────

function DocRootNode({ data }: NodeProps<{ label: string; pages: string }>) {
  return (
    <div style={{ width: NODE_W, height: NODE_H }}
      className="rounded-xl border-2 border-[var(--accent)] bg-[var(--accent)] text-white shadow-md flex items-center gap-2 px-3">
      <Handle type="source" position={Position.Bottom} className="!bg-[var(--accent)]" />
      <BookOpen size={18} className="flex-shrink-0" />
      <div className="min-w-0">
        <p className="text-[11px] font-semibold truncate">{data.label}</p>
        <p className="text-[9px] opacity-80">{data.pages}</p>
      </div>
    </div>
  )
}

function SectionNode({ data }: NodeProps<{ label: string; pages: string; depth: number; selected: boolean }>) {
  const color = depthColor(data.depth)
  return (
    <div style={{ width: NODE_W, height: NODE_H, borderColor: data.selected ? color : 'var(--border-default)' }}
      className={`rounded-lg border bg-[var(--bg-surface)] shadow-sm flex items-stretch overflow-hidden transition-shadow hover:shadow-md ${data.selected ? 'ring-2' : ''}`}>
      <Handle type="target" position={Position.Top} className="!bg-[var(--border-default)]" />
      <span className="w-1 flex-shrink-0" style={{ background: color }} />
      <div className="min-w-0 flex-1 px-2.5 py-1.5 flex flex-col justify-center">
        <p className="text-[11px] font-medium text-[var(--text-primary)] leading-tight line-clamp-2">{data.label}</p>
        {data.pages && <p className="text-[9px] text-[var(--text-tertiary)] mt-0.5">pp {data.pages}</p>}
      </div>
      <Handle type="source" position={Position.Bottom} className="!bg-[var(--border-default)]" />
    </div>
  )
}

const nodeTypes = { docRoot: DocRootNode, section: SectionNode }

// ── Build + layout ──────────────────────────────────────────────────────────────

const ROOT_ID = '__doc_root__'

function buildGraph(tree: DocTreeResponse, selectedId: string | null): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = []
  const edges: Edge[] = []

  nodes.push({
    id: ROOT_ID, type: 'docRoot', position: { x: 0, y: 0 },
    data: { label: tree.doc_name, pages: tree.page_count ? `${tree.page_count} pages` : '' },
  })

  const walk = (n: DocTreeNode, parentId: string) => {
    nodes.push({
      id: n.node_id, type: 'section', position: { x: 0, y: 0 },
      data: { label: n.title || `§${n.node_id}`, pages: n.pages, depth: n.depth, selected: selectedId === n.node_id },
    })
    edges.push({
      id: `${parentId}->${n.node_id}`, source: parentId, target: n.node_id,
      type: 'smoothstep', animated: false,
      style: { stroke: 'var(--border-default)', strokeWidth: 1.5 },
    })
    for (const c of n.children) walk(c, n.node_id)
  }
  for (const root of tree.nodes) walk(root, ROOT_ID)

  // dagre layout (top-down)
  const g = new dagre.graphlib.Graph()
  g.setDefaultEdgeLabel(() => ({}))
  g.setGraph({ rankdir: 'TB', nodesep: 28, ranksep: 64, marginx: 20, marginy: 20 })
  nodes.forEach((nd) => g.setNode(nd.id, { width: NODE_W, height: NODE_H }))
  edges.forEach((e) => g.setEdge(e.source, e.target))
  dagre.layout(g)
  const laidOut = nodes.map((nd) => {
    const p = g.node(nd.id)
    return { ...nd, position: { x: p.x - NODE_W / 2, y: p.y - NODE_H / 2 } }
  })
  return { nodes: laidOut, edges }
}

// ── Panel ───────────────────────────────────────────────────────────────────────

export function DocStructurePanel({ appId, docId }: { appId: string; docId: string }) {
  const [tree, setTree] = useState<DocTreeResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [rfNodes, setRfNodes, onNodesChange] = useNodesState([])
  const [rfEdges, setRfEdges, onEdgesChange] = useEdgesState([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [section, setSection] = useState<WikiSectionContent | null>(null)
  const [sectionLoading, setSectionLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try { setTree(await api.apps.getDocTree(appId, docId)) }
    catch { setTree(null) }
    finally { setLoading(false) }
  }, [appId, docId])

  useEffect(() => { load() }, [load])
  useEffect(() => { setSelectedId(null); setSection(null) }, [docId])

  useEffect(() => {
    if (tree?.has_tree) {
      const { nodes, edges } = buildGraph(tree, selectedId)
      setRfNodes(nodes)
      setRfEdges(edges)
    }
  }, [tree, selectedId, setRfNodes, setRfEdges])

  const onNodeClick = useCallback(async (_: unknown, node: Node) => {
    if (node.id === ROOT_ID) return
    setSelectedId(node.id)
    setSection(null)
    setSectionLoading(true)
    try { setSection(await api.apps.getCorpusSection(appId, docId, node.id)) }
    catch { setSection(null) }
    finally { setSectionLoading(false) }
  }, [appId, docId])

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <RefreshCw size={18} className="animate-spin text-[var(--text-tertiary)]" />
      </div>
    )
  }

  if (!tree?.has_tree) {
    return (
      <div className="h-full flex flex-col items-center justify-center gap-3 p-8 text-center">
        <div className="w-12 h-12 rounded-full bg-[var(--bg-elevated)] border border-[var(--border-default)] flex items-center justify-center">
          <Network size={22} className="text-[var(--text-tertiary)]" strokeWidth={1.5} />
        </div>
        <div>
          <p className="text-sm font-semibold text-[var(--text-secondary)]">No PageIndex structure yet</p>
          <p className="text-xs text-[var(--text-tertiary)] mt-1 max-w-[280px] leading-relaxed">
            The reasoning tree is built during indexing. Re-index this document to generate it.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center gap-3 px-3 py-2 border-b border-[var(--border-subtle)] flex-shrink-0">
        <span className="text-[11px] text-[var(--text-tertiary)] flex items-center gap-1.5">
          <Network size={12} /> {tree.node_count} sections
        </span>
        {tree.page_count != null && <span className="text-[11px] text-[var(--text-tertiary)]">· {tree.page_count} pages</span>}
        <span className="text-[10px] text-[var(--text-tertiary)] ml-auto truncate">{tree.model}</span>
      </div>

      {/* Graph + detail */}
      <div className="flex-1 relative min-h-0">
        <ReactFlow
          nodes={rfNodes}
          edges={rfEdges}
          nodeTypes={nodeTypes}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={onNodeClick}
          fitView
          minZoom={0.2}
          proOptions={{ hideAttribution: true }}
        >
          <Background variant={BackgroundVariant.Dots} gap={18} size={1} color="var(--border-subtle)" />
          <Controls showInteractive={false} />
          <MiniMap pannable zoomable className="!bg-[var(--bg-elevated)]"
            nodeColor={(n) => (n.id === ROOT_ID ? 'var(--accent)' : depthColor((n.data?.depth as number) ?? 0))} />
        </ReactFlow>

        {/* Section detail overlay */}
        {selectedId && (
          <div className="absolute top-3 right-3 bottom-3 w-80 max-w-[70%] z-10 rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface)] shadow-2xl flex flex-col overflow-hidden">
            <div className="flex items-start justify-between gap-2 px-3 py-2.5 border-b border-[var(--border-subtle)] bg-[var(--bg-elevated)]">
              <div className="min-w-0">
                <p className="text-xs font-semibold text-[var(--text-primary)] leading-tight">
                  {section?.title || `Section ${selectedId}`}
                </p>
                {section?.pages && <p className="text-[10px] text-[var(--text-tertiary)] mt-0.5">pp {section.pages}</p>}
              </div>
              <button onClick={() => { setSelectedId(null); setSection(null) }}
                className="text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] flex-shrink-0"><X size={14} /></button>
            </div>
            <div className="flex-1 overflow-y-auto px-3 py-2.5">
              {sectionLoading ? (
                <div className="space-y-2 animate-pulse">
                  {[1, 0.9, 0.8, 0.95, 0.7].map((w, i) => (
                    <div key={i} className="h-2.5 bg-[var(--bg-elevated)] rounded-full" style={{ width: `${w * 100}%` }} />
                  ))}
                </div>
              ) : section ? (
                <>
                  {section.summary && (
                    <div className="mb-3 pb-3 border-b border-[var(--border-subtle)] rounded-md bg-[var(--bg-elevated)] px-2.5 py-2">
                      <p className="text-[9px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)] mb-1">Summary</p>
                      <Markdown md={section.summary} />
                    </div>
                  )}
                  {section.text
                    ? <Markdown md={section.text} />
                    : <p className="text-[11px] text-[var(--text-tertiary)]">(no text for this section)</p>}
                </>
              ) : (
                <p className="text-[11px] text-[var(--text-tertiary)] flex items-center gap-1.5"><FileText size={12} /> Couldn&apos;t load this section.</p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
