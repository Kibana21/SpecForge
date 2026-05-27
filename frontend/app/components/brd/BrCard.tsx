'use client'
import { useState } from 'react'
import { Edit2, History, Lock, RotateCcw, ChevronDown, ChevronUp, AlertTriangle, Check, X, Trash2, Clock } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { MOSCOW_COLORS, RISK_SEVERITY_COLORS } from '@/lib/brd-manifest'
import { TraceChip } from './TraceChip'
import { api } from '@/lib/api'
import type {
  BrdBusinessRequirementRow,
  BrdObjectiveRow,
  BrdRiskRow,
  BrdKpiRow,
  BrdTraceabilityRow,
  BrdFinding,
} from '@/lib/types'

type Variant = 'br' | 'objective' | 'risk' | 'kpi'

type RowForVariant<V extends Variant> =
  V extends 'br' ? BrdBusinessRequirementRow :
  V extends 'objective' ? BrdObjectiveRow :
  V extends 'risk' ? BrdRiskRow :
  BrdKpiRow

const TABLE_FOR_VARIANT: Record<Variant, string> = {
  br: 'brd_business_requirements',
  objective: 'brd_objectives',
  risk: 'brd_risks',
  kpi: 'brd_kpis',
}

interface BrCardProps<V extends Variant> {
  variant: V
  row: RowForVariant<V>
  traces?: BrdTraceabilityRow[]
  projectId: string
  onMutate: () => void
  finding?: BrdFinding
}

function MoSCoWPill({ priority }: { priority: 'must' | 'should' | 'could' | 'wont' }) {
  const c = MOSCOW_COLORS[priority]
  return (
    <span className={cn('inline-flex items-center rounded border px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide', c.bg, c.text, c.border)}>
      {priority}
    </span>
  )
}

function RiskSeverityPill({ severity }: { severity: 'critical' | 'high' | 'medium' | 'low' }) {
  return (
    <span className={cn('inline-flex items-center rounded border px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide', RISK_SEVERITY_COLORS[severity])}>
      {severity}
    </span>
  )
}

// ── History panel ─────────────────────────────────────────────────────────────

