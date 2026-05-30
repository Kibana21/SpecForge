'use client'
/**
 * Understanding Studio (E2 intake).
 *
 * The intake hero: a three-zone workspace where the system's understanding of the
 * project comes alive as the user resolves high-signal clarification questions.
 *   • Left   — Sources & Project Wiki concept index
 *   • Center — the living Understanding Canvas (RU fields w/ confidence) ⇄ Project Wiki
 *   • Right  — the Clarification Stream (contradiction / ambiguity / gap questions)
 * Header carries the Understanding meter + Validate ("seal" the understanding).
 *
 * Exported as `InterviewPanel` (unchanged name) so the workspace import is stable.
 */
import { Fragment, useEffect, useMemo, useState } from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import {
  AlertTriangle, ArrowLeft, BookMarked, CheckCircle2, ChevronRight, CircleHelp,
  Database, FileText, HelpCircle, Layers, Network, Quote, Send, Sparkles, X,
} from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/app/components/ui/button'
import { Badge } from '@/app/components/ui/badge'
import { Skeleton } from '@/app/components/Skeleton'
import { BrdConfettiBurst } from '@/app/components/brd/BrdConfettiBurst'
import { ProjectWiki } from '@/app/components/ProjectWiki'
import { LineageMap } from '@/app/components/LineageMap'
import { IntakeTraceChip } from '@/app/components/IntakeTraceChip'
import { api } from '@/lib/api'
import { useUnderstanding } from '@/lib/hooks/useUnderstanding'
import type {
  Clarification, ClarificationKind, Confidence, RequirementUnderstanding,
} from '@/lib/types'

// ── helpers ─────────────────────────────────────────────────────────────────

function asList(v: unknown): string[] {
  return Array.isArray(v) ? v.filter((x) => typeof x === 'string') : []
}

const CONF_COLOR: Record<Confidence, string> = {
  high: 'var(--status-success)', medium: 'var(--status-warning)', low: 'var(--status-danger)',
}

const KIND_META: Record<ClarificationKind, { label: string; icon: typeof AlertTriangle; tint: string; bg: string; border: string }> = {
  contradiction: { label: 'Contradiction', icon: AlertTriangle, tint: 'var(--status-danger)', bg: 'var(--status-danger-bg)', border: '#F1C9C4' },
  ambiguity:     { label: 'Ambiguity',     icon: HelpCircle,    tint: 'var(--status-warning)', bg: 'var(--status-warning-bg)', border: '#EBD9AE' },
  gap:           { label: 'Gap',           icon: CircleHelp,    tint: 'var(--status-info)',  bg: 'var(--status-info-bg)',  border: '#C6D9E6' },
}
const SEVERITY_ORDER = { blocker: 0, major: 1, minor: 2 } as Record<string, number>

// RU canvas fields, in display order.
const RU_FIELDS: Array<{ key: string; label: string; type: 'text' | 'list' }> = [
  { key: 'objective', label: 'Objective', type: 'text' },
  { key: 'target_process', label: 'Target Process', type: 'text' },
  { key: 'stakeholders', label: 'Stakeholders', type: 'list' },
  { key: 'roles', label: 'Roles', type: 'list' },
  { key: 'pain_points', label: 'Pain Points', type: 'list' },
  { key: 'functional_areas', label: 'Functional Areas', type: 'list' },
  { key: 'systems', label: 'Systems', type: 'list' },
  { key: 'integrations', label: 'Integrations', type: 'list' },
  { key: 'risks', label: 'Risks', type: 'list' },
]

interface Props {
  projectId: string
  onBack?: () => void
  onValidated?: () => void
}

