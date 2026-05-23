'use client'
import { useState, useMemo, useRef, useEffect } from 'react'
import { Pencil, Plus, Trash2, X, Check, RefreshCw, Search, Sparkles, Zap, FileText } from 'lucide-react'
import { toast } from 'sonner'
import type { AppFact, AppCorpusDoc, FactKind } from '@/lib/types'
import { Badge } from '@/app/components/ui/badge'
import { api } from '@/lib/api'

const KIND_ORDER: FactKind[] = ['capability', 'constraint', 'limitation', 'integration', 'gotcha']

const KIND_META: Record<FactKind, {
  label: string; short: string; prefix: string
  dot: string; ring: string; heading: string; pill: string; pillActive: string
}> = {
  capability:  { label: 'Capabilities',   short: 'Cap',   prefix: 'C', dot: 'bg-emerald-500', ring: 'border-emerald-200', heading: 'text-emerald-700', pill: 'border-emerald-200 text-emerald-700 hover:bg-emerald-50',  pillActive: 'bg-emerald-500 text-white border-emerald-500' },
  constraint:  { label: 'Constraints',    short: 'Con',   prefix: 'K', dot: 'bg-red-500',     ring: 'border-red-200',     heading: 'text-red-700',     pill: 'border-red-200 text-red-700 hover:bg-red-50',             pillActive: 'bg-red-500 text-white border-red-500'         },
  limitation:  { label: 'Limitations',    short: 'Lim',   prefix: 'L', dot: 'bg-orange-500',  ring: 'border-orange-200',  heading: 'text-orange-700',  pill: 'border-orange-200 text-orange-700 hover:bg-orange-50',    pillActive: 'bg-orange-500 text-white border-orange-500'   },
  integration: { label: 'Integrations',   short: 'Int',   prefix: 'I', dot: 'bg-blue-500',    ring: 'border-blue-200',    heading: 'text-blue-700',    pill: 'border-blue-200 text-blue-700 hover:bg-blue-50',          pillActive: 'bg-blue-500 text-white border-blue-500'       },
  gotcha:      { label: 'Gotchas',        short: 'Gotcha',prefix: 'G', dot: 'bg-violet-500',  ring: 'border-violet-200',  heading: 'text-violet-700',  pill: 'border-violet-200 text-violet-700 hover:bg-violet-50',    pillActive: 'bg-violet-500 text-white border-violet-500'   },
}

const CONF: Record<string, { bar: string; w: string; label: string; tip: string }> = {
  high:   { bar: 'bg-emerald-500', w: 'w-10', label: 'high', tip: 'High confidence — explicitly stated in the source' },
  medium: { bar: 'bg-amber-400',   w: 'w-6',  label: 'med',  tip: 'Medium confidence — clearly implied by the source' },
  low:    { bar: 'bg-red-400',     w: 'w-3',  label: 'low',  tip: 'Low confidence — inferred from context'           },
}

interface EditState {
  factId: string | null
  kind: FactKind
  text: string
  confidence: string
  source_ref: string
}

interface Props {
  facts: AppFact[]
  appId: string
  canWrite: boolean
  onRefresh: () => void
  corpusDocs?: AppCorpusDoc[]
}

