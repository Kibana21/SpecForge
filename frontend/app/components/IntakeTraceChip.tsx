'use client'
/**
 * IntakeTraceChip (E2 traceability) — turns a citation token into a clickable
 * chip that resolves to what it points at:
 *   • facts  — `F:<uuid>` (canonical), or positional `F117` / `F:117` / `F:F117`
 *   • `C:<concept_slug>`  → a Project Wiki concept (title + brief)
 *   • `S:<doc_id>:<node>` → a source section (document + page range + excerpt)
 *
 * Used wherever intake citations surface as pure text (clarification cards, RU
 * canvas, wiki prose). The popover is rendered in a portal with fixed
 * positioning so it floats above the surrounding overflow containers instead of
 * being clipped, and flips above the chip when there isn't room below.
 */
import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { FileText, Network, Database, Loader2, ExternalLink } from 'lucide-react'
import { api } from '@/lib/api'

type Resolved =
  | { kind: 'fact'; app: string; factKind: string; text: string; confidence: string; sourceRef: string | null }
  | { kind: 'concept'; title: string; brief: string }
  | { kind: 'section'; docName: string; title: string; pages: string; text: string }

type Meta = { label: string; Icon: typeof FileText; tint: string; bg: string }

const UUID_RE = /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/

function chipMeta(token: string): Meta | null {
  // Facts: canonical `F:<uuid>` or positional `F117` / `F:117` / `F:F117`.
  if (/^F[:\d]/.test(token)) return { label: 'app fact', Icon: Database, tint: 'var(--status-info)', bg: 'var(--status-info-bg)' }
  if (token.startsWith('C:')) return { label: token.slice(2), Icon: Network, tint: 'var(--accent)', bg: 'var(--accent-subtle)' }
  if (token.startsWith('S:')) return { label: 'source', Icon: FileText, tint: 'var(--text-secondary)', bg: 'var(--bg-elevated)' }
  return null
}

async function resolve(projectId: string, token: string): Promise<Resolved> {
  if (token.startsWith('C:')) {
    const c = await api.projects.getWikiConcept(projectId, token.slice(2))
    return { kind: 'concept', title: c.title, brief: c.brief }
  }
  if (token.startsWith('S:')) {
    const rest = token.slice(2)
    const sep = rest.indexOf(':')
    const s = await api.projects.getSourceSection(projectId, rest.slice(0, sep), rest.slice(sep + 1))
    return { kind: 'section', docName: s.doc_name, title: s.title, pages: s.pages, text: s.text }
  }
  // Fact tokens: F117 (prose), F:117 / F:F117 (structured positional), F:<uuid> (canonical).
  const payload = token.startsWith('F:') ? token.slice(2) : token.startsWith('F') ? token.slice(1) : null
  if (payload !== null) {
    const f = UUID_RE.test(payload)
      ? await api.projects.resolveFact(projectId, payload)
      : await api.projects.resolveFactByIndex(projectId, parseInt((payload.match(/\d+/) ?? ['0'])[0], 10))
    return { kind: 'fact', app: f.app, factKind: f.kind, text: f.text, confidence: f.confidence, sourceRef: f.source_ref }
  }
  throw new Error('unknown token')
}

