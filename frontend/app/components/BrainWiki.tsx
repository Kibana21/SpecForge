'use client'
import { useState, useEffect, useCallback, useMemo, Fragment } from 'react'
import {
  RefreshCw, BookMarked, FileText, Network, AlertTriangle, Link2, MapPin,
  ShieldCheck, ShieldAlert, GitFork, X,
} from 'lucide-react'
import { toast } from 'sonner'
import { api } from '@/lib/api'
import type {
  WikiIndexResponse, AppWikiConcept, AppWikiSummary, WikiTreeNodeRef, WikiHealth, WikiSectionContent,
} from '@/lib/types'
import { IntakeTraceChip } from '@/app/components/IntakeTraceChip'

// Canonical intake citation tokens, linkified inline when a projectId is present:
//   F:<uuid>  app fact   ·   C:<slug>  wiki concept   ·   S:<doc>:<node>  source section
const TOKEN_SPLIT = /(\[\[[^\]]+\]\]|\*\*[^*]+\*\*|\bF:[0-9a-fA-F-]{8,}\b|\bC:[a-z0-9][a-z0-9_-]+\b|\bS:[0-9a-fA-F-]{8,}:[A-Za-z0-9._-]+\b)/g

/** Scope-agnostic data adapter so the same wiki UI serves App Brain (E1) and
 *  Project (E2). When omitted, an App Brain adapter is built from `appId` —
 *  keeping the existing App caller 100% backward-compatible. */
export interface WikiAdapter {
  label: string
  getIndex: () => Promise<WikiIndexResponse>
  getConcept: (slug: string) => Promise<AppWikiConcept>
  getSummary: (docId: string) => Promise<AppWikiSummary>
  rebuild: () => Promise<unknown>
  checkHealth: () => Promise<unknown>
  getSection: (docId: string, nodeId: string) => Promise<WikiSectionContent>
}

interface Props {
  appId?: string
  adapter?: WikiAdapter
  initialCompiledAt: string | null
  initialStatus: string
  lastIndexedAt: string | null
  canWrite: boolean
  /** Project scope (E2): enables open-on-slug deep-linking + inline citation
   *  trace chips (`F:`/`C:`/`S:`) in wiki prose. Omitted for App Brain. */
  projectId?: string
  initialSlug?: string
}

type Selection =
  | { type: 'concept'; slug: string }
  | { type: 'summary'; docId: string }

// ── Inline markdown (bold + [[wikilinks]]) ──────────────────────────────────────

