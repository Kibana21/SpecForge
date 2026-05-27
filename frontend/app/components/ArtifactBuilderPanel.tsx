'use client'
import { useState, useRef, useEffect } from 'react'
import {
  ArrowLeft, CheckCircle2, Send, Sparkles, RotateCcw, Lock, AlertTriangle,
  History, Download, ChevronDown, ChevronUp, ChevronRight, Edit2, Building2, Loader2, Info, Trash2, Check, X,
  Search, FileText, Brain, Zap,
} from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/app/components/ui/button'
import { Badge } from '@/app/components/ui/badge'
import { Skeleton } from '@/app/components/Skeleton'
import { api } from '@/lib/api'
import { useArtifact } from '@/lib/hooks/useArtifact'
import { useProject } from '@/lib/hooks/useProject'
import type {
  ArtifactMessage, CbRow, Confidence, DiscoverEnhanceBriefResult,
  DiscoverQuestion, DiscoverSource, ProjectDetail,
} from '@/lib/types'

const CONF_VARIANT: Record<Confidence, 'success' | 'warning' | 'danger'> = {
  high: 'success', medium: 'warning', low: 'danger',
}

const SECTION_LABELS: Record<string, string> = {
  cb_text_blocks:   'Prose Blocks',
  cb_context_map:   '1. Context Map',
  cb_outcomes:      '2. Expected Outcomes',
  cb_metrics:       '3. Success Metrics',
  cb_capabilities:  '4. Proposed Capabilities',
  cb_scope_items:   '5. Scope & Assumptions',
  cb_milestones:    '6. Delivery Milestones',
  cb_gate_criteria: '7. Approval Gate',
}

const SECTION_ORDER = [
  'cb_text_blocks', 'cb_context_map', 'cb_outcomes', 'cb_metrics',
  'cb_capabilities', 'cb_scope_items', 'cb_milestones', 'cb_gate_criteria',
]

const UNIT_FOR_TABLE: Record<string, string> = {
  cb_text_blocks:   'problem_context',
  cb_context_map:   'problem_context',
  cb_outcomes:      'value_hypothesis',
  cb_metrics:       'metrics',
  cb_capabilities:  'capabilities',
  cb_scope_items:   'scope',
  cb_milestones:    'milestones',
  cb_gate_criteria: 'gate',
}

const TABLE_COLS: Record<string, string[]> = {
  cb_text_blocks:   ['field_key', 'text'],
  cb_context_map:   ['dimension', 'detail'],
  cb_outcomes:      ['outcome', 'description'],
  cb_metrics:       ['metric', 'description', 'quantifiable'],
  cb_capabilities:  ['capability', 'description'],
  cb_scope_items:   ['kind', 'text'],
  cb_milestones:    ['milestone', 'target', 'description'],
  cb_gate_criteria: ['criterion', 'gate_status', 'notes'],
}

function completenessColor(pct: number) {
  if (pct >= 90) return 'text-success'
  if (pct >= 60) return 'text-warning'
  return 'text-danger'
}

function UnitScoreChip({ completeness, confidence }: { completeness: number; confidence: Confidence }) {
  return (
    <div className="inline-flex items-center gap-1 rounded border border-[var(--border-subtle)] bg-[var(--bg-elevated)] px-1.5 py-0.5">
      <Info size={8} className="text-[var(--text-tertiary)] opacity-40 shrink-0" />
      <span className="text-[9px] text-[var(--text-tertiary)]">completeness</span>
      <span className={`text-[10px] font-semibold ${completenessColor(completeness)}`}>{completeness}%</span>
      <span className="text-[9px] text-[var(--text-tertiary)]">·</span>
      <span className="text-[9px] text-[var(--text-tertiary)]">confidence</span>
      <Badge variant={CONF_VARIANT[confidence]} className="text-[9px] py-0">{confidence}</Badge>
    </div>
  )
}

export interface ArtifactBuilderPanelProps {
  projectId: string
  artifactType: string
  onBack?: () => void
}

