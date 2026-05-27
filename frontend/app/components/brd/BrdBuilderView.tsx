'use client'
import { useState, useRef, useEffect, useCallback } from 'react'
import useSWR from 'swr'
import {
  ArrowLeft, CheckCircle2, Download, AlertTriangle, Send, Sparkles,
  Loader2, ChevronDown, ChevronUp, RotateCcw,
} from 'lucide-react'
import { toast } from 'sonner'

import { api } from '@/lib/api'
import { useProject } from '@/lib/hooks/useProject'
import { useBrdReadiness } from '@/lib/hooks/useBrdReadiness'
import { BRD_SECTIONS } from '@/lib/brd-manifest'

import { SectionRail } from '@/app/components/brd/SectionRail'
import { BrCard } from '@/app/components/brd/BrCard'
import { BrdEmptyState } from '@/app/components/brd/BrdEmptyState'
import { UnitDagViz } from '@/app/components/brd/UnitDagViz'
import { FindingsDrawer } from '@/app/components/brd/FindingsDrawer'
import { SourceStrip } from '@/app/components/brd/SourceStrip'
import { CbEchoStrip } from '@/app/components/brd/CbEchoStrip'
import { BrdConfettiBurst } from '@/app/components/brd/BrdConfettiBurst'
import { EditableRows } from '@/app/components/brd/EditableRows'
import { SectionQuestions } from '@/app/components/brd/SectionQuestions'
import { Skeleton } from '@/app/components/Skeleton'

import type {
  BrdDetail, BrdFinding, BrdBusinessRequirementRow, BrdObjectiveRow,
  BrdRiskRow, BrdKpiRow, BrdTraceabilityRow, BrdTextBlockRow,
} from '@/lib/types'

// ── local row types ────────────────────────────────────────────────────────────

type BrdStakeholderRow = {
  id: string; row_key: string; name: string; stakeholder_type: string
  role: string; interest: string; influence: string; status: string; is_current: boolean
}
type BrdActorRow = {
  id: string; row_key: string; name: string; actor_type: string
  description: string; interactions: string; status: string; is_current: boolean
}
type BrdScopeItemRow = {
  id: string; row_key: string; kind: 'in_scope' | 'out_of_scope' | 'assumption'
  text: string; rationale: string; cb_scope_ref: string; status: string; is_current: boolean
}
type BrdProcessStepRow = {
  id: string; row_key: string; step_type: 'asis' | 'tobe'
  step_number: number; actor: string; action: string
  pain_point: string; improvement: string; status: string; is_current: boolean
}

// ── helpers ────────────────────────────────────────────────────────────────────

function getRows<T>(sections: Record<string, unknown[]>, table: string): T[] {
  return (sections[table] ?? []) as T[]
}
function getActiveRows<T>(rows: T[]): T[] {
  return rows.filter((r) => {
    const rec = r as Record<string, unknown>
    return rec['status'] === 'active' && rec['is_current'] !== false
  })
}
function getTraces(
  traceability: Record<string, BrdTraceabilityRow[]>,
  _table: string,
  rowKey: string,
): BrdTraceabilityRow[] {
  return traceability[rowKey] ?? []
}

const SCOPE_KIND_STYLES = {
  in_scope:     'bg-[var(--status-success-bg)] text-[var(--status-success)] border-[var(--status-success-border)]',
  out_of_scope: 'bg-[var(--status-danger-bg)] text-[var(--status-danger)] border-[var(--status-danger-border)]',
  assumption:   'bg-[var(--status-info-bg)] text-[var(--status-info)] border-[var(--status-info-border)]',
} as const

// ── Coverage modal ─────────────────────────────────────────────────────────────