export function InterviewPanel({ projectId, onBack, onValidated }: Props) {
  const reduce = useReducedMotion()
  const { detail, isLoading, mutate } = useUnderstanding(projectId)
  const [busy, setBusy] = useState(false)
  const [center, setCenter] = useState<'canvas' | 'wiki'>('canvas')
  const [sealed, setSealed] = useState(false)
  const [lineageOpen, setLineageOpen] = useState(false)
  const [wikiSlug, setWikiSlug] = useState<string | undefined>(undefined)

  const ru = detail?.understanding ?? null
  const clarifications = useMemo(() => detail?.clarifications ?? [], [detail?.clarifications])
  const generated = ru && ru.status !== 'draft'
  const validated = ru?.status === 'validated'
  const content = useMemo(() => (ru?.content_json ?? {}) as Record<string, unknown>, [ru?.content_json])
  const fc = useMemo(
    () => (ru?.field_confidence ?? {}) as Record<string, { confidence?: Confidence; completeness?: number }>,
    [ru?.field_confidence],
  )

  // Understanding meter — blend mean field completeness with clarification resolution.
  const meter = useMemo(() => {
    const comps = RU_FIELDS.map(f => fc[f.key]?.completeness).filter((n): n is number => typeof n === 'number')
    const meanComp = comps.length ? comps.reduce((a, b) => a + b, 0) / comps.length : (generated ? 50 : 0)
    const total = clarifications.length
    const resolved = clarifications.filter(c => c.resolved).length
    const clarRate = total ? (resolved / total) * 100 : 100
    return Math.round(meanComp * 0.7 + clarRate * 0.3)
  }, [fc, clarifications, generated])

  const openBlockers = clarifications.filter(c => !c.resolved && c.severity === 'blocker').length
  const canValidate = generated && !validated

  async function run(fn: () => Promise<unknown>, ok: string) {
    setBusy(true)
    try { await fn(); await mutate(); if (ok) toast.success(ok) }
    catch (e) { toast.error(e instanceof Error ? e.message : 'Failed') }
    finally { setBusy(false) }
  }

  const handleGenerate = () => run(() => api.projects.generateUnderstanding(projectId), 'Understanding generated')
  const handleValidate = () => run(async () => {
    await api.projects.validateUnderstanding(projectId)
    setSealed(true)
    onValidated?.()
  }, '')

  // ── render gates ──────────────────────────────────────────────────────────
  if (isLoading) {
    return <div className="p-6 h-full"><Skeleton className="h-full rounded-xl" /></div>
  }

  return (
    <div className="flex flex-col h-full overflow-hidden bg-[var(--bg-base)]">
      <BrdConfettiBurst active={sealed} />

      {/* Header */}
      <header className="shrink-0 flex items-center gap-3 h-12 border-b border-[var(--border-default)] bg-[var(--bg-surface)] px-4">
        {onBack && (
          <button onClick={onBack}
            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] transition-colors">
            <ArrowLeft size={14} /> Back
          </button>
        )}
        <span className="text-sm font-semibold text-[var(--text-primary)]">Requirement Understanding</span>
        {generated && <UnderstandingMeter pct={meter} validated={!!validated} reduce={!!reduce} />}
        <div className="flex-1" />
        {generated && (
          <>
            <button
              onClick={() => setLineageOpen(true)}
              className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] px-2.5 py-1.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] transition-colors">
              <Network size={13} /> Provenance
            </button>
            <button
              onClick={() => setCenter(c => c === 'wiki' ? 'canvas' : 'wiki')}
              className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs transition-colors ${
                center === 'wiki'
                  ? 'border-[var(--accent)] bg-[var(--accent-subtle)] text-[var(--accent)]'
                  : 'border-[var(--border-default)] bg-[var(--bg-surface)] text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]'
              }`}>
              <BookMarked size={13} /> Wiki
            </button>
          </>
        )}
        {!generated && (
          <Button onClick={handleGenerate} disabled={busy}><Sparkles size={15} /> Generate Understanding</Button>
        )}
        {canValidate && (
          <Button onClick={handleValidate} disabled={busy} title={openBlockers ? `${openBlockers} blocker clarification(s) open` : undefined}>
            <CheckCircle2 size={15} /> Validate
          </Button>
        )}
        {validated && <Badge variant="success">Sealed ✓</Badge>}
      </header>

      {!generated ? (
        <EmptyState busy={busy} onGenerate={handleGenerate} />
      ) : sealed && validated ? (
        <SealSummary
          ru={ru} clarifications={clarifications}
          onExplore={() => { setSealed(false); setCenter('wiki') }}
          onContinue={() => setSealed(false)}
        />
      ) : (
        <div className="flex flex-1 overflow-hidden">
          <IntakeSourceRail projectId={projectId} clarifications={clarifications}
            onOpenWiki={(slug) => { setWikiSlug(slug); setCenter('wiki') }} />

          <div className="flex-1 overflow-y-auto min-w-0">
            {center === 'wiki'
              ? <div className="h-full p-4"><ProjectWiki projectId={projectId} canWrite initialSlug={wikiSlug} /></div>
              : <UnderstandingCanvas projectId={projectId} content={content} fc={fc} reduce={!!reduce} />}
          </div>

          <ClarificationStream
            projectId={projectId}
            clarifications={clarifications} busy={busy}
            onAnswer={(id, ans) => run(() => api.projects.answerClarification(projectId, id, ans), 'Clarified')}
            reduce={!!reduce}
          />
        </div>
      )}

      <LineageMap projectId={projectId} open={lineageOpen} onClose={() => setLineageOpen(false)} />
    </div>
  )
}

// ── Understanding meter ───────────────────────────────────────────────────────

function UnderstandingMeter({ pct, validated, reduce }: { pct: number; validated: boolean; reduce: boolean }) {
  const color = validated ? 'var(--accent)' : pct >= 75 ? 'var(--accent)' : pct >= 45 ? 'var(--status-warning)' : 'var(--status-danger)'
  return (
    <div className="hidden sm:flex items-center gap-2 ml-1" title="How well the system understands this project">
      <span className="text-[11px] font-medium text-[var(--text-tertiary)]">◍ Understood</span>
      <div className="w-28 h-1.5 rounded-full bg-[var(--bg-sunken)] overflow-hidden">
        <motion.div className="h-full rounded-full" style={{ background: color }}
          initial={false} animate={{ width: `${pct}%` }}
          transition={{ duration: reduce ? 0 : 0.6, ease: 'easeOut' }} />
      </div>
      <span className="text-[11px] font-semibold tabular-nums" style={{ color }}>{pct}%</span>
    </div>
  )
}

// ── Understanding Canvas ──────────────────────────────────────────────────────

// ── Inline citations ──────────────────────────────────────────────────────────
// RU field text carries citation markers like "[F26, F184, F244]" (F# = an App
// Brain fact, S# = a source section). Instead of dumping that as raw noise, we
// collapse each group into one compact chip that resolves the markers against
// the RU's own `citations` array (and the live fact resolver for canonical tokens).

type RUCite = { marker?: string; kind?: string; ref?: string; excerpt?: string }

function normMarker(m?: string): string {
  return (m || '').replace(/[[\]]/g, '').trim()
}

// A bracketed, comma-separated run of F#/S# (or canonical F:/S:/C:) markers.
const CITE_GROUP_RE = /\[(?:[SFC][A-Za-z0-9:._-]*)(?:\s*,\s*[SFC][A-Za-z0-9:._-]*)*\]/g

// Tokens that appear loose in prose (clarification question/rationale): a
// positional fact "F117", or a canonical F:/C:/S: token. Bare "S12" is skipped
// (no per-index source resolver). Each becomes a clickable chip in place.
const PROSE_TOKEN_RE = /\bF\d+\b|\bF:[0-9a-fA-F-]{8,}\b|\bC:[a-z0-9][a-z0-9_-]+\b|\bS:[0-9a-fA-F-]{8,}:[A-Za-z0-9._-]+\b/g

function linkifyCitations(text: string, projectId: string): React.ReactNode {
  if (!text) return text
  const parts: React.ReactNode[] = []
  const re = new RegExp(PROSE_TOKEN_RE.source, 'g')
  let last = 0
  let m: RegExpExecArray | null
  let k = 0
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) parts.push(<Fragment key={`t${k}`}>{text.slice(last, m.index)}</Fragment>)
    parts.push(<IntakeTraceChip key={`c${k}`} projectId={projectId} token={m[0]} inline labelOverride={m[0]} />)
    last = m.index + m[0].length
    k++
  }
  if (last < text.length) parts.push(<Fragment key={`t${k}`}>{text.slice(last)}</Fragment>)
  return <>{parts}</>
}

function CitedText({ text, citeMap, projectId }: {
  text: string
  citeMap: Map<string, RUCite>
  projectId: string
}) {
  const parts: React.ReactNode[] = []
  const re = new RegExp(CITE_GROUP_RE.source, 'g')
  let last = 0
  let m: RegExpExecArray | null
  let k = 0
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) parts.push(<Fragment key={`t${k}`}>{text.slice(last, m.index)}</Fragment>)
    const tokens = m[0].slice(1, -1).split(',').map(t => t.trim()).filter(Boolean)
    parts.push(<CitationPill key={`c${k}`} tokens={tokens} citeMap={citeMap} projectId={projectId} />)
    last = m.index + m[0].length
    k++
  }
  if (last < text.length) parts.push(<Fragment key={`t${k}`}>{text.slice(last)}</Fragment>)
  return <>{parts}</>
}

function CitationPill({ tokens, citeMap, projectId }: {
  tokens: string[]
  citeMap: Map<string, RUCite>
  projectId: string
}) {
  const [open, setOpen] = useState(false)
  return (
    <span className="relative inline-block align-baseline">
      <button type="button" onClick={() => setOpen(o => !o)}
        title="Grounded in app facts / source sections"
        className={`ml-1 inline-flex items-center gap-0.5 rounded-full px-1.5 align-super text-[9px] font-semibold transition-colors ${
          open ? 'bg-[var(--accent)] text-white' : 'bg-[var(--accent-subtle)] text-[var(--accent)] hover:bg-[var(--accent)]/15'
        }`}>
        <Quote size={8} /> {tokens.length}
      </button>
      {open && (
        <span className="absolute left-0 top-full z-30 mt-1 block w-72 space-y-1 rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] p-2 text-left shadow-[var(--shadow-lg)]"
          onClick={e => e.stopPropagation()}>
          <span className="mb-0.5 block text-[10px] font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
            Grounded in {tokens.length} citation{tokens.length !== 1 ? 's' : ''}
          </span>
          {tokens.map((tok, i) => (
            <CitationRow key={i} token={tok} cite={citeMap.get(normMarker(tok))} projectId={projectId} />
          ))}
        </span>
      )}
    </span>
  )
}

function CitationRow({ token, cite, projectId }: {
  token: string
  cite: RUCite | undefined
  projectId: string
}) {
  const isFact = token[0] === 'F'
  const resolvable = /^[FSC]:/.test(token) || /^F\d+$/.test(token)
  if (cite && (cite.ref || cite.excerpt)) {
    return (
      <span className="block rounded-md bg-[var(--bg-elevated)] px-2 py-1 text-[11px] leading-snug">
        <span className="flex items-center gap-1 font-semibold text-[var(--text-secondary)]">
          {cite.kind === 'fact' ? <Database size={10} /> : <FileText size={10} />}
          {cite.kind === 'fact' ? 'Fact' : 'Source'}{cite.ref ? ` · ${cite.ref}` : ''}
        </span>
        {cite.excerpt && <span className="mt-0.5 block text-[var(--text-tertiary)]">{cite.excerpt}</span>}
      </span>
    )
  }
  if (resolvable) {
    return <span className="block"><IntakeTraceChip projectId={projectId} token={token} labelOverride={token} /></span>
  }
  return (
    <span className="flex items-center gap-1 rounded-md bg-[var(--bg-elevated)] px-2 py-1 text-[11px] text-[var(--text-tertiary)]">
      {isFact ? <Database size={10} /> : <FileText size={10} />}
      {isFact ? 'App fact' : 'Source'} {token} — detail not captured
    </span>
  )
}

function UnderstandingCanvas({ projectId, content, fc, reduce }: {
  projectId: string
  content: Record<string, unknown>
  fc: Record<string, { confidence?: Confidence; completeness?: number }>
  reduce: boolean
}) {
  const citations = useMemo(
    () => (Array.isArray(content.citations) ? content.citations as RUCite[] : []),
    [content.citations],
  )
  const assumptions = Array.isArray(content.assumptions) ? content.assumptions as Array<{ text?: string }> : []

  // Map each citation marker ("[F26]" / "[S1]") → its resolved fact/source, so
  // the inline markers in the field text become compact, clickable provenance.
  const citeMap = useMemo(() => {
    const m = new Map<string, RUCite>()
    for (const c of citations) m.set(normMarker(c.marker), c)
    return m
  }, [citations])

  return (
    <div className="max-w-3xl mx-auto px-5 py-5 space-y-3">
      {RU_FIELDS.map((f, i) => {
        const conf = fc[f.key]
        const value = f.type === 'text' ? (content[f.key] as string) || '' : asList(content[f.key])
        const empty = f.type === 'text' ? !value : (value as string[]).length === 0
        return (
          <motion.div key={f.key}
            initial={reduce ? false : { opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2, delay: Math.min(i * 0.03, 0.25) }}
            className="rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-3.5">
            <div className="flex items-center gap-2 mb-1.5">
              <p className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-tertiary)]">{f.label}</p>
              <div className="flex-1" />
              {conf?.confidence && (
                <ConfidenceBar confidence={conf.confidence} completeness={conf.completeness ?? 0} reduce={reduce} />
              )}
            </div>
            {empty ? (
              <p className="text-sm text-[var(--text-tertiary)] italic">Not yet captured</p>
            ) : f.type === 'text' ? (
              <p className="text-sm text-[var(--text-primary)] leading-relaxed">
                <CitedText text={value as string} citeMap={citeMap} projectId={projectId} />
              </p>
            ) : (
              <div className="flex flex-wrap gap-1.5">
                {(value as string[]).map((v, j) => (
                  <span key={j} className="inline-flex items-center rounded-md bg-[var(--bg-elevated)] px-2 py-0.5 text-xs text-[var(--text-secondary)]">
                    <CitedText text={v} citeMap={citeMap} projectId={projectId} />
                  </span>
                ))}
              </div>
            )}
          </motion.div>
        )
      })}

      {assumptions.length > 0 && (
        <div className="rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-3.5">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-tertiary)] mb-1.5">Assumptions</p>
          <ul className="space-y-1">
            {assumptions.map((a, i) => (
              <li key={i} className="text-sm text-[var(--text-secondary)] flex gap-2">
                <span className="text-[var(--text-tertiary)]">·</span>{a.text}
              </li>
            ))}
          </ul>
        </div>
      )}

      {citations.length > 0 && (
        <div className="pt-1 flex flex-wrap items-center gap-1.5">
          <span className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)]">Grounded in</span>
          {citations.slice(0, 8).map((c, i) => (
            <span key={i} title={c.excerpt}
              className="inline-flex items-center gap-1 rounded-full border border-[var(--border-default)] bg-[var(--bg-elevated)] px-2 py-0.5 text-[10px] text-[var(--text-secondary)]">
              {c.kind === 'fact' ? <Database size={9} /> : <FileText size={9} />}
              {c.ref || c.marker || 'source'}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

function ConfidenceBar({ confidence, completeness, reduce }: { confidence: Confidence; completeness: number; reduce: boolean }) {
  const color = CONF_COLOR[confidence]
  return (
    <div className="flex items-center gap-1.5" title={`${confidence} confidence · ${completeness}% complete`}>
      <div className="w-16 h-1.5 rounded-full bg-[var(--bg-sunken)] overflow-hidden">
        <motion.div className="h-full rounded-full" style={{ background: color }}
          initial={false} animate={{ width: `${completeness}%` }}
          transition={{ duration: reduce ? 0 : 0.5, ease: 'easeOut' }} />
      </div>
      <span className="text-[10px] font-medium tabular-nums" style={{ color }}>{completeness}%</span>
    </div>
  )
}

// ── Left rail: Sources + Wiki concepts ────────────────────────────────────────

function IntakeSourceRail({ projectId, clarifications, onOpenWiki }: {
  projectId: string
  clarifications: Clarification[]
  onOpenWiki: (slug?: string) => void
}) {
  const openByConcept = useMemo(() => {
    const m = new Set<string>()
    for (const c of clarifications) {
      if (c.resolved) continue
      for (const tok of c.citations || []) if (tok.startsWith('C:')) m.add(tok.slice(2))
    }
    return m
  }, [clarifications])

  return (
    <aside className="w-56 shrink-0 flex flex-col overflow-y-auto border-r border-[var(--border-default)] bg-[var(--bg-surface)] p-3">
      <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)] mb-2 flex items-center gap-1.5">
        <BookMarked size={11} /> Wiki Concepts
      </p>
      <WikiConceptList projectId={projectId} openByConcept={openByConcept} onOpenWiki={onOpenWiki} />
    </aside>
  )
}

function WikiConceptList({ projectId, openByConcept, onOpenWiki }: {
  projectId: string
  openByConcept: Set<string>
  onOpenWiki: (slug?: string) => void
}) {
  const [concepts, setConcepts] = useState<Array<{ slug: string; title: string }> | null>(null)
  useEffect(() => {
    let alive = true
    api.projects.getWiki(projectId)
      .then(d => { if (alive) setConcepts(d.concepts) })
      .catch(() => { if (alive) setConcepts([]) })
    return () => { alive = false }
  }, [projectId])

  if (concepts === null) return <Skeleton className="h-24 rounded-lg" />
  if (concepts.length === 0) {
    return <p className="text-xs text-[var(--text-tertiary)] leading-relaxed">Upload documents to build the project wiki — concepts and contradictions will appear here.</p>
  }
  return (
    <div className="space-y-0.5">
      {concepts.map(c => (
        <button key={c.slug} onClick={() => onOpenWiki(c.slug)}
          className="w-full flex items-center gap-1.5 rounded-md px-2 py-1.5 text-left text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] transition-colors">
          <FileText size={12} className="shrink-0 text-[var(--text-tertiary)]" />
          <span className="flex-1 min-w-0 truncate">{c.title}</span>
          {openByConcept.has(c.slug) && <AlertTriangle size={11} className="shrink-0 text-[var(--status-warning)]" />}
        </button>
      ))}
      <button onClick={() => onOpenWiki()} className="mt-1 inline-flex items-center gap-0.5 text-[11px] text-[var(--accent)] hover:underline px-2">
        Open Project Wiki <ChevronRight size={11} />
      </button>
    </div>
  )
}

// ── Right: Clarification stream ───────────────────────────────────────────────

type Filter = 'all' | ClarificationKind | 'answered'

function ClarificationStream({ projectId, clarifications, busy, onAnswer, reduce }: {
  projectId: string
  clarifications: Clarification[]
  busy: boolean
  onAnswer: (id: string, answer: string) => void
  reduce: boolean
}) {
  const [filter, setFilter] = useState<Filter>('all')

  const counts = useMemo(() => {
    const c = { contradiction: 0, ambiguity: 0, gap: 0, answered: 0 }
    for (const x of clarifications) {
      if (x.resolved) c.answered++
      else if (x.kind) c[x.kind]++
    }
    return c
  }, [clarifications])

  const visible = useMemo(() => {
    const open = clarifications.filter(c => !c.resolved)
    const list = filter === 'all' ? open
      : filter === 'answered' ? clarifications.filter(c => c.resolved)
      : open.filter(c => c.kind === filter)
    return [...list].sort((a, b) => (SEVERITY_ORDER[a.severity] ?? 9) - (SEVERITY_ORDER[b.severity] ?? 9))
  }, [clarifications, filter])

  const chips: Array<[Filter, string, number]> = [
    ['all', 'All', clarifications.filter(c => !c.resolved).length],
    ['contradiction', '⚠', counts.contradiction],
    ['ambiguity', '❓', counts.ambiguity],
    ['gap', '◌', counts.gap],
    ['answered', '✓', counts.answered],
  ]

  return (
    <aside className="w-[360px] shrink-0 flex flex-col overflow-hidden border-l border-[var(--border-default)] bg-[var(--bg-surface)]">
      <div className="shrink-0 px-3 pt-3 pb-2 border-b border-[var(--border-subtle)]">
        <p className="text-[11px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)] mb-2">Clarifications</p>
        <div className="flex flex-wrap gap-1">
          {chips.map(([k, label, n]) => (
            <button key={k} onClick={() => setFilter(k)}
              className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium transition-colors ${
                filter === k ? 'bg-[var(--text-primary)] text-white' : 'bg-[var(--bg-elevated)] text-[var(--text-secondary)] hover:bg-[var(--bg-sunken)]'
              }`}>
              {label}<span className="opacity-70 tabular-nums">{n}</span>
            </button>
          ))}
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-2.5">
        {visible.length === 0 ? (
          <div className="flex flex-col items-center text-center gap-2 py-10 px-4">
            <CheckCircle2 size={28} className="text-[var(--accent)]" strokeWidth={1.5} />
            <p className="text-sm font-medium text-[var(--text-secondary)]">
              {filter === 'answered' ? 'No answered clarifications yet.' : 'No open clarifications — the corpus reads clean.'}
            </p>
            <p className="text-xs text-[var(--text-tertiary)]">Questions appear here when documents conflict, leave terms undefined, or omit needed detail.</p>
          </div>
        ) : visible.map(c => (
          <ClarificationCard key={c.id} projectId={projectId} c={c} busy={busy} onAnswer={onAnswer} reduce={reduce} />
        ))}
      </div>
    </aside>
  )
}