export function ArtifactBuilderPanel({ projectId, artifactType, onBack }: ArtifactBuilderPanelProps) {
  const { detail, isLoading, mutate } = useArtifact(projectId, artifactType)
  const { project } = useProject(projectId)

  const [answer, setAnswer] = useState('')
  const [initContext, setInitContext] = useState('')
  const [busy, setBusy] = useState(false)
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({})
  const [editingRow, setEditingRow] = useState<{ table: string; row: CbRow } | null>(null)
  const [historyRow, setHistoryRow] = useState<{ table: string; rowKey: string; unitKey: string } | null>(null)
  const [historyData, setHistoryData] = useState<CbRow[]>([])
  const threadEndRef = useRef<HTMLDivElement>(null)

  // Discover phase state
  const [discoverQuestions, setDiscoverQuestions] = useState<DiscoverQuestion[]>([])
  const [enhancing, setEnhancing] = useState(false)
  const [enhanceResult, setEnhanceResult] = useState<DiscoverEnhanceBriefResult | null>(null)
  const [discoverBusy, setDiscoverBusy] = useState(false)
  const [discoverDrawerOpen, setDiscoverDrawerOpen] = useState(false)

  const doc = detail?.document ?? null
  const messages = detail?.messages ?? []
  const sections = detail?.sections ?? {}
  const unitStatus = doc?.unit_status ?? {}
  const generated = doc !== null
  const validated = doc?.status === 'validated'
  const refiningUnit = (unitStatus['_current_unit'] as unknown as string | undefined) ?? null
  const refineError = (unitStatus['_refine_error'] as unknown as string | undefined) ?? null

  // Toast when background refinement fails (suppress repeats for same error)
  const shownRefineErrorRef = useRef<string | null>(null)
  useEffect(() => {
    if (refineError && refineError !== shownRefineErrorRef.current) {
      shownRefineErrorRef.current = refineError
      toast.error('Section refinement failed — please try again.')
    }
  }, [refineError])

  // Toast when background refinement completes successfully
  const prevRefiningUnitRef = useRef<string | null>(null)
  useEffect(() => {
    const prev = prevRefiningUnitRef.current
    prevRefiningUnitRef.current = refiningUnit
    if (prev && !refiningUnit && !refineError) {
      toast.success('Section refined — check for any new follow-up questions.')
    }
  }, [refiningUnit, refineError])

  // Open clarification questions grouped by unit_key.
  // A question is open if no synthesis for its unit_key was emitted AFTER it
  // (a later synthesis means the unit was regenerated and the question resolved).
  const _latestSynthesisSeq: Record<string, number> = {}
  messages.forEach(m => {
    if (m.role === 'synthesis' && m.meta?.unit_key) {
      const uk = m.meta.unit_key as string
      if ((m.seq ?? 0) > (_latestSynthesisSeq[uk] ?? -1)) _latestSynthesisSeq[uk] = m.seq ?? 0
    }
  })
  const questionsByUnit: Record<string, ArtifactMessage[]> = {}
  messages
    .filter(m => {
      if (m.role !== 'question') return false
      const uk = (m.meta?.unit_key as string) ?? 'unknown'
      return (m.seq ?? 0) > (_latestSynthesisSeq[uk] ?? -1)
    })
    .forEach(q => {
      const uk = (q.meta?.unit_key as string) ?? 'unknown'
      if (!questionsByUnit[uk]) questionsByUnit[uk] = []
      questionsByUnit[uk].push(q)
    })
  Object.values(questionsByUnit).forEach(qs => qs.sort((a, b) => (a.seq ?? 0) - (b.seq ?? 0)))

  const typeLabel = artifactType === 'concept-brief' ? 'Concept Brief' : artifactType

  useEffect(() => {
    threadEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages.length])

  async function run<T>(fn: () => Promise<T>, ok: string): Promise<T | undefined> {
    setBusy(true)
    try {
      const r = await fn()
      await mutate()
      toast.success(ok)
      return r
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed')
    } finally {
      setBusy(false)
    }
  }

  // Load discover questions on mount when status=in_discover
  useEffect(() => {
    if (doc?.status === 'in_discover' && discoverQuestions.length === 0) {
      api.artifacts.getDiscover(projectId, artifactType)
        .then(r => setDiscoverQuestions(r.questions))
        .catch(() => {})
    }
  }, [doc?.status]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleGenerate = () => run(
    () => api.artifacts.generate(projectId, artifactType, { context: initContext || undefined }),
    `${typeLabel} generated`,
  )

  async function handleEnhance() {
    if (enhancing) return
    setEnhancing(true)
    try {
      const r = await api.artifacts.enhanceBrief(projectId, artifactType, initContext)
      setInitContext(r.enhanced_brief)
      setEnhanceResult(r)
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Enhance failed'
      const isNetwork = msg.toLowerCase().includes('fetch') || msg.toLowerCase().includes('network')
      toast.error(isNetwork ? 'Enhancement timed out — the AI took too long. Try again.' : msg)
    } finally {
      setEnhancing(false)
    }
  }

  async function handleAnalyze() {
    if (discoverBusy) return
    setDiscoverBusy(true)
    try {
      const r = await api.artifacts.analyzeDiscover(projectId, artifactType, initContext)
      setDiscoverQuestions(r.questions)
      await mutate()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Analysis failed')
    } finally {
      setDiscoverBusy(false)
    }
  }

  async function handleDiscoverAnswer(questionId: string, answer: string) {
    try {
      const updated = await api.artifacts.answerDiscover(projectId, artifactType, questionId, answer)
      setDiscoverQuestions(qs => qs.map(q => q.id === updated.id ? updated : q))
    } catch {
      toast.error('Failed to save answer')
    }
  }

  async function handleDiscoverComplete() {
    if (discoverBusy) return
    setDiscoverBusy(true)
    try {
      await api.artifacts.completeDiscover(projectId, artifactType)
      await mutate()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to generate')
    } finally {
      setDiscoverBusy(false)
    }
  }

  const handleValidate = () => run(async () => {
    const result = await api.artifacts.validate(projectId, artifactType)
    if (!result.ok) {
      toast.error(`Validation failed:\n${result.failures.join('\n')}`)
      throw new Error('Validation failed')
    }
    return result
  }, `${typeLabel} validated`)

  async function handleAnswer(questionSeq?: number) {
    if (!answer.trim() || busy) return
    const a = answer.trim()
    setAnswer('')
    setBusy(true)
    try {
      const detail = await api.artifacts.answer(projectId, artifactType, a, questionSeq)
      // Seed the SWR cache immediately with the returned detail, which already
      // has _current_unit set by save_answer. Using revalidate:false avoids a
      // redundant re-fetch that could race with the Celery task start and miss
      // the _current_unit window. SWR will poll (refreshInterval=2000) from here.
      await mutate(detail, { revalidate: false })
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to submit answer')
      await mutate()
    } finally {
      setBusy(false)
    }
  }

  async function handleRegenUnit(unitKey: string) {
    await run(
      () => api.artifacts.regenerateUnit(projectId, artifactType, unitKey),
      `${unitKey} regenerated`,
    )
  }

  async function handleDeleteRow(table: string, rowId: string) {
    await run(
      () => api.artifacts.deleteRow(projectId, artifactType, table, rowId),
      'Row deleted',
    )
  }

  async function handleProseEdit(rowId: string, text: string) {
    await run(
      () => api.artifacts.editRow(projectId, artifactType, 'cb_text_blocks', rowId, { text }, false),
      'Saved',
    )
  }

  async function handleEditRowSave(table: string, row: CbRow, fields: Record<string, unknown>) {
    await run(
      () => api.artifacts.editRow(projectId, artifactType, table, row.id as string, fields),
      'Row updated',
    )
    setEditingRow(null)
  }

  async function handleUnlock(table: string, rowId: string) {
    await run(() => api.artifacts.unlockRow(projectId, artifactType, table, rowId), 'Row unlocked')
  }

  async function handleShowHistory(table: string, rowKey: string, unitKey: string) {
    setHistoryRow({ table, rowKey, unitKey })
    try {
      const h = await api.artifacts.rowHistory(projectId, artifactType, unitKey, rowKey, table)
      setHistoryData(h)
    } catch {
      toast.error('Failed to load history')
    }
  }

  async function handleRestore(table: string, rowId: string, version: number) {
    await run(
      () => api.artifacts.restoreRow(projectId, artifactType, table, rowId, version),
      `Restored to version ${version}`,
    )
    setHistoryRow(null)
  }

  function toggleSection(table: string) {
    setExpandedSections(p => ({ ...p, [table]: !p[table] }))
  }

  const isExpanded = (table: string) => expandedSections[table] !== false // default open

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* ── Breadcrumb / action bar ── */}
      <div className="shrink-0 flex items-center justify-between gap-3 border-b border-[var(--border-default)] bg-[var(--bg-surface)] px-3 py-2">
        <div className="flex items-center gap-2 min-w-0">
          {onBack && (
            <button
              onClick={onBack}
              className="inline-flex items-center gap-1 rounded-full border border-[var(--border-default)] bg-[var(--bg-elevated)] px-2.5 py-1 text-[11px] text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:border-[var(--text-tertiary)] transition-colors shrink-0"
              aria-label="Back"
            >
              <ArrowLeft size={11} />
              Concept Brief
            </button>
          )}
          {validated && <Badge variant="success">Validated</Badge>}
          {generated && !validated && <Badge variant="warning">In Progress</Badge>}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {generated && !validated && (
            <Button onClick={handleValidate} disabled={busy} variant="outline" size="sm">
              <CheckCircle2 size={14} /> Validate
            </Button>
          )}
          {generated && discoverQuestions.length > 0 && (
            <button
              onClick={() => setDiscoverDrawerOpen(true)}
              className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] px-2.5 py-1.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] transition-colors"
            >
              <Search size={13} /> Discovery Q&amp;A
            </button>
          )}
          {validated && (
            <a
              href={api.artifacts.exportUrl(projectId, artifactType)}
              className="flex items-center gap-1.5 rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] px-2.5 py-1.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] transition-colors"
            >
              <Download size={13} /> Export MD
            </a>
          )}
        </div>
      </div>

      {isLoading ? (
        <div className="p-6"><Skeleton className="h-64 rounded-xl" /></div>
      ) : doc?.status === 'generating' ? (
        /* ── Generating progress view ── */
        <GeneratingProgress unitStatus={unitStatus} />
      ) : doc?.status === 'in_discover' ? (
        /* ── Discover phase ── */
        <DiscoverPhase
          questions={discoverQuestions}
          project={project}
          busy={discoverBusy}
          onAnswer={handleDiscoverAnswer}
          onComplete={handleDiscoverComplete}
          onBack={() => { /* reset to empty state — just mutate to reload */ mutate() }}
        />
      ) : !generated ? (
        /* ── Empty state (enhanced with ✨ button) ── */
        <div className="flex flex-1 flex-col items-center justify-center text-center gap-5 p-8">
          <div className="w-16 h-16 rounded-2xl bg-[var(--accent-subtle)] flex items-center justify-center">
            <Sparkles size={32} className="text-[var(--accent)]" strokeWidth={1.4} />
          </div>
          <div>
            <p className="text-lg font-semibold text-[var(--text-primary)]">Generate your {typeLabel}</p>
            <p className="mt-1.5 text-sm text-[var(--text-secondary)] max-w-md">
              SpecForge will synthesize a structured brief from your project description, uploaded documents, and in-scope application facts.
            </p>
          </div>
          {/* Grounding indicator */}
          {((project?.apps_in_scope?.length ?? 0) > 0 || (project?.documents?.length ?? 0) > 0) && (
            <div className="flex items-center gap-1.5 text-xs text-[var(--text-tertiary)] bg-[var(--bg-surface)] border border-[var(--border-default)] rounded-lg px-3 py-2">
              {(project?.apps_in_scope?.length ?? 0) > 0 && (
                <><Building2 size={13} className="text-[var(--accent)]" />
                {project!.apps_in_scope.length} app{project!.apps_in_scope.length !== 1 ? 's' : ''}</>
              )}
              {(project?.apps_in_scope?.length ?? 0) > 0 && (project?.documents?.length ?? 0) > 0 && (
                <span className="text-[var(--border-strong)]">·</span>
              )}
              {(project?.documents?.length ?? 0) > 0 && (
                <><FileText size={13} className="text-[var(--accent)]" />
                {project!.documents.length} document{project!.documents.length !== 1 ? 's' : ''}</>
              )}
            </div>
          )}
          <div className="w-full max-w-md text-left">
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-semibold text-[var(--text-secondary)]">
                Describe your initiative <span className="font-normal text-[var(--text-tertiary)]">(optional)</span>
              </label>
              <button
                onClick={handleEnhance}
                disabled={enhancing}
                className="inline-flex items-center gap-1 rounded-md border border-[var(--border-default)] bg-[var(--bg-surface)] px-2 py-1 text-[11px] font-medium text-[var(--text-secondary)] hover:bg-[var(--accent-subtle)] hover:text-[var(--accent)] hover:border-[var(--accent-subtle)] transition-colors disabled:opacity-50"
              >
                {enhancing
                  ? <><Loader2 size={11} className="animate-spin" /> Enhancing…</>
                  : <><Sparkles size={11} /> AI Enhance</>}
              </button>
            </div>
            <textarea
              value={initContext}
              onChange={(e) => setInitContext(e.target.value)}
              rows={4}
              placeholder="e.g. We're building a real-time payment gateway for SME customers using SEPA and domestic ACH rails…"
              className="w-full resize-y rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-ring)]"
            />
            {/* Post-enhance attribution banner */}
            {enhanceResult && (
              <div className="mt-2 flex items-center gap-1.5 rounded-lg border border-[var(--accent-subtle)] bg-[var(--accent-subtle)] px-3 py-2 text-xs text-[var(--accent)]">
                <CheckCircle2 size={13} className="shrink-0" />
                <span>
                  Enhanced using{' '}
                  {enhanceResult.doc_sources.length > 0
                    ? enhanceResult.doc_sources.map(d => d.filename).slice(0, 2).join(', ')
                    : null}
                  {enhanceResult.doc_sources.length > 0 && enhanceResult.app_sources.length > 0 ? ' + ' : null}
                  {enhanceResult.app_sources.length > 0
                    ? enhanceResult.app_sources.map(a => a.app_name).slice(0, 2).join(', ')
                    : null}
                  {enhanceResult.doc_sources.length === 0 && enhanceResult.app_sources.length === 0
                    ? 'available context'
                    : null}
                </span>
              </div>
            )}
          </div>
          <Button onClick={handleAnalyze} disabled={discoverBusy} size="lg">
            {discoverBusy ? <Loader2 size={15} className="animate-spin" /> : <Sparkles size={15} />}
            {discoverBusy ? 'Analyzing…' : 'Analyze & Continue →'}
          </Button>
        </div>
      ) : (
        /* ── Full-width document view ── */
        <div className="flex-1 overflow-y-auto bg-[var(--bg-base)]">
          {/* Prose blocks — prose units own problem_context + value_hypothesis questions */}
          <ProseSection
            sections={sections}
            unitStatus={unitStatus}
            validated={validated}
            busy={busy}
            refining={refiningUnit === 'problem_context' || refiningUnit === 'value_hypothesis'}
            onRegenUnit={handleRegenUnit}
            onEditProse={handleProseEdit}
            openQuestions={[
              ...(questionsByUnit['problem_context'] ?? []),
              ...(questionsByUnit['value_hypothesis'] ?? []),
            ]}
            answer={answer}
            onAnswerChange={setAnswer}
            onAnswerSubmit={handleAnswer}
          />

          {/* Typed table sections — each owns its own unit_key's questions */}
          {SECTION_ORDER.filter(t => t !== 'cb_text_blocks').map(table => {
            const unitKey = UNIT_FOR_TABLE[table]
            // Prose section already owns these two unit_keys — don't duplicate
            const ownedByProse = unitKey === 'problem_context' || unitKey === 'value_hypothesis'
            const rows = sections[table] ?? []
            const us = unitStatus[unitKey]
            return (
              <SectionPanel
                key={table}
                table={table}
                label={SECTION_LABELS[table]}
                rows={rows}
                unitKey={unitKey}
                unitStatus={us}
                validated={validated}
                busy={busy}
                expanded={isExpanded(table)}
                onToggle={() => toggleSection(table)}
                onRegenUnit={handleRegenUnit}
                onEdit={(row) => setEditingRow({ table, row })}
                onUnlock={(rowId) => handleUnlock(table, rowId)}
                onHistory={(row) => handleShowHistory(table, row.row_key as string, unitKey)}
                onDelete={(rowId) => handleDeleteRow(table, rowId)}
                openQuestions={ownedByProse ? [] : (questionsByUnit[unitKey] ?? [])}
                refining={refiningUnit === unitKey}
                answer={answer}
                onAnswerChange={setAnswer}
                onAnswerSubmit={handleAnswer}
              />
            )
          })}
        </div>
      )}

      {/* ── Edit Row Modal ── */}
      {editingRow && (
        <RowEditModal
          table={editingRow.table}
          row={editingRow.row}
          onClose={() => setEditingRow(null)}
          onSave={(fields) => handleEditRowSave(editingRow.table, editingRow.row, fields)}
        />
      )}

      {/* ── Row History Drawer ── */}
      {historyRow && (
        <HistoryDrawer
          rowKey={historyRow.rowKey}
          table={historyRow.table}
          history={historyData}
          onClose={() => setHistoryRow(null)}
          onRestore={(rowId, version) => handleRestore(historyRow.table, rowId, version)}
        />
      )}

      {/* ── Discovery Q&A Drawer ── */}
      {discoverDrawerOpen && (
        <DiscoverQADrawer
          questions={discoverQuestions}
          onClose={() => setDiscoverDrawerOpen(false)}
        />
      )}
    </div>
  )
}