function HistoryPanel({ projectId, table, rowId, currentVersion, onClose }: {
  projectId: string; table: string; rowId: string; currentVersion: number; onClose: () => void
}) {
  const [history, setHistory] = useState<{ id: string; version: number; source: string; created_at: string }[] | null>(null)
  const [loading, setLoading] = useState(false)

  useState(() => {
    setLoading(true)
    api.brd.rowHistory(projectId, table, rowId)
      .then((h) => setHistory(h as { id: string; version: number; source: string; created_at: string }[]))
      .catch(() => toast.error('Failed to load history'))
      .finally(() => setLoading(false))
  })

  return (
    <div className="border-t border-[var(--border-default)] bg-[var(--bg-surface)]">
      <div className="flex items-center justify-between px-3 py-2 border-b border-[var(--border-subtle)]">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)]">Version history</p>
        <button onClick={onClose} className="text-[var(--text-tertiary)] hover:text-[var(--text-primary)]"><X size={13} /></button>
      </div>
      <div className="max-h-40 overflow-y-auto">
        {loading && <p className="px-3 py-2 text-xs text-[var(--text-tertiary)]">Loading…</p>}
        {history?.map((h) => (
          <div key={h.id} className={cn('flex items-center gap-2 px-3 py-2 border-b border-[var(--border-subtle)] last:border-0', h.version === currentVersion && 'bg-[var(--accent-subtle)]/30')}>
            <span className="text-[10px] font-semibold text-[var(--text-tertiary)]">v{h.version}</span>
            <span className={cn('text-[9px] rounded px-1 py-0.5', h.source === 'human' ? 'bg-blue-100 text-blue-700' : 'bg-[var(--bg-elevated)] text-[var(--text-tertiary)]')}>{h.source}</span>
            <span className="flex-1 text-[10px] text-[var(--text-tertiary)]">{new Date(h.created_at).toLocaleString()}</span>
            {h.version === currentVersion && <span className="text-[9px] text-[var(--accent)] font-semibold">current</span>}
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Edit form ─────────────────────────────────────────────────────────────────

function EditForm<V extends Variant>({ variant, row, projectId, onSaved, onCancel }: {
  variant: V; row: RowForVariant<V>; projectId: string; onSaved: () => void; onCancel: () => void
}) {
  const table = TABLE_FOR_VARIANT[variant]
  const initDraft = (): Record<string, string> => {
    if (variant === 'br') {
      const br = row as BrdBusinessRequirementRow
      return { title: br.title ?? '', description: br.description ?? '', rationale: br.rationale ?? '', priority: br.priority ?? 'must', category: br.category ?? '' }
    }
    if (variant === 'objective') {
      const obj = row as BrdObjectiveRow
      return { statement: obj.statement ?? '', category: obj.category ?? '', priority: obj.priority ?? 'must', owner: obj.owner ?? '' }
    }
    if (variant === 'risk') {
      const risk = row as BrdRiskRow
      return { risk: risk.risk ?? '', description: risk.description ?? '', severity: risk.severity ?? 'medium', likelihood: risk.likelihood ?? 'medium', mitigation: risk.mitigation ?? '', owner: risk.owner ?? '' }
    }
    if (variant === 'kpi') {
      const kpi = row as BrdKpiRow
      return { kpi_name: kpi.kpi_name ?? '', description: kpi.description ?? '', baseline: kpi.baseline ?? '', target: kpi.target ?? '', timeframe: kpi.timeframe ?? '', data_source: kpi.data_source ?? '' }
    }
    return {}
  }
  const [draft, setDraft] = useState<Record<string, string>>(initDraft)
  const [saving, setSaving] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [deleting, setDeleting] = useState(false)

  function field(key: string, label: string, type: 'text' | 'textarea' | 'select' = 'text', options?: string[]) {
    return (
      <div key={key}>
        <label className="block text-[10px] font-semibold uppercase tracking-wider text-[var(--text-tertiary)] mb-1">{label}</label>
        {type === 'textarea' ? (
          <textarea
            rows={3}
            value={draft[key] ?? ''}
            onChange={(e) => setDraft((d) => ({ ...d, [key]: e.target.value }))}
            className="w-full resize-none rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] px-3 py-2 text-sm text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-ring)]"
          />
        ) : type === 'select' && options ? (
          <select
            value={draft[key] ?? ''}
            onChange={(e) => setDraft((d) => ({ ...d, [key]: e.target.value }))}
            className="w-full rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] px-3 py-2 text-sm text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-ring)]"
          >
            {options.map((o) => <option key={o} value={o}>{o}</option>)}
          </select>
        ) : (
          <input
            type="text"
            value={draft[key] ?? ''}
            onChange={(e) => setDraft((d) => ({ ...d, [key]: e.target.value }))}
            className="w-full rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] px-3 py-2 text-sm text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-ring)]"
          />
        )}
      </div>
    )
  }

  function renderFields() {
    if (variant === 'br') return (
      <>
        {field('title', 'Title')}
        {field('description', 'Description', 'textarea')}
        {field('rationale', 'Rationale', 'textarea')}
        {field('priority', 'Priority', 'select', ['must', 'should', 'could', 'wont'])}
        {field('category', 'Category')}
      </>
    )
    if (variant === 'objective') return (
      <>
        {field('statement', 'Statement', 'textarea')}
        {field('category', 'Category')}
        {field('priority', 'Priority', 'select', ['must', 'should', 'could', 'wont'])}
        {field('owner', 'Owner')}
      </>
    )
    if (variant === 'risk') return (
      <>
        {field('risk', 'Risk title')}
        {field('description', 'Description', 'textarea')}
        {field('severity', 'Severity', 'select', ['critical', 'high', 'medium', 'low'])}
        {field('likelihood', 'Likelihood', 'select', ['high', 'medium', 'low'])}
        {field('mitigation', 'Mitigation', 'textarea')}
        {field('owner', 'Owner')}
      </>
    )
    if (variant === 'kpi') return (
      <>
        {field('kpi_name', 'KPI name')}
        {field('description', 'Description', 'textarea')}
        {field('baseline', 'Baseline')}
        {field('target', 'Target')}
        {field('timeframe', 'Timeframe')}
        {field('data_source', 'Data source')}
      </>
    )
    return null
  }

  async function handleSave() {
    setSaving(true)
    try {
      await api.brd.editRow(projectId, table, row.id, draft, false)
      toast.success('Saved')
      onSaved()
    } catch {
      toast.error('Save failed')
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    setDeleting(true)
    try {
      await api.brd.deleteRow(projectId, table, row.id)
      toast.success('Deleted')
      onSaved()
    } catch {
      toast.error('Delete failed')
    } finally {
      setDeleting(false)
      setConfirmDelete(false)
    }
  }

  return (
    <div className="border-t border-[var(--accent)]/30 bg-[var(--accent-subtle)]/10 px-3 py-3 space-y-3">
      {renderFields()}
      <div className="flex items-center gap-2 pt-1">
        <button
          onClick={handleSave}
          disabled={saving}
          className="inline-flex items-center gap-1 rounded-lg bg-[var(--accent)] px-3 py-1.5 text-xs font-semibold text-white hover:bg-[var(--accent-hover)] disabled:opacity-50 transition-colors"
        >
          {saving ? '…' : <><Check size={12} /> Save</>}
        </button>
        <button
          onClick={onCancel}
          className="inline-flex items-center gap-1 rounded-lg border border-[var(--border-default)] bg-[var(--bg-elevated)] px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-sunken)] transition-colors"
        >
          <X size={12} /> Cancel
        </button>
        <div className="flex-1" />
        {!confirmDelete ? (
          <button
            onClick={() => setConfirmDelete(true)}
            className="inline-flex items-center gap-1 rounded-lg border border-[var(--border-default)] px-2 py-1.5 text-xs text-[var(--text-tertiary)] hover:text-[var(--status-danger)] hover:border-[var(--status-danger-border)] hover:bg-[var(--status-danger-bg)] transition-colors"
          >
            <Trash2 size={11} /> Delete
          </button>
        ) : (
          <div className="flex items-center gap-1">
            <button
              onClick={handleDelete}
              disabled={deleting}
              className="rounded-lg px-2 py-1.5 text-xs font-semibold bg-[var(--status-danger-bg)] text-[var(--status-danger)] border border-[var(--status-danger-border)] disabled:opacity-50"
            >
              {deleting ? '…' : 'Confirm delete'}
            </button>
            <button onClick={() => setConfirmDelete(false)} className="rounded-md p-1 text-[var(--text-tertiary)] hover:text-[var(--text-primary)]">
              <X size={11} />
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Main BrCard ───────────────────────────────────────────────────────────────

export function BrCard<V extends Variant>({
  variant,
  row,
  traces = [],
  projectId,
  onMutate,
  finding,
}: BrCardProps<V>) {
  const [descOpen, setDescOpen] = useState(true)
  const [acOpen, setAcOpen] = useState(false)
  const [tracesOpen, setTracesOpen] = useState(false)
  const [editing, setEditing] = useState(false)
  const [showHistory, setShowHistory] = useState(false)

  const isHumanEdited = row.source === 'human'
  const isLocked = row.is_locked
  const hasFinding = !!finding

  function renderHeaderMeta() {
    if (variant === 'br') {
      const r = row as BrdBusinessRequirementRow
      return (
        <>
          <MoSCoWPill priority={r.priority} />
          {r.category && (
            <span className="text-[10px] text-[var(--text-tertiary)] border border-[var(--border-subtle)] rounded px-1.5 py-0.5 bg-[var(--bg-elevated)]">
              {r.category}
            </span>
          )}
          {r.completeness > 0 && (
            <span className={cn('text-[10px] font-medium', r.completeness >= 90 ? 'text-[var(--status-success)]' : r.completeness >= 60 ? 'text-[var(--status-warning)]' : 'text-[var(--status-danger)]')}>
              {r.completeness}%
            </span>
          )}
        </>
      )
    }
    if (variant === 'objective') {
      const r = row as BrdObjectiveRow
      return (
        <>
          <MoSCoWPill priority={r.priority} />
          {r.category && <span className="text-[10px] text-[var(--text-tertiary)] border border-[var(--border-subtle)] rounded px-1.5 py-0.5 bg-[var(--bg-elevated)]">{r.category}</span>}
        </>
      )
    }
    if (variant === 'risk') {
      const r = row as BrdRiskRow
      return (
        <>
          <RiskSeverityPill severity={r.severity} />
          <span className="text-[10px] text-[var(--text-tertiary)]">likelihood: {r.likelihood}</span>
        </>
      )
    }
    if (variant === 'kpi') {
      const r = row as BrdKpiRow
      return r.timeframe ? (
        <span className="text-[10px] text-[var(--text-tertiary)] border border-[var(--border-subtle)] rounded px-1.5 py-0.5 bg-[var(--bg-elevated)]">{r.timeframe}</span>
      ) : null
    }
    return null
  }

  function renderTitle() {
    if (variant === 'br') return (row as BrdBusinessRequirementRow).title
    if (variant === 'objective') return (row as BrdObjectiveRow).statement
    if (variant === 'risk') return (row as BrdRiskRow).risk
    if (variant === 'kpi') return (row as BrdKpiRow).kpi_name
    return ''
  }

  function renderBody() {
    if (variant === 'br') {
      const r = row as BrdBusinessRequirementRow
      return (
        <div className="space-y-1">
          <p className="text-sm text-[var(--text-primary)] leading-relaxed whitespace-pre-wrap">{r.description}</p>
          {r.rationale && (
            <p className="text-xs text-[var(--text-secondary)] italic">
              <span className="font-medium not-italic">Rationale: </span>{r.rationale}
            </p>
          )}
        </div>
      )
    }
    if (variant === 'objective') {
      const r = row as BrdObjectiveRow
      return r.owner ? <p className="text-xs text-[var(--text-tertiary)]"><span className="font-medium">Owner: </span>{r.owner}</p> : null
    }
    if (variant === 'risk') {
      const r = row as BrdRiskRow
      return (
        <div className="space-y-1">
          <p className="text-sm text-[var(--text-primary)] leading-relaxed">{r.description}</p>
          {r.mitigation && <p className="text-xs text-[var(--text-secondary)]"><span className="font-medium">Mitigation: </span>{r.mitigation}</p>}
          {r.owner && <p className="text-xs text-[var(--text-tertiary)]"><span className="font-medium">Owner: </span>{r.owner}</p>}
        </div>
      )
    }
    if (variant === 'kpi') {
      const r = row as BrdKpiRow
      return (
        <div className="space-y-1">
          <p className="text-sm text-[var(--text-primary)] leading-relaxed">{r.description}</p>
          <div className="flex flex-wrap gap-3 text-xs text-[var(--text-secondary)]">
            {r.baseline && <span><span className="font-medium">Baseline:</span> {r.baseline}</span>}
            {r.target && <span><span className="font-medium">Target:</span> {r.target}</span>}
            {r.data_source && <span><span className="font-medium">Source:</span> {r.data_source}</span>}
          </div>
        </div>
      )
    }
    return null
  }

  return (
    <div
      className={cn(
        'group relative rounded-xl border bg-[var(--bg-surface)] shadow-[var(--shadow-sm)] overflow-hidden',
        'transition-shadow hover:shadow-[var(--shadow-card)]',
        isHumanEdited && !hasFinding && 'border-l-4 border-[var(--human-edited)]',
        hasFinding && 'border-l-4 border-[var(--status-danger)]',
        !isHumanEdited && !hasFinding && 'border-[var(--border-default)]',
      )}
    >
      {/* ── Header ── */}
      <div className="flex items-start gap-2 px-3 pt-3 pb-2">
        <span className="shrink-0 mt-0.5 font-mono text-[10px] text-[var(--text-tertiary)] bg-[var(--bg-elevated)] border border-[var(--border-subtle)] rounded px-1.5 py-0.5">
          {row.row_key}
        </span>
        <p className="flex-1 text-sm font-semibold text-[var(--text-primary)] leading-snug min-w-0">{renderTitle()}</p>

        {/* Action buttons — show on hover */}
        <div className="shrink-0 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          {isLocked ? (
            <span className="inline-flex items-center gap-0.5 rounded border border-amber-200 bg-amber-50 px-1.5 py-0.5 text-[10px] text-amber-700" title="Locked">
              <Lock size={9} /> locked
            </span>
          ) : (
            <button
              onClick={() => { setEditing((e) => !e); setShowHistory(false) }}
              className={cn('p-1.5 rounded-md border transition-colors', editing ? 'border-[var(--accent)] bg-[var(--accent-subtle)] text-[var(--accent)]' : 'border-[var(--border-default)] bg-[var(--bg-elevated)] text-[var(--text-secondary)] hover:border-[var(--accent)] hover:text-[var(--accent)] hover:bg-[var(--accent-subtle)]')}
              title={editing ? 'Close editor' : 'Edit'}
            >
              <Edit2 size={12} />
            </button>
          )}
          {row.version > 1 && (
            <button
              onClick={() => { setShowHistory((h) => !h); setEditing(false) }}
              className={cn('inline-flex items-center gap-0.5 rounded-md border px-1.5 py-0.5 text-[10px] transition-colors', showHistory ? 'border-[var(--accent)] bg-[var(--accent-subtle)] text-[var(--accent)]' : 'border-[var(--border-default)] bg-[var(--bg-elevated)] text-[var(--text-tertiary)] hover:text-[var(--text-primary)]')}
              title="Version history"
            >
              <Clock size={9} /> v{row.version}
            </button>
          )}
        </div>
      </div>

      {/* Meta pills */}
      <div className="flex flex-wrap items-center gap-1.5 px-3 pb-2">
        {renderHeaderMeta()}
        {isHumanEdited && (
          <span className="inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium bg-[var(--human-edited-bg)] text-[var(--human-edited)] border border-[var(--human-edited-bg)]">
            human-edited
          </span>
        )}
        {hasFinding && (
          <span className="inline-flex items-center gap-0.5 rounded border border-[var(--status-danger-border)] bg-[var(--status-danger-bg)] px-1.5 py-0.5 text-[10px] text-[var(--status-danger)]">
            <AlertTriangle size={9} /> {finding!.group}
          </span>
        )}
      </div>

      {/* ── Inline edit form ── */}
      {editing && (
        <EditForm
          variant={variant}
          row={row}
          projectId={projectId}
          onSaved={() => { setEditing(false); onMutate() }}
          onCancel={() => setEditing(false)}
        />
      )}

      {/* ── Description (only when not editing) ── */}
      {!editing && (
        <div className="border-t border-[var(--border-subtle)]">
          <button
            onClick={() => setDescOpen((o) => !o)}
            className="flex w-full items-center justify-between px-3 py-1.5 text-[11px] font-semibold text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] transition-colors"
          >
            <span>Description</span>
            {descOpen ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
          </button>
          {descOpen && <div className="px-3 pb-3">{renderBody()}</div>}
        </div>
      )}

      {/* ── Acceptance Criteria (BR only, not while editing) ── */}
      {!editing && variant === 'br' && (() => {
        const r = row as BrdBusinessRequirementRow
        const acs = r.acceptance_criteria ?? []
        if (acs.length === 0) return null
        return (
          <div className="border-t border-[var(--border-subtle)]">
            <button
              onClick={() => setAcOpen((o) => !o)}
              className="flex w-full items-center justify-between px-3 py-1.5 text-[11px] font-semibold text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] transition-colors"
            >
              <span>Acceptance Criteria <span className="font-normal text-[var(--text-tertiary)]">({acs.length})</span></span>
              {acOpen ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            </button>
            {acOpen && (
              <div className="px-3 pb-3 space-y-2">
                {acs.map((ac, i) => (
                  <div key={i} className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-elevated)] px-3 py-2 text-xs space-y-1">
                    <p><span className="font-semibold text-[var(--text-tertiary)] uppercase text-[10px]">Given</span> <span className="text-[var(--text-primary)]">{ac.given}</span></p>
                    <p><span className="font-semibold text-[var(--text-tertiary)] uppercase text-[10px]">When</span> <span className="text-[var(--text-primary)]">{ac.when}</span></p>
                    <p><span className="font-semibold text-[var(--text-tertiary)] uppercase text-[10px]">Then</span> <span className="text-[var(--text-primary)]">{ac.then}</span></p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )
      })()}

      {/* ── Traces ── */}
      {!editing && traces.length > 0 && (
        <div className="border-t border-[var(--border-subtle)]">
          <button
            onClick={() => setTracesOpen((o) => !o)}
            className="flex w-full items-center justify-between px-3 py-1.5 text-[11px] font-semibold text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] transition-colors"
          >
            <span>Sources <span className="font-normal text-[var(--text-tertiary)]">({traces.length})</span></span>
            {tracesOpen ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
          </button>
          {tracesOpen && (
            <div className="px-3 pb-3 flex flex-wrap gap-1.5">
              {traces.map((t) => <TraceChip key={t.id} trace={t} />)}
            </div>
          )}
        </div>
      )}

      {/* ── Finding hint ── */}
      {hasFinding && !editing && (
        <div className="border-t border-[var(--status-danger-border)] bg-[var(--status-danger-bg)] px-3 py-2">
          <p className="text-xs text-[var(--status-danger)] font-medium">{finding!.description}</p>
          {finding!.suggested_fix && (
            <p className="mt-0.5 text-[11px] text-[var(--status-danger)] opacity-80 italic">{finding!.suggested_fix}</p>
          )}
        </div>
      )}

      {/* ── Version history ── */}
      {showHistory && (
        <HistoryPanel
          projectId={projectId}
          table={TABLE_FOR_VARIANT[variant]}
          rowId={row.id}
          currentVersion={row.version}
          onClose={() => setShowHistory(false)}
        />
      )}
    </div>
  )
}