function ClarificationCard({ projectId, c, busy, onAnswer, reduce }: {
  projectId: string
  c: Clarification
  busy: boolean
  onAnswer: (id: string, answer: string) => void
  reduce: boolean
}) {
  const [open, setOpen] = useState(false)
  const [answer, setAnswer] = useState('')
  const meta = KIND_META[c.kind ?? 'gap']
  const Icon = meta.icon

  if (c.resolved) {
    return (
      <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-elevated)] px-3 py-2">
        <p className="text-xs text-[var(--text-secondary)] line-through decoration-[var(--text-tertiary)]">{c.question}</p>
        {c.resolution_text && <p className="mt-1 text-xs text-[var(--accent)]">→ {c.resolution_text}</p>}
      </div>
    )
  }

  return (
    <motion.div
      initial={reduce ? false : { opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.18 }}
      className="rounded-xl border bg-[var(--bg-surface)] overflow-hidden"
      style={{ borderColor: meta.border }}>
      <div className="px-3 py-2" style={{ background: meta.bg }}>
        <div className="flex items-center gap-1.5">
          <Icon size={12} style={{ color: meta.tint }} />
          <span className="text-[10px] font-bold uppercase tracking-wide" style={{ color: meta.tint }}>{meta.label}</span>
          <span className="text-[10px] font-medium text-[var(--text-tertiary)]">· {c.severity}</span>
        </div>
      </div>
      <div className="px-3 py-2.5">
        <p className="text-sm text-[var(--text-primary)] leading-snug">{linkifyCitations(c.question, projectId)}</p>
        {c.rationale && (
          <p className="mt-1.5 text-[11px] text-[var(--text-tertiary)] leading-relaxed">▸ {linkifyCitations(c.rationale, projectId)}</p>
        )}
        {c.citations.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {c.citations.map((tok, i) => (
              <IntakeTraceChip key={i} projectId={projectId} token={tok} />
            ))}
          </div>
        )}
        {!open ? (
          <button onClick={() => setOpen(true)}
            className="mt-2.5 inline-flex items-center gap-1 rounded-md bg-[var(--accent)] px-2.5 py-1 text-xs font-semibold text-white hover:bg-[var(--accent-hover)] transition-colors">
            Answer
          </button>
        ) : (
          <div className="mt-2.5">
            <textarea autoFocus value={answer} onChange={e => setAnswer(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey) && answer.trim()) onAnswer(c.id, answer.trim()) }}
              rows={2} placeholder="Resolve this… (⌘+Enter)"
              className="w-full resize-none rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent-ring)]" />
            <div className="mt-1.5 flex items-center gap-2">
              <Button onClick={() => answer.trim() && onAnswer(c.id, answer.trim())} disabled={busy || !answer.trim()} className="h-7 text-xs">
                <Send size={12} /> Save
              </Button>
              <button onClick={() => { setOpen(false); setAnswer('') }} className="text-xs text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]">
                <X size={13} className="inline" /> Cancel
              </button>
            </div>
          </div>
        )}
      </div>
    </motion.div>
  )
}