function renderInline(
  text: string,
  onLink: (target: string) => void,
  projectId?: string,
): React.ReactNode {
  // Split on [[wikilink]], **bold**, and (project scope) canonical citation tokens.
  const parts = text.split(TOKEN_SPLIT)
  return parts.map((p, i) => {
    if (projectId && (p.startsWith('F:') || p.startsWith('C:') || p.startsWith('S:'))) {
      return <IntakeTraceChip key={i} projectId={projectId} token={p} inline />
    }
    if (p.startsWith('[[') && p.endsWith(']]')) {
      const inner = p.slice(2, -2)
      const [target, alias] = inner.split('|')
      const label = (alias || target).replace(/^(concepts|summaries)\//, '')
      return (
        <button
          key={i}
          onClick={() => onLink(target.trim())}
          className="inline-flex items-center gap-0.5 text-[var(--accent)] hover:underline font-medium"
        >
          <Link2 size={10} className="inline" />
          {label}
        </button>
      )
    }
    if (p.startsWith('**') && p.endsWith('**')) {
      return <strong key={i} className="font-semibold text-[var(--text-primary)]">{p.slice(2, -2)}</strong>
    }
    return <Fragment key={i}>{p}</Fragment>
  })
}

// Drop a leading heading that just repeats the page title (the UI shows it already).
function stripLeadingTitle(md: string, title: string): string {
  const lines = md.split('\n')
  let i = 0
  while (i < lines.length && lines[i].trim() === '') i++
  const m = i < lines.length ? lines[i].match(/^#{1,3}\s+(.*)$/) : null
  if (m && m[1].trim().toLowerCase() === title.trim().toLowerCase()) {
    return lines.slice(i + 1).join('\n').replace(/^\n+/, '')
  }
  return md
}

function MarkdownBody({ md, onLink, projectId }: { md: string; onLink: (t: string) => void; projectId?: string }) {
  const lines = md.split('\n')
  return (
    <div className="text-[13px] space-y-0.5 max-w-[680px]">
      {lines.map((line, i) => {
        if (line.startsWith('### '))
          return <h3 key={i} className="text-xs font-semibold text-[var(--text-secondary)] mt-4 mb-1 uppercase tracking-wide">{renderInline(line.slice(4), onLink, projectId)}</h3>
        if (line.startsWith('## '))
          return <h2 key={i} className="text-sm font-bold text-[var(--text-primary)] mt-5 mb-1.5">{renderInline(line.slice(3), onLink, projectId)}</h2>
        if (line.startsWith('# '))
          return <h1 key={i} className="text-base font-bold text-[var(--text-primary)] mt-5 mb-2">{renderInline(line.slice(2), onLink, projectId)}</h1>
        if (/^---+$/.test(line.trim()))
          return <hr key={i} className="my-4 border-[var(--border-subtle)]" />
        if (line.trim() === '')
          return <div key={i} className="h-2" />
        if (line.startsWith('- ') || line.startsWith('* '))
          return (
            <div key={i} className="flex gap-2 leading-relaxed">
              <span className="text-[var(--text-tertiary)] mt-0.5 flex-shrink-0">·</span>
              <span className="text-[var(--text-secondary)]">{renderInline(line.slice(2), onLink, projectId)}</span>
            </div>
          )
        return <p key={i} className="leading-relaxed text-[var(--text-secondary)]">{renderInline(line, onLink, projectId)}</p>
      })}
    </div>
  )
}

// ── Grounded-in (PageIndex) chips ───────────────────────────────────────────────

function GroundedIn({ refs, getSection }: {
  refs: WikiTreeNodeRef[]
  getSection: (docId: string, nodeId: string) => Promise<WikiSectionContent>
}) {
  const [openKey, setOpenKey] = useState<string | null>(null)
  const [section, setSection] = useState<WikiSectionContent | null>(null)
  const [loading, setLoading] = useState(false)
  if (!refs?.length) return null

  async function toggle(r: WikiTreeNodeRef) {
    const key = `${r.doc_id}:${r.node_id}`
    if (openKey === key) { setOpenKey(null); setSection(null); return }
    setOpenKey(key); setSection(null); setLoading(true)
    try {
      setSection(await getSection(r.doc_id, r.node_id))
    } catch {
      setSection(null)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mt-5 pt-3 border-t border-[var(--border-subtle)]">
      <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)] mb-2 flex items-center gap-1.5">
        <MapPin size={11} /> Grounded in
      </p>
      <div className="flex flex-wrap gap-1.5">
        {refs.map((r, i) => {
          const key = `${r.doc_id}:${r.node_id}`
          const active = openKey === key
          return (
            <button key={`${key}-${i}`} onClick={() => toggle(r)}
              title="Click to view the source section"
              className={`inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full border transition-colors ${
                active
                  ? 'bg-[var(--accent)] border-[var(--accent)] text-white'
                  : 'border-[var(--border-default)] bg-[var(--bg-elevated)] text-[var(--text-secondary)] hover:border-[var(--accent)] hover:text-[var(--accent)]'
              }`}>
              {r.title || `§${r.node_id}`}{r.pages ? ` · pp ${r.pages}` : ''}
            </button>
          )
        })}
      </div>

      {openKey && (
        <div className="mt-3 rounded-lg border border-[var(--border-default)] bg-[var(--bg-elevated)] overflow-hidden">
          {loading ? (
            <div className="p-3 space-y-2 animate-pulse">
              {[1, 0.9, 0.8].map((w, i) => (
                <div key={i} className="h-2.5 bg-[var(--bg-base)] rounded-full" style={{ width: `${w * 100}%` }} />
              ))}
            </div>
          ) : section ? (
            <>
              <div className="flex items-center justify-between gap-2 px-3 py-2 border-b border-[var(--border-subtle)] bg-[var(--bg-surface)]/50">
                <p className="text-[11px] font-medium text-[var(--text-secondary)] truncate">
                  {section.doc_name} › {section.title || `§${section.node_id}`}
                  {section.pages ? <span className="text-[var(--text-tertiary)]"> · pp {section.pages}</span> : null}
                </p>
                <button onClick={() => { setOpenKey(null); setSection(null) }}
                  className="text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] flex-shrink-0">
                  <X size={12} />
                </button>
              </div>
              <div className="px-3 py-2.5 max-h-64 overflow-y-auto">
                <p className="text-[12px] leading-relaxed text-[var(--text-secondary)] whitespace-pre-wrap">
                  {section.text || '(no text for this section)'}
                </p>
              </div>
            </>
          ) : (
            <p className="p-3 text-[11px] text-[var(--text-tertiary)]">Couldn&apos;t load this section.</p>
          )}
        </div>
      )}
    </div>
  )
}

// ── Main component ──────────────────────────────────────────────────────────────

export function BrainWiki({ appId, adapter, initialCompiledAt, initialStatus, lastIndexedAt, canWrite, projectId, initialSlug }: Props) {
  // Default to an App Brain adapter when none is supplied (backward-compatible).
  const a: WikiAdapter = useMemo(() => adapter ?? {
    label: 'Brain Wiki',
    getIndex: () => api.apps.getWiki(appId!),
    getConcept: (slug) => api.apps.getWikiConcept(appId!, slug),
    getSummary: (docId) => api.apps.getWikiSummary(appId!, docId),
    rebuild: () => api.apps.rebuildWiki(appId!),
    checkHealth: () => api.apps.checkWikiHealth(appId!),
    getSection: (docId, nodeId) => api.apps.getCorpusSection(appId!, docId, nodeId),
  }, [adapter, appId])
  const [index, setIndex] = useState<WikiIndexResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(initialStatus === 'running')
  const [selection, setSelection] = useState<Selection | null>(null)
  const [concept, setConcept] = useState<AppWikiConcept | null>(null)
  const [summary, setSummary] = useState<AppWikiSummary | null>(null)
  const [pageLoading, setPageLoading] = useState(false)
  const [checkingHealth, setCheckingHealth] = useState(false)
  const [showHealth, setShowHealth] = useState(false)

  const load = useCallback(async () => {
    try {
      const data = await a.getIndex()
      setIndex(data)
      setRunning(data.status === 'running')
      setSelection(prev => {
        if (prev) return prev
        if (initialSlug && data.concepts.some(c => c.slug === initialSlug)) return { type: 'concept', slug: initialSlug }
        if (data.concepts.length) return { type: 'concept', slug: data.concepts[0].slug }
        if (data.summaries.length) return { type: 'summary', docId: data.summaries[0].doc_id }
        return null
      })
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }, [a, initialSlug])

  useEffect(() => { load() }, [load])

  // Deep-link: when the caller targets a specific concept (studio rail click),
  // switch to it — even if the wiki was already open on another page.
  useEffect(() => {
    if (initialSlug) setSelection({ type: 'concept', slug: initialSlug })
  }, [initialSlug])

  // Poll while compiling
  useEffect(() => {
    if (!running) return
    const id = setInterval(async () => {
      try {
        const data = await a.getIndex()
        setIndex(data)
        if (data.status !== 'running') {
          setRunning(false)
          clearInterval(id)
          toast.success(`${a.label} compiled`, {
            description: `${data.concepts.length} concepts · ${data.summaries.length} documents`,
          })
        }
      } catch {
        clearInterval(id)
        setRunning(false)
      }
    }, 4000)
    return () => clearInterval(id)
  }, [running, a])

  // Fetch selected page
  useEffect(() => {
    if (!selection) { setConcept(null); setSummary(null); return }
    setPageLoading(true); setConcept(null); setSummary(null)
    const p = selection.type === 'concept'
      ? a.getConcept(selection.slug).then(setConcept)
      : a.getSummary(selection.docId).then(setSummary)
    p.catch(() => {}).finally(() => setPageLoading(false))
  }, [a, selection])

  function handleWikiLink(target: string) {
    if (!index) return
    const clean = target.replace(/^(concepts|summaries)\//, '')
    const c = index.concepts.find(x => x.slug === clean || x.slug === target.replace('concepts/', ''))
    if (c) { setSelection({ type: 'concept', slug: c.slug }); return }
    const s = index.summaries.find(x => x.doc_name === clean || x.doc_name.replace(/\.[^.]+$/, '') === clean)
    if (s) { setSelection({ type: 'summary', docId: s.doc_id }) }
  }

  async function handleRebuild() {
    setRunning(true)
    try {
      await a.rebuild()
      toast.info('Wiki compilation started', { description: 'This may take a minute for large corpora.' })
    } catch (e: unknown) {
      setRunning(false)
      toast.error('Compilation failed', { description: e instanceof Error ? e.message : 'Unknown error' })
    }
  }

  async function handleCheckHealth() {
    setCheckingHealth(true)
    setShowHealth(true)
    const prevCheckedAt = index?.health?.checked_at ?? null
    try {
      await a.checkHealth()
      // Poll until the report's checked_at changes (or give up after ~40s)
      for (let i = 0; i < 10; i++) {
        await new Promise(r => setTimeout(r, 4000))
        const data = await a.getIndex()
        setIndex(data)
        if (data.health && data.health.checked_at !== prevCheckedAt) {
          const n = data.health.contradictions.length + data.health.orphans.length
          toast.success('Health check complete', {
            description: n === 0 ? 'No issues found.' : `${n} issue${n !== 1 ? 's' : ''} found.`,
          })
          break
        }
      }
    } catch (e: unknown) {
      toast.error('Health check failed', { description: e instanceof Error ? e.message : 'Unknown error' })
    } finally {
      setCheckingHealth(false)
    }
  }

  const compiledAt = index?.compiled_at ?? initialCompiledAt
  const isStale = !running && compiledAt && lastIndexedAt && new Date(lastIndexedAt) > new Date(compiledAt)
  const isEmpty = !loading && index && index.concepts.length === 0 && index.summaries.length === 0

  if (loading) {
    return (
      <div className="max-w-2xl space-y-4 animate-pulse">
        <div className="h-4 bg-[var(--bg-elevated)] rounded-full w-1/3" />
        <div className="h-32 bg-[var(--bg-elevated)] rounded-xl" />
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 mb-3 flex-shrink-0">
        <div>
          <h2 className="text-sm font-semibold text-[var(--text-primary)] flex items-center gap-2">
            <BookMarked size={15} className="text-[var(--accent)]" />
            {a.label}
          </h2>
          <p className="text-xs text-[var(--text-tertiary)] mt-1">
            {compiledAt
              ? <>Compiled {new Date(compiledAt).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })} · {index?.concepts.length ?? 0} concepts · {index?.summaries.length ?? 0} documents</>
              : 'Emergent topics compiled from your corpus documents, with section-level traceability.'}
          </p>
        </div>
        {canWrite && (
          <div className="flex items-center gap-2 flex-shrink-0">
            {compiledAt && (
              <button
                onClick={handleCheckHealth}
                disabled={checkingHealth || running}
                className="flex items-center gap-2 rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] px-3 py-2 text-xs font-medium text-[var(--text-secondary)] hover:border-[var(--accent)] hover:text-[var(--accent)] disabled:opacity-60 transition-all duration-150"
              >
                <ShieldCheck size={12} className={checkingHealth ? 'animate-pulse' : ''} />
                {checkingHealth ? 'Checking…' : 'Health'}
              </button>
            )}
            <button
              onClick={handleRebuild}
              disabled={running}
              className="flex items-center gap-2 rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] px-4 py-2 text-xs font-medium text-[var(--text-secondary)] hover:border-[var(--accent)] hover:text-[var(--accent)] disabled:opacity-60 transition-all duration-150"
            >
              <RefreshCw size={12} className={running ? 'animate-spin' : ''} />
              {running ? 'Compiling…' : compiledAt ? 'Rebuild' : 'Compile'}
            </button>
          </div>
        )}
      </div>

      {/* Stale banner */}
      {isStale && (
        <div className="flex items-center gap-2.5 px-4 py-2.5 mb-3 rounded-lg bg-amber-50 border border-amber-200 text-[11px] text-amber-700 flex-shrink-0">
          <AlertTriangle size={12} className="flex-shrink-0" />
          <span>Documents changed since last compile. Rebuild for fresh results.</span>
          {canWrite && (
            <button onClick={handleRebuild} className="ml-auto font-semibold hover:underline flex-shrink-0">Rebuild now</button>
          )}
        </div>
      )}

      {/* Health report */}
      {showHealth && index?.health && (() => {
        const h = index.health
        const clean = h.contradictions.length === 0 && h.orphans.length === 0
        return (
          <div className={`mb-3 rounded-lg border px-4 py-3 flex-shrink-0 ${
            clean ? 'border-emerald-200 bg-emerald-50' : 'border-amber-200 bg-amber-50'
          }`}>
            <div className="flex items-center gap-2 mb-1.5">
              {clean
                ? <ShieldCheck size={13} className="text-emerald-600" />
                : <ShieldAlert size={13} className="text-amber-600" />}
              <span className={`text-xs font-semibold ${clean ? 'text-emerald-700' : 'text-amber-700'}`}>
                {clean ? 'No issues found' : `${h.contradictions.length} contradiction${h.contradictions.length !== 1 ? 's' : ''}, ${h.orphans.length} orphan${h.orphans.length !== 1 ? 's' : ''}`}
              </span>
              <button onClick={() => setShowHealth(false)} className="ml-auto text-[10px] text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]">Hide</button>
            </div>
            {h.contradictions.length > 0 && (
              <div className="space-y-1 mt-2">
                {h.contradictions.map((c, i) => (
                  <div key={i} className="flex items-start gap-2 text-[11px] text-amber-800">
                    <AlertTriangle size={11} className="mt-0.5 flex-shrink-0" />
                    <span>
                      <button onClick={() => setSelection({ type: 'concept', slug: c.concept_a })} className="font-medium underline hover:no-underline">{c.concept_a}</button>
                      {' ↔ '}
                      <button onClick={() => setSelection({ type: 'concept', slug: c.concept_b })} className="font-medium underline hover:no-underline">{c.concept_b}</button>
                      {' — '}{c.issue}
                    </span>
                  </div>
                ))}
              </div>
            )}
            {h.orphans.length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5 mt-2">
                <span className="text-[10px] font-semibold uppercase tracking-widest text-amber-700 flex items-center gap-1"><GitFork size={10} /> Orphans</span>
                {h.orphans.map(o => (
                  <button key={o.slug} onClick={() => setSelection({ type: 'concept', slug: o.slug })}
                    className="text-[10px] font-medium px-2 py-0.5 rounded-full border border-amber-300 text-amber-700 hover:bg-amber-100">
                    {o.title}
                  </button>
                ))}
              </div>
            )}
            <p className="text-[10px] text-[var(--text-tertiary)] mt-2">Checked {new Date(h.checked_at).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</p>
          </div>
        )
      })()}

      {/* Empty state */}
      {isEmpty && !running && (
        <div className="rounded-xl border border-dashed border-[var(--border-default)] p-10 flex flex-col items-center gap-4 text-center">
          <div className="w-14 h-14 rounded-2xl bg-[var(--bg-elevated)] border border-[var(--border-default)] flex items-center justify-center">
            <BookMarked size={26} className="text-[var(--text-tertiary)]" strokeWidth={1.5} />
          </div>
          <div>
            <p className="text-sm font-semibold text-[var(--text-secondary)]">No wiki yet</p>
            <p className="text-xs text-[var(--text-tertiary)] mt-1.5 max-w-[320px] leading-relaxed">
              Index corpus documents, then click <strong>Compile</strong> to build a navigable knowledge base of emergent topics.
            </p>
          </div>
          {canWrite && (
            <button onClick={handleRebuild}
              className="flex items-center gap-2 text-xs font-semibold text-[var(--accent)] border border-[var(--accent)]/30 px-4 py-2 rounded-lg hover:bg-[var(--accent)]/5 transition-colors">
              <RefreshCw size={12} /> Compile now
            </button>
          )}
        </div>
      )}

      {/* Two-panel body */}
      {!isEmpty && index && (
        <div className="flex flex-1 min-h-0 rounded-xl border border-[var(--border-default)] overflow-hidden bg-[var(--bg-surface)]">
          {/* Left rail */}
          <div className="w-[210px] flex-shrink-0 flex flex-col overflow-y-auto bg-[var(--bg-elevated)] border-r border-[var(--border-default)] p-2">
            {index.concepts.length > 0 && (
              <>
                <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)] px-2 py-1.5 flex items-center gap-1.5">
                  <Network size={11} /> Concepts
                </p>
                {index.concepts.map(c => {
                  const active = selection?.type === 'concept' && selection.slug === c.slug
                  return (
                    <button key={c.slug}
                      onClick={() => setSelection({ type: 'concept', slug: c.slug })}
                      title={c.brief}
                      className={`relative text-left px-2.5 py-1.5 rounded-lg text-xs transition-colors mb-0.5 ${
                        active ? 'bg-[var(--bg-surface)] font-semibold text-[var(--text-primary)] shadow-sm' : 'text-[var(--text-secondary)] hover:bg-[var(--bg-surface)]'
                      }`}>
                      {active && <span className="absolute left-0 top-1.5 bottom-1.5 w-0.5 rounded-full bg-[var(--accent)]" />}
                      <span className="truncate block">{c.title}</span>
                    </button>
                  )
                })}
              </>
            )}
            {index.summaries.length > 0 && (
              <>
                <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)] px-2 py-1.5 mt-2 flex items-center gap-1.5">
                  <FileText size={11} /> Documents
                </p>
                {index.summaries.map(s => {
                  const active = selection?.type === 'summary' && selection.docId === s.doc_id
                  return (
                    <button key={s.doc_id}
                      onClick={() => setSelection({ type: 'summary', docId: s.doc_id })}
                      title={s.brief}
                      className={`relative text-left px-2.5 py-1.5 rounded-lg text-xs transition-colors mb-0.5 ${
                        active ? 'bg-[var(--bg-surface)] font-semibold text-[var(--text-primary)] shadow-sm' : 'text-[var(--text-secondary)] hover:bg-[var(--bg-surface)]'
                      }`}>
                      {active && <span className="absolute left-0 top-1.5 bottom-1.5 w-0.5 rounded-full bg-[var(--accent)]" />}
                      <span className="truncate block">{s.doc_name}</span>
                    </button>
                  )
                })}
              </>
            )}
          </div>

          {/* Right panel */}
          <div className="flex-1 overflow-y-auto p-5 min-w-0">
            {pageLoading && (
              <div className="space-y-2 animate-pulse">
                <div className="h-4 bg-[var(--bg-elevated)] rounded-full w-1/3" />
                {[1, 0.9, 0.8, 0.95].map((w, i) => (
                  <div key={i} className="h-2.5 bg-[var(--bg-elevated)] rounded-full" style={{ width: `${w * 100}%` }} />
                ))}
              </div>
            )}

            {!pageLoading && concept && (
              <div>
                <h1 className="text-base font-bold text-[var(--text-primary)]">{concept.title}</h1>
                {concept.brief && (
                  <p className="mt-2 text-[13px] leading-relaxed text-[var(--text-secondary)] border-l-2 border-[var(--accent)]/50 pl-3">
                    {concept.brief}
                  </p>
                )}
                <div className="mt-4">
                  <MarkdownBody md={stripLeadingTitle(concept.content_md, concept.title)} onLink={handleWikiLink} projectId={projectId} />
                </div>
                <GroundedIn refs={concept.tree_node_refs} getSection={a.getSection} />
                {concept.related_slugs.length > 0 && (
                  <div className="mt-4 pt-3 border-t border-[var(--border-subtle)]">
                    <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)] mb-2">Related</p>
                    <div className="flex flex-wrap gap-1.5">
                      {concept.related_slugs.map(slug => {
                        const c = index.concepts.find(x => x.slug === slug)
                        return (
                          <button key={slug} onClick={() => setSelection({ type: 'concept', slug })}
                            className="inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full border border-[var(--accent)]/30 text-[var(--accent)] hover:bg-[var(--accent)]/5">
                            <Link2 size={10} /> {c?.title ?? slug}
                          </button>
                        )
                      })}
                    </div>
                  </div>
                )}
              </div>
            )}

            {!pageLoading && summary && (() => {
              const docName = index.summaries.find(s => s.doc_id === summary.doc_id)?.doc_name ?? 'Document'
              return (
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)] mb-1">Document Summary</p>
                <h1 className="text-base font-bold text-[var(--text-primary)]">{docName}</h1>
                {summary.brief && (
                  <p className="mt-2 text-[13px] leading-relaxed text-[var(--text-secondary)] border-l-2 border-[var(--accent)]/50 pl-3">
                    {summary.brief}
                  </p>
                )}
                <div className="mt-4">
                  <MarkdownBody md={stripLeadingTitle(summary.content_md, docName)} onLink={handleWikiLink} projectId={projectId} />
                </div>
                {summary.related_slugs.length > 0 && (
                  <div className="mt-4 pt-3 border-t border-[var(--border-subtle)]">
                    <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)] mb-2">Concepts in this document</p>
                    <div className="flex flex-wrap gap-1.5">
                      {summary.related_slugs.map(slug => {
                        const c = index.concepts.find(x => x.slug === slug)
                        return (
                          <button key={slug} onClick={() => setSelection({ type: 'concept', slug })}
                            className="inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full border border-[var(--accent)]/30 text-[var(--accent)] hover:bg-[var(--accent)]/5">
                            <Network size={10} /> {c?.title ?? slug}
                          </button>
                        )
                      })}
                    </div>
                  </div>
                )}
              </div>
              )
            })()}
          </div>
        </div>
      )}
    </div>
  )
}
