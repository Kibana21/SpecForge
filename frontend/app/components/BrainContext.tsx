'use client'
import { useState, useEffect, useCallback, useRef } from 'react'
import {
  Sparkles, RefreshCw, ChevronDown, ChevronUp, AlertTriangle,
  Brain, Search, X, Pencil, Trash2, Check,
} from 'lucide-react'
import { toast } from 'sonner'
import { api } from '@/lib/api'
import type { AppFact, BrainContextResponse, FactKind, FactConfidence } from '@/lib/types'

// ── Constants ──────────────────────────────────────────────────────────────────

const KIND_COLOR: Record<FactKind, { dot: string; bg: string; text: string; border: string }> = {
  capability:  { dot: 'bg-emerald-500', bg: 'bg-emerald-50',  text: 'text-emerald-700',  border: 'border-emerald-200' },
  constraint:  { dot: 'bg-orange-500',  bg: 'bg-orange-50',   text: 'text-orange-700',   border: 'border-orange-200'  },
  limitation:  { dot: 'bg-red-500',     bg: 'bg-red-50',      text: 'text-red-700',      border: 'border-red-200'     },
  integration: { dot: 'bg-blue-500',    bg: 'bg-blue-50',     text: 'text-blue-700',     border: 'border-blue-200'    },
  gotcha:      { dot: 'bg-violet-500',  bg: 'bg-violet-50',   text: 'text-violet-700',   border: 'border-violet-200'  },
}
const KIND_LABEL: Record<FactKind, string> = {
  capability: 'Capabilities', constraint: 'Constraints',
  limitation: 'Limitations', integration: 'Integrations', gotcha: 'Gotchas',
}
const KIND_DESC: Record<FactKind, string> = {
  capability:  'What the system can do',
  constraint:  'Rules and limits it must operate within',
  limitation:  'What the system cannot do or handles poorly',
  integration: 'Connections with other systems and protocols',
  gotcha:      'Non-obvious behaviour that would surprise a developer',
}
const FACT_KINDS: FactKind[] = ['capability', 'constraint', 'limitation', 'integration', 'gotcha']
const CONFIDENCES: FactConfidence[] = ['high', 'medium', 'low']
const CONFIDENCE_BAR: Record<string, number> = { high: 1, medium: 0.6, low: 0.3 }

// ── Source facts expandable section ───────────────────────────────────────────