export function FactList({ facts, appId, canWrite, onRefresh, corpusDocs = [] }: Props) {
  const [search, setSearch] = useState('')
  const [kindFilter, setKindFilter] = useState<FactKind | 'all'>('all')
  const [editState, setEditState] = useState<EditState | null>(null)
  const [saving, setSaving] = useState(false)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [extracting, setExtracting] = useState(false)
  const [extractionPending, setExtractionPending] = useState(false)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [bulkDeleting, setBulkDeleting] = useState(false)
  const searchRef = useRef<HTMLInputElement>(null)
  const pendingTimers = useRef<ReturnType<typeof setTimeout>[]>([])

  useEffect(() => () => pendingTimers.current.forEach(clearTimeout), [])

  const visible = useMemo(() => facts.filter(f => f.status !== 'dismissed'), [facts])

  const afterSearch = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return visible
    return visible.filter(f =>
      f.text.toLowerCase().includes(q) ||
      (f.source_ref?.toLowerCase().includes(q))
    )
  }, [visible, search])

  const displayed = useMemo(() =>
    kindFilter === 'all' ? afterSearch : afterSearch.filter(f => f.kind === kindFilter),
    [afterSearch, kindFilter]
  )

  const kindCounts = useMemo(() =>
    KIND_ORDER.reduce((acc, k) => ({ ...acc, [k]: afterSearch.filter(f => f.kind === k).length }), {} as Record<FactKind, number>),
    [afterSearch]
  )

  const isGrouped = kindFilter === 'all'
  const groupedKinds = KIND_ORDER.filter(k => displayed.some(f => f.kind === k))
  const isEmpty = displayed.length === 0 && !editState
  const selectionMode = selectedIds.size > 0
  const allDisplayedSelected = displayed.length > 0 && displayed.every(f => selectedIds.has(f.id))

  function toggleSelect(id: string) {
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }
  function selectAll() { setSelectedIds(new Set(displayed.map(f => f.id))) }
  function clearSelection() { setSelectedIds(new Set()) }

  async function deleteSelected() {
    const ids = Array.from(selectedIds)
    setBulkDeleting(true)
    try {
      const results = await Promise.allSettled(ids.map(id => api.apps.deleteFact(appId, id)))
      const failed = results.filter(r => r.status === 'rejected').length
      const succeeded = ids.length - failed
      if (failed === 0) {
        toast.success(`${succeeded} fact${succeeded !== 1 ? 's' : ''} removed`)
      } else if (succeeded === 0) {
        toast.error('All deletions failed — please try again')
      } else {
        toast.warning(`${succeeded} removed, ${failed} failed`)
      }
      setSelectedIds(new Set())
      onRefresh()
    } finally {
      setBulkDeleting(false)
    }
  }

  // ── Extraction ──────────────────────────────────────────────────────────────
  async function handleExtract() {
    setExtracting(true)
    setExtractionPending(true)
    try {
      await api.apps.extractFacts(appId)
      toast.success('Extraction queued — ~20 s')
      for (const delay of [15_000, 25_000, 40_000, 65_000]) {
        const t = setTimeout(() => {
          onRefresh()
          if (delay >= 40_000) setExtractionPending(false)
        }, delay)
        pendingTimers.current.push(t)
      }
    } catch {
      toast.error('Failed to queue extraction')
      setExtractionPending(false)
    } finally {
      setExtracting(false)
    }
  }

  // ── CRUD ────────────────────────────────────────────────────────────────────
  function startAdd() {
    setEditState({ factId: null, kind: kindFilter === 'all' ? 'capability' : kindFilter, text: '', confidence: 'high', source_ref: '' })
  }

  function startEdit(fact: AppFact) {
    setEditState({ factId: fact.id, kind: fact.kind as FactKind, text: fact.text, confidence: fact.confidence, source_ref: fact.source_ref ?? '' })
  }

  async function saveEdit() {
    if (!editState?.text.trim()) return
    setSaving(true)
    try {
      const body = { kind: editState.kind, text: editState.text.trim(), confidence: editState.confidence, source_ref: editState.source_ref.trim() || null }
      if (editState.factId === null) {
        await api.apps.createFact(appId, body)
        toast.success('Fact added')
      } else {
        await api.apps.updateFact(appId, editState.factId, body)
        toast.success('Fact updated')
      }
      setEditState(null)
      onRefresh()
    } catch {
      toast.error('Failed to save')
    } finally {
      setSaving(false)
    }
  }

  async function deleteFact(id: string) {
    setDeletingId(id)
    try {
      await api.apps.deleteFact(appId, id)
      toast.success('Fact removed')
      onRefresh()
    } catch {
      toast.error('Failed to remove')
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <div className="flex flex-col gap-0">

      {/* ── Sticky control strip ──────────────────────────────────────────── */}
      <div className="sticky top-0 z-20 bg-[var(--bg-base)] pt-0 pb-3 space-y-2.5">

        {/* Row 1 — search + actions */}
        <div className="flex items-center gap-2">
          <div className="relative flex-1">
            <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)] pointer-events-none" />
            <input
              ref={searchRef}
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search facts…"
              className="w-full pl-7 pr-3 py-1.5 text-[12px] rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:border-[var(--accent)] transition-colors"
            />
            {search && (
              <button onClick={() => setSearch('')} className="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)] hover:text-[var(--text-primary)]">
                <X size={11} />
              </button>
            )}
          </div>

          {canWrite && (
            <button
              onClick={startAdd}
              className="flex items-center gap-1.5 rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] px-2.5 py-1.5 text-[11px] font-medium text-[var(--text-secondary)] hover:bg-[var(--accent)] hover:text-white hover:border-[var(--accent)] transition-all"
            >
              <Plus size={11} /> Add
            </button>
          )}

          {canWrite && (
            <button
              onClick={handleExtract}
              disabled={extracting}
              title="Re-run AI fact extraction on corpus"
              className="flex items-center gap-1.5 rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] px-2.5 py-1.5 text-[11px] text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] disabled:opacity-50 transition-colors"
            >
              <Zap size={11} className={extracting ? 'animate-pulse text-amber-500' : ''} />
              {extracting ? 'Queuing…' : 'Re-extract'}
            </button>
          )}
        </div>

        {/* Row 2 — kind filter pills */}
        <div className="flex items-center gap-1.5 flex-wrap">
          <button
            onClick={() => setKindFilter('all')}
            className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[10px] font-semibold transition-colors ${
              kindFilter === 'all'
                ? 'bg-[var(--text-primary)] text-[var(--bg-base)] border-[var(--text-primary)]'
                : 'border-[var(--border-default)] text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]'
            }`}
          >
            All
            <span className={`tabular-nums ${kindFilter === 'all' ? 'opacity-70' : 'text-[var(--text-tertiary)]'}`}>
              {afterSearch.length}
            </span>
          </button>

          {KIND_ORDER.filter(k => kindCounts[k] > 0).map(k => {
            const m = KIND_META[k]
            const active = kindFilter === k
            return (
              <button
                key={k}
                onClick={() => setKindFilter(active ? 'all' : k)}
                className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[10px] font-semibold transition-colors ${
                  active ? m.pillActive : m.pill
                }`}
              >
                <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${active ? 'bg-white' : m.dot}`} />
                {m.label}
                <span className={`tabular-nums ${active ? 'opacity-80' : ''}`}>{kindCounts[k]}</span>
              </button>
            )
          })}

          <button
            onClick={() => { onRefresh() }}
            title="Refresh"
            className="ml-auto p-1 rounded text-[var(--text-tertiary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-elevated)] transition-colors"
          >
            <RefreshCw size={11} />
          </button>
        </div>

        {/* Row 3 — bulk selection bar */}
        {selectionMode && (
          <div className="flex items-center gap-2 rounded-lg border border-[var(--accent)]/25 bg-[var(--accent)]/[0.06] px-3 py-2">
            <div className="flex items-center gap-1.5">
              <div className="w-3.5 h-3.5 rounded border-2 border-[var(--accent)] bg-[var(--accent)] flex items-center justify-center flex-shrink-0">
                <Check size={8} className="text-white" strokeWidth={3} />
              </div>
              <span className="text-[11px] font-semibold text-[var(--accent)]">
                {selectedIds.size} selected
              </span>
            </div>
            <span className="text-[var(--border-default)]">·</span>
            <button
              onClick={allDisplayedSelected ? clearSelection : selectAll}
              className="text-[11px] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
            >
              {allDisplayedSelected ? 'Deselect all' : `Select all ${displayed.length}`}
            </button>
            <button
              onClick={clearSelection}
              className="text-[11px] text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] transition-colors"
            >
              Clear
            </button>
            <div className="flex-1" />
            <button
              onClick={deleteSelected}
              disabled={bulkDeleting}
              className="flex items-center gap-1.5 text-[11px] font-semibold text-red-600 hover:text-red-700 disabled:opacity-50 transition-colors"
            >
              <Trash2 size={11} />
              {bulkDeleting ? 'Deleting…' : `Delete ${selectedIds.size}`}
            </button>
          </div>
        )}

        {/* Row 4 — extraction in-progress banner */}
        {extractionPending && (
          <div className="flex items-center gap-2.5 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2">
            <span className="relative flex h-2 w-2 shrink-0">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-amber-500" />
            </span>
            <p className="text-[11px] text-amber-800 flex-1">
              Extraction in progress — new facts will appear automatically
            </p>
            <button
              onClick={() => { onRefresh(); setExtractionPending(false) }}
              className="text-[10px] font-medium text-amber-700 hover:underline shrink-0"
            >
              Refresh now
            </button>
            <button onClick={() => setExtractionPending(false)} className="text-amber-500 hover:text-amber-700">
              <X size={10} />
            </button>
          </div>
        )}

        {/* Row 5 — new fact inline form */}
        {editState?.factId === null && (
          <FactForm
            editState={editState}
            setEditState={setEditState}
            onSave={saveEdit}
            onCancel={() => setEditState(null)}
            saving={saving}
            variant="new"
            corpusDocs={corpusDocs}
          />
        )}
      </div>

      {/* ── Empty state ───────────────────────────────────────────────────── */}
      {isEmpty && (
        <div className="flex flex-col items-center justify-center py-14 text-center">
          <div className="w-10 h-10 rounded-full bg-[var(--bg-elevated)] flex items-center justify-center mb-3">
            {search ? <Search size={16} className="text-[var(--text-tertiary)]" /> : <span className="text-[var(--text-tertiary)] text-lg">∅</span>}
          </div>
          <p className="text-xs font-medium text-[var(--text-secondary)]">
            {search ? `No facts matching "${search}"` : 'No facts extracted yet'}
          </p>
          <p className="text-[10px] text-[var(--text-tertiary)] mt-0.5">
            {search ? 'Try a different search term' : 'Index corpus documents or add facts manually.'}
          </p>
        </div>
      )}

      {/* ── Fact groups ───────────────────────────────────────────────────── */}
      <div className="space-y-6 mt-1">
        {isGrouped
          ? groupedKinds.map(kind => (
              <KindSection
                key={kind}
                kind={kind}
                facts={displayed.filter(f => f.kind === kind)}
                editState={editState}
                setEditState={setEditState}
                onSave={saveEdit}
                onCancel={() => setEditState(null)}
                saving={saving}
                deletingId={deletingId}
                onEdit={startEdit}
                onDelete={deleteFact}
                canWrite={canWrite}
                showSearch={!!search}
                corpusDocs={corpusDocs}
                selectedIds={selectedIds}
                onToggleSelect={toggleSelect}
                selectionMode={selectionMode}
              />
            ))
          : (
            <FlatSection
              facts={displayed}
              editState={editState}
              setEditState={setEditState}
              onSave={saveEdit}
              onCancel={() => setEditState(null)}
              saving={saving}
              deletingId={deletingId}
              onEdit={startEdit}
              onDelete={deleteFact}
              canWrite={canWrite}
              showSearch={!!search}
              corpusDocs={corpusDocs}
              selectedIds={selectedIds}
              onToggleSelect={toggleSelect}
              selectionMode={selectionMode}
            />
          )
        }
      </div>
    </div>
  )
}

// ── Kind section (grouped mode) ──────────────────────────────────────────────

function KindSection({ kind, facts, editState, setEditState, onSave, onCancel, saving, deletingId, onEdit, onDelete, canWrite, showSearch, corpusDocs, selectedIds, onToggleSelect, selectionMode }: {
  kind: FactKind; facts: AppFact[]
  editState: EditState | null; setEditState: (s: EditState) => void
  onSave: () => void; onCancel: () => void; saving: boolean
  deletingId: string | null
  onEdit: (f: AppFact) => void; onDelete: (id: string) => void
  canWrite: boolean; showSearch: boolean; corpusDocs: AppCorpusDoc[]
  selectedIds: Set<string>; onToggleSelect: (id: string) => void; selectionMode: boolean
}) {
  const meta = KIND_META[kind]
  return (
    <section>
      <div className="flex items-center gap-2 mb-2">
        <span className={`inline-block w-2 h-2 rounded-full ${meta.dot} shrink-0`} />
        <span className={`text-[10px] font-bold uppercase tracking-[0.1em] ${meta.heading}`}>{meta.label}</span>
        <span className="text-[10px] text-[var(--text-tertiary)] tabular-nums">{facts.length}</span>
      </div>
      <div className={`rounded-xl border overflow-hidden ${meta.ring}`}>
        {facts.map((fact, idx) => {
          const code = `${meta.prefix}${idx + 1}`
          if (editState?.factId === fact.id) {
            return (
              <div key={fact.id} className={`px-4 py-3 bg-[var(--bg-elevated)] ${idx > 0 ? 'border-t border-[var(--border-subtle)]' : ''}`}>
                <FactForm editState={editState} setEditState={setEditState} onSave={onSave} onCancel={onCancel} saving={saving} variant="edit" corpusDocs={corpusDocs} />
              </div>
            )
          }
          return (
            <FactRow key={fact.id} fact={fact} code={code} meta={meta} bordered={idx > 0}
              deletingId={deletingId} onEdit={onEdit} onDelete={onDelete} canWrite={canWrite} showKindBadge={showSearch}
              isSelected={selectedIds.has(fact.id)} onToggleSelect={onToggleSelect} selectionMode={selectionMode} />
          )
        })}
      </div>
    </section>
  )
}

// ── Flat section (kind-filtered or search mode) ──────────────────────────────

function FlatSection({ facts, editState, setEditState, onSave, onCancel, saving, deletingId, onEdit, onDelete, canWrite, showSearch, corpusDocs, selectedIds, onToggleSelect, selectionMode }: {
  facts: AppFact[]
  editState: EditState | null; setEditState: (s: EditState) => void
  onSave: () => void; onCancel: () => void; saving: boolean
  deletingId: string | null
  onEdit: (f: AppFact) => void; onDelete: (id: string) => void
  canWrite: boolean; showSearch: boolean; corpusDocs: AppCorpusDoc[]
  selectedIds: Set<string>; onToggleSelect: (id: string) => void; selectionMode: boolean
}) {
  const grouped = KIND_ORDER.reduce((acc, k) => {
    const kf = facts.filter(f => f.kind === k)
    kf.forEach((f, i) => acc.push({ fact: f, code: `${KIND_META[k].prefix}${i + 1}` }))
    return acc
  }, [] as { fact: AppFact; code: string }[])

  if (grouped.length === 0) return null
  const meta = KIND_META[grouped[0].fact.kind as FactKind]

  return (
    <div className={`rounded-xl border overflow-hidden ${meta.ring}`}>
      {grouped.map(({ fact, code }, idx) => {
        const m = KIND_META[fact.kind as FactKind]
        if (editState?.factId === fact.id) {
          return (
            <div key={fact.id} className={`px-4 py-3 bg-[var(--bg-elevated)] ${idx > 0 ? 'border-t border-[var(--border-subtle)]' : ''}`}>
              <FactForm editState={editState} setEditState={setEditState} onSave={onSave} onCancel={onCancel} saving={saving} variant="edit" corpusDocs={corpusDocs} />
            </div>
          )
        }
        return (
          <FactRow key={fact.id} fact={fact} code={code} meta={m} bordered={idx > 0}
            deletingId={deletingId} onEdit={onEdit} onDelete={onDelete} canWrite={canWrite} showKindBadge
            isSelected={selectedIds.has(fact.id)} onToggleSelect={onToggleSelect} selectionMode={selectionMode} />
        )
      })}
    </div>
  )
}

// ── Single fact row ──────────────────────────────────────────────────────────

function FactRow({ fact, code, meta, bordered, deletingId, onEdit, onDelete, canWrite, showKindBadge, isSelected, onToggleSelect, selectionMode }: {
  fact: AppFact; code: string
  meta: typeof KIND_META[FactKind]; bordered: boolean
  deletingId: string | null
  onEdit: (f: AppFact) => void; onDelete: (id: string) => void
  canWrite: boolean; showKindBadge: boolean
  isSelected: boolean; onToggleSelect: (id: string) => void; selectionMode: boolean
}) {
  const conf = CONF[fact.confidence] ?? CONF.medium
  const isProposed = fact.status === 'proposed'

  return (
    <div
      onClick={() => selectionMode && onToggleSelect(fact.id)}
      className={`
        relative flex items-center gap-3 px-4 py-3 group transition-colors
        ${bordered ? 'border-t border-[var(--border-subtle)]' : ''}
        ${isSelected ? 'bg-[var(--accent)]/[0.06]' : isProposed ? 'bg-violet-50 border-l-[3px] border-l-violet-400 pl-[13px]' : 'bg-[var(--bg-surface)] hover:bg-[var(--bg-elevated)]'}
        ${selectionMode ? 'cursor-pointer' : ''}
      `}
    >
      {/* Checkbox (always in DOM; visible on hover or when selection is active) */}
      {canWrite && (
        <div
          onClick={e => { e.stopPropagation(); onToggleSelect(fact.id) }}
          className={`shrink-0 flex items-center justify-center transition-opacity ${selectionMode ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`}
        >
          <div className={`w-3.5 h-3.5 rounded border-2 flex items-center justify-center transition-all ${
            isSelected
              ? 'bg-[var(--accent)] border-[var(--accent)]'
              : 'border-[var(--border-default)] bg-[var(--bg-surface)] hover:border-[var(--accent)]'
          }`}>
            {isSelected && <Check size={8} className="text-white" strokeWidth={3} />}
          </div>
        </div>
      )}

      {/* Code (hidden when checkbox is shown) */}
      <div className={`flex items-center gap-1.5 shrink-0 transition-opacity ${selectionMode ? 'opacity-0 w-0 overflow-hidden' : 'opacity-100'}`}>
        <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${meta.dot}`} />
        <span className="font-mono text-[9px] font-bold text-[var(--text-tertiary)] w-5 leading-none">{code}</span>
      </div>

      {/* Text */}
      <p className="flex-1 text-[13px] text-[var(--text-primary)] leading-snug min-w-0">{fact.text}</p>

      {/* Right metadata */}
      <div className="flex items-center gap-2 shrink-0 ml-1">
        {fact.source_ref && (
          <span
            title={fact.source_ref}
            className="hidden sm:inline-flex items-center gap-1 rounded border border-[var(--border-default)] bg-[var(--bg-base)] px-1.5 py-px text-[9px] text-[var(--text-tertiary)] max-w-[120px] cursor-default"
          >
            <FileText size={9} className="shrink-0" />
            <span className="truncate">{fact.source_ref.replace(/\.[^.]+$/, '')}</span>
          </span>
        )}

        {showKindBadge && (
          <span className={`text-[9px] font-bold uppercase tracking-wide ${meta.heading}`}>{meta.label}</span>
        )}

        {isProposed && <Badge variant="ai" className="text-[9px] shrink-0">Proposed</Badge>}

        {fact.source === 'human'
          ? <Badge variant="success" className="text-[9px] shrink-0">Human</Badge>
          : <span className="text-[9px] font-medium text-[var(--text-tertiary)] flex items-center gap-0.5"><Sparkles size={8} />AI</span>
        }

        <div className="flex items-center gap-1.5 cursor-help" title={conf.tip}>
          <div className={`h-[3px] rounded-full ${conf.bar} ${conf.w}`} />
          <span className="text-[9px] font-medium text-[var(--text-tertiary)] w-5 leading-none">{conf.label}</span>
        </div>

        {/* Row actions — hidden in selection mode */}
        {canWrite && !selectionMode && (
          <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
            <button onClick={e => { e.stopPropagation(); onEdit(fact) }} className="p-1 rounded text-[var(--text-tertiary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-elevated)]" title="Edit">
              <Pencil size={11} />
            </button>
            <button onClick={e => { e.stopPropagation(); onDelete(fact.id) }} disabled={deletingId === fact.id} className="p-1 rounded text-[var(--text-tertiary)] hover:text-red-500 hover:bg-[var(--bg-elevated)] disabled:opacity-40" title="Remove">
              <Trash2 size={11} />
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Fact form (add / edit) ───────────────────────────────────────────────────

function FactForm({ editState, setEditState, onSave, onCancel, saving, variant, corpusDocs }: {
  editState: EditState; setEditState: (s: EditState) => void
  onSave: () => void; onCancel: () => void; saving: boolean
  variant: 'new' | 'edit'; corpusDocs: AppCorpusDoc[]
}) {
  return (
    <div className={`flex items-start gap-3 ${variant === 'new' ? 'rounded-xl border border-dashed border-[var(--accent)] bg-[var(--bg-elevated)] p-3' : ''}`}>
      <div className="flex-1 flex flex-col gap-2 min-w-0">
        <div className="flex gap-2">
          <select
            value={editState.kind}
            onChange={e => setEditState({ ...editState, kind: e.target.value as FactKind })}
            className="text-[11px] rounded-md border border-[var(--border-default)] bg-[var(--bg-surface)] px-2 py-1 text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent)]"
          >
            {(Object.entries(KIND_META) as [FactKind, typeof KIND_META[FactKind]][]).map(([k, m]) => (
              <option key={k} value={k}>{m.label}</option>
            ))}
          </select>
          <select
            value={editState.confidence}
            onChange={e => setEditState({ ...editState, confidence: e.target.value })}
            className="text-[11px] rounded-md border border-[var(--border-default)] bg-[var(--bg-surface)] px-2 py-1 text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent)]"
          >
            {['high', 'medium', 'low'].map(c => <option key={c} value={c}>{c} confidence</option>)}
          </select>
        </div>
        <textarea
          autoFocus
          value={editState.text}
          onChange={e => setEditState({ ...editState, text: e.target.value })}
          placeholder="Fact statement…"
          rows={2}
          className="w-full text-[12px] rounded-md border border-[var(--border-default)] bg-[var(--bg-surface)] px-2.5 py-1.5 text-[var(--text-primary)] resize-none focus:outline-none focus:border-[var(--accent)]"
        />
        {corpusDocs.length > 0 ? (
          <select
            value={editState.source_ref}
            onChange={e => setEditState({ ...editState, source_ref: e.target.value })}
            className="text-[11px] rounded-md border border-[var(--border-default)] bg-[var(--bg-surface)] px-2.5 py-1 text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent)]"
          >
            <option value="">No source document</option>
            {corpusDocs.map(d => (
              <option key={d.id} value={d.name}>{d.name}</option>
            ))}
          </select>
        ) : (
          <input
            value={editState.source_ref}
            onChange={e => setEditState({ ...editState, source_ref: e.target.value })}
            placeholder="Source reference (optional)"
            className="text-[11px] rounded-md border border-[var(--border-default)] bg-[var(--bg-surface)] px-2.5 py-1 text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent)]"
          />
        )}
      </div>
      <div className="flex flex-col gap-1.5 shrink-0 pt-0.5">
        <button
          onClick={onSave}
          disabled={saving || !editState.text.trim()}
          className="flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-[11px] font-semibold bg-[var(--accent)] text-white hover:opacity-90 disabled:opacity-40 transition-opacity"
        >
          <Check size={11} /> Save
        </button>
        <button
          onClick={onCancel}
          className="flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-[11px] text-[var(--text-secondary)] hover:bg-[var(--bg-surface)] transition-colors"
        >
          <X size={11} /> Cancel
        </button>
      </div>
    </div>
  )
}