// ── Source Badge ─────────────────────────────────────────────────────────────

const SOURCE_BADGE_MAP: Record<string, { label: string; cls: string }> = {
  project:     { label: 'from project',    cls: 'bg-[var(--bg-elevated)] text-[var(--text-secondary)] border-[var(--border-default)]' },
  brief:       { label: 'from your brief', cls: 'bg-[var(--status-info-bg)] text-[var(--status-info)] border-[var(--status-info-border)]' },
  documents:   { label: 'from document',   cls: 'bg-[var(--status-info-bg)] text-[var(--status-info)] border-[var(--status-info-border)]' },
  app_brain:   { label: 'from app brain',  cls: 'bg-purple-50 text-purple-700 border-purple-200' },
  combined:    { label: 'multi-source',    cls: 'bg-[var(--status-warning-bg)] text-[var(--status-warning)] border-[var(--status-warning-border)]' },
  ai_enhanced: { label: 'AI enhanced',     cls: 'bg-[var(--accent-subtle)] text-[var(--accent)] border-[var(--accent-subtle)]' },
  user:        { label: 'you answered',    cls: 'bg-[var(--status-success-bg)] text-[var(--status-success)] border-[var(--status-success-border)]' },
}

function SourceBadge({ source, contextSources }: {
  source: DiscoverSource
  contextSources?: DiscoverQuestion['context_sources']
}) {
  if (!source || !SOURCE_BADGE_MAP[source]) return null
  const { cls } = SOURCE_BADGE_MAP[source]
  let label = SOURCE_BADGE_MAP[source].label
  if (source === 'documents') {
    const docName = contextSources?.docs?.[0]?.filename?.split('/').pop()
    if (docName) label = `doc · ${docName}`
  } else if (source === 'app_brain') {
    const appName = contextSources?.apps?.[0]?.app_name
    if (appName) label = `app · ${appName}`
  }
  return (
    <span className={`inline-flex items-center rounded border px-1.5 py-0.5 text-[10px] font-medium shrink-0 ${cls}`}>
      {label}
    </span>
  )
}

// ── Discover Phase ────────────────────────────────────────────────────────────

const CATEGORY_META: Record<string, { emoji: string; label: string }> = {
  initiative_context: { emoji: '🎯', label: 'Initiative Context' },
  business_context:   { emoji: '🏢', label: 'Business Context' },
  value_outcomes:     { emoji: '💡', label: 'Value & Outcomes' },
  scope_assumptions:  { emoji: '📦', label: 'Scope & Assumptions' },
  delivery:           { emoji: '🚀', label: 'Delivery' },
}