function CoverageModal({ projectId, onClose }: { projectId: string; onClose: () => void }) {
  const [loading, setLoading] = useState(true)
  const [coverage, setCoverage] = useState<{
    covered_count: number; total_count: number; all_covered: boolean; uncovered_keys: string[]
  } | null>(null)

  useEffect(() => {
    api.brd.coverage(projectId)
      .then(setCoverage)
      .catch(() => toast.error('Failed to load coverage'))
      .finally(() => setLoading(false))
  }, [projectId])

  const pct = coverage ? Math.round((coverage.covered_count / coverage.total_count) * 100) : 0

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div
        className="w-full max-w-md bg-[var(--bg-surface)] rounded-2xl shadow-2xl border border-[var(--border-default)] overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-5 pt-5 pb-4 border-b border-[var(--border-subtle)]">
          <p className="text-xs font-semibold uppercase tracking-widest text-[var(--text-tertiary)] mb-0.5">BRD Coverage</p>
          <h3 className="text-base font-semibold text-[var(--text-primary)]">Requirement Traceability</h3>
        </div>
        <div className="px-5 py-5">
          {loading ? (
            <Skeleton className="h-24 rounded-xl" />
          ) : coverage ? (
            <div className="space-y-4">
              <div className="flex items-center gap-4">
                <div className="flex-1 h-2 rounded-full bg-[var(--bg-sunken)]">
                  <div
                    className="h-2 rounded-full bg-[var(--accent)] transition-[width] duration-500"
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <span className={`text-sm font-bold ${pct >= 90 ? 'text-[var(--status-success)]' : pct >= 60 ? 'text-[var(--status-warning)]' : 'text-[var(--status-danger)]'}`}>
                  {pct}%
                </span>
              </div>
              <p className="text-xs text-[var(--text-secondary)]">
                {coverage.covered_count} of {coverage.total_count} requirements traced to source.
              </p>
              {coverage.uncovered_keys.length > 0 && (
                <div>
                  <p className="text-[11px] font-semibold text-[var(--text-tertiary)] uppercase tracking-wide mb-2">
                    Uncovered ({coverage.uncovered_keys.length})
                  </p>
                  <div className="flex flex-wrap gap-1.5 max-h-32 overflow-y-auto">
                    {coverage.uncovered_keys.map((k) => (
                      <span key={k} className="rounded border border-[var(--status-danger-border)] bg-[var(--status-danger-bg)] px-2 py-0.5 font-mono text-[10px] text-[var(--status-danger)]">
                        {k}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {coverage.all_covered && (
                <div className="flex items-center gap-2 rounded-xl border border-[var(--status-success-border)] bg-[var(--status-success-bg)] px-3 py-2.5">
                  <CheckCircle2 size={15} className="text-[var(--status-success)] shrink-0" />
                  <p className="text-xs font-semibold text-[var(--status-success)]">Full coverage — all requirements traced</p>
                </div>
              )}
            </div>
          ) : (
            <p className="text-sm text-[var(--text-tertiary)]">No coverage data available.</p>
          )}
        </div>
        <div className="px-5 pb-5 flex justify-end">
          <button onClick={onClose} className="rounded-xl border border-[var(--border-default)] bg-[var(--bg-elevated)] px-4 py-2 text-sm font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-sunken)] transition-colors">
            Close
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Thread Q&A panel ───────────────────────────────────────────────────────────

function ThreadPanel({
  messages, answer, busy, validated, onAnswerChange, onAnswerSubmit,
}: {
  messages: BrdDetail['messages']
  answer: string
  busy: boolean
  validated: boolean
  onAnswerChange: (v: string) => void
  onAnswerSubmit: () => void
}) {
  const threadEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    threadEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages.length])

  const questions = messages.filter((m) => m.role === 'question')
  const lastAnswerSeq = messages.filter((m) => m.role === 'user').at(-1)?.seq ?? -1
  const openQuestions = questions.filter((m) => m.seq > lastAnswerSeq)
  const activeQ = openQuestions.at(-1) ?? null

  return (
    <div className="flex flex-col h-full border-r border-[var(--border-default)] bg-[var(--bg-base)]">
      <div className="shrink-0 px-4 py-3 border-b border-[var(--border-subtle)] bg-[var(--bg-surface)]">
        <p className="text-xs font-semibold text-[var(--text-primary)]">Clarification Q&A</p>
        <p className="text-[10px] text-[var(--text-tertiary)] mt-0.5">
          {openQuestions.length > 0 ? `${openQuestions.length} open question${openQuestions.length !== 1 ? 's' : ''}` : 'No open questions'}
        </p>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {messages.length === 0 && (
          <div className="flex flex-col items-center gap-2 py-8 text-center px-4">
            <div className="w-9 h-9 rounded-xl bg-[var(--bg-elevated)] border border-[var(--border-default)] flex items-center justify-center">
              <Sparkles size={16} className="text-[var(--text-tertiary)]" />
            </div>
            <p className="text-xs text-[var(--text-tertiary)]">Questions will appear here as SpecForge discovers gaps.</p>
          </div>
        )}
        {messages.map((m) => {
          if (m.role === 'user') return (
            <div key={m.id} className="flex justify-end">
              <div className="max-w-[82%] rounded-2xl rounded-br-sm bg-[var(--accent)] px-3 py-2 text-sm text-white">{m.content}</div>
            </div>
          )
          if (m.role === 'question') {
            const isOpen = m.seq > lastAnswerSeq
            return (
              <div key={m.id} className="flex justify-start">
                <div className={`max-w-[88%] rounded-2xl rounded-bl-sm px-3 py-2 text-sm ${isOpen ? 'bg-[var(--accent-subtle)] text-[var(--accent-deep)] border border-[var(--accent)]/20' : 'bg-[var(--bg-surface)] text-[var(--text-secondary)] border border-[var(--border-default)] opacity-60'}`}>
                  <span className="mr-1 font-semibold text-[10px] uppercase tracking-wide">Q</span>
                  {m.content}
                  {!!m.meta?.why && <p className="mt-1 text-[10px] italic opacity-70">{String(m.meta.why)}</p>}
                </div>
              </div>
            )
          }
          if (m.role === 'synthesis') return (
            <div key={m.id} className="flex justify-start">
              <div className="max-w-[88%] rounded-2xl rounded-bl-sm bg-[var(--bg-surface)] border border-[var(--border-default)] px-3 py-2 text-sm text-[var(--text-secondary)]">
                <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-[var(--accent)] mb-1"><Sparkles size={9} /> AI synthesis</span>
                <p>{m.content}</p>
              </div>
            </div>
          )
          return null
        })}
        <div ref={threadEndRef} />
      </div>

      {activeQ && !validated && (
        <div className="shrink-0 mx-3 mb-2 rounded-xl border border-amber-200 bg-amber-50/80 px-3 py-2.5">
          <p className="text-xs font-semibold text-amber-800 mb-0.5">Current question</p>
          <p className="text-xs text-amber-700 leading-snug">{activeQ.content}</p>
        </div>
      )}

      {!validated && (
        <div className="shrink-0 border-t border-[var(--border-default)] px-3 py-3 bg-[var(--bg-surface)]">
          <textarea
            value={answer}
            onChange={(e) => onAnswerChange(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) onAnswerSubmit() }}
            rows={2}
            placeholder="Type your answer… (⌘+Enter to send)"
            disabled={busy || !activeQ}
            className="w-full resize-none rounded-lg border border-[var(--border-default)] bg-[var(--bg-elevated)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-ring)] disabled:opacity-50"
          />
          <div className="flex justify-end mt-2">
            <button
              onClick={onAnswerSubmit}
              disabled={busy || !answer.trim() || !activeQ}
              className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-1.5 text-xs font-semibold text-white hover:bg-[var(--accent-hover)] disabled:opacity-50 transition-colors"
            >
              {busy ? <><Loader2 size={12} className="animate-spin" /> Refining…</> : <><Send size={12} /> Submit</>}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Section helpers ────────────────────────────────────────────────────────────

function EditableProseBlock({
  label, fieldKey, text, projectId, rowId, onMutate,
}: {
  label: string; fieldKey: string; text: string
  projectId: string; rowId: string | null; onMutate: () => void
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(text)
  const [saving, setSaving] = useState(false)

  async function handleSave() {
    if (!rowId) return
    setSaving(true)
    try {
      await api.brd.editRow(projectId, 'brd_text_blocks', rowId, { field_key: fieldKey, text: draft }, false)
      toast.success('Saved')
      setEditing(false)
      onMutate()
    } catch {
      toast.error('Save failed')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-1 group">
      <div className="flex items-center gap-2">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)]">{label}</p>
        {!editing && rowId && (
          <button
            onClick={() => { setDraft(text); setEditing(true) }}
            className="opacity-0 group-hover:opacity-100 transition-opacity p-0.5 rounded text-[var(--text-tertiary)] hover:text-[var(--accent)]"
            title="Edit"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
          </button>
        )}
      </div>
      {editing ? (
        <div className="space-y-2">
          <textarea
            rows={6}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            className="w-full resize-none rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] px-3 py-2 text-sm text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-ring)]"
          />
          <div className="flex items-center gap-2">
            <button
              onClick={handleSave}
              disabled={saving}
              className="inline-flex items-center gap-1 rounded-lg bg-[var(--accent)] px-3 py-1.5 text-xs font-semibold text-white hover:bg-[var(--accent-hover)] disabled:opacity-50 transition-colors"
            >
              {saving ? '…' : 'Save'}
            </button>
            <button
              onClick={() => setEditing(false)}
              className="inline-flex items-center gap-1 rounded-lg border border-[var(--border-default)] bg-[var(--bg-elevated)] px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-sunken)] transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <p className="text-sm text-[var(--text-primary)] leading-relaxed whitespace-pre-wrap">
          {text || <span className="text-[var(--text-tertiary)] italic">Not yet generated</span>}
        </p>
      )}
    </div>
  )
}

function SectionPanel({
  sectionNum, title, emoji, unitStatus, children, id,
}: {
  sectionNum: number; title: string; emoji: string
  unitStatus?: { completeness: number; confidence: string }
  children: React.ReactNode; id?: string
}) {
  const [open, setOpen] = useState(true)
  return (
    <div id={id} className="border-b border-[var(--border-subtle)]">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-3 px-4 py-3 bg-[var(--bg-elevated)] hover:bg-[var(--bg-sunken)] transition-colors text-left"
      >
        <span className="text-[10px] font-bold text-[var(--text-tertiary)] w-5 shrink-0">{sectionNum}</span>
        <span className="text-base leading-none">{emoji}</span>
        <span className="flex-1 text-sm font-semibold text-[var(--text-primary)]">{title}</span>
        {unitStatus && (
          <span className={`text-[10px] font-semibold shrink-0 ${unitStatus.completeness >= 90 ? 'text-[var(--status-success)]' : unitStatus.completeness >= 60 ? 'text-[var(--status-warning)]' : 'text-[var(--status-danger)]'}`}>
            {unitStatus.completeness}%
          </span>
        )}
        {open ? <ChevronUp size={14} className="text-[var(--text-tertiary)] shrink-0" /> : <ChevronDown size={14} className="text-[var(--text-tertiary)] shrink-0" />}
      </button>
      {open && <div className="px-4 pb-5 pt-3 space-y-3">{children}</div>}
    </div>
  )
}

// ── Main component ─────────────────────────────────────────────────────────────

export interface BrdBuilderViewProps {
  projectId: string
  onBack: () => void
}

export function BrdBuilderView({ projectId, onBack }: BrdBuilderViewProps) {
  const { project } = useProject(projectId)
  const { readiness, isLoading: readinessLoading } = useBrdReadiness(projectId)

  const { data: detail, isLoading, mutate } = useSWR<BrdDetail>(
    `brd-detail-${projectId}`,
    () => api.brd.get(projectId),
    {
      revalidateOnFocus: false,
      refreshInterval: (data) => {
        const status = data?.document?.status
        if (status === 'generating') return 2000
        if (data?.document?.unit_status?.['_current_unit']) return 2000
        return 0
      },
    },
  )

  const [answer, setAnswer] = useState('')
  const [busy, setBusy] = useState(false)
  const [activeSection, setActiveSection] = useState(1)
  const [showFindingsDrawer, setShowFindingsDrawer] = useState(false)
  const [findings, setFindings] = useState<BrdFinding[]>([])
  const [showCoverageModal, setShowCoverageModal] = useState(false)
  const [confettiActive, setConfettiActive] = useState(false)

  const doc = detail?.document ?? null
  const sections = detail?.sections ?? {}
  const traceability = detail?.traceability_by_source ?? {}
  const messages = detail?.messages ?? []
  const unitStatus = doc?.unit_status ?? {}

  const status = doc?.status ?? null
  const validated = status === 'validated'
  const generating = status === 'generating'

  const currentUnit = (unitStatus as Record<string, unknown>)['_current_unit'] as string | null ?? null

  const [resettingStall, setResettingStall] = useState(false)

  async function handleResetStall() {
    setResettingStall(true)
    try {
      await api.brd.resetGenerating(projectId)
      await mutate()
      toast.success('Generation reset — you can regenerate individual sections')
    } catch {
      toast.error('Reset failed')
    } finally {
      setResettingStall(false)
    }
  }

  const prevValidated = useRef(false)
  useEffect(() => {
    if (validated && !prevValidated.current) {
      setConfettiActive(true)
      setTimeout(() => setConfettiActive(false), 800)
    }
    prevValidated.current = validated
  }, [validated])

  async function run<T>(fn: () => Promise<T>, okMsg: string): Promise<T | undefined> {
    setBusy(true)
    try {
      const r = await fn()
      await mutate()
      toast.success(okMsg)
      return r
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed')
    } finally {
      setBusy(false)
    }
  }

  async function handleStart(context?: string) {
    await run(() => api.brd.generate(projectId, { context }), 'BRD generation started')
  }

  async function handleRegenerate() {
    await run(() => api.brd.generate(projectId, {}), 'BRD regeneration started')
  }

  async function handleAnswer() {
    if (!answer.trim() || busy) return
    const a = answer.trim()
    setAnswer('')
    setBusy(true)
    try {
      const updated = await api.brd.answer(projectId, { answer: a })
      await mutate(updated as BrdDetail, { revalidate: false })
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to submit answer')
    } finally {
      setBusy(false)
    }
  }

  // Step 1 — read-only check: runs validation rules, shows findings, no state change
  async function handleCheckFindings() {
    setBusy(true)
    try {
      const result = await api.brd.findings(projectId)
      setFindings(result.findings)
      setShowFindingsDrawer(true)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Could not load findings')
    } finally {
      setBusy(false)
    }
  }

  // Step 2 — called from inside the drawer after user reviews findings and clicks "Validate BRD"
  async function handleApprove() {
    setBusy(true)
    try {
      const result = await api.brd.validate(projectId)
      setFindings(result.findings)
      await mutate()
      if (result.ok) {
        setShowFindingsDrawer(false)
        toast.success('BRD validated ✓')
      } else {
        toast.error('Validation blocked — review findings')
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Validation failed')
    } finally {
      setBusy(false)
    }
  }

  async function handleExport() {
    try {
      const res = await api.brd.export(projectId)
      if (!res.ok) throw new Error('Export failed')
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      const cd = res.headers.get('content-disposition')
      a.download = cd?.match(/filename="([^"]+)"/)?.[1] ?? 'brd.md'
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch {
      toast.error('Export failed — try again')
    }
  }

  const handleSectionClick = useCallback((num: number) => {
    setActiveSection(num)
    const el = document.getElementById(`brd-section-${num}`)
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [])

  function renderSections() {
    const s = sections
    const textBlocks = getActiveRows(getRows<BrdTextBlockRow>(s, 'brd_text_blocks'))
    const getTextBlock = (fieldKey: string) => textBlocks.find((r) => r.field_key === fieldKey) ?? null
    const objectives = getActiveRows(getRows<BrdObjectiveRow>(s, 'brd_objectives'))
    const businessReqs = getActiveRows(getRows<BrdBusinessRequirementRow>(s, 'brd_business_requirements'))
    const risks = getActiveRows(getRows<BrdRiskRow>(s, 'brd_risks'))
    const kpis = getActiveRows(getRows<BrdKpiRow>(s, 'brd_kpis'))
    const processSteps = getActiveRows(getRows<BrdProcessStepRow>(s, 'brd_process_steps'))
    const asisSteps = processSteps.filter((p) => p.step_type === 'asis')
    const tobeSteps = processSteps.filter((p) => p.step_type === 'tobe')
    const scopeItems = getActiveRows(getRows<BrdScopeItemRow>(s, 'brd_scope_items'))

    const sectionQ = (unitKey: string) => validated ? null : (
      <SectionQuestions
        unitKey={unitKey}
        messages={messages as { id: string; role: string; content: string; meta: Record<string, unknown>; seq: number }[]}
        projectId={projectId}
        onAnswered={() => mutate()}
        onRegenerateUnit={(key) => {
          api.brd.regenerateUnit(projectId, key)
            .then(() => { toast.success('Section regeneration started'); mutate() })
            .catch(() => toast.error('Regeneration failed'))
        }}
      />
    )

    return BRD_SECTIONS.map((section) => {
      const us = unitStatus[section.unit_key] as { completeness: number; confidence: string } | undefined
      return (
        <SectionPanel key={section.num} sectionNum={section.num} title={section.title} emoji={section.emoji} unitStatus={us} id={`brd-section-${section.num}`}>

          {section.num === 1 && (() => {
            const blk = getTextBlock('business_context')
            return <EditableProseBlock label="Business Context" fieldKey="business_context" text={blk?.text ?? ''} projectId={projectId} rowId={blk?.id ?? null} onMutate={() => mutate()} />
          })()}
          {section.num === 2 && (() => {
            const blk = getTextBlock('problem_statement')
            return <EditableProseBlock label="Problem Statement" fieldKey="problem_statement" text={blk?.text ?? ''} projectId={projectId} rowId={blk?.id ?? null} onMutate={() => mutate()} />
          })()}
          {section.num === 3 && (
            objectives.length === 0
              ? <p className="text-sm text-[var(--text-tertiary)] italic">No objectives generated yet.</p>
              : <div className="grid gap-3">{objectives.map((obj) => <BrCard key={obj.id} variant="objective" row={obj} traces={getTraces(traceability, 'brd_objectives', obj.row_key)} projectId={projectId} onMutate={() => mutate()} />)}</div>
          )}
          {section.num === 4 && (
            <div className="space-y-4">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)] mb-2">Stakeholders</p>
                <EditableRows
                  rows={getRows<Record<string, unknown>>(s, 'brd_stakeholders')}
                  table="brd_stakeholders"
                  projectId={projectId}
                  onMutate={() => mutate()}
                  columns={[
                    { key: 'name', label: 'Name', primary: true },
                    { key: 'stakeholder_type', label: 'Type', type: 'select', options: ['internal', 'external', 'regulator', 'vendor', 'other'] },
                    { key: 'role', label: 'Role' },
                    { key: 'interest', label: 'Interest' },
                    { key: 'influence', label: 'Influence', type: 'select', options: ['high', 'medium', 'low'] },
                  ]}
                  emptyText="No stakeholders generated yet."
                />
              </div>
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)] mb-2">Actors</p>
                <EditableRows
                  rows={getRows<Record<string, unknown>>(s, 'brd_actors')}
                  table="brd_actors"
                  projectId={projectId}
                  onMutate={() => mutate()}
                  columns={[
                    { key: 'name', label: 'Name', primary: true },
                    { key: 'actor_type', label: 'Type', type: 'select', options: ['human', 'system', 'external', 'other'] },
                    { key: 'description', label: 'Description', type: 'textarea' },
                    { key: 'interactions', label: 'Interactions', type: 'textarea' },
                  ]}
                  emptyText="No actors generated yet."
                />
              </div>
            </div>
          )}
          {section.num === 5 && (
            <div className="space-y-3">
              {(['in_scope', 'out_of_scope', 'assumption'] as const).map((kind) => {
                const kindRows = getRows<Record<string, unknown>>(s, 'brd_scope_items').filter((r) => r.kind === kind)
                return (
                  <div key={kind}>
                    <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)] mb-2">
                      {kind.replace(/_/g, ' ')}
                    </p>
                    <EditableRows
                      rows={kindRows}
                      table="brd_scope_items"
                      projectId={projectId}
                      onMutate={() => mutate()}
                      columns={[
                        { key: 'text', label: 'Description', primary: true, type: 'textarea' },
                        { key: 'rationale', label: 'Rationale', type: 'textarea' },
                        { key: 'cb_scope_ref', label: 'CB ref' },
                      ]}
                      emptyText={`No ${kind.replace(/_/g, ' ')} items yet.`}
                    />
                  </div>
                )
              })}
            </div>
          )}
          {section.num === 6 && (
            <div className="space-y-4">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)] mb-2">As-Is Process</p>
                <EditableRows
                  rows={asisSteps as unknown as Record<string, unknown>[]}
                  table="brd_process_steps"
                  projectId={projectId}
                  onMutate={() => mutate()}
                  showIndex
                  sortBy="step_number"
                  columns={[
                    { key: 'action', label: 'Action', primary: true, type: 'textarea' },
                    { key: 'actor', label: 'Actor' },
                    { key: 'pain_point', label: 'Pain point', type: 'textarea' },
                  ]}
                  emptyText="No as-is process steps yet."
                />
              </div>
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)] mb-2">To-Be Process</p>
                <EditableRows
                  rows={tobeSteps as unknown as Record<string, unknown>[]}
                  table="brd_process_steps"
                  projectId={projectId}
                  onMutate={() => mutate()}
                  showIndex
                  sortBy="step_number"
                  columns={[
                    { key: 'action', label: 'Action', primary: true, type: 'textarea' },
                    { key: 'actor', label: 'Actor' },
                    { key: 'improvement', label: 'Improvement', type: 'textarea' },
                  ]}
                  emptyText="No to-be process steps yet."
                />
              </div>
            </div>
          )}
          {section.num === 7 && (
            businessReqs.length === 0
              ? <p className="text-sm text-[var(--text-tertiary)] italic">No business requirements generated yet.</p>
              : <div className="grid gap-3">{businessReqs.map((br) => <BrCard key={br.id} variant="br" row={br} traces={getTraces(traceability, 'brd_business_requirements', br.row_key)} projectId={projectId} onMutate={() => mutate()} />)}</div>
          )}
          {section.num === 8 && (
            <div className="space-y-4">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)] mb-2">Data Entities</p>
                <EditableRows
                  rows={getRows<Record<string, unknown>>(s, 'brd_data_entities')}
                  table="brd_data_entities"
                  projectId={projectId}
                  onMutate={() => mutate()}
                  columns={[
                    { key: 'entity_name', label: 'Entity', primary: true },
                    { key: 'description', label: 'Description', type: 'textarea' },
                    { key: 'owner_system', label: 'Owner system' },
                    { key: 'data_sensitivity', label: 'Sensitivity', type: 'select', options: ['public', 'internal', 'confidential', 'restricted'] },
                  ]}
                  emptyText="No data entities generated yet."
                />
              </div>
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)] mb-2">Report Requirements</p>
                <EditableRows
                  rows={getRows<Record<string, unknown>>(s, 'brd_report_requirements')}
                  table="brd_report_requirements"
                  projectId={projectId}
                  onMutate={() => mutate()}
                  columns={[
                    { key: 'report_name', label: 'Report name', primary: true },
                    { key: 'description', label: 'Description', type: 'textarea' },
                    { key: 'frequency', label: 'Frequency' },
                    { key: 'audience', label: 'Audience' },
                  ]}
                  emptyText="No report requirements generated yet."
                />
              </div>
            </div>
          )}
          {section.num === 9 && (
            <div className="space-y-4">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)] mb-2">Assumptions</p>
                <EditableRows
                  rows={getRows<Record<string, unknown>>(s, 'brd_assumptions')}
                  table="brd_assumptions"
                  projectId={projectId}
                  onMutate={() => mutate()}
                  columns={[
                    { key: 'assumption', label: 'Assumption', primary: true, type: 'textarea' },
                    { key: 'impact_if_wrong', label: 'Impact if wrong', type: 'textarea' },
                    { key: 'owner', label: 'Owner' },
                  ]}
                  emptyText="No assumptions generated yet."
                />
              </div>
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)] mb-2">Constraints</p>
                <EditableRows
                  rows={getRows<Record<string, unknown>>(s, 'brd_constraints')}
                  table="brd_constraints"
                  projectId={projectId}
                  onMutate={() => mutate()}
                  columns={[
                    { key: 'constraint_text', label: 'Constraint', primary: true, type: 'textarea' },
                    { key: 'constraint_type', label: 'Type' },
                    { key: 'source_ref', label: 'Source' },
                  ]}
                  emptyText="No constraints generated yet."
                />
              </div>
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)] mb-2">Dependencies</p>
                <EditableRows
                  rows={getRows<Record<string, unknown>>(s, 'brd_dependencies')}
                  table="brd_dependencies"
                  projectId={projectId}
                  onMutate={() => mutate()}
                  columns={[
                    { key: 'dependency', label: 'Dependency', primary: true, type: 'textarea' },
                    { key: 'dependency_type', label: 'Type' },
                    { key: 'owner', label: 'Owner' },
                    { key: 'due_date', label: 'Due date' },
                  ]}
                  emptyText="No dependencies generated yet."
                />
              </div>
            </div>
          )}
          {section.num === 10 && (
            risks.length === 0
              ? <p className="text-sm text-[var(--text-tertiary)] italic">No risks generated yet.</p>
              : <div className="grid gap-3">{risks.map((risk) => <BrCard key={risk.id} variant="risk" row={risk} traces={getTraces(traceability, 'brd_risks', risk.row_key)} projectId={projectId} onMutate={() => mutate()} />)}</div>
          )}
          {section.num === 11 && (
            <div className="space-y-4">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)] mb-2">Phases</p>
                <EditableRows
                  rows={getRows<Record<string, unknown>>(s, 'brd_phases')}
                  table="brd_phases"
                  projectId={projectId}
                  onMutate={() => mutate()}
                  columns={[
                    { key: 'phase_name', label: 'Phase', primary: true },
                    { key: 'description', label: 'Description', type: 'textarea' },
                    { key: 'target_date', label: 'Target date' },
                  ]}
                  emptyText="No implementation phases yet."
                />
              </div>
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)] mb-2">Milestones</p>
                <EditableRows
                  rows={getRows<Record<string, unknown>>(s, 'brd_milestones')}
                  table="brd_milestones"
                  projectId={projectId}
                  onMutate={() => mutate()}
                  columns={[
                    { key: 'milestone', label: 'Milestone', primary: true },
                    { key: 'target', label: 'Target' },
                    { key: 'description', label: 'Description', type: 'textarea' },
                    { key: 'phase_ref', label: 'Phase ref' },
                  ]}
                  emptyText="No milestones yet."
                />
              </div>
            </div>
          )}
          {section.num === 12 && (
            kpis.length === 0
              ? <p className="text-sm text-[var(--text-tertiary)] italic">No KPIs generated yet.</p>
              : <div className="grid gap-3">{kpis.map((kpi) => <BrCard key={kpi.id} variant="kpi" row={kpi} traces={getTraces(traceability, 'brd_kpis', kpi.row_key)} projectId={projectId} onMutate={() => mutate()} />)}</div>
          )}
          {section.num === 13 && (
            <div className="space-y-4">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)] mb-2">Open Questions</p>
                <EditableRows
                  rows={getRows<Record<string, unknown>>(s, 'brd_open_questions')}
                  table="brd_open_questions"
                  projectId={projectId}
                  onMutate={() => mutate()}
                  columns={[
                    { key: 'question', label: 'Question', primary: true, type: 'textarea' },
                    { key: 'context', label: 'Context', type: 'textarea' },
                    { key: 'owner', label: 'Owner' },
                    { key: 'due_date', label: 'Due date' },
                  ]}
                  emptyText="No open questions yet."
                />
              </div>
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)] mb-2">Decisions</p>
                <EditableRows
                  rows={getRows<Record<string, unknown>>(s, 'brd_decisions')}
                  table="brd_decisions"
                  projectId={projectId}
                  onMutate={() => mutate()}
                  columns={[
                    { key: 'decision', label: 'Decision', primary: true, type: 'textarea' },
                    { key: 'rationale', label: 'Rationale', type: 'textarea' },
                    { key: 'owner', label: 'Owner' },
                    { key: 'decision_date', label: 'Decision date' },
                  ]}
                  emptyText="No decisions yet."
                />
              </div>
            </div>
          )}
          {section.num === 14 && (
            <div className="space-y-4">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)] mb-2">References</p>
                <EditableRows
                  rows={getRows<Record<string, unknown>>(s, 'brd_references')}
                  table="brd_references"
                  projectId={projectId}
                  onMutate={() => mutate()}
                  columns={[
                    { key: 'title', label: 'Title', primary: true },
                    { key: 'reference_type', label: 'Type' },
                    { key: 'location', label: 'Location / URL' },
                    { key: 'description', label: 'Description', type: 'textarea' },
                  ]}
                  emptyText="No references yet."
                />
              </div>
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)] mb-2">Glossary</p>
                <EditableRows
                  rows={getRows<Record<string, unknown>>(s, 'brd_glossary_entries')}
                  table="brd_glossary_entries"
                  projectId={projectId}
                  onMutate={() => mutate()}
                  columns={[
                    { key: 'term', label: 'Term', primary: true },
                    { key: 'definition', label: 'Definition', type: 'textarea' },
                    { key: 'source_ref', label: 'Source' },
                  ]}
                  emptyText="No glossary entries yet."
                />
              </div>
            </div>
          )}
          {/* Questions at bottom — after content so user reads the generated output first */}
          {sectionQ(section.unit_key)}

        </SectionPanel>
      )
    })
  }

  // ── Back button (shared across all stages) ────────────────────────────────

  const BackBtn = () => (
    <button
      onClick={onBack}
      className="inline-flex items-center gap-1 rounded-full border border-[var(--border-default)] bg-[var(--bg-elevated)] px-2.5 py-1 text-[11px] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors shrink-0"
    >
      <ArrowLeft size={11} /> Back
    </button>
  )

  // ── Loading ───────────────────────────────────────────────────────────────

  if (isLoading || readinessLoading) {
    return (
      <div className="flex flex-col h-full overflow-hidden bg-[var(--bg-base)]">
        <div className="h-12 border-b border-[var(--border-default)] bg-[var(--bg-surface)] flex items-center px-4 gap-3">
          <BackBtn />
          <Skeleton className="h-4 w-48" />
        </div>
        <div className="p-8 space-y-3">
          <Skeleton className="h-32 rounded-xl" />
          <Skeleton className="h-24 rounded-xl" />
        </div>
      </div>
    )
  }

  // ── Stage 0: No document yet ──────────────────────────────────────────────

  if (!doc && readiness) {
    return (
      <div className="flex flex-col h-full overflow-hidden bg-[var(--bg-base)]">
        <div className="shrink-0 h-12 flex items-center gap-3 border-b border-[var(--border-default)] bg-[var(--bg-surface)] px-4">
          <BackBtn />
          <span className="text-sm font-semibold text-[var(--text-primary)]">BRD Builder</span>
        </div>
        <BrdEmptyState
          projectId={projectId}
          onStart={handleStart}
          readiness={readiness}
          isLoading={busy}
          appCount={project?.apps_in_scope?.filter((a: { included: boolean }) => a.included).length ?? 0}
          cbReady={false}
        />
      </div>
    )
  }

  // ── Stage 1: Generating ───────────────────────────────────────────────────

  if (generating) {
    return (
      <div className="flex flex-col h-full overflow-hidden bg-[var(--bg-base)]">
        <div className="shrink-0 h-12 flex items-center gap-3 border-b border-[var(--border-default)] bg-[var(--bg-surface)] px-4">
          <BackBtn />
          <span className="text-sm font-semibold text-[var(--text-primary)]">BRD Builder</span>
          <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold bg-blue-100 text-blue-700 border border-blue-200">
            <Loader2 size={9} className="animate-spin" /> Generating…
          </span>
          <div className="flex-1" />
          <button
            onClick={handleResetStall}
            disabled={resettingStall}
            title="If generation is stuck, click to recover — existing sections are preserved"
            className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-default)] bg-[var(--bg-elevated)] px-3 py-1 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-sunken)] disabled:opacity-50 transition-colors"
          >
            <AlertTriangle size={12} className="text-amber-500" />
            {resettingStall ? 'Resetting…' : 'Resume from here'}
          </button>
        </div>
        <UnitDagViz unitStatus={unitStatus} currentUnit={currentUnit} />
      </div>
    )
  }

  // ── Stage 2+: Full builder ────────────────────────────────────────────────

  return (
    <div className="flex flex-col h-full overflow-hidden bg-[var(--bg-base)]">
      <BrdConfettiBurst active={confettiActive} />

      {/* Sticky header */}
      <div className="shrink-0 h-12 flex items-center gap-3 border-b border-[var(--border-default)] bg-[var(--bg-surface)] px-4 z-10">
        <BackBtn />
        <span className="text-sm font-semibold text-[var(--text-primary)] hidden sm:block">
          Business Requirements Document
        </span>
        {validated ? (
          <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold bg-[var(--status-success-bg)] text-[var(--status-success)] border border-[var(--status-success-border)]">
            <CheckCircle2 size={9} /> Validated
          </span>
        ) : (
          <span className="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold bg-amber-100 text-amber-700 border border-amber-200">
            Draft
          </span>
        )}
        <div className="flex-1" />
        <div className="flex items-center gap-2 shrink-0">
          {!validated && (
            <button
              onClick={handleRegenerate}
              disabled={busy}
              title="Re-run all BRD generation units"
              className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] px-2.5 py-1.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] disabled:opacity-50 transition-colors"
            >
              <RotateCcw size={13} className={busy ? 'animate-spin' : ''} /> Regenerate
            </button>
          )}
          <button onClick={() => setShowCoverageModal(true)} className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] px-2.5 py-1.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] transition-colors">
            <span className="text-[var(--accent)]">✦</span> Coverage
          </button>
          {!validated && (
            <button onClick={handleCheckFindings} disabled={busy} className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] px-2.5 py-1.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] disabled:opacity-50 transition-colors">
              <CheckCircle2 size={13} /> Check & Validate
            </button>
          )}
          {findings.length > 0 && (
            <button onClick={() => setShowFindingsDrawer(true)} className="inline-flex items-center gap-1 rounded-lg border border-[var(--status-warning-border)] bg-[var(--status-warning-bg)] px-2.5 py-1.5 text-xs text-[var(--status-warning)] hover:opacity-90 transition-opacity">
              <AlertTriangle size={12} /> {findings.length}
            </button>
          )}
          <button onClick={handleExport} className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] px-2.5 py-1.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] transition-colors">
            <Download size={13} /> Export
          </button>
        </div>
      </div>

      {/* Two-column body */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left: thread */}
        <div className="w-[360px] shrink-0 flex flex-col overflow-hidden">
          {readiness && <SourceStrip projectId={projectId} readiness={readiness} cbStatus={readiness.cb_status ?? undefined} />}
          <CbEchoStrip cbSummary={undefined} />
          <div className="flex-1 overflow-hidden">
            <ThreadPanel messages={messages} answer={answer} busy={busy} validated={validated} onAnswerChange={setAnswer} onAnswerSubmit={handleAnswer} />
          </div>
        </div>
        {/* Right: rail + content */}
        <div className="flex flex-1 overflow-hidden">
          <SectionRail
            unitStatus={unitStatus as Record<string, { completeness: number; confidence: string }>}
            activeSection={activeSection}
            onSectionClick={handleSectionClick}
            findings={findings}
          />
          <main className="flex-1 overflow-y-auto bg-[var(--bg-base)]">
            {renderSections()}
            <div className="h-16" />
          </main>
        </div>
      </div>

      {showFindingsDrawer && (
        <FindingsDrawer
          findings={findings}
          onClose={() => setShowFindingsDrawer(false)}
          onAcceptFix={async () => { toast.success('Fix noted — regenerate section to apply') }}
          onJumpToRow={(rowKey) => { toast.info(`Jump to ${rowKey}`) }}
          onValidate={handleApprove}
        />
      )}
      {showCoverageModal && <CoverageModal projectId={projectId} onClose={() => setShowCoverageModal(false)} />}
    </div>
  )
}