// ── Empty + seal ──────────────────────────────────────────────────────────────

function EmptyState({ busy, onGenerate }: { busy: boolean; onGenerate: () => void }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center text-center gap-4 p-8">
      <Sparkles size={40} className="text-[var(--accent)]" strokeWidth={1.4} />
      <div>
        <p className="text-base font-semibold text-[var(--text-primary)]">Build the Requirement Understanding</p>
        <p className="mt-1 text-sm text-[var(--text-secondary)] max-w-md">
          The system reads your brief, all uploaded documents, and the associated App Brain — then surfaces
          contradictions, ambiguities, and gaps as questions worth answering.
        </p>
      </div>
      <Button onClick={onGenerate} disabled={busy}><Sparkles size={15} /> Generate Understanding</Button>
    </div>
  )
}

function SealSummary({ ru, clarifications, onExplore, onContinue }: {
  ru: RequirementUnderstanding | null
  clarifications: Clarification[]
  onExplore: () => void
  onContinue: () => void
}) {
  const resolved = clarifications.filter(c => c.resolved).length
  const cites = Array.isArray((ru?.content_json as Record<string, unknown>)?.citations)
    ? ((ru!.content_json as Record<string, unknown>).citations as unknown[]).length : 0
  return (
    <div className="flex flex-1 flex-col items-center justify-center text-center gap-5 p-8">
      <motion.div initial={{ scale: 0.9 }} animate={{ scale: 1 }} transition={{ duration: 0.24 }}
        className="w-16 h-16 rounded-2xl bg-[var(--accent)] text-white flex items-center justify-center">
        <CheckCircle2 size={32} />
      </motion.div>
      <div>
        <p className="text-lg font-bold text-[var(--text-primary)]">Understanding Sealed</p>
        <p className="mt-1.5 text-sm text-[var(--text-secondary)] max-w-md leading-relaxed">
          SpecForge now understands this project — <strong>{resolved} clarification{resolved !== 1 ? 's' : ''} resolved</strong>
          {cites > 0 && <> · <strong>{cites} source{cites !== 1 ? 's' : ''} cited</strong></>}.
          This understanding now powers your Concept Brief, BRD, and FRS.
        </p>
      </div>
      <div className="flex items-center gap-2">
        <button onClick={onExplore}
          className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--accent)]/40 bg-white px-3 py-2 text-sm font-semibold text-[var(--accent)] hover:bg-[var(--accent-subtle)] transition-colors">
          <Layers size={14} /> Explore the Project Wiki
        </button>
        <button onClick={onContinue}
          className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-semibold text-white hover:bg-[var(--accent-hover)] transition-colors">
          Continue <ChevronRight size={14} />
        </button>
      </div>
    </div>
  )
}