function DiscoverPhase({
  questions, project, busy, onAnswer, onComplete, onBack,
}: {
  questions: DiscoverQuestion[]
  project: ProjectDetail | undefined
  busy: boolean
  onAnswer: (questionId: string, answer: string) => void
  onComplete: () => void
  onBack: () => void
}) {
  const [localAnswers, setLocalAnswers] = useState<Record<string, string>>({})
  const [saveState, setSaveState] = useState<Record<string, 'saving' | 'saved' | null>>({})
  const [answeredOpen, setAnsweredOpen] = useState(false)
  const [editingKey, setEditingKey] = useState<string | null>(null)

  const answered = questions.filter(q => q.answer && q.answer.trim())
  const gaps = questions.filter(q => !q.answer || !q.answer.trim())
  const total = questions.length
  const answeredCount = answered.length
  const pendingCount = gaps.length

  // Initialise local answers from gap questions' inferred_answer
  useEffect(() => {
    const init: Record<string, string> = {}
    questions.forEach(q => { init[q.id] = '' })
    setLocalAnswers(init)
  }, [questions.length]) // eslint-disable-line react-hooks/exhaustive-deps

  async function handleBlur(q: DiscoverQuestion) {
    const val = (localAnswers[q.id] ?? '').trim()
    if (!val) return
    setSaveState(s => ({ ...s, [q.id]: 'saving' }))
    await onAnswer(q.id, val)
    setSaveState(s => ({ ...s, [q.id]: 'saved' }))
    setTimeout(() => setSaveState(s => ({ ...s, [q.id]: null })), 1500)
  }

  async function handleEditAnswer(q: DiscoverQuestion, val: string) {
    setSaveState(s => ({ ...s, [q.id]: 'saving' }))
    await onAnswer(q.id, val)
    setSaveState(s => ({ ...s, [q.id]: 'saved' }))
    setEditingKey(null)
    setTimeout(() => setSaveState(s => ({ ...s, [q.id]: null })), 1500)
  }

  // Group gap questions by category
  const gapsByCategory: Record<string, DiscoverQuestion[]> = {}
  gaps.forEach(q => {
    if (!gapsByCategory[q.category]) gapsByCategory[q.category] = []
    gapsByCategory[q.category].push(q)
  })

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Fixed header */}
      <div className="shrink-0 border-b border-[var(--border-default)] bg-[var(--bg-surface)] px-4 pt-3 pb-3">
        <div className="flex items-center justify-between">
          <p className="text-base font-semibold text-[var(--text-primary)] flex items-center gap-2">
            🔍 Discovery Questions
          </p>
          <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium border
            ${pendingCount === 0
              ? 'bg-[var(--status-success-bg)] text-[var(--status-success)] border-[var(--status-success-border)]'
              : 'bg-[var(--status-info-bg)] text-[var(--status-info)] border-[var(--status-info-border)]'}`}
          >
            {answeredCount} of {total} complete
          </span>
        </div>
        {project && (
          <p className="mt-0.5 text-xs text-[var(--text-tertiary)]">
            SpecForge analysed your brief
            {(project.documents?.length ?? 0) > 0 && `, ${project.documents.length} document${project.documents.length !== 1 ? 's' : ''}`}
            {(project.apps_in_scope?.length ?? 0) > 0 && `, and ${project.apps_in_scope.length} app${project.apps_in_scope.length !== 1 ? 's' : ''}`}.
          </p>
        )}
        {/* Progress bar */}
        <div className="mt-2 h-1.5 w-full rounded-full bg-[var(--bg-sunken)]">
          <div
            className="h-1.5 rounded-full bg-[var(--accent)] transition-[width] duration-300"
            style={{ width: total > 0 ? `${(answeredCount / total) * 100}%` : '0%' }}
          />
        </div>
      </div>

      {/* Scrollable body */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Answered accordion */}
        {answered.length > 0 && (
          <div>
            <button
              onClick={() => setAnsweredOpen(o => !o)}
              className="flex items-center gap-2 w-full py-1 text-xs font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
            >
              {answeredOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              {answered.length} answered
              <span className="flex-1 h-px bg-[var(--border-default)] ml-1" />
            </button>
            {answeredOpen && (
              <div className="mt-2 space-y-2">
                {answered.map(q => (
                  <div
                    key={q.id}
                    className="rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] px-3 py-2.5"
                  >
                    {editingKey === q.id ? (
                      <AnswerEditInline
                        question={q}
                        onSave={(val) => handleEditAnswer(q, val)}
                        onCancel={() => setEditingKey(null)}
                        saving={saveState[q.id] === 'saving'}
                      />
                    ) : (
                      <div className="flex items-start gap-2">
                        <CheckCircle2 size={14} className="shrink-0 mt-0.5 text-[var(--accent)]" />
                        <div className="flex-1 min-w-0">
                          <p className="text-[10px] text-[var(--text-tertiary)]">{q.question_key}. {q.question_text}</p>
                          <p className="text-sm text-[var(--text-primary)] mt-0.5 truncate">{q.answer}</p>
                        </div>
                        <SourceBadge source={q.source} contextSources={q.context_sources} />
                        <button
                          onClick={() => setEditingKey(q.id)}
                          className="shrink-0 text-[10px] text-[var(--text-tertiary)] hover:text-[var(--accent)] transition-colors"
                        >
                          Edit
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Gap questions */}
        {pendingCount > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-3">
              <span className="text-xs font-semibold text-[var(--text-secondary)]">❓ {pendingCount} gap{pendingCount !== 1 ? 's' : ''} to fill</span>
              <span className="flex-1 h-px bg-[var(--border-default)]" />
            </div>
            {Object.entries(gapsByCategory).map(([category, catQuestions]) => {
              const meta = CATEGORY_META[category] ?? { emoji: '•', label: category }
              return (
                <div key={category} className="mb-4">
                  <p className="text-[11px] font-semibold text-[var(--text-tertiary)] uppercase tracking-wide mb-2">
                    {meta.emoji} {meta.label}
                  </p>
                  <div className="space-y-3">
                    {catQuestions.map(q => {
                      const localVal = localAnswers[q.id] ?? ''
                      const isFilled = localVal.trim().length > 0
                      const ss = saveState[q.id]
                      return (
                        <div
                          key={q.id}
                          className={`rounded-lg border bg-[var(--bg-surface)] px-3 py-2.5 space-y-1.5 transition-shadow
                            ${isFilled
                              ? 'border-[var(--status-success-border)]'
                              : 'border-[var(--border-default)]'}
                            focus-within:ring-1 focus-within:ring-[var(--accent-ring)] focus-within:border-[var(--accent)]`}
                        >
                          <p className="text-xs font-medium text-[var(--text-primary)]">
                            <span className="text-[10px] text-[var(--text-tertiary)] mr-1">{q.question_key}.</span>
                            {q.question_text}
                          </p>
                          <textarea
                            value={localVal}
                            onChange={e => setLocalAnswers(a => ({ ...a, [q.id]: e.target.value }))}
                            onBlur={() => handleBlur(q)}
                            rows={2}
                            placeholder={q.inferred_answer ? `Hint: ${q.inferred_answer}` : 'Type your answer…'}
                            className="w-full resize-none rounded border border-[var(--border-default)] bg-[var(--bg-elevated)] px-2.5 py-1.5 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] placeholder:italic placeholder:text-xs focus:outline-none focus:border-[var(--accent)]"
                          />
                          {ss && (
                            <p className={`text-[10px] ${ss === 'saved' ? 'text-[var(--status-success)]' : 'text-[var(--text-tertiary)]'}`}>
                              {ss === 'saving' ? 'Saving…' : 'Saved ✓'}
                            </p>
                          )}
                        </div>
                      )
                    })}
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {pendingCount === 0 && answered.length > 0 && (
          <div className="flex flex-col items-center gap-2 py-6 text-center">
            <CheckCircle2 size={28} className="text-[var(--accent)]" />
            <p className="text-sm font-medium text-[var(--text-primary)]">All questions answered</p>
            <p className="text-xs text-[var(--text-tertiary)]">Click Generate to create your Concept Brief.</p>
          </div>
        )}
      </div>

      {/* Fixed footer */}
      <div className="shrink-0 border-t border-[var(--border-default)] flex items-center justify-between px-4 py-3">
        <Button variant="outline" size="sm" onClick={onBack} disabled={busy}>
          <ArrowLeft size={14} /> Back to brief
        </Button>
        <Button
          size="default"
          onClick={onComplete}
          disabled={busy || pendingCount > 0}
          title={pendingCount > 0 ? `Answer ${pendingCount} remaining question${pendingCount !== 1 ? 's' : ''} first` : undefined}
        >
          {busy ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
          {busy ? 'Generating…' : 'Generate Concept Brief →'}
        </Button>
      </div>
    </div>
  )
}

function AnswerEditInline({ question, onSave, onCancel, saving }: {
  question: DiscoverQuestion
  onSave: (val: string) => void
  onCancel: () => void
  saving: boolean
}) {
  const [val, setVal] = useState(question.answer ?? '')
  return (
    <div className="space-y-2">
      <p className="text-[10px] text-[var(--text-tertiary)]">{question.question_key}. {question.question_text}</p>
      <textarea
        value={val}
        onChange={e => setVal(e.target.value)}
        rows={2}
        autoFocus
        className="w-full resize-none rounded border border-[var(--accent)] bg-[var(--bg-elevated)] px-2.5 py-1.5 text-sm text-[var(--text-primary)] focus:outline-none"
      />
      <div className="flex items-center gap-2">
        <button
          onClick={() => onSave(val)}
          disabled={saving || !val.trim()}
          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-[var(--accent)] text-white text-xs font-semibold hover:opacity-90 disabled:opacity-50"
        >
          <Check size={11} /> Save
        </button>
        <button
          onClick={onCancel}
          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg border border-[var(--border-default)] text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]"
        >
          <X size={11} /> Cancel
        </button>
      </div>
    </div>
  )
}

// ── Discover Q&A Drawer ───────────────────────────────────────────────────────

function DiscoverQADrawer({ questions, onClose }: {
  questions: DiscoverQuestion[]
  onClose: () => void
}) {
  // Group by category
  const byCategory: Record<string, DiscoverQuestion[]> = {}
  questions.forEach(q => {
    if (!byCategory[q.category]) byCategory[q.category] = []
    byCategory[q.category].push(q)
  })

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-[var(--text-primary)]/20 z-40"
        onClick={onClose}
      />
      {/* Panel */}
      <div className="fixed top-0 right-0 h-full w-[400px] max-w-[90vw] bg-[var(--bg-surface)] border-l border-[var(--border-default)] shadow-[-4px_0_24px_rgba(0,0,0,0.08)] z-50 flex flex-col">
        {/* Header */}
        <div className="shrink-0 flex items-center justify-between px-4 py-3 border-b border-[var(--border-default)]">
          <p className="text-sm font-semibold text-[var(--text-primary)] flex items-center gap-1.5">
            <Search size={14} className="text-[var(--text-tertiary)]" />
            Discovery Q&amp;A
          </p>
          <button
            onClick={onClose}
            className="p-1 rounded-md text-[var(--text-tertiary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-elevated)] transition-colors"
          >
            <X size={16} />
          </button>
        </div>
        {/* Body */}
        <div className="flex-1 overflow-y-auto px-4 py-3 space-y-5">
          {Object.entries(byCategory).map(([category, qs]) => {
            const meta = CATEGORY_META[category] ?? { emoji: '•', label: category }
            return (
              <div key={category}>
                <p className="text-[11px] font-semibold text-[var(--text-tertiary)] uppercase tracking-wide mb-2">
                  {meta.emoji} {meta.label}
                </p>
                <div className="space-y-3">
                  {qs.map(q => (
                    <div key={q.id}>
                      <p className="text-xs text-[var(--text-secondary)]">
                        <span className="text-[10px] text-[var(--text-tertiary)] mr-1">{q.question_key}.</span>
                        {q.question_text}
                      </p>
                      {q.answer ? (
                        <>
                          <p className="text-sm text-[var(--text-primary)] mt-0.5 leading-relaxed">{q.answer}</p>
                          <div className="mt-1">
                            <SourceBadge source={q.source} contextSources={q.context_sources} />
                          </div>
                        </>
                      ) : (
                        <p className="text-sm text-[var(--text-tertiary)] italic mt-0.5">—</p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </>
  )
}

// ── Generating Progress View ──────────────────────────────────────────────────

const CB_UNITS = [
  { key: 'problem_context',  label: 'Problem Context' },
  { key: 'value_hypothesis', label: 'Value Hypothesis' },
  { key: 'metrics',          label: 'Success Metrics' },
  { key: 'capabilities',     label: 'Capabilities' },
  { key: 'scope',            label: 'Scope & Assumptions' },
  { key: 'milestones',       label: 'Delivery Milestones' },
]

function GeneratingProgress({
  unitStatus,
}: {
  unitStatus: Record<string, unknown>
}) {
  const currentUnit = unitStatus['_current_unit'] as string | undefined

  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-6 p-8">
      <div className="w-14 h-14 rounded-2xl bg-[var(--accent-subtle)] flex items-center justify-center">
        <Loader2 size={28} className="text-[var(--accent)] animate-spin" strokeWidth={1.5} />
      </div>
      <div className="text-center">
        <p className="text-base font-semibold text-[var(--text-primary)]">Generating Concept Brief</p>
        <p className="mt-1 text-sm text-[var(--text-tertiary)]">
          This takes about 30–60 seconds with Gemini 2.5 Flash
        </p>
      </div>
      <div className="w-full max-w-sm bg-[var(--bg-surface)] border border-[var(--border-default)] rounded-xl px-5 py-4 space-y-3">
        {CB_UNITS.map(({ key, label }) => {
          const us = unitStatus[key] as { completeness?: number } | undefined
          const isDone = us !== undefined && (us as { completeness?: number }).completeness !== undefined
          const isCurrent = key === currentUnit && !isDone

          return (
            <div key={key} className="flex items-center gap-3">
              {isDone ? (
                <CheckCircle2 size={16} className="shrink-0 text-[var(--accent)]" strokeWidth={2} />
              ) : isCurrent ? (
                <Loader2 size={16} className="shrink-0 text-[var(--accent)] animate-spin" strokeWidth={2} />
              ) : (
                <span className="shrink-0 w-4 h-4 rounded-full border-2 border-[var(--border-default)] bg-transparent inline-block" />
              )}
              <span
                className={`text-sm ${
                  isDone
                    ? 'text-[var(--text-primary)]'
                    : isCurrent
                    ? 'text-[var(--text-primary)] font-medium'
                    : 'text-[var(--text-tertiary)]'
                }`}
              >
                {label}
              </span>
              {isCurrent && (
                <span className="ml-auto text-xs text-[var(--text-tertiary)]">Calling Gemini…</span>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── Prose Section (text blocks) ───────────────────────────────────────────────

function ProseBlock({
  label, text, rowId, validated, busy,
  onEdit,
}: {
  label: string
  text: string
  rowId: string | undefined
  validated: boolean
  busy: boolean
  onEdit: (rowId: string, text: string) => void
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(text)

  function startEdit() { setDraft(text); setEditing(true) }
  function cancel() { setEditing(false) }
  async function save() {
    if (!rowId) return
    await onEdit(rowId, draft)
    setEditing(false)
  }

  return (
    <div className="group/prose relative">
      <div className="flex items-center justify-between mb-1">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)]">{label}</p>
        {!validated && rowId && !editing && (
          <button
            onClick={startEdit}
            disabled={busy}
            className="p-1.5 rounded-md border border-[var(--border-default)] bg-[var(--bg-elevated)] text-[var(--text-secondary)] hover:border-[var(--accent)] hover:text-[var(--accent)] hover:bg-[var(--accent-subtle)] disabled:opacity-40 transition-colors"
            title="Edit"
          >
            <Edit2 size={13} />
          </button>
        )}
      </div>
      {editing ? (
        <div className="space-y-2">
          <textarea
            value={draft}
            onChange={e => setDraft(e.target.value)}
            rows={4}
            className="w-full resize-y rounded-lg border border-[var(--accent)] bg-[var(--bg-surface)] px-3 py-2 text-sm text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/30"
            autoFocus
          />
          <div className="flex items-center gap-2">
            <button
              onClick={save}
              disabled={busy}
              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-[var(--accent)] text-white text-xs font-semibold hover:opacity-90 disabled:opacity-50 transition-opacity"
            >
              <Check size={12} /> Save
            </button>
            <button
              onClick={cancel}
              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg border border-[var(--border-default)] text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] transition-colors"
            >
              <X size={12} /> Cancel
            </button>
          </div>
        </div>
      ) : (
        <p className="text-sm text-[var(--text-primary)] leading-relaxed whitespace-pre-wrap">{text}</p>
      )}
    </div>
  )
}

function ProseSection({
  sections, unitStatus, validated, busy, refining, onRegenUnit, onEditProse,
  openQuestions, answer, onAnswerChange, onAnswerSubmit,
}: {
  sections: Record<string, CbRow[]>
  unitStatus: Record<string, { completeness: number; confidence: Confidence }>
  validated: boolean
  busy: boolean
  refining?: boolean
  onRegenUnit: (u: string) => void
  onEditProse: (rowId: string, text: string) => void
  openQuestions: ArtifactMessage[]
  answer: string
  onAnswerChange: (v: string) => void
  onAnswerSubmit: (questionSeq?: number) => void
}) {
  const textBlocks = sections['cb_text_blocks'] ?? []
  const getRow = (key: string) => textBlocks.find(r => r.field_key === key)
  const getText = (key: string) => getRow(key)?.text as string || '—'
  const getId = (key: string) => getRow(key)?.id as string | undefined

  const proseUnits = ['problem_context', 'value_hypothesis']
  const hasQuestion = openQuestions.length > 0

  return (
    <div className="border-b border-[var(--border-subtle)]">
      <div className="px-4 pt-3 pb-2 flex items-center justify-between bg-[var(--bg-elevated)]">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-[var(--text-primary)]">Problem Statement & Value Hypothesis</span>
          {refining && (
            <span className="inline-flex items-center gap-1 text-[10px] text-[var(--text-tertiary)]">
              <Loader2 size={10} className="animate-spin" /> Refining…
            </span>
          )}
          {!refining && hasQuestion && (
            <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 border border-amber-200 px-1.5 py-0.5 text-[9px] font-semibold text-amber-700">
              <AlertTriangle size={8} /> {openQuestions.length}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {proseUnits.map(uk => {
            const us = unitStatus[uk]
            if (!us) return null
            return <UnitScoreChip key={uk} completeness={us.completeness} confidence={us.confidence} />
          })}
          {!validated && (
            <button
              onClick={() => onRegenUnit('problem_context')}
              disabled={busy}
              className="p-1.5 rounded-md border border-[var(--border-default)] bg-[var(--bg-elevated)] text-[var(--text-secondary)] hover:border-[var(--accent)] hover:text-[var(--accent)] hover:bg-[var(--accent-subtle)] disabled:opacity-40 transition-colors"
              title="Regenerate"
            >
              <RotateCcw size={13} />
            </button>
          )}
        </div>
      </div>
      <div className="px-4 pb-4 space-y-4">
        {[
          { key: 'business_context', label: 'Business Context' },
          { key: 'problem_statement', label: 'Problem Statement' },
          { key: 'value_hypothesis_if', label: 'Value Hypothesis (If…)' },
          { key: 'value_hypothesis_then', label: '…Then' },
        ].map(({ key, label }) => (
          <ProseBlock
            key={key}
            label={label}
            text={getText(key)}
            rowId={getId(key)}
            validated={validated}
            busy={busy}
            onEdit={onEditProse}
          />
        ))}
        {hasQuestion && (
          <InlineClarification
            questions={openQuestions}
            answer={answer}
            onAnswerChange={onAnswerChange}
            onAnswerSubmit={onAnswerSubmit}
            busy={busy}
            validated={validated}
          />
        )}
      </div>
    </div>
  )
}

// ── Section Panel (typed tables) ──────────────────────────────────────────────

function SectionPanel({
  table, label, rows, unitKey, unitStatus, validated, busy, expanded, refining,
  onToggle, onRegenUnit, onEdit, onUnlock, onHistory, onDelete,
  openQuestions = [], answer = '', onAnswerChange, onAnswerSubmit,
}: {
  table: string
  label: string
  rows: CbRow[]
  unitKey: string
  unitStatus?: { completeness: number; confidence: Confidence }
  validated: boolean
  busy: boolean
  expanded: boolean
  refining?: boolean
  onToggle: () => void
  onRegenUnit: (u: string) => void
  onEdit: (r: CbRow) => void
  onUnlock: (id: string) => void
  onHistory: (r: CbRow) => void
  onDelete: (id: string) => void
  openQuestions?: ArtifactMessage[]
  answer?: string
  onAnswerChange?: (v: string) => void
  onAnswerSubmit?: (questionSeq?: number) => void
}) {
  const cols = TABLE_COLS[table] ?? []
  const activeRows = rows.filter(r => r.status === 'active')
  const hasQuestion = openQuestions.length > 0

  return (
    <div className="border-b border-[var(--border-subtle)]">
      <button
        onClick={onToggle}
        className="w-full px-4 py-2.5 flex items-center justify-between bg-[var(--bg-elevated)] hover:bg-[var(--bg-sunken)] transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-[var(--text-primary)]">{label}</span>
          <span className="text-[10px] text-[var(--text-tertiary)]">({activeRows.length})</span>
          {unitStatus && (
            <UnitScoreChip completeness={unitStatus.completeness} confidence={unitStatus.confidence} />
          )}
          {refining && (
            <span className="inline-flex items-center gap-1 text-[10px] text-[var(--text-tertiary)]">
              <Loader2 size={10} className="animate-spin" /> Refining…
            </span>
          )}
          {!refining && hasQuestion && (
            <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 border border-amber-200 px-1.5 py-0.5 text-[9px] font-semibold text-amber-700">
              <AlertTriangle size={8} /> {openQuestions.length}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          {!validated && unitKey !== 'gate' && (
            <button
              onClick={(e) => { e.stopPropagation(); onRegenUnit(unitKey) }}
              disabled={busy}
              className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] font-medium text-[var(--text-secondary)] border border-[var(--border-default)] bg-[var(--bg-surface)] hover:border-[var(--accent)] hover:text-[var(--accent)] disabled:opacity-40 transition-colors"
              title={`Regenerate ${label}`}
            >
              <RotateCcw size={11} />
            </button>
          )}
          {expanded ? <ChevronUp size={14} className="text-[var(--text-tertiary)]" /> : <ChevronDown size={14} className="text-[var(--text-tertiary)]" />}
        </div>
      </button>

      {expanded && (
        <div className="px-4 pb-3">
          {activeRows.length === 0 ? (
            <p className="text-sm text-[var(--text-tertiary)] italic py-2">No content yet — generate to populate.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-[var(--border-subtle)]">
                    {cols.map(c => (
                      <th key={c} className="text-left py-1.5 pr-3 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-tertiary)] capitalize">
                        {c.replace(/_/g, ' ')}
                      </th>
                    ))}
                    <th className="text-right text-[10px] font-semibold uppercase tracking-wider text-[var(--text-tertiary)]">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {activeRows.map(row => (
                    <tr key={row.id as string} className="border-b border-[var(--border-subtle)] last:border-0 hover:bg-[var(--bg-elevated)]">
                      {cols.map(c => (
                        <td key={c} className="py-2 pr-3 align-top text-[var(--text-primary)] leading-relaxed max-w-[200px]">
                          {c === 'quantifiable' ? (
                            <span className={`font-semibold ${row[c] ? 'text-success' : 'text-[var(--text-tertiary)]'}`}>
                              {row[c] ? 'Yes' : 'No'}
                            </span>
                          ) : (
                            <span className="whitespace-pre-wrap break-words">{String(row[c] ?? '—')}</span>
                          )}
                        </td>
                      ))}
                      <td className="py-2 align-top">
                        <div className="flex items-center gap-1.5 justify-end">
                          {row.is_locked ? (
                            <button
                              onClick={() => onUnlock(row.id as string)}
                              title="Unlock row"
                              className="p-1.5 rounded-md border border-warning/50 bg-warning/10 text-warning hover:bg-warning/20 transition-colors"
                            >
                              <Lock size={13} />
                            </button>
                          ) : !validated && (
                            <>
                              <button
                                onClick={() => onEdit(row)}
                                title="Edit"
                                className="p-1.5 rounded-md border border-[var(--border-default)] bg-[var(--bg-elevated)] text-[var(--text-secondary)] hover:border-[var(--accent)] hover:text-[var(--accent)] hover:bg-[var(--accent-subtle)] transition-colors"
                              >
                                <Edit2 size={13} />
                              </button>
                              <button
                                onClick={() => onDelete(row.id as string)}
                                title="Delete"
                                className="p-1.5 rounded-md border border-[var(--border-default)] bg-[var(--bg-elevated)] text-[var(--text-secondary)] hover:border-danger hover:text-danger hover:bg-danger/10 transition-colors"
                              >
                                <Trash2 size={13} />
                              </button>
                            </>
                          )}
                          <button
                            onClick={() => onHistory(row)}
                            title="Version history"
                            className="p-1.5 rounded-md border border-[var(--border-default)] bg-[var(--bg-elevated)] text-[var(--text-secondary)] hover:border-[var(--text-tertiary)] hover:text-[var(--text-primary)] transition-colors"
                          >
                            <History size={13} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {openQuestions.length > 0 && onAnswerChange && onAnswerSubmit && (
            <InlineClarification
              questions={openQuestions}
              answer={answer}
              onAnswerChange={onAnswerChange}
              onAnswerSubmit={onAnswerSubmit}
              busy={busy}
              validated={validated}
            />
          )}
        </div>
      )}
    </div>
  )
}

// ── Bubble ────────────────────────────────────────────────────────────────────

// ── Inline Clarification Card ─────────────────────────────────────────────────

function InlineClarification({
  questions, answer, onAnswerChange, onAnswerSubmit, busy, validated,
}: {
  questions: ArtifactMessage[]
  answer: string
  onAnswerChange: (v: string) => void
  onAnswerSubmit: (questionSeq?: number) => void
  busy: boolean
  validated: boolean
}) {
  const [expandedQ, setExpandedQ] = useState<string | null>(null)

  if (questions.length === 0) return null

  // Active = last by seq (matches backend desc-sorted questions[0])
  const activeQ = questions.at(-1)!
  const pendingQs = questions.slice(0, -1)

  return (
    <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50/70 overflow-hidden">
      <div className="px-4 py-2.5 border-b border-amber-200/80 flex items-center gap-2">
        <AlertTriangle size={12} className="text-amber-600 shrink-0" />
        <span className="text-[11px] font-semibold text-amber-800">
          SpecForge needs more information to refine this section
        </span>
        {questions.length > 1 && (
          <span className="ml-auto text-[10px] text-amber-600">{questions.length} questions</span>
        )}
      </div>

      {/* Active question */}
      <div className="px-4 pt-3 pb-2">
        <p className="text-sm font-medium text-amber-900 leading-snug">{activeQ.content}</p>
        {activeQ.meta?.why && (
          <p className="mt-1.5 text-[11px] text-amber-700 italic leading-snug">{activeQ.meta.why}</p>
        )}
        {activeQ.meta?.example && (
          <p className="mt-2 text-[11px] text-amber-800 bg-amber-100/80 rounded-md px-2.5 py-1.5 leading-snug border border-amber-200/60">
            <span className="font-semibold">Example: </span>{activeQ.meta.example}
          </p>
        )}
      </div>

      {/* Pending questions — collapsed, expandable */}
      {pendingQs.map(q => {
        const isOpen = expandedQ === q.id
        return (
          <button
            key={q.id}
            onClick={() => setExpandedQ(isOpen ? null : q.id)}
            className="w-full px-4 py-2 border-t border-amber-200/70 text-left hover:bg-amber-100/50 transition-colors"
          >
            <div className="flex items-start gap-2">
              <p className={`text-xs text-amber-700 flex-1 ${isOpen ? '' : 'line-clamp-1'}`}>{q.content}</p>
              {isOpen
                ? <ChevronUp size={11} className="shrink-0 mt-0.5 text-amber-500" />
                : <ChevronDown size={11} className="shrink-0 mt-0.5 text-amber-500" />}
            </div>
            {isOpen && q.meta?.why && (
              <p className="mt-1 text-[10px] text-amber-600 italic">{q.meta.why}</p>
            )}
          </button>
        )
      })}

      {/* Answer input */}
      {!validated && (
        <div className="px-4 py-3 border-t border-amber-200/70">
          <textarea
            value={answer}
            onChange={e => onAnswerChange(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) onAnswerSubmit(activeQ.seq) }}
            placeholder="Type your answer… (⌘+Enter to send)"
            rows={2}
            className="w-full resize-none rounded-lg border border-amber-200 bg-white/80 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-300 disabled:opacity-50"
            disabled={busy}
          />
          <div className="flex justify-end mt-2">
            <Button
              onClick={() => onAnswerSubmit(activeQ.seq)}
              disabled={busy || !answer.trim()}
              className="bg-amber-600 hover:bg-amber-700 text-white border-0"
            >
              {busy
                ? <><Loader2 size={13} className="animate-spin" /> Refining…</>
                : <><Send size={13} /> Submit answer</>}
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Clarification Panel ───────────────────────────────────────────────────────

const UNIT_LABELS: Record<string, string> = {
  problem_context:  'Problem Statement',
  value_hypothesis: 'Value Hypothesis',
  metrics:          'Metrics',
  capabilities:     'Capabilities',
  scope:            'Scope',
  milestones:       'Milestones',
}

function ClarificationPanel({
  messages, project, validated, busy, answer, onAnswerChange, onAnswerSubmit, threadEndRef,
}: {
  messages: ArtifactMessage[]
  project: ProjectDetail | undefined
  validated: boolean
  busy: boolean
  answer: string
  onAnswerChange: (v: string) => void
  onAnswerSubmit: () => void
  threadEndRef: React.RefObject<HTMLDivElement>
}) {
  const [expandedPending, setExpandedPending] = useState<string | null>(null)
  const [showResolved, setShowResolved] = useState(false)

  const userAnswers = messages.filter(m => m.role === 'user' && !m.meta?.is_initial_context)
  const lastAnswerSeq = userAnswers.at(-1)?.seq ?? -1
  const lastAnswer = userAnswers.at(-1)

  // Current open questions (after last answer), ascending by seq
  const currentQuestions = messages
    .filter(m => m.role === 'question' && m.seq > lastAnswerSeq)
    .sort((a, b) => a.seq - b.seq)

  // Active = last by seq (matches backend: desc-sorted questions[0])
  const activeQuestion = currentQuestions.at(-1) ?? null
  // Pending = all except the active one, shown collapsed below
  const pendingQuestions = currentQuestions.slice(0, -1)

  // Resolved history (questions + answers before last answer)
  const resolvedMessages = messages
    .filter(m => (m.role === 'question' || (m.role === 'user' && !m.meta?.is_initial_context)) && m.seq <= lastAnswerSeq)
    .sort((a, b) => a.seq - b.seq)

  const resolvedCount = messages.filter(m => m.role === 'question' && m.seq <= lastAnswerSeq).length
  const includedApps = project?.apps_in_scope?.filter(a => a.included) ?? []

  return (
    <div className="flex flex-col overflow-hidden border-r border-[var(--border-default)] bg-[var(--bg-base)]">

      {/* Header */}
      <div className="shrink-0 px-4 py-3 border-b border-[var(--border-subtle)] bg-[var(--bg-surface)]">
        <div className="flex items-center justify-between">
          <p className="text-xs font-semibold text-[var(--text-primary)]">Clarification Questions</p>
          <span className="text-[10px] text-[var(--text-tertiary)]">
            {currentQuestions.length > 0 ? `${currentQuestions.length} open` : ''}
            {currentQuestions.length > 0 && resolvedCount > 0 ? ' · ' : ''}
            {resolvedCount > 0 ? `${resolvedCount} resolved` : ''}
          </span>
        </div>
        <p className="text-[10px] text-[var(--text-tertiary)] mt-0.5">
          Answer one at a time — each answer refines its section, then the next question activates.
        </p>
      </div>

      {/* Grounded apps strip */}
      {includedApps.length > 0 && (
        <div className="shrink-0 border-b border-[var(--border-subtle)] bg-[var(--accent-subtle)]/40 px-3 py-2">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--accent-deep)] mb-1.5">
            Grounded in {includedApps.length} app{includedApps.length !== 1 ? 's' : ''}
          </p>
          <div className="flex flex-wrap gap-1.5">
            {includedApps.map(app => (
              <span key={app.app_id} className="inline-flex items-center gap-1 rounded-md bg-[var(--bg-surface)] border border-[var(--border-default)] px-2 py-0.5 text-[10px] text-[var(--text-secondary)]">
                <span className="w-1.5 h-1.5 rounded-full bg-[var(--accent)] inline-block" />
                {app.name}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Scroll area */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3">

        {/* Empty state */}
        {currentQuestions.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full gap-3 py-8 text-center px-4">
            <div className="w-10 h-10 rounded-xl bg-[var(--bg-elevated)] border border-[var(--border-default)] flex items-center justify-center">
              <CheckCircle2 size={18} className="text-success" strokeWidth={1.5} />
            </div>
            <div>
              <p className="text-sm font-medium text-[var(--text-primary)]">
                {resolvedCount > 0 ? 'All questions answered' : 'No open questions'}
              </p>
              <p className="text-xs text-[var(--text-tertiary)] mt-1 max-w-[200px]">
                {resolvedCount > 0
                  ? 'Your answers were incorporated. Regenerate any section to refine further.'
                  : 'SpecForge generated all sections with enough confidence. Regenerate a section to ask new questions.'}
              </p>
            </div>
          </div>
        )}

        {/* Last answer context pill */}
        {lastAnswer && currentQuestions.length > 0 && (
          <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-elevated)] px-3 py-2">
            <p className="text-[10px] font-semibold text-[var(--text-tertiary)] uppercase tracking-wide mb-0.5">Your last answer</p>
            <p className="text-xs text-[var(--text-secondary)] line-clamp-3">{lastAnswer.content}</p>
          </div>
        )}

        {/* ── Active question card ── */}
        {activeQuestion && (
          <div className="rounded-xl border-2 border-[var(--accent)] bg-[var(--bg-surface)] overflow-hidden shadow-sm">
            {/* Section refresh tag */}
            <div className="px-3 pt-3 flex items-center gap-2">
              <span className="inline-flex items-center gap-1 rounded-md bg-[var(--accent-subtle)] px-2 py-0.5 text-[10px] font-semibold text-[var(--accent)]">
                <RotateCcw size={9} />
                Will refresh: {activeQuestion.meta?.unit_key ? (UNIT_LABELS[activeQuestion.meta.unit_key] ?? activeQuestion.meta.unit_key) : 'section'}
              </span>
            </div>

            {/* Question text */}
            <div className="px-3 pt-2 pb-1">
              <p className="text-sm font-medium text-[var(--text-primary)] leading-snug">
                {activeQuestion.content}
              </p>
              {activeQuestion.meta?.why && (
                <p className="mt-1.5 text-[11px] text-[var(--text-secondary)] italic leading-snug">
                  {activeQuestion.meta.why}
                </p>
              )}
              {activeQuestion.meta?.example && (
                <p className="mt-2 text-[11px] text-[var(--text-secondary)] bg-[var(--bg-elevated)] rounded-md px-2.5 py-1.5 leading-snug border border-[var(--border-subtle)]">
                  <span className="font-semibold text-[var(--text-primary)]">Example: </span>{activeQuestion.meta.example}
                </p>
              )}
            </div>

            {/* Answer input */}
            {!validated && (
              <div className="px-3 pb-3 pt-2">
                <textarea
                  value={answer}
                  onChange={(e) => onAnswerChange(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) onAnswerSubmit() }}
                  placeholder="Type your answer… (⌘+Enter to send)"
                  rows={3}
                  className="w-full resize-none rounded-lg border border-[var(--border-default)] bg-[var(--bg-elevated)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent-ring)] disabled:opacity-50"
                  disabled={busy}
                />
                <div className="flex justify-end mt-2">
                  <Button onClick={onAnswerSubmit} disabled={busy || !answer.trim()}>
                    {busy
                      ? <><Loader2 size={13} className="animate-spin" /> Refining…</>
                      : <><Send size={13} /> Submit answer</>}
                  </Button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── Pending questions (collapsed, dimmed) ── */}
        {pendingQuestions.length > 0 && (
          <div className="space-y-1.5">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)] px-0.5">
              Up next · {pendingQuestions.length}
            </p>
            {pendingQuestions.map((q) => {
              const isOpen = expandedPending === q.id
              return (
                <button
                  key={q.id}
                  onClick={() => setExpandedPending(isOpen ? null : q.id)}
                  className="w-full text-left rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] px-3 py-2.5 opacity-55 hover:opacity-80 transition-opacity"
                >
                  <div className="flex items-start justify-between gap-2">
                    <p className={`text-xs text-[var(--text-secondary)] ${isOpen ? '' : 'line-clamp-2'}`}>
                      {q.content}
                    </p>
                    {isOpen
                      ? <ChevronUp size={12} className="shrink-0 mt-0.5 text-[var(--text-tertiary)]" />
                      : <ChevronDown size={12} className="shrink-0 mt-0.5 text-[var(--text-tertiary)]" />}
                  </div>
                  {isOpen && q.meta?.why && (
                    <p className="mt-1.5 text-[10px] text-[var(--text-tertiary)] italic leading-snug">{q.meta.why}</p>
                  )}
                  {q.meta?.unit_key && (
                    <p className="mt-1.5 text-[10px] text-[var(--text-tertiary)]">
                      → {UNIT_LABELS[q.meta.unit_key] ?? q.meta.unit_key}
                    </p>
                  )}
                </button>
              )
            })}
          </div>
        )}

        {/* ── Resolved history toggle ── */}
        {resolvedCount > 0 && (
          <div>
            <button
              onClick={() => setShowResolved(v => !v)}
              className="flex items-center gap-1 text-[11px] text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] transition-colors px-0.5"
            >
              <ChevronRight size={11} className={`transition-transform ${showResolved ? 'rotate-90' : ''}`} />
              {resolvedCount} resolved question{resolvedCount !== 1 ? 's' : ''}
            </button>
            {showResolved && (
              <div className="mt-2 space-y-2">
                {resolvedMessages.map((m) => <ArtifactBubble key={m.id} m={m} />)}
              </div>
            )}
          </div>
        )}

        <div ref={threadEndRef} />
      </div>
    </div>
  )
}

function ArtifactBubble({ m }: { m: ArtifactMessage }) {
  if (m.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-2xl rounded-br-sm bg-[var(--accent)] px-3 py-2 text-sm text-white">
          {m.content}
        </div>
      </div>
    )
  }
  if (m.role === 'question') {
    return (
      <div className="flex justify-start">
        <div className="max-w-[88%] rounded-2xl rounded-bl-sm bg-[var(--accent-subtle)] px-3 py-2 text-sm text-[var(--accent-deep)]">
          <span className="mr-1 font-semibold">Q:</span>
          {m.content}
          {m.meta?.why && (
            <p className="mt-1 text-[10px] text-[var(--accent-deep)]/60 italic">{m.meta.why}</p>
          )}
        </div>
      </div>
    )
  }
  if (m.role === 'synthesis') {
    return (
      <div className="flex justify-start">
        <div className="max-w-[88%] rounded-2xl rounded-bl-sm bg-[var(--bg-surface)] border border-[var(--border-default)] px-3 py-2 text-sm text-[var(--text-secondary)]">
          <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-[var(--accent)] mb-1">
            <Sparkles size={10} /> AI synthesis
          </span>
          <p>{m.content}</p>
          {m.citations && m.citations.length > 0 && (
            <div className="mt-1.5 flex flex-wrap gap-1">
              {m.citations.slice(0, 3).map((c, i) => (
                <span key={i} className="rounded border border-[var(--border-default)] bg-[var(--bg-base)] px-1.5 py-0.5 text-[10px] text-[var(--text-tertiary)]">
                  {c.doc_name || c.section_title || 'source'}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    )
  }
  return null
}

// ── Row Edit Modal ────────────────────────────────────────────────────────────

const _SHORT_COLS = new Set(['field_key', 'dimension', 'metric', 'capability', 'milestone', 'target', 'gate_status', 'kind'])
const _LONG_COLS  = new Set(['text', 'description', 'detail', 'notes'])
function _fieldRows(col: string) {
  if (_SHORT_COLS.has(col)) return 1
  if (_LONG_COLS.has(col))  return 6
  return 3
}

function RowEditModal({
  table, row, onClose, onSave,
}: {
  table: string
  row: CbRow
  onClose: () => void
  onSave: (fields: Record<string, unknown>) => void
}) {
  const cols = TABLE_COLS[table] ?? []
  const [fields, setFields] = useState<Record<string, unknown>>(
    Object.fromEntries(cols.map(c => [c, row[c]]))
  )

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4" onClick={onClose}>
      <div
        className="w-full max-w-2xl bg-[var(--bg-surface)] rounded-2xl shadow-2xl border border-[var(--border-default)] flex flex-col max-h-[90vh]"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-6 pt-5 pb-4 border-b border-[var(--border-subtle)] shrink-0">
          <p className="text-xs font-semibold uppercase tracking-widest text-[var(--text-tertiary)] mb-0.5">Edit row</p>
          <h3 className="text-base font-semibold text-[var(--text-primary)]">{(row.row_key as string).replace(/_/g, ' ')}</h3>
        </div>

        {/* Fields — scrollable */}
        <div className="overflow-y-auto px-6 py-5 space-y-5 flex-1">
          {cols.map(c => (
            <div key={c}>
              <label className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-tertiary)] block mb-2">
                {c.replace(/_/g, ' ')}
              </label>
              {c === 'quantifiable' ? (
                <div className="flex gap-3">
                  {['true', 'false'].map(val => (
                    <button
                      key={val}
                      type="button"
                      onClick={() => setFields(f => ({ ...f, [c]: val === 'true' }))}
                      className={`flex-1 py-2 rounded-lg border text-sm font-medium transition-colors ${
                        String(fields[c]) === val
                          ? val === 'true'
                            ? 'border-[var(--accent)] bg-[var(--accent-subtle)] text-[var(--accent)]'
                            : 'border-[var(--border-default)] bg-[var(--bg-elevated)] text-[var(--text-primary)]'
                          : 'border-[var(--border-subtle)] bg-transparent text-[var(--text-tertiary)] hover:border-[var(--border-default)]'
                      }`}
                    >
                      {val === 'true' ? 'Yes — quantifiable' : 'No — qualitative'}
                    </button>
                  ))}
                </div>
              ) : (
                <textarea
                  value={String(fields[c] ?? '')}
                  onChange={e => setFields(f => ({ ...f, [c]: e.target.value }))}
                  rows={_fieldRows(c)}
                  className="w-full resize-y rounded-xl border border-[var(--border-default)] bg-[var(--bg-base)] px-4 py-3 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] leading-relaxed focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/40 focus:border-[var(--accent)] transition-colors"
                />
              )}
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-[var(--border-subtle)] flex justify-end gap-2 shrink-0">
          <Button variant="outline" size="sm" onClick={onClose}>Cancel</Button>
          <Button size="sm" onClick={() => onSave(fields)}>Save & Lock</Button>
        </div>
      </div>
    </div>
  )
}

// ── History Drawer ────────────────────────────────────────────────────────────

function HistoryDrawer({
  rowKey, table, history, onClose, onRestore,
}: {
  rowKey: string
  table: string
  history: CbRow[]
  onClose: () => void
  onRestore: (rowId: string, version: number) => void
}) {
  const cols = TABLE_COLS[table] ?? []

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} />
      <div className="relative w-full max-w-md bg-[var(--bg-surface)] h-full shadow-2xl overflow-y-auto border-l border-[var(--border-default)]">
        <div className="sticky top-0 bg-[var(--bg-surface)] border-b border-[var(--border-default)] px-4 py-3 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-[var(--text-primary)]">Row History</h3>
            <p className="text-[11px] text-[var(--text-tertiary)]">{rowKey}</p>
          </div>
          <button onClick={onClose} className="text-[var(--text-tertiary)] hover:text-[var(--text-primary)] p-1 rounded">✕</button>
        </div>
        <div className="p-4 space-y-4">
          {history.length === 0 && (
            <p className="text-sm text-[var(--text-tertiary)]">No history yet.</p>
          )}
          {history.map(row => (
            <div key={row.id as string} className={`rounded-xl border p-3 ${row.is_current ? 'border-[var(--accent)] bg-[var(--accent-subtle)]/20' : 'border-[var(--border-default)] bg-[var(--bg-base)]'}`}>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-1.5">
                  <span className="text-[10px] font-semibold text-[var(--text-tertiary)]">v{row.version}</span>
                  {row.is_current && <Badge variant="success" className="text-[9px]">current</Badge>}
                  <Badge variant={row.source === 'human' ? 'warning' : 'default'} className="text-[9px]">
                    {row.source}
                  </Badge>
                  {row.is_locked && <Lock size={10} className="text-warning" />}
                </div>
                {!row.is_current && (
                  <button
                    onClick={() => onRestore(row.id as string, row.version)}
                    className="text-[10px] text-[var(--accent)] hover:underline"
                  >
                    Restore
                  </button>
                )}
              </div>
              <div className="space-y-1">
                {cols.map(c => (
                  <div key={c} className="flex gap-2">
                    <span className="text-[10px] text-[var(--text-tertiary)] w-24 shrink-0">{c.replace(/_/g, ' ')}</span>
                    <span className="text-[11px] text-[var(--text-primary)] break-words">
                      {c === 'quantifiable' ? (row[c] ? 'Yes' : 'No') : String(row[c] ?? '—')}
                    </span>
                  </div>
                ))}
              </div>
              <p className="mt-2 text-[9px] text-[var(--text-tertiary)]">{row.created_at}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