export function IntakeTraceChip({ projectId, token, inline = false, labelOverride }: {
  projectId: string
  token: string
  inline?: boolean
  /** Show this text on the chip instead of the resolved kind label — used when
   *  linkifying prose so "Fact F117" keeps reading as "Fact F117". */
  labelOverride?: string
}) {
  const [open, setOpen] = useState(false)
  const [data, setData] = useState<Resolved | null>(null)
  const [loading, setLoading] = useState(false)
  const [failed, setFailed] = useState(false)
  const [pos, setPos] = useState<{ left: number; top: number; flip: boolean } | null>(null)
  const btnRef = useRef<HTMLButtonElement>(null)

  const POP_W = 288
  const POP_MAXH = 240

  function place() {
    const el = btnRef.current
    if (!el) return
    const r = el.getBoundingClientRect()
    const spaceBelow = window.innerHeight - r.bottom
    const flip = spaceBelow < POP_MAXH + 16 && r.top > spaceBelow
    const left = Math.max(8, Math.min(r.left, window.innerWidth - POP_W - 8))
    const top = flip ? r.top - 6 : r.bottom + 6
    setPos({ left, top, flip })
  }

  useEffect(() => {
    if (!open) return
    place()
    const onScroll = () => place()
    window.addEventListener('scroll', onScroll, true)
    window.addEventListener('resize', onScroll)
    return () => {
      window.removeEventListener('scroll', onScroll, true)
      window.removeEventListener('resize', onScroll)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  const meta = chipMeta(token)
  if (!meta) {
    return (
      <span className="rounded-full border border-[var(--border-default)] bg-[var(--bg-elevated)] px-1.5 py-0.5 text-[10px] text-[var(--text-secondary)]">
        {token}
      </span>
    )
  }
  const { Icon } = meta

  function toggle() {
    if (open) { setOpen(false); return }
    setOpen(true)
    if (data || failed) return
    setLoading(true)
    resolve(projectId, token)
      .then(setData)
      .catch(() => setFailed(true))
      .finally(() => setLoading(false))
  }

  const popover = open && typeof document !== 'undefined' ? createPortal(
    <>
      {/* click-away backdrop */}
      <div className="fixed inset-0 z-[60]" onClick={() => setOpen(false)} />
      <div
        role="tooltip"
        className="fixed z-[61] w-72 rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] p-2.5 text-left shadow-[var(--shadow-lg)]"
        style={pos
          ? { left: pos.left, top: pos.top, maxHeight: POP_MAXH, overflowY: 'auto', transform: pos.flip ? 'translateY(-100%)' : undefined }
          : { left: -9999, top: -9999 }}
        onClick={e => e.stopPropagation()}
      >
        {loading ? (
          <span className="flex items-center gap-2 text-[11px] text-[var(--text-tertiary)]">
            <Loader2 size={12} className="animate-spin" /> Resolving…
          </span>
        ) : failed || !data ? (
          <span className="block text-[11px] text-[var(--text-tertiary)]">Couldn&apos;t resolve this citation.</span>
        ) : data.kind === 'fact' ? (
          <>
            <span className="mb-1 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide text-[var(--status-info)]">
              <Database size={11} /> {data.app} · {data.factKind} · {data.confidence}
            </span>
            <span className="block text-xs leading-relaxed text-[var(--text-primary)]">{data.text}</span>
            {data.sourceRef && (
              <span className="mt-1.5 flex items-center gap-1 text-[10px] text-[var(--text-tertiary)]">
                <ExternalLink size={10} /> {data.sourceRef}
              </span>
            )}
          </>
        ) : data.kind === 'concept' ? (
          <>
            <span className="mb-1 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide text-[var(--accent)]">
              <Network size={11} /> Wiki concept
            </span>
            <span className="block text-xs font-semibold text-[var(--text-primary)]">{data.title}</span>
            {data.brief && <span className="mt-0.5 block text-[11px] leading-relaxed text-[var(--text-secondary)]">{data.brief}</span>}
          </>
        ) : (
          <>
            <span className="mb-1 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide text-[var(--text-secondary)]">
              <FileText size={11} /> {data.docName}{data.pages ? ` · pp ${data.pages}` : ''}
            </span>
            {data.title && <span className="block text-xs font-semibold text-[var(--text-primary)]">{data.title}</span>}
            <span className="mt-0.5 block text-[11px] leading-relaxed text-[var(--text-secondary)] whitespace-pre-wrap">{data.text}</span>
          </>
        )}
      </div>
    </>,
    document.body,
  ) : null

  return (
    <span className={inline ? 'inline-block align-baseline' : 'inline-block'}>
      <button
        ref={btnRef}
        type="button"
        onClick={toggle}
        title="Click to trace this citation"
        className={`inline-flex items-center gap-1 rounded-full border px-1.5 py-0.5 text-[10px] font-medium transition-colors ${
          open ? 'text-white' : 'text-[var(--text-secondary)] hover:border-current'
        }`}
        style={open
          ? { background: meta.tint, borderColor: meta.tint }
          : { background: meta.bg, borderColor: 'var(--border-default)', color: meta.tint }}
      >
        <Icon size={10} />
        <span className="max-w-[160px] truncate">{labelOverride ?? meta.label}</span>
      </button>
      {popover}
    </span>
  )
}
