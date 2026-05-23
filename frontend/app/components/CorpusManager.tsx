'use client'
import { useRef, useState, useEffect, useCallback } from 'react'
import {
  Upload, RefreshCw, Trash2, FileText, FileX, AlertTriangle,
  RotateCcw, Plus, Pencil, X, Search,
} from 'lucide-react'
import { toast } from 'sonner'
import { IndexStatusBadge } from './IndexStatusBadge'
import { api } from '@/lib/api'
import type { AppCorpusDoc, AppFact, FactKind, FactConfidence } from '@/lib/types'

// ── Types ─────────────────────────────────────────────────────────────────────

interface MarkdownData {
  markdown_text: string
  provider: string
  filename: string
  created_at: string
}

interface Props {
  appId: string
  docs: AppCorpusDoc[]
  canWrite: boolean
  rebuildStatus: string | null
  onRefresh: () => void
}

// ── Markdown renderer ────────────────────────────────────────────────────────

function MarkdownLine({ line }: { line: string }) {
  const inlineBold = (text: string) => {
    const parts = text.split(/(\*\*[^*]+\*\*)/)
    return parts.map((p, i) =>
      p.startsWith('**') && p.endsWith('**')
        ? <strong key={i} className="font-semibold text-[var(--text-primary)]">{p.slice(2, -2)}</strong>
        : <span key={i}>{p}</span>
    )
  }
  if (line.startsWith('# '))
    return <h1 className="text-base font-bold text-[var(--text-primary)] mt-5 mb-1.5 leading-tight">{line.slice(2)}</h1>
  if (line.startsWith('## '))
    return <h2 className="text-sm font-semibold text-[var(--text-primary)] mt-4 mb-1 leading-tight">{line.slice(3)}</h2>
  if (line.startsWith('### '))
    return <h3 className="text-xs font-semibold text-[var(--text-secondary)] mt-3 mb-0.5 uppercase tracking-wide">{line.slice(4)}</h3>
  if (/^---+$/.test(line.trim()))
    return <hr className="my-4 border-[var(--border-subtle)]" />
  if (line.startsWith('<!-- '))
    return (
      <div className="text-[11px] text-[var(--text-tertiary)] font-mono bg-[var(--bg-elevated)] px-2.5 py-1 rounded border border-[var(--border-subtle)] my-1">
        {line}
      </div>
    )
  if (line.startsWith('|'))
    return <div className="font-mono text-[11px] text-[var(--text-secondary)] leading-relaxed">{line}</div>
  if (line.trim() === '')
    return <div className="h-2" />
  if (line.startsWith('- ') || line.startsWith('* '))
    return (
      <div className="flex gap-2 leading-relaxed">
        <span className="text-[var(--text-tertiary)] mt-0.5 flex-shrink-0">·</span>
        <span className="text-[var(--text-secondary)]">{inlineBold(line.slice(2))}</span>
      </div>
    )
  return <p className="leading-relaxed text-[var(--text-secondary)]">{inlineBold(line)}</p>
}

// ── Kind colors ───────────────────────────────────────────────────────────────

const KIND_COLOR: Record<FactKind, string> = {
  capability:  'bg-emerald-500',
  constraint:  'bg-orange-500',
  limitation:  'bg-red-500',
  integration: 'bg-blue-500',
  gotcha:      'bg-violet-500',
}
const KIND_LABEL: Record<FactKind, string> = {
  capability: 'Capability', constraint: 'Constraint',
  limitation: 'Limitation', integration: 'Integration', gotcha: 'Gotcha',
}
const FACT_KINDS: FactKind[] = ['capability', 'constraint', 'limitation', 'integration', 'gotcha']
const CONFIDENCES: FactConfidence[] = ['high', 'medium', 'low']

// ── Inline fact edit form ────────────────────────────────────────────────────

interface FactFormData { kind: FactKind; text: string; confidence: FactConfidence }