function SourceFactsSection({ sourceFactIds, allSourceFacts }: {
  sourceFactIds: string[]
  allSourceFacts: AppFact[]
}) {
  const [open, setOpen] = useState(false)
  const sources = allSourceFacts.filter(f => sourceFactIds.includes(f.id))
  if (sources.length === 0) return null
  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-1.5 text-[10px] text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] transition-colors"
      >
        {open ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
        {open ? 'Hide' : `Sources (${sources.length})`}
      </button>
      {open && (
        <div className="mt-2 space-y-1.5 pl-3 border-l-2 border-[var(--border-subtle)]">
          {sources.map(sf => (
            <div key={sf.id} className="flex flex-col gap-0.5">
              <p className="text-[11px] text-[var(--text-secondary)] leading-relaxed">"{sf.text}"</p>
              {sf.source_ref && (
                <span className="text-[10px] text-[var(--text-tertiary)] font-medium">{sf.source_ref}</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Confidence bar ─────────────────────────────────────────────────────────────

function ConfidencePip({ confidence }: { confidence: string }) {
  const fill = CONFIDENCE_BAR[confidence] ?? 0.5
  const color = confidence === 'high' ? 'bg-emerald-500' : confidence === 'medium' ? 'bg-amber-400' : 'bg-slate-300'
  return (
    <div className="flex items-center gap-1.5" title={`${confidence} confidence`}>
      <div className="w-12 h-1 rounded-full bg-[var(--bg-base)] overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${fill * 100}%` }} />
      </div>
      <span className="text-[10px] text-[var(--text-tertiary)] capitalize">{confidence}</span>
    </div>
  )
}

// ── Brain Fact Card ────────────────────────────────────────────────────────────

function BrainFactCard({
  fact, allSourceFacts, appId, selected, onToggleSelect, onUpdate, onDelete,
}: {
  fact: AppFact
  allSourceFacts: AppFact[]
  appId: string
  selected: boolean
  onToggleSelect: (id: string) => void
  onUpdate: (f: AppFact) => void
  onDelete: (id: string) => void
}) {
  const [editing, setEditing] = useState(false)
  const [editText, setEditText] = useState(fact.text)
  const [editConfidence, setEditConfidence] = useState<FactConfidence>(fact.confidence as FactConfidence)
  const [saving, setSaving] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)

  const colors = KIND_COLOR[fact.kind as FactKind]
  const sourceDocNames = Array.from(new Set(
    allSourceFacts
      .filter(sf => fact.source_fact_ids.includes(sf.id))
      .map(sf => sf.source_ref)
      .filter(Boolean)
  ))

  async function handleSave() {
    if (!editText.trim()) return
    setSaving(true)
    try {
      const updated = await api.apps.updateFact(appId, fact.id, {
        text: editText.trim(),
        confidence: editConfidence,
      })
      onUpdate(updated)
      setEditing(false)
    } catch {
      toast.error('Failed to update fact')
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    try {
      await api.apps.deleteFact(appId, fact.id)
      onDelete(fact.id)
    } catch {
      toast.error('Failed to delete fact')
    }
  }

  if (editing) {
    return (
      <div className="rounded-xl border border-[var(--accent)]/30 bg-[var(--accent)]/[0.03] p-4 space-y-3">
        <textarea
          value={editText}
          onChange={e => setEditText(e.target.value)}
          rows={3}
          className="w-full text-xs rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] text-[var(--text-primary)] px-3 py-2 resize-none focus:outline-none focus:ring-1 focus:ring-[var(--accent)]/40"
        />
        <div className="flex items-center justify-between gap-3">
          <select
            value={editConfidence}
            onChange={e => setEditConfidence(e.target.value as FactConfidence)}
            className="text-[11px] rounded border border-[var(--border-default)] bg-[var(--bg-surface)] text-[var(--text-secondary)] px-2 py-1"
          >
            {CONFIDENCES.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
          <div className="flex items-center gap-2">
            <button onClick={() => { setEditing(false); setEditText(fact.text); setEditConfidence(fact.confidence as FactConfidence) }}
              className="text-[11px] text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] px-2 py-1">
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={!editText.trim() || saving}
              className="flex items-center gap-1 text-[11px] font-semibold text-white bg-[var(--accent)] px-3 py-1 rounded disabled:opacity-50 hover:opacity-90"
            >
              <Check size={10} />
              {saving ? 'Saving…' : 'Save'}
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className={`group rounded-xl border bg-[var(--bg-surface)] p-4 transition-all duration-150 ${
      selected
        ? 'border-[var(--accent)]/40 bg-[var(--accent)]/[0.03] shadow-sm'
        : 'border-[var(--border-default)] hover:shadow-sm'
    }`}>
      <div className="flex items-start gap-3">
        <input
          type="checkbox"
          checked={selected}
          onChange={() => onToggleSelect(fact.id)}
          className="mt-1 flex-shrink-0 accent-[var(--accent)] cursor-pointer"
        />
        <div className={`mt-1.5 w-2 h-2 rounded-full flex-shrink-0 ${colors.dot}`} />
        <div className="flex-1 min-w-0">
          <p className="text-sm text-[var(--text-primary)] leading-relaxed">{fact.text}</p>
          <div className="flex items-center gap-3 mt-2.5 flex-wrap">
            <ConfidencePip confidence={fact.confidence} />
            {sourceDocNames.map(name => (
              <span key={name}
                className={`text-[10px] font-medium px-2 py-0.5 rounded-full border ${colors.bg} ${colors.text} ${colors.border}`}>
                {name}
              </span>
            ))}
          </div>
          <SourceFactsSection sourceFactIds={fact.source_fact_ids} allSourceFacts={allSourceFacts} />
        </div>
        {/* Per-card actions */}
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0">
          {confirmDelete ? (
            <>
              <button onClick={handleDelete}
                className="text-[10px] font-semibold text-red-600 hover:text-red-700 px-1.5 py-0.5 rounded">
                Confirm
              </button>
              <button onClick={() => setConfirmDelete(false)}
                className="text-[10px] text-[var(--text-tertiary)] px-1 py-0.5 rounded">
                <X size={10} />
              </button>
            </>
          ) : (
            <>
              <button onClick={() => setEditing(true)}
                className="p-1.5 rounded hover:bg-[var(--bg-elevated)] text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]">
                <Pencil size={11} />
              </button>
              <button onClick={() => setConfirmDelete(true)}
                className="p-1.5 rounded hover:bg-[var(--bg-elevated)] text-[var(--text-tertiary)] hover:text-red-500">
                <Trash2 size={11} />
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Main BrainContext component ────────────────────────────────────────────────

interface Props {
  appId: string
  initialSynthesizedAt: string | null
  initialStatus: string
}

export function BrainContext({ appId, initialSynthesizedAt, initialStatus }: Props) {
  const [data, setData] = useState<BrainContextResponse | null>(null)
  const [facts, setFacts] = useState<AppFact[]>([])
  const [loading, setLoading] = useState(true)
  const [synthesizing, setSynthesizing] = useState(initialStatus === 'running')
  const [sourceFacts, setSourceFacts] = useState<AppFact[]>([])

  // Filters + selection
  const [search, setSearch] = useState('')
  const [activeKind, setActiveKind] = useState<FactKind | 'all'>('all')
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [bulkDeleting, setBulkDeleting] = useState(false)

  const load = useCallback(async () => {
    try {
      const result = await api.apps.getBrainContext(appId)
      setData(result)
      setFacts(result.facts)
      setSynthesizing(result.status === 'running')
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }, [appId])

  useEffect(() => { load() }, [load])

  // Poll while synthesizing
  useEffect(() => {
    if (!synthesizing) return
    const id = setInterval(async () => {
      try {
        const result = await api.apps.getBrainContext(appId)
        setData(result)
        setFacts(result.facts)
        if (result.status !== 'running') {
          setSynthesizing(false)
          clearInterval(id)
          toast.success('Brain Context synthesized', { description: `${result.facts.length} synthesized facts ready.` })
        }
      } catch {
        clearInterval(id)
        setSynthesizing(false)
      }
    }, 4000)
    return () => clearInterval(id)
  }, [synthesizing, appId])

  // Load source facts for traceability
  useEffect(() => {
    if (!facts.length) return
    const sourceIds = Array.from(new Set(facts.flatMap(f => f.source_fact_ids)))
    if (!sourceIds.length) return
    api.apps.listFacts(appId, { status: 'active' })
      .then(all => { if (Array.isArray(all)) setSourceFacts(all.filter(f => f.source !== 'brain')) })
      .catch(() => {})
  }, [appId, facts])

  async function handleSynthesize() {
    setSynthesizing(true)
    try {
      await api.apps.synthesizeBrainContext(appId)
      toast.info('Synthesis started', { description: 'This may take 20–60 seconds.' })
    } catch (e: unknown) {
      setSynthesizing(false)
      toast.error('Synthesis failed', { description: e instanceof Error ? e.message : 'Unknown error' })
    }
  }

  function toggleSelect(id: string) {
    setSelectedIds(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  function toggleSelectAll() {
    if (selectedIds.size === filtered.length && filtered.length > 0) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(filtered.map(f => f.id)))
    }
  }

  async function handleBulkDelete() {
    setBulkDeleting(true)
    const ids = Array.from(selectedIds)
    const results = await Promise.allSettled(ids.map(id => api.apps.deleteFact(appId, id)))
    const failed = results.filter(r => r.status === 'rejected').length
    setFacts(prev => prev.filter(f => !selectedIds.has(f.id)))
    setSelectedIds(new Set())
    setBulkDeleting(false)
    if (failed > 0) toast.error(`${failed} deletion(s) failed`)
    else toast.success(`Deleted ${ids.length} fact${ids.length !== 1 ? 's' : ''}`)
  }

  // Filtering
  const q = search.trim().toLowerCase()
  const filtered = facts.filter(f => {
    if (activeKind !== 'all' && f.kind !== activeKind) return false
    if (q && !f.text.toLowerCase().includes(q)) return false
    return true
  })

  const kindCounts = FACT_KINDS.reduce<Record<string, number>>((acc, k) => {
    acc[k] = facts.filter(f => f.kind === k).length
    return acc
  }, {})

  const byKind = FACT_KINDS
    .map(k => ({ kind: k, facts: filtered.filter(f => f.kind === k) }))
    .filter(g => g.facts.length > 0)

  const isStale = data?.synthesized_at && sourceFacts.some(sf => {
    if (!data.synthesized_at) return false
    return new Date(sf.updated_at) > new Date(data.synthesized_at)
  })

  const selectAllRef = useRef<HTMLInputElement>(null)
  useEffect(() => {
    if (!selectAllRef.current) return
    selectAllRef.current.indeterminate = selectedIds.size > 0 && selectedIds.size < filtered.length
  }, [selectedIds.size, filtered.length])

  if (loading) {
    return (
      <div className="max-w-2xl space-y-4 animate-pulse">
        <div className="h-4 bg-[var(--bg-elevated)] rounded-full w-1/3" />
        <div className="h-20 bg-[var(--bg-elevated)] rounded-xl" />
        <div className="h-32 bg-[var(--bg-elevated)] rounded-xl" />
      </div>
    )
  }

  return (
    <div className="max-w-2xl space-y-5">
      {/* ── Header ── */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold text-[var(--text-primary)] flex items-center gap-2">
            <Brain size={15} className="text-[var(--accent)]" />
            Brain Context
          </h2>
          <p className="text-xs text-[var(--text-tertiary)] mt-1">
            LLM synthesis of all document-level facts with full traceability.
          </p>
        </div>
        <button
          onClick={handleSynthesize}
          disabled={synthesizing}
          className="flex items-center gap-2 rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] px-4 py-2 text-xs font-medium text-[var(--text-secondary)] hover:border-[var(--accent)] hover:text-[var(--accent)] disabled:opacity-60 transition-all duration-150 flex-shrink-0"
        >
          {synthesizing ? <RefreshCw size={12} className="animate-spin" /> : <Sparkles size={12} />}
          {synthesizing ? 'Synthesizing…' : 'Synthesize'}
        </button>
      </div>

      {/* ── Status bar ── */}
      {(data?.synthesized_at || synthesizing) && (
        <div className="flex items-center gap-3 text-[11px] text-[var(--text-tertiary)] px-4 py-2.5 rounded-lg bg-[var(--bg-elevated)] border border-[var(--border-subtle)]">
          {synthesizing ? (
            <>
              <RefreshCw size={11} className="animate-spin text-[var(--accent)] flex-shrink-0" />
              <span>Synthesizing facts across all corpus documents…</span>
            </>
          ) : (
            <>
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 flex-shrink-0" />
              <span>
                Last synthesized{' '}
                {data?.synthesized_at
                  ? new Date(data.synthesized_at).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
                  : '—'
                }
                {' · '}{facts.length} facts · {data?.source_doc_count ?? 0} source doc{data?.source_doc_count !== 1 ? 's' : ''}
              </span>
            </>
          )}
        </div>
      )}

      {/* ── Stale banner ── */}
      {isStale && !synthesizing && (
        <div className="flex items-center gap-2.5 px-4 py-2.5 rounded-lg bg-amber-50 border border-amber-200 text-[11px] text-amber-700">
          <AlertTriangle size={12} className="flex-shrink-0" />
          <span>Documents have been updated since last synthesis. Re-synthesize for fresh results.</span>
          <button onClick={handleSynthesize} className="ml-auto font-semibold hover:underline flex-shrink-0">
            Synthesize now
          </button>
        </div>
      )}

      {/* ── Empty state ── */}
      {!synthesizing && facts.length === 0 && (
        <div className="rounded-xl border border-dashed border-[var(--border-default)] p-10 flex flex-col items-center gap-4 text-center">
          <div className="w-14 h-14 rounded-2xl bg-[var(--bg-elevated)] border border-[var(--border-default)] flex items-center justify-center">
            <Brain size={26} className="text-[var(--text-tertiary)]" strokeWidth={1.5} />
          </div>
          <div>
            <p className="text-sm font-semibold text-[var(--text-secondary)]">No Brain Context yet</p>
            <p className="text-xs text-[var(--text-tertiary)] mt-1.5 max-w-[300px] leading-relaxed">
              Upload and index corpus documents, then click <strong>Synthesize</strong> to generate a unified, traced knowledge view.
            </p>
          </div>
          <button onClick={handleSynthesize}
            className="flex items-center gap-2 text-xs font-semibold text-[var(--accent)] border border-[var(--accent)]/30 px-4 py-2 rounded-lg hover:bg-[var(--accent)]/5 transition-colors">
            <Sparkles size={12} />
            Synthesize now
          </button>
        </div>
      )}

      {/* ── Search + filters (shown when facts exist) ── */}
      {facts.length > 0 && (
        <div className="space-y-2">
          {/* Search row */}
          <div className="flex items-center gap-2">
            <input
              ref={selectAllRef}
              type="checkbox"
              title="Select all visible"
              checked={filtered.length > 0 && selectedIds.size === filtered.length}
              onChange={toggleSelectAll}
              className="flex-shrink-0 accent-[var(--accent)] cursor-pointer"
            />
            <div className="relative flex-1">
              <Search size={11} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)] pointer-events-none" />
              <input
                type="text"
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Search brain facts…"
                className="w-full pl-7 pr-7 py-1.5 text-[11px] rounded-md border border-[var(--border-default)] bg-[var(--bg-base)] text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]/40 focus:border-[var(--accent)]/60"
              />
              {search && (
                <button onClick={() => setSearch('')}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]">
                  <X size={10} />
                </button>
              )}
            </div>
          </div>

          {/* Kind filter chips */}
          <div className="flex items-center gap-1.5 overflow-x-auto scrollbar-none">
            <button
              onClick={() => setActiveKind('all')}
              className={`flex-shrink-0 text-[10px] font-medium px-2.5 py-1 rounded-full border transition-colors ${
                activeKind === 'all'
                  ? 'bg-[var(--accent)] border-[var(--accent)] text-white'
                  : 'border-[var(--border-default)] text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]'
              }`}
            >
              All · {facts.length}
            </button>
            {FACT_KINDS.filter(k => kindCounts[k] > 0).map(k => {
              const c = KIND_COLOR[k]
              const isActive = activeKind === k
              return (
                <button key={k}
                  onClick={() => setActiveKind(activeKind === k ? 'all' : k)}
                  className={`flex-shrink-0 flex items-center gap-1.5 text-[10px] font-medium px-2.5 py-1 rounded-full border transition-colors ${
                    isActive
                      ? `${c.bg} ${c.text} ${c.border}`
                      : 'border-[var(--border-default)] text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]'
                  }`}
                >
                  <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${c.dot}`} />
                  {KIND_LABEL[k]} · {kindCounts[k]}
                </button>
              )
            })}
          </div>

          {/* Bulk action bar */}
          {selectedIds.size > 0 && (
            <div className="flex items-center justify-between px-3 py-1.5 rounded-lg bg-[var(--accent)]/[0.06] border border-[var(--accent)]/20">
              <span className="text-[11px] font-medium text-[var(--accent)]">{selectedIds.size} selected</span>
              <div className="flex items-center gap-2">
                <button onClick={() => setSelectedIds(new Set())}
                  className="text-[10px] text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]">
                  Clear
                </button>
                <button
                  onClick={handleBulkDelete}
                  disabled={bulkDeleting}
                  className="flex items-center gap-1 text-[10px] font-semibold text-red-600 hover:text-red-700 px-2 py-1 rounded hover:bg-red-50 disabled:opacity-50 transition-colors"
                >
                  <Trash2 size={9} />
                  {bulkDeleting ? 'Deleting…' : `Delete ${selectedIds.size}`}
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── No filter match ── */}
      {facts.length > 0 && filtered.length === 0 && (
        <div className="flex flex-col items-center gap-1.5 py-10 text-center">
          <p className="text-xs text-[var(--text-secondary)]">No facts match your filter</p>
          <button onClick={() => { setSearch(''); setActiveKind('all') }}
            className="text-[11px] text-[var(--accent)] hover:underline">
            Clear filters
          </button>
        </div>
      )}

      {/* ── Brain facts grouped by kind ── */}
      {byKind.length > 0 && (
        <div className="space-y-8">
          {byKind.map(({ kind, facts: kfacts }) => {
            const colors = KIND_COLOR[kind]
            return (
              <div key={kind} className="space-y-3">
                <div className="flex items-center gap-3">
                  <div className={`w-2 h-2 rounded-full flex-shrink-0 ${colors.dot}`} />
                  <div className="flex-1">
                    <span className="text-xs font-semibold text-[var(--text-primary)]">{KIND_LABEL[kind]}</span>
                    <span className="ml-2 text-xs text-[var(--text-tertiary)]">{kfacts.length}</span>
                    <p className="text-[10px] text-[var(--text-tertiary)] mt-0.5">{KIND_DESC[kind]}</p>
                  </div>
                </div>
                <div className="space-y-2 pl-5">
                  {kfacts.map(f => (
                    <BrainFactCard
                      key={f.id}
                      fact={f}
                      allSourceFacts={sourceFacts}
                      appId={appId}
                      selected={selectedIds.has(f.id)}
                      onToggleSelect={toggleSelect}
                      onUpdate={updated => setFacts(prev => prev.map(p => p.id === updated.id ? updated : p))}
                      onDelete={id => setFacts(prev => prev.filter(p => p.id !== id))}
                    />
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
