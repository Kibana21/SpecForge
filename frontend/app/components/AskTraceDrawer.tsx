'use client'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Network, FileText, MapPin, Hash, Sparkles, Telescope, Zap } from 'lucide-react'
import type { DeepTrace } from '@/lib/types'

function Section({ icon: Icon, title, count, children }: {
  icon: typeof Network; title: string; count: number; children: React.ReactNode
}) {
  if (count === 0) return null
  return (
    <div className="mb-5">
      <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)] mb-2 flex items-center gap-1.5">
        <Icon size={11} /> {title} <span className="text-[var(--text-tertiary)]">· {count}</span>
      </p>
      <div className="space-y-2">{children}</div>
    </div>
  )
}

export function AskTraceDrawer({ trace, onClose }: { trace: DeepTrace | null; onClose: () => void }) {
  return (
    <AnimatePresence>
      {trace && (
        <>
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/30 z-40"
          />
          <motion.div
            initial={{ x: '100%' }} animate={{ x: 0 }} exit={{ x: '100%' }}
            transition={{ type: 'spring', stiffness: 380, damping: 38 }}
            className="fixed right-0 top-0 bottom-0 w-full max-w-md z-50 bg-[var(--bg-surface)] border-l border-[var(--border-default)] shadow-2xl flex flex-col"
          >
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-3.5 border-b border-[var(--border-default)] bg-[var(--bg-elevated)]">
              <div>
                <p className="text-sm font-semibold text-[var(--text-primary)] flex items-center gap-2">
                  <Sparkles size={14} className="text-[var(--accent)]" /> Answer trace
                </p>
                <p className="text-[11px] text-[var(--text-tertiary)] mt-0.5 flex items-center gap-1.5">
                  {trace.mode === 'deep'
                    ? <><Telescope size={11} /> Deep search</>
                    : <><Zap size={11} /> Quick search</>}
                  {' · '}{trace.context_chars.toLocaleString()} chars of context
                  {trace.fallback_used ? ' · vector fallback used' : ''}
                </p>
              </div>
              <button onClick={onClose} className="p-1 rounded-md text-[var(--text-tertiary)] hover:bg-[var(--bg-base)] hover:text-[var(--text-secondary)]">
                <X size={16} />
              </button>
            </div>

            {/* Body */}
            <div className="flex-1 overflow-y-auto px-5 py-4">
              {/* Pipeline summary */}
              <div className="grid grid-cols-3 gap-2 mb-5">
                {[
                  { label: 'Concepts', value: trace.selected_concepts.length },
                  { label: 'Sections', value: trace.sections.length },
                  { label: 'Chunks', value: trace.chunks.length },
                ].map(({ label, value }) => (
                  <div key={label} className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-elevated)] px-3 py-2 text-center">
                    <p className="text-lg font-bold text-[var(--text-primary)]">{value}</p>
                    <p className="text-[10px] text-[var(--text-tertiary)]">{label}</p>
                  </div>
                ))}
              </div>

              <Section icon={Network} title="Selected concepts" count={trace.selected_concepts.length}>
                {trace.selected_concepts.map((c) => (
                  <div key={c.slug} className="rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] p-2.5">
                    <p className="text-xs font-semibold text-[var(--text-primary)]">{c.title}</p>
                    <p className="text-[11px] text-[var(--text-secondary)] mt-0.5 leading-relaxed">{c.brief}</p>
                  </div>
                ))}
              </Section>

              <Section icon={FileText} title="Documents included" count={trace.selected_documents.length}>
                {trace.selected_documents.map((d) => (
                  <div key={d.doc_id} className="rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] p-2.5">
                    <p className="text-xs font-semibold text-[var(--text-primary)]">{d.name}</p>
                    <p className="text-[11px] text-[var(--text-secondary)] mt-0.5 leading-relaxed">{d.brief}</p>
                  </div>
                ))}
              </Section>

              <Section icon={MapPin} title="Drilled sections" count={trace.sections.length}>
                {trace.sections.map((s, i) => (
                  <div key={`${s.node_id}-${i}`} className="rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] p-2.5">
                    <p className="text-xs font-medium text-[var(--text-primary)]">
                      {s.doc_name} › {s.title || `§${s.node_id}`}
                      {s.pages ? <span className="text-[var(--text-tertiary)]"> · pp {s.pages}</span> : null}
                    </p>
                    <p className="text-[11px] text-[var(--text-tertiary)] mt-1 leading-relaxed line-clamp-3">{s.excerpt}</p>
                  </div>
                ))}
              </Section>

              <Section icon={Hash} title="Vector chunks" count={trace.chunks.length}>
                {trace.chunks.map((c, i) => (
                  <div key={i} className="rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] p-2.5">
                    <p className="text-xs font-medium text-[var(--text-primary)] flex items-center justify-between gap-2">
                      <span className="truncate">{c.doc_name} · chunk {c.chunk_no}</span>
                      <span className="text-[10px] text-[var(--text-tertiary)] flex-shrink-0">sim {c.similarity}</span>
                    </p>
                    <p className="text-[11px] text-[var(--text-tertiary)] mt-1 leading-relaxed line-clamp-3">{c.excerpt}</p>
                  </div>
                ))}
              </Section>

              {/* Synthesis note */}
              <div className="rounded-lg border border-[var(--accent)]/30 bg-[var(--accent)]/[0.04] p-3 mt-2">
                <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)] mb-1.5 flex items-center gap-1.5">
                  <Sparkles size={11} /> Synthesis
                </p>
                <p className="text-[11px] text-[var(--text-secondary)] leading-relaxed">
                  {trace.mode === 'deep'
                    ? 'The concept pages, drilled sections, and any fallback chunks above were assembled into a single grounded context and streamed through the QA model with inline [Citation N] markers.'
                    : 'The retrieved sections and chunks above were assembled into a single context and streamed through the QA model with inline [Citation N] markers.'}
                  {' '}Total context fed: <strong>{trace.context_chars.toLocaleString()}</strong> characters.
                </p>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