function FactForm({
  initial, onSave, onCancel, saving,
}: {
  initial?: Partial<FactFormData>
  onSave: (d: FactFormData) => void
  onCancel: () => void
  saving: boolean
}) {
  const [kind, setKind] = useState<FactKind>(initial?.kind ?? 'capability')
  const [text, setText] = useState(initial?.text ?? '')
  const [confidence, setConfidence] = useState<FactConfidence>(initial?.confidence ?? 'high')

  return (
    <div className="rounded-lg border border-[var(--accent)]/30 bg-[var(--accent)]/[0.03] p-3 space-y-2">
      <div className="flex gap-2">
        <select value={kind} onChange={e => setKind(e.target.value as FactKind)}
          className="text-[11px] rounded border border-[var(--border-default)] bg-[var(--bg-surface)] text-[var(--text-secondary)] px-1.5 py-1 flex-shrink-0">
          {FACT_KINDS.map(k => <option key={k} value={k}>{KIND_LABEL[k]}</option>)}
        </select>
        <select value={confidence} onChange={e => setConfidence(e.target.value as FactConfidence)}
          className="text-[11px] rounded border border-[var(--border-default)] bg-[var(--bg-surface)] text-[var(--text-secondary)] px-1.5 py-1 flex-shrink-0">
          {CONFIDENCES.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>
      <textarea
        value={text} onChange={e => setText(e.target.value)} rows={2}
        placeholder="Describe the fact in one clear sentence…"
        className="w-full text-xs rounded border border-[var(--border-default)] bg-[var(--bg-surface)] text-[var(--text-primary)] px-2.5 py-2 resize-none focus:outline-none focus:ring-1 focus:ring-[var(--accent)]/40 placeholder:text-[var(--text-tertiary)]"
      />
      <div className="flex justify-end gap-2">
        <button onClick={onCancel} className="text-[11px] text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] px-2 py-1">Cancel</button>
        <button
          onClick={() => text.trim() && onSave({ kind, text: text.trim(), confidence })}
          disabled={!text.trim() || saving}
          className="text-[11px] font-semibold text-white bg-[var(--accent)] px-3 py-1 rounded disabled:opacity-50 hover:opacity-90 transition-opacity"
        >
          {saving ? 'Saving…' : 'Save'}
        </button>
      </div>
    </div>
  )
}

// ── Doc-level fact row ────────────────────────────────────────────────────────

function DocFactRow({
  fact, canWrite, appId, selected, onToggleSelect, onUpdate, onDelete,
}: {
  fact: AppFact
  canWrite: boolean
  appId: string
  selected: boolean
  onToggleSelect: (id: string) => void
  onUpdate: (f: AppFact) => void
  onDelete: (id: string) => void
}) {
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)

  async function handleSave(d: FactFormData) {
    setSaving(true)
    try {
      const updated = await api.apps.updateFact(appId, fact.id, d)
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
      <div className="px-3 py-2">
        <FactForm initial={{ kind: fact.kind as FactKind, text: fact.text, confidence: fact.confidence as FactConfidence }}
          onSave={handleSave} onCancel={() => setEditing(false)} saving={saving} />
      </div>
    )
  }

  return (
    <div className={`group flex items-start gap-2.5 px-3 py-2.5 rounded-lg transition-colors ${selected ? 'bg-[var(--accent)]/[0.05]' : 'hover:bg-[var(--bg-elevated)]'}`}>
      {canWrite && (
        <input
          type="checkbox"
          checked={selected}
          onChange={() => onToggleSelect(fact.id)}
          className="mt-1.5 flex-shrink-0 accent-[var(--accent)] cursor-pointer"
        />
      )}
      <div className={`mt-1.5 w-1.5 h-1.5 rounded-full flex-shrink-0 ${KIND_COLOR[fact.kind as FactKind]}`} />
      <div className="flex-1 min-w-0">
        <p className="text-xs text-[var(--text-primary)] leading-relaxed">{fact.text}</p>
        <div className="flex items-center gap-2 mt-1">
          <span className="text-[10px] font-medium text-[var(--text-tertiary)] capitalize">{fact.kind}</span>
          <span className="text-[10px] text-[var(--text-tertiary)]">·</span>
          <span className="text-[10px] text-[var(--text-tertiary)]">{fact.confidence}</span>
          <span className="text-[10px] px-1.5 py-0.5 rounded-full border border-[var(--border-subtle)] text-[var(--text-tertiary)]">
            {fact.source}
          </span>
        </div>
      </div>
      {canWrite && (
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0">
          {confirmDelete ? (
            <>
              <button onClick={handleDelete} className="text-[10px] font-semibold text-red-600 hover:text-red-700 px-1.5 py-0.5 rounded">
                Confirm
              </button>
              <button onClick={() => setConfirmDelete(false)} className="text-[10px] text-[var(--text-tertiary)] px-1 py-0.5 rounded">
                <X size={10} />
              </button>
            </>
          ) : (
            <>
              <button onClick={() => setEditing(true)}
                className="p-1 rounded hover:bg-[var(--bg-base)] text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]">
                <Pencil size={10} />
              </button>
              <button onClick={() => setConfirmDelete(true)}
                className="p-1 rounded hover:bg-[var(--bg-base)] text-[var(--text-tertiary)] hover:text-red-500">
                <Trash2 size={10} />
              </button>
            </>
          )}
        </div>
      )}
    </div>
  )
}

