'use client'
/**
 * EvidencePanel — live cross-index reference rail for the Project Copilot.
 * Updates on every partial/final trace event from the SSE stream.
 * Shows: grounding meter, per-document tree map (visited nodes highlighted),
 * wiki concept cards (expandable to grounded sections), and app fact cards.
 */
import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Network, FileText, MapPin, Database, ChevronDown, ChevronRight, Sparkles } from 'lucide-react'
import type { ProjectAskTrace, TreeMapDoc, TreeMapNode, TraceFact } from '@/lib/types'
import { IntakeTraceChip } from './IntakeTraceChip'

interface Props {
  projectId: string
  trace: ProjectAskTrace | null
  hoverToken: string | null
}

// ── Grounding meter ───────────────────────────────────────────────────────────

function GroundingMeter({ trace }: { trace: ProjectAskTrace }) {
  const sections = trace.sections.length
  const concepts = trace.selected_concepts.length
  const facts = (trace.facts ?? []).length
  const docs = trace.tree_map?.length ?? 0
  const strength = Math.min(1, (sections + concepts * 1.5 + facts * 0.5) / 6)

  const label = strength >= 0.7 ? 'strong' : strength >= 0.35 ? 'medium' : 'weak'
  const barColor = strength >= 0.7
    ? 'bg-emerald-500'
    : strength >= 0.35
    ? 'bg-amber-500'
    : 'bg-[var(--text-tertiary)]'

  return (
    <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3">
      <div className="flex items-center justify-between mb-2">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)] flex items-center gap-1.5">
          <Sparkles size={10} /> Grounding
        </p>
        <span className="text-[10px] text-[var(--text-tertiary)]">{label}</span>
      </div>
      <div className="h-1.5 rounded-full bg-[var(--bg-base)] overflow-hidden mb-2">
        <motion.div
          className={`h-full rounded-full ${barColor}`}
          initial={{ width: 0 }}
          animate={{ width: `${strength * 100}%` }}
          transition={{ type: 'spring', stiffness: 300, damping: 30 }}
        />
      </div>
      <p className="text-[10px] text-[var(--text-tertiary)]">
        {sections} section{sections !== 1 ? 's' : ''} · {docs} doc{docs !== 1 ? 's' : ''} · {concepts} concept{concepts !== 1 ? 's' : ''}{facts ? ` · ${facts} fact${facts !== 1 ? 's' : ''}` : ''}
        {trace.partial && <span className="ml-1 text-[var(--accent)]">· researching…</span>}
      </p>
    </div>
  )
}

// ── Tree map ──────────────────────────────────────────────────────────────────

