'use client'
import { useState, useRef, useEffect } from 'react'
import {
  ArrowLeft, CheckCircle2, Send, Sparkles, RotateCcw, Lock,
  History, Download, ChevronDown, ChevronUp, Edit2, Building2, Loader2,
} from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/app/components/ui/button'
import { Badge } from '@/app/components/ui/badge'
import { Skeleton } from '@/app/components/Skeleton'
import { api } from '@/lib/api'
import { useArtifact } from '@/lib/hooks/useArtifact'
import { useProject } from '@/lib/hooks/useProject'
import type { ArtifactMessage, CbRow, Confidence } from '@/lib/types'

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

  const doc = detail?.document ?? null
  const messages = detail?.messages ?? []
  const sections = detail?.sections ?? {}
  const unitStatus = doc?.unit_status ?? {}
  const generated = doc !== null
  const validated = doc?.status === 'validated'

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

  const handleGenerate = () => run(
    () => api.artifacts.generate(projectId, artifactType, { context: initContext || undefined }),
    `${typeLabel} generated`,
  )

  const handleValidate = () => run(async () => {
    const result = await api.artifacts.validate(projectId, artifactType)
    if (!result.ok) {
      toast.error(`Validation failed:\n${result.failures.join('\n')}`)
      throw new Error('Validation failed')
    }
    return result
  }, `${typeLabel} validated`)

  async function handleAnswer() {
    if (!answer.trim() || busy) return
    const a = answer.trim()
    setAnswer('')
    await run(() => api.artifacts.answer(projectId, artifactType, a), 'Answer incorporated')
  }

  async function handleRegenUnit(unitKey: string) {
    await run(
      () => api.artifacts.regenerateUnit(projectId, artifactType, unitKey),
      `${unitKey} regenerated`,
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
      ) : !generated ? (
        /* ── Empty state ── */
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
          {project?.apps_in_scope && project.apps_in_scope.length > 0 && (
            <div className="flex items-center gap-1.5 text-xs text-[var(--text-tertiary)] bg-[var(--bg-surface)] border border-[var(--border-default)] rounded-lg px-3 py-2">
              <Building2 size={13} className="text-[var(--accent)]" />
              Grounded in {project.apps_in_scope.length} in-scope app{project.apps_in_scope.length !== 1 ? 's' : ''}
            </div>
          )}
          <div className="w-full max-w-md text-left">
            <label className="block text-xs font-semibold text-[var(--text-secondary)] mb-1.5">
              Describe your initiative <span className="font-normal text-[var(--text-tertiary)]">(optional)</span>
            </label>
            <textarea
              value={initContext}
              onChange={(e) => setInitContext(e.target.value)}
              rows={3}
              placeholder="e.g. We're building a real-time payment gateway for SME customers using SEPA and domestic ACH rails…"
              className="w-full resize-y rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
            />
          </div>
          <Button onClick={handleGenerate} disabled={busy} size="lg">
            <Sparkles size={15} />
            {busy ? 'Generating…' : `Generate ${typeLabel}`}
          </Button>
        </div>
      ) : (
        /* ── Main two-column builder ── */
        <div className="flex-1 grid grid-cols-1 lg:grid-cols-[minmax(0,360px)_1fr] overflow-hidden">
          {/* ── Left: Q&A Thread ── */}
          <div className="flex flex-col overflow-hidden border-r border-[var(--border-default)] bg-[var(--bg-base)]">
            {/* Impacted apps strip */}
            {project?.apps_in_scope && project.apps_in_scope.filter(a => a.included).length > 0 && (
              <div className="shrink-0 border-b border-[var(--border-subtle)] bg-[var(--accent-subtle)]/40 px-3 py-2">
                <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--accent-deep)] mb-1.5">
                  Grounded in {project.apps_in_scope.filter(a => a.included).length} app{project.apps_in_scope.filter(a => a.included).length !== 1 ? 's' : ''}
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {project.apps_in_scope.filter(a => a.included).map(app => (
                    <span key={app.app_id} className="inline-flex items-center gap-1 rounded-md bg-[var(--bg-surface)] border border-[var(--border-default)] px-2 py-0.5 text-[10px] text-[var(--text-secondary)]">
                      <span className="w-1.5 h-1.5 rounded-full bg-[var(--accent)] inline-block" />
                      {app.name}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Thread */}
            <div className="flex-1 overflow-y-auto p-3 space-y-2.5">
              {messages.map((m) => <ArtifactBubble key={m.id} m={m} />)}
              <div ref={threadEndRef} />
            </div>

            {/* Composer */}
            {!validated && (
              <div className="shrink-0 border-t border-[var(--border-default)] p-3">
                <div className="flex items-end gap-2">
                  <textarea
                    value={answer}
                    onChange={(e) => setAnswer(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleAnswer() }}
                    placeholder="Answer an open question… (⌘+Enter)"
                    rows={2}
                    className="flex-1 resize-none rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent)] disabled:opacity-50"
                    disabled={busy}
                  />
                  <Button onClick={handleAnswer} disabled={busy || !answer.trim()} className="h-9">
                    <Send size={14} />
                  </Button>
                </div>
              </div>
            )}
          </div>

          {/* ── Right: Structured sections ── */}
          <div className="overflow-y-auto bg-[var(--bg-base)]">
            {/* Prose blocks (business context + problem statement + value hypothesis) */}
            <ProseSection
              sections={sections}
              unitStatus={unitStatus}
              validated={validated}
              busy={busy}
              onRegenUnit={handleRegenUnit}
            />

            {/* Typed tables */}
            {SECTION_ORDER.filter(t => t !== 'cb_text_blocks').map(table => {
              const rows = sections[table] ?? []
              const unitKey = UNIT_FOR_TABLE[table]
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
                />
              )
            })}
          </div>
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
    </div>
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

function ProseSection({
  sections, unitStatus, validated, busy, onRegenUnit,
}: {
  sections: Record<string, CbRow[]>
  unitStatus: Record<string, { completeness: number; confidence: Confidence }>
  validated: boolean
  busy: boolean
  onRegenUnit: (u: string) => void
}) {
  const textBlocks = sections['cb_text_blocks'] ?? []
  const getBlock = (key: string) => textBlocks.find(r => r.field_key === key)?.text as string || '—'

  const proseUnits = ['problem_context', 'value_hypothesis']

  return (
    <div className="border-b border-[var(--border-subtle)]">
      <div className="px-4 pt-3 pb-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-[var(--text-primary)]">Problem Statement & Value Hypothesis</span>
        </div>
        <div className="flex items-center gap-2">
          {proseUnits.map(uk => {
            const us = unitStatus[uk]
            if (!us) return null
            return (
              <div key={uk} className="flex items-center gap-1">
                <span className={`text-[10px] font-semibold ${completenessColor(us.completeness)}`}>
                  {us.completeness}%
                </span>
                <Badge variant={CONF_VARIANT[us.confidence]} className="text-[9px] py-0">{us.confidence}</Badge>
              </div>
            )
          })}
          {!validated && (
            <button
              onClick={() => onRegenUnit('problem_context')}
              disabled={busy}
              className="p-1 rounded text-[var(--text-tertiary)] hover:text-[var(--accent)] hover:bg-[var(--accent-subtle)] disabled:opacity-40"
              title="Regenerate problem context"
            >
              <RotateCcw size={12} />
            </button>
          )}
        </div>
      </div>
      <div className="px-4 pb-4 space-y-3">
        {[
          { key: 'business_context', label: 'Business Context' },
          { key: 'problem_statement', label: 'Problem Statement' },
          { key: 'value_hypothesis_if', label: 'Value Hypothesis (If…)' },
          { key: 'value_hypothesis_then', label: '…Then' },
        ].map(({ key, label }) => (
          <div key={key}>
            <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)] mb-1">{label}</p>
            <p className="text-sm text-[var(--text-primary)] leading-relaxed whitespace-pre-wrap">{getBlock(key)}</p>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Section Panel (typed tables) ──────────────────────────────────────────────

function SectionPanel({
  table, label, rows, unitKey, unitStatus, validated, busy, expanded,
  onToggle, onRegenUnit, onEdit, onUnlock, onHistory,
}: {
  table: string
  label: string
  rows: CbRow[]
  unitKey: string
  unitStatus?: { completeness: number; confidence: Confidence }
  validated: boolean
  busy: boolean
  expanded: boolean
  onToggle: () => void
  onRegenUnit: (u: string) => void
  onEdit: (r: CbRow) => void
  onUnlock: (id: string) => void
  onHistory: (r: CbRow) => void
}) {
  const cols = TABLE_COLS[table] ?? []
  const activeRows = rows.filter(r => r.status === 'active')

  return (
    <div className="border-b border-[var(--border-subtle)]">
      <button
        onClick={onToggle}
        className="w-full px-4 py-2.5 flex items-center justify-between hover:bg-[var(--bg-elevated)] transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-[var(--text-primary)]">{label}</span>
          <span className="text-[10px] text-[var(--text-tertiary)]">({activeRows.length})</span>
          {unitStatus && (
            <div className="flex items-center gap-1">
              <span className={`text-[10px] font-semibold ${completenessColor(unitStatus.completeness)}`}>
                {unitStatus.completeness}%
              </span>
              <Badge variant={CONF_VARIANT[unitStatus.confidence]} className="text-[9px] py-0">
                {unitStatus.confidence}
              </Badge>
            </div>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          {!validated && unitKey !== 'gate' && (
            <button
              onClick={(e) => { e.stopPropagation(); onRegenUnit(unitKey) }}
              disabled={busy}
              className="p-1 rounded text-[var(--text-tertiary)] hover:text-[var(--accent)] hover:bg-[var(--accent-subtle)] disabled:opacity-40"
              title={`Regenerate ${unitKey}`}
            >
              <RotateCcw size={12} />
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
                    <tr key={row.id as string} className="border-b border-[var(--border-subtle)] last:border-0 hover:bg-[var(--bg-elevated)] group">
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
                        <div className="flex items-center gap-1 justify-end opacity-0 group-hover:opacity-100 transition-opacity">
                          {row.is_locked ? (
                            <button onClick={() => onUnlock(row.id as string)} title="Unlock" className="p-1 rounded hover:bg-warning-bg text-warning">
                              <Lock size={12} />
                            </button>
                          ) : (
                            !validated && (
                              <button onClick={() => onEdit(row)} title="Edit" className="p-1 rounded hover:bg-[var(--accent-subtle)] text-[var(--text-tertiary)] hover:text-[var(--accent)]">
                                <Edit2 size={12} />
                              </button>
                            )
                          )}
                          <button onClick={() => onHistory(row)} title="History" className="p-1 rounded hover:bg-[var(--bg-elevated)] text-[var(--text-tertiary)]">
                            <History size={12} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Bubble ────────────────────────────────────────────────────────────────────

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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div
        className="w-full max-w-lg bg-[var(--bg-surface)] rounded-xl shadow-2xl border border-[var(--border-default)] p-5"
        onClick={e => e.stopPropagation()}
      >
        <h3 className="text-sm font-semibold mb-4 text-[var(--text-primary)]">
          Edit row <span className="text-[var(--text-tertiary)]">({row.row_key as string})</span>
        </h3>
        <div className="space-y-3 max-h-96 overflow-y-auto">
          {cols.map(c => (
            <div key={c}>
              <label className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-tertiary)] block mb-1">
                {c.replace(/_/g, ' ')}
              </label>
              {c === 'quantifiable' ? (
                <select
                  value={fields[c] ? 'true' : 'false'}
                  onChange={e => setFields(f => ({ ...f, [c]: e.target.value === 'true' }))}
                  className="w-full rounded-lg border border-[var(--border-default)] bg-[var(--bg-base)] px-3 py-2 text-sm"
                >
                  <option value="true">Yes</option>
                  <option value="false">No</option>
                </select>
              ) : (
                <textarea
                  value={String(fields[c] ?? '')}
                  onChange={e => setFields(f => ({ ...f, [c]: e.target.value }))}
                  rows={2}
                  className="w-full resize-y rounded-lg border border-[var(--border-default)] bg-[var(--bg-base)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
                />
              )}
            </div>
          ))}
        </div>
        <div className="flex justify-end gap-2 mt-4">
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