// ── Doc Facts Panel ────────────────────────────────────────────────────────────

const KIND_CHIP_COLOR: Record<FactKind, { active: string; dot: string }> = {
  capability:  { active: 'bg-emerald-50 border-emerald-200 text-emerald-700', dot: 'bg-emerald-500' },
  constraint:  { active: 'bg-orange-50 border-orange-200 text-orange-700',   dot: 'bg-orange-500' },
  limitation:  { active: 'bg-red-50 border-red-200 text-red-700',            dot: 'bg-red-500' },
  integration: { active: 'bg-blue-50 border-blue-200 text-blue-700',         dot: 'bg-blue-500' },
  gotcha:      { active: 'bg-violet-50 border-violet-200 text-violet-700',   dot: 'bg-violet-500' },
}

function DocFactsPanel({ appId, docId, canWrite, docName }: {
  appId: string
  docId: string
  canWrite: boolean
  docName: string
}) {
  const [facts, setFacts] = useState<AppFact[]>([])
  const [loading, setLoading] = useState(true)
  const [adding, setAdding] = useState(false)
  const [saving, setSaving] = useState(false)
  const [reextracting, setReextracting] = useState(false)
  const [search, setSearch] = useState('')
  const [activeKind, setActiveKind] = useState<FactKind | 'all'>('all')
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [bulkDeleting, setBulkDeleting] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.apps.getDocFacts(appId, docId)
      setFacts(data)
    } catch {
      setFacts([])
    } finally {
      setLoading(false)
    }
  }, [appId, docId])

  useEffect(() => { load() }, [load])

  // Reset filters + selection when doc changes
  useEffect(() => { setSearch(''); setActiveKind('all'); setSelectedIds(new Set()) }, [docId])

  async function handleAdd(d: FactFormData) {
    setSaving(true)
    try {
      const fact = await api.apps.createDocFact(appId, docId, { ...d, source_ref: docName })
      setFacts(prev => [fact, ...prev])
      setAdding(false)
      toast.success('Fact added')
    } catch {
      toast.error('Failed to add fact')
    } finally {
      setSaving(false)
    }
  }

  async function handleReextract() {
    setReextracting(true)
    try {
      await api.apps.extractFacts(appId)
      toast.success('Fact re-extraction started', { description: 'Facts will update when the task completes.' })
      setTimeout(load, 3000)
    } catch {
      toast.error('Re-extraction failed')
    } finally {
      setTimeout(() => setReextracting(false), 2000)
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

  if (loading) {
    return (
      <div className="p-4 space-y-2 animate-pulse">
        {[0.9, 0.7, 0.85].map((w, i) => (
          <div key={i} className="h-8 rounded-lg bg-[var(--bg-elevated)]" style={{ width: `${w * 100}%` }} />
        ))}
      </div>
    )
  }

  const byKind = FACT_KINDS
    .map(k => ({ kind: k, facts: filtered.filter(f => f.kind === k) }))
    .filter(g => g.facts.length > 0)

  return (
    <div className="flex flex-col h-full">
      {/* ── Toolbar row: search + actions ── */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-[var(--border-subtle)] flex-shrink-0">
        {canWrite && (
          <input
            type="checkbox"
            title="Select all visible"
            checked={filtered.length > 0 && selectedIds.size === filtered.length}
            ref={el => { if (el) el.indeterminate = selectedIds.size > 0 && selectedIds.size < filtered.length }}
            onChange={toggleSelectAll}
            className="flex-shrink-0 accent-[var(--accent)] cursor-pointer"
          />
        )}
        <div className="relative flex-1">
          <Search size={11} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)] pointer-events-none" />
          <input
            type="text"
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search facts…"
            className="w-full pl-7 pr-7 py-1.5 text-[11px] rounded-md border border-[var(--border-default)] bg-[var(--bg-base)] text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]/40 focus:border-[var(--accent)]/60"
          />
          {search && (
            <button onClick={() => setSearch('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]">
              <X size={10} />
            </button>
          )}
        </div>
        {canWrite && (
          <div className="flex items-center gap-1 flex-shrink-0">
            <button
              onClick={handleReextract}
              disabled={reextracting}
              className="flex items-center gap-1 text-[10px] text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] px-2 py-1.5 rounded hover:bg-[var(--bg-elevated)] disabled:opacity-50 transition-colors"
            >
              <RefreshCw size={9} className={reextracting ? 'animate-spin' : ''} />
              Re-extract
            </button>
            <button
              onClick={() => { setAdding(true); setSearch(''); setActiveKind('all') }}
              className="flex items-center gap-1 text-[10px] font-medium text-white bg-[var(--accent)] px-2.5 py-1.5 rounded hover:opacity-90 transition-opacity"
            >
              <Plus size={10} />
              Add
            </button>
          </div>
        )}
      </div>

      {/* ── Bulk-action bar (shown when any selected) ── */}
      {selectedIds.size > 0 && (
        <div className="flex items-center justify-between px-3 py-1.5 bg-[var(--accent)]/[0.06] border-b border-[var(--accent)]/20 flex-shrink-0">
          <span className="text-[11px] font-medium text-[var(--accent)]">
            {selectedIds.size} selected
          </span>
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

      {/* ── Kind filter chips ── */}
      <div className="flex items-center gap-1.5 px-3 py-2 border-b border-[var(--border-subtle)] overflow-x-auto flex-shrink-0 scrollbar-none">
        <button
          onClick={() => setActiveKind('all')}
          className={`flex-shrink-0 text-[10px] font-medium px-2.5 py-1 rounded-full border transition-colors ${
            activeKind === 'all'
              ? 'bg-[var(--accent)] border-[var(--accent)] text-white'
              : 'border-[var(--border-default)] text-[var(--text-tertiary)] hover:border-[var(--border-default)] hover:text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]'
          }`}
        >
          All · {facts.length}
        </button>
        {FACT_KINDS.filter(k => kindCounts[k] > 0).map(k => {
          const chips = KIND_CHIP_COLOR[k]
          const isActive = activeKind === k
          return (
            <button
              key={k}
              onClick={() => setActiveKind(activeKind === k ? 'all' : k)}
              className={`flex-shrink-0 flex items-center gap-1.5 text-[10px] font-medium px-2.5 py-1 rounded-full border transition-colors ${
                isActive ? chips.active : 'border-[var(--border-default)] text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]'
              }`}
            >
              <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${chips.dot}`} />
              {KIND_LABEL[k]} · {kindCounts[k]}
            </button>
          )
        })}
      </div>

      <div className="flex-1 overflow-y-auto">
        {/* Add form */}
        {adding && (
          <div className="p-3 border-b border-[var(--border-subtle)]">
            <FactForm onSave={handleAdd} onCancel={() => setAdding(false)} saving={saving} />
          </div>
        )}

        {/* Empty: no facts at all */}
        {facts.length === 0 && !adding && (
          <div className="flex flex-col items-center justify-center h-40 gap-2 text-center px-6">
            <p className="text-xs font-medium text-[var(--text-secondary)]">No facts yet</p>
            <p className="text-[11px] text-[var(--text-tertiary)]">Index the document or add facts manually.</p>
            {canWrite && (
              <button onClick={() => setAdding(true)}
                className="text-xs text-[var(--accent)] hover:underline font-medium mt-1">
                + Add fact
              </button>
            )}
          </div>
        )}

        {/* Empty: facts exist but search/filter has no match */}
        {facts.length > 0 && filtered.length === 0 && !adding && (
          <div className="flex flex-col items-center justify-center h-32 gap-1.5 text-center px-6">
            <p className="text-xs text-[var(--text-secondary)]">No facts match your filter</p>
            <button onClick={() => { setSearch(''); setActiveKind('all') }}
              className="text-[11px] text-[var(--accent)] hover:underline">
              Clear filters
            </button>
          </div>
        )}

        {/* Fact list grouped by kind */}
        {byKind.length > 0 && (
          <div className="py-1">
            {byKind.map(({ kind, facts: kfacts }) => (
              <div key={kind}>
                <div className="flex items-center gap-2 px-3 pt-3 pb-1">
                  <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${KIND_COLOR[kind]}`} />
                  <span className="text-[10px] font-semibold text-[var(--text-tertiary)] uppercase tracking-widest">{KIND_LABEL[kind]}</span>
                  <span className="text-[10px] text-[var(--text-tertiary)]">{kfacts.length}</span>
                </div>
                {kfacts.map(f => (
                  <DocFactRow key={f.id} fact={f} canWrite={canWrite} appId={appId}
                    selected={selectedIds.has(f.id)}
                    onToggleSelect={toggleSelect}
                    onUpdate={updated => setFacts(prev => prev.map(p => p.id === updated.id ? updated : p))}
                    onDelete={id => setFacts(prev => prev.filter(p => p.id !== id))} />
                ))}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Main CorpusManager ────────────────────────────────────────────────────────

export function CorpusManager({ appId, docs, canWrite, rebuildStatus, onRefresh }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [rightTab, setRightTab] = useState<'preview' | 'facts'>('preview')
  const [markdown, setMarkdown] = useState<MarkdownData | null>(null)
  const [markdownLoading, setMarkdownLoading] = useState(false)
  const [markdownUnavailable, setMarkdownUnavailable] = useState(false)
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [reindexingId, setReindexingId] = useState<string | null>(null)

  // Auto-select first doc; clear stale selection on delete
  useEffect(() => {
    if (docs.length > 0 && !selectedId) {
      setSelectedId(docs[0].id)
    } else if (selectedId && !docs.find(d => d.id === selectedId)) {
      setSelectedId(docs.length > 0 ? docs[0].id : null)
    }
  }, [docs, selectedId])

  // Fetch markdown when selection changes (only for preview tab)
  useEffect(() => {
    if (!selectedId) { setMarkdown(null); setMarkdownUnavailable(false); return }
    setMarkdownLoading(true); setMarkdownUnavailable(false); setMarkdown(null)
    api.apps.getCorpusDocMarkdown(appId, selectedId)
      .then(data => { setMarkdown(data); setMarkdownUnavailable(false) })
      .catch(() => setMarkdownUnavailable(true))
      .finally(() => setMarkdownLoading(false))
  }, [appId, selectedId])

  async function handleUpload(files: FileList | null) {
    if (!files?.length) return
    setUploading(true)
    try {
      await api.apps.uploadCorpusDoc(appId, files[0])
      toast.success('Document uploaded', { description: 'Indexing has started.' })
      onRefresh()
    } catch (e: unknown) {
      toast.error('Upload failed', { description: e instanceof Error ? e.message : 'Unknown error' })
    } finally {
      setUploading(false)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  async function handleReindexDoc(docId: string) {
    setReindexingId(docId)
    try {
      await api.apps.reindexDoc(appId, docId)
      toast.success('Re-indexing started')
      onRefresh()
    } catch (e: unknown) {
      toast.error('Re-index failed', { description: e instanceof Error ? e.message : 'Unknown error' })
    } finally {
      setTimeout(() => setReindexingId(null), 2000)
    }
  }

  async function handleDelete(docId: string) {
    setDeleting(docId)
    try {
      await api.apps.deleteCorpusDoc(appId, docId)
      toast.success('Document deleted', { description: 'Associated facts and index removed.' })
      setConfirmDeleteId(null)
      onRefresh()
    } catch (e: unknown) {
      toast.error('Delete failed', { description: e instanceof Error ? e.message : 'Unknown error' })
    } finally {
      setDeleting(null)
    }
  }

  const selectedDoc = docs.find(d => d.id === selectedId)
  const isRebuilding = rebuildStatus === 'rebuilding'

  return (
    <div
      className="rounded-xl border border-[var(--border-default)] overflow-hidden flex flex-col"
      style={{ boxShadow: '0 1px 4px rgba(0,0,0,0.06), 0 0 0 1px rgba(0,0,0,0.03)' }}
    >
      {/* ── Header ── */}
      <div className="flex items-center justify-between px-5 py-3.5 bg-[var(--bg-elevated)] border-b border-[var(--border-default)] flex-shrink-0">
        <div className="flex items-center gap-2.5">
          <span className="text-sm font-semibold text-[var(--text-primary)]">Corpus Documents</span>
          <span className="inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded-full bg-[var(--bg-base)] border border-[var(--border-subtle)] text-[10px] font-semibold text-[var(--text-tertiary)] tabular-nums">
            {docs.length}
          </span>
        </div>
        {canWrite && (
          <>
            <input ref={inputRef} type="file" accept=".pdf,.docx,.txt" className="hidden"
              onChange={e => handleUpload(e.target.files)} />
            <button
              onClick={() => inputRef.current?.click()}
              disabled={uploading}
              className="group flex items-center gap-2 rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] px-3.5 py-2 text-xs font-medium text-[var(--text-secondary)] hover:border-[var(--accent)] hover:text-[var(--accent)] disabled:opacity-50 transition-all duration-150"
            >
              <Upload size={13} className={`transition-transform group-hover:scale-110 ${uploading ? 'animate-pulse' : ''}`} />
              {uploading ? 'Uploading…' : 'Upload Document'}
            </button>
          </>
        )}
      </div>

      {isRebuilding && (
        <div className="flex items-center gap-2 px-5 py-2 bg-sky-50 border-b border-sky-100 text-[11px] text-sky-700 font-medium flex-shrink-0">
          <RotateCcw size={11} className="animate-spin flex-shrink-0" />
          Rebuilding app brain — all documents are being re-indexed…
        </div>
      )}

      {/* ── Two-panel body (fixed height, own scroll) ── */}
      <div className="flex overflow-hidden" style={{ height: 'calc(100vh - 220px)', minHeight: 480 }}>

        {/* Left: document list */}
        <div className="w-[240px] flex-shrink-0 flex flex-col overflow-y-auto bg-[var(--bg-elevated)] border-r border-[var(--border-default)]">
          {docs.length === 0 ? (
            <div className="flex flex-col items-center justify-center flex-1 gap-3 p-6 text-center">
              <div className="w-11 h-11 rounded-full bg-[var(--bg-base)] border border-[var(--border-default)] flex items-center justify-center">
                <FileText size={19} className="text-[var(--text-tertiary)]" strokeWidth={1.5} />
              </div>
              <div>
                <p className="text-xs font-semibold text-[var(--text-secondary)]">No documents yet</p>
                <p className="text-[11px] text-[var(--text-tertiary)] mt-0.5">Upload a PDF, DOCX, or TXT file</p>
              </div>
              {canWrite && (
                <button onClick={() => inputRef.current?.click()}
                  className="text-xs text-[var(--accent)] hover:underline font-semibold">
                  Upload now
                </button>
              )}
            </div>
          ) : (
            <ul className="p-2 space-y-0.5">
              {docs.map(doc => {
                const isSelected = doc.id === selectedId
                const isConfirming = confirmDeleteId === doc.id
                const isDeleting_ = deleting === doc.id
                const isReindexing = reindexingId === doc.id

                return (
                  <li key={doc.id}
                    onClick={() => { if (!isConfirming) { setSelectedId(doc.id); setRightTab('preview') } }}
                    className={`group relative flex flex-col gap-2 p-2.5 cursor-pointer rounded-lg transition-all duration-100 border ${
                      isSelected
                        ? 'bg-[var(--bg-surface)] border-[var(--border-default)] shadow-sm'
                        : 'border-transparent hover:bg-[var(--bg-surface)] hover:border-[var(--border-subtle)]'
                    }`}
                  >
                    {isSelected && (
                      <div className="absolute left-0 top-2 bottom-2 w-0.5 rounded-full bg-[var(--accent)]" />
                    )}
                    <div className="flex items-start gap-2.5 min-w-0 pl-1.5">
                      <div className={`mt-0.5 flex-shrink-0 w-7 h-7 rounded-md flex items-center justify-center transition-colors ${
                        isSelected ? 'bg-[var(--accent)]/10' : 'bg-[var(--bg-base)]'
                      }`}>
                        <FileText size={14} strokeWidth={1.5}
                          className={isSelected ? 'text-[var(--accent)]' : 'text-[var(--text-tertiary)]'} />
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className={`text-xs truncate leading-snug transition-colors ${
                          isSelected ? 'font-semibold text-[var(--text-primary)]' : 'font-medium text-[var(--text-secondary)]'
                        }`}>{doc.name}</p>
                        <div className="flex items-center gap-1.5 mt-1 flex-wrap">
                          {doc.page_count != null && (
                            <span className="text-[10px] text-[var(--text-tertiary)] tabular-nums leading-none">{doc.page_count}p</span>
                          )}
                          <IndexStatusBadge status={doc.index_status} />
                        </div>
                      </div>
                    </div>

                    {isConfirming && (
                      <div className="flex items-center gap-1.5 pl-4" onClick={e => e.stopPropagation()}>
                        <AlertTriangle size={11} className="text-orange-500 flex-shrink-0" />
                        <span className="text-[10px] text-[var(--text-secondary)]">Delete + linked facts?</span>
                        <button onClick={() => handleDelete(doc.id)} disabled={isDeleting_}
                          className="text-[10px] font-semibold text-red-600 hover:text-red-700 disabled:opacity-50 ml-0.5">
                          {isDeleting_ ? 'Deleting…' : 'Confirm'}
                        </button>
                        <button onClick={() => setConfirmDeleteId(null)}
                          className="text-[10px] text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]">Cancel</button>
                      </div>
                    )}

                    {!isConfirming && canWrite && (
                      <div
                        className={`flex items-center gap-0.5 pl-4 transition-opacity duration-100 ${isSelected ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`}
                        onClick={e => e.stopPropagation()}
                      >
                        <button onClick={() => handleReindexDoc(doc.id)}
                          disabled={isReindexing || doc.index_status === 'running'}
                          className="flex items-center gap-1 text-[10px] text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] disabled:opacity-40 px-1.5 py-0.5 rounded hover:bg-[var(--bg-elevated)] transition-colors">
                          <RefreshCw size={9} className={isReindexing ? 'animate-spin' : ''} />
                          {isReindexing ? 'Indexing…' : 'Re-index'}
                        </button>
                        <span className="text-[var(--text-tertiary)] text-[11px] select-none">·</span>
                        <button onClick={() => setConfirmDeleteId(doc.id)}
                          className="flex items-center gap-1 text-[10px] text-[var(--text-tertiary)] hover:text-red-500 px-1.5 py-0.5 rounded hover:bg-[var(--bg-elevated)] transition-colors">
                          <Trash2 size={9} />
                          Delete
                        </button>
                      </div>
                    )}
                  </li>
                )
              })}
            </ul>
          )}
        </div>

        {/* Right: doc viewer */}
        <div className="flex-1 flex flex-col overflow-hidden min-w-0 bg-[var(--bg-surface)]">

          {!selectedDoc ? (
            <div className="flex flex-col items-center justify-center flex-1 gap-3 p-8 text-center">
              <div className="w-12 h-12 rounded-full bg-[var(--bg-elevated)] border border-[var(--border-default)] flex items-center justify-center">
                <FileText size={22} className="text-[var(--text-tertiary)]" strokeWidth={1.5} />
              </div>
              <p className="text-sm text-[var(--text-tertiary)]">Select a document to view its content and facts</p>
            </div>
          ) : (
            <>
              {/* Doc header */}
              <div className="flex items-center justify-between px-4 py-2.5 bg-[var(--bg-elevated)] border-b border-[var(--border-subtle)] flex-shrink-0">
                <p className="text-xs font-medium text-[var(--text-primary)] truncate min-w-0 mr-3">
                  {selectedDoc.name}
                </p>
                <div className="flex items-center gap-1.5 flex-shrink-0">
                  <IndexStatusBadge status={selectedDoc.index_status} />
                  {canWrite && (
                    <>
                      <button
                        onClick={() => handleReindexDoc(selectedDoc.id)}
                        disabled={reindexingId === selectedDoc.id || selectedDoc.index_status === 'running'}
                        className="flex items-center gap-1 text-[10px] text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] px-2 py-1 rounded hover:bg-[var(--bg-base)] disabled:opacity-40 transition-colors"
                      >
                        <RefreshCw size={9} className={reindexingId === selectedDoc.id ? 'animate-spin' : ''} />
                        Re-index
                      </button>
                      <button
                        onClick={() => setConfirmDeleteId(selectedDoc.id)}
                        className="flex items-center gap-1 text-[10px] text-[var(--text-tertiary)] hover:text-red-500 px-2 py-1 rounded hover:bg-[var(--bg-base)] transition-colors"
                      >
                        <Trash2 size={9} />
                        Delete
                      </button>
                    </>
                  )}
                </div>
              </div>

              {/* Tab bar */}
              <div className="flex border-b border-[var(--border-default)] bg-[var(--bg-elevated)] flex-shrink-0">
                {(['preview', 'facts'] as const).map(tab => (
                  <button
                    key={tab}
                    onClick={() => setRightTab(tab)}
                    className={`px-4 py-2.5 text-xs font-medium capitalize border-b-2 transition-colors ${
                      rightTab === tab
                        ? 'border-[var(--accent)] text-[var(--accent)]'
                        : 'border-transparent text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]'
                    }`}
                  >
                    {tab === 'preview' ? 'Preview' : 'Facts'}
                  </button>
                ))}
              </div>

              {/* Tab content */}
              <div className="flex-1 overflow-hidden">
                {rightTab === 'preview' ? (
                  <>
                    {markdownLoading && (
                      <div className="p-6 space-y-3 animate-pulse overflow-y-auto h-full">
                        <div className="h-3 bg-[var(--bg-elevated)] rounded-full w-2/5" />
                        <div className="space-y-2 mt-5">
                          {[1, 0.92, 0.85, 1, 0.78, 1, 0.88].map((w, i) => (
                            <div key={i} className="h-2.5 bg-[var(--bg-elevated)] rounded-full" style={{ width: `${w * 100}%` }} />
                          ))}
                        </div>
                      </div>
                    )}

                    {!markdownLoading && markdownUnavailable && (
                      <div className="flex flex-col items-center justify-center h-full gap-3 p-8 text-center">
                        <div className="w-12 h-12 rounded-full bg-[var(--bg-elevated)] border border-[var(--border-default)] flex items-center justify-center">
                          <FileX size={22} className="text-[var(--text-tertiary)]" strokeWidth={1.5} />
                        </div>
                        <div>
                          <p className="text-sm font-semibold text-[var(--text-secondary)]">
                            {selectedDoc.index_status === 'pending' || selectedDoc.index_status === 'running'
                              ? 'Indexing in progress…'
                              : 'Markdown not yet available'}
                          </p>
                          <p className="text-xs text-[var(--text-tertiary)] mt-1.5 max-w-[240px] leading-relaxed">
                            {selectedDoc.index_status === 'done'
                              ? 'Re-index this document to generate a markdown preview.'
                              : 'Preview will appear once indexing completes.'}
                          </p>
                        </div>
                        {canWrite && selectedDoc.index_status === 'done' && (
                          <button
                            onClick={() => handleReindexDoc(selectedDoc.id)}
                            disabled={reindexingId === selectedDoc.id}
                            className="flex items-center gap-1.5 text-xs text-[var(--accent)] hover:underline font-semibold disabled:opacity-50"
                          >
                            <RefreshCw size={11} className={reindexingId === selectedDoc.id ? 'animate-spin' : ''} />
                            {reindexingId === selectedDoc.id ? 'Starting…' : 'Re-index now'}
                          </button>
                        )}
                      </div>
                    )}

                    {!markdownLoading && !markdownUnavailable && markdown && (
                      <div className="h-full overflow-y-auto">
                        {/* Viewer header */}
                        <div className="flex items-center justify-between px-5 py-2.5 border-b border-[var(--border-subtle)] bg-[var(--bg-elevated)]/60 sticky top-0 backdrop-blur-sm z-10">
                          <p className="text-[10px] font-mono text-[var(--text-tertiary)] truncate min-w-0 mr-3">{markdown.filename}</p>
                          <div className="flex items-center gap-2 flex-shrink-0">
                            <span className="text-[10px] px-2 py-0.5 rounded-full bg-[var(--bg-base)] border border-[var(--border-subtle)] text-[var(--text-tertiary)] uppercase tracking-widest font-semibold">
                              {markdown.provider}
                            </span>
                            <span className="text-[10px] text-[var(--text-tertiary)]">
                              {new Date(markdown.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
                            </span>
                          </div>
                        </div>
                        {/* Content */}
                        <div className="px-6 py-5 text-[12.5px] space-y-0.5 max-w-[680px]">
                          {markdown.markdown_text.split('\n').map((line, i) => (
                            <MarkdownLine key={i} line={line} />
                          ))}
                        </div>
                      </div>
                    )}
                  </>
                ) : (
                  <DocFactsPanel
                    key={selectedDoc.id}
                    appId={appId}
                    docId={selectedDoc.id}
                    docName={selectedDoc.name}
                    canWrite={canWrite}
                  />
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