function TreeMapItem({
  doc,
  projectId,
  hoverToken,
}: {
  doc: TreeMapDoc
  projectId: string
  hoverToken: string | null
}) {
  const [open, setOpen] = useState(true)
  const visitedSet = new Set(doc.visited)

  return (
    <div className="rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] overflow-hidden">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-2 px-3 py-2 hover:bg-[var(--bg-elevated)] transition-colors"
      >
        <FileText size={12} className="text-[var(--text-tertiary)] flex-shrink-0" />
        <span className="text-xs font-medium text-[var(--text-primary)] truncate flex-1 text-left">{doc.doc_name}</span>
        {doc.visited.length > 0 && (
          <span className="text-[10px] text-[var(--accent)] flex-shrink-0 font-semibold">{doc.visited.length} read</span>
        )}
        {open ? <ChevronDown size={12} className="text-[var(--text-tertiary)] flex-shrink-0" /> : <ChevronRight size={12} className="text-[var(--text-tertiary)] flex-shrink-0" />}
      </button>
      {open && doc.outline.length > 0 && (
        <div className="px-3 pb-2 space-y-0.5 border-t border-[var(--border-subtle)]">
          {doc.outline.map((node) => {
            const visited = visitedSet.has(node.node_id)
            const token = `S:${doc.doc_id}:${node.node_id}`
            const hover = hoverToken === token
            return (
              <div
                key={node.node_id}
                style={{ paddingLeft: `${node.depth * 12}px` }}
                className={`flex items-center gap-1.5 py-0.5 rounded px-1 transition-colors ${hover ? 'bg-[var(--accent)]/10 ring-1 ring-[var(--accent)]/40' : ''}`}
              >
                {visited ? (
                  <IntakeTraceChip projectId={projectId} token={token} inline />
                ) : (
                  <span className="text-[10px] text-[var(--text-tertiary)] truncate">
                    <span className="mr-1 opacity-30">○</span>{node.title || node.node_id}
                  </span>
                )}
                {visited && (
                  <span className="text-[9px] text-[var(--accent)] flex-shrink-0 font-medium">read</span>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ── Concept list ──────────────────────────────────────────────────────────────

function ConceptCard({
  concept,
  projectId,
  hoverToken,
}: {
  concept: { slug: string; title: string; brief: string; tree_node_refs?: Array<{ doc_id: string; node_id: string; title?: string }> }
  projectId: string
  hoverToken: string | null
}) {
  const token = `C:${concept.slug}`
  const hover = hoverToken === token
  return (
    <div className={`rounded-lg border p-2.5 transition-colors ${hover ? 'border-[var(--accent)] bg-[var(--accent)]/[0.04]' : 'border-[var(--border-default)] bg-[var(--bg-surface)]'}`}>
      <div className="flex items-center gap-1.5 mb-0.5">
        <Network size={11} className="text-[var(--accent)] flex-shrink-0" />
        <IntakeTraceChip projectId={projectId} token={token} inline />
      </div>
      <p className="text-[11px] text-[var(--text-secondary)] leading-relaxed">{concept.brief}</p>
    </div>
  )
}

// ── Fact list ─────────────────────────────────────────────────────────────────

function FactCard({
  fact,
  projectId,
  hoverToken,
}: {
  fact: TraceFact
  projectId: string
  hoverToken: string | null
}) {
  const token = `F:${fact.id}`
  const hover = hoverToken === token
  return (
    <div className={`rounded-lg border p-2.5 transition-colors ${hover ? 'border-[var(--accent)] bg-[var(--accent)]/[0.04]' : 'border-[var(--border-default)] bg-[var(--bg-surface)]'}`}>
      <div className="flex items-center gap-1.5 mb-0.5">
        <Database size={11} className="text-[var(--text-tertiary)] flex-shrink-0" />
        <span className="text-[10px] text-[var(--text-tertiary)]">{fact.app} · {fact.kind}</span>
        <IntakeTraceChip projectId={projectId} token={token} inline />
      </div>
      <p className="text-[11px] text-[var(--text-secondary)] leading-relaxed">{fact.text.slice(0, 140)}</p>
    </div>
  )
}

// ── Section label ─────────────────────────────────────────────────────────────

function SectionLabel({ icon: Icon, title, count }: { icon: typeof Network; title: string; count: number }) {
  if (count === 0) return null
  return (
    <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)] flex items-center gap-1.5">
      <Icon size={10} /> {title} <span>· {count}</span>
    </p>
  )
}

// ── Empty state ───────────────────────────────────────────────────────────────

function EvidenceEmpty() {
  return (
    <div className="h-full flex flex-col items-center justify-center gap-2 p-6 text-center">
      <div className="w-10 h-10 rounded-full bg-[var(--bg-elevated)] border border-[var(--border-subtle)] flex items-center justify-center">
        <MapPin size={16} className="text-[var(--text-tertiary)]" strokeWidth={1.5} />
      </div>
      <p className="text-xs text-[var(--text-tertiary)] max-w-[200px]">
        References will appear here as the copilot navigates the knowledge base.
      </p>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export function EvidencePanel({ projectId, trace, hoverToken }: Props) {
  if (!trace) {
    return (
      <div className="rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface)] h-full flex items-center">
        <EvidenceEmpty />
      </div>
    )
  }

  const facts = trace.facts ?? []
  const treeMap = trace.tree_map ?? []
  const concepts = trace.selected_concepts

  return (
    <div className="rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface)] overflow-y-auto h-full">
      <div className="p-3 space-y-3">
        <GroundingMeter trace={trace} />

        {treeMap.length > 0 && (
          <div className="space-y-2">
            <SectionLabel icon={FileText} title="Documents" count={treeMap.length} />
            <AnimatePresence initial={false}>
              {treeMap.map((doc) => (
                <motion.div key={doc.doc_id} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }}>
                  <TreeMapItem doc={doc} projectId={projectId} hoverToken={hoverToken} />
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        )}

        {concepts.length > 0 && (
          <div className="space-y-2">
            <SectionLabel icon={Network} title="Concepts" count={concepts.length} />
            {concepts.map((c) => (
              <ConceptCard key={c.slug} concept={c} projectId={projectId} hoverToken={hoverToken} />
            ))}
          </div>
        )}

        {facts.length > 0 && (
          <div className="space-y-2">
            <SectionLabel icon={Database} title="App facts" count={facts.length} />
            {facts.map((f) => (
              <FactCard key={f.id} fact={f} projectId={projectId} hoverToken={hoverToken} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
