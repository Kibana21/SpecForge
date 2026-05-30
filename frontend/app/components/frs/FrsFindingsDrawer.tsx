'use client'
/**
 * FRS Findings Drawer (Stage B-aware).
 *
 * Right-slide drawer that consumes the GET /findings response and lets the
 * user commit Stage B validation. Mirrors the Stage A `FrsModularizeFindings`
 * shape but routes through `api.frs.validate` (POST) — which now locks all
 * current rows and flips `status='validated'` when blocking == 0 and Stage B
 * has produced designed specs.
 *
 * Per finding card: description + suggested fix + optional [Jump to row →]
 * and [Accept fix] actions. Accept-fix kicks off `api.frs.regenerateSpec` for
 * the spec referenced in `row_key`.
 */
import { useState } from 'react'
import {
  ArrowRight, Check, ChevronDown, ChevronRight, Loader2, X,
} from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'
import { FRS_FINDING_GROUPS } from '@/lib/frs-manifest'
import type {
  FrsFinding, FrsFindingsResponse, FrsValidateResponse,
} from '@/lib/types'

interface Props {
  projectId: string
  open: boolean
  findings: FrsFindingsResponse | null
  onClose: () => void
  /** Re-fetch findings (used after accept-fix to see fresh state). */
  onRefresh: () => void
  /** Called when commit succeeds; parent triggers confetti + status flip. */
  onValidated: (response: FrsValidateResponse) => void
  /** Smooth-scroll the body to the row referenced by a finding. */
  onJumpToRow?: (rowKey: string) => void
}

export function FrsFindingsDrawer({
  projectId, open, findings, onClose, onRefresh, onValidated, onJumpToRow,
}: Props) {
  const [expanded, setExpanded] = useState<Set<string>>(
    new Set(['critical', 'major', 'coverage']),
  )
  const [submitting, setSubmitting] = useState(false)

  if (!open) return null

  const summary = findings?.summary
  const list = findings?.findings ?? []
  const blocking = summary?.blocking ?? 0

  const grouped = FRS_FINDING_GROUPS.map((g) => ({
    ...g,
    items: list.filter((f) => f.group === g.key),
  }))

  function toggleGroup(key: string) {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  async function handleValidate() {
    if (blocking > 0) return
    setSubmitting(true)
    try {
      const result = await api.frs.validate(projectId)
      const r = result as FrsValidateResponse
      if (r.ok) {
        if (r.stage_b_validated) {
          toast.success(
            `FRS validated — ${r.locked_row_count ?? 0} rows locked. Ready to export.`,
          )
        } else {
          toast.success('Stage 1 approved')
        }
        onValidated(r)
      } else {
        toast.error('Validation failed — refresh findings and try again')
        onRefresh()
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Validation failed')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      <div
        className="fixed inset-0 z-40 bg-black/20 backdrop-blur-[2px]"
        onClick={onClose}
        aria-hidden="true"
      />
      <aside
        className="fixed right-0 top-0 bottom-0 z-50 w-[480px] max-w-[100vw] bg-[var(--bg-surface)] border-l border-[var(--border-default)] shadow-[var(--shadow-lg)] flex flex-col"
        role="dialog"
        aria-modal="true"
        aria-labelledby="frs-findings-title"
      >
        {/* Header */}
        <div className="shrink-0 flex items-start gap-3 px-4 py-3 border-b border-[var(--border-default)]">
          <div className="flex-1">
            <h2 id="frs-findings-title" className="text-base font-semibold text-[var(--text-primary)]">
              FRS Findings
            </h2>
            {summary && (
              <p className="text-[11px] text-[var(--text-tertiary)] mt-0.5">
                {summary.total} total · {summary.blocking} blocking
                {summary.coverage > 0 && ` · ${summary.coverage} coverage`}
                {summary.warnings > 0 && ` · ${summary.warnings} warnings`}
              </p>
            )}
          </div>
          <button
            onClick={onRefresh}
            title="Refresh findings"
            className="rounded-md p-1 text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] transition-colors"
            aria-label="Refresh"
          >
            <Loader2 size={14} />
          </button>
          <button
            onClick={onClose}
            className="rounded-md p-1 text-[var(--text-tertiary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-elevated)] transition-colors"
            aria-label="Close"
          >
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-3 py-3 space-y-2">
          {grouped.map((g) => g.items.length === 0 ? null : (
            <div key={g.key} className="rounded-lg border border-[var(--border-subtle)] overflow-hidden">
              <button
                onClick={() => toggleGroup(g.key)}
                className={cn(
                  'w-full flex items-center gap-2 px-3 py-2 text-left transition-colors',
                  g.cls,
                )}
                aria-expanded={expanded.has(g.key)}
              >
                {expanded.has(g.key)
                  ? <ChevronDown size={13} />
                  : <ChevronRight size={13} />}
                <span className="text-xs font-semibold flex-1">{g.label}</span>
                <span className="text-[10px] font-semibold rounded-full px-1.5 py-0.5 bg-white/60">
                  {g.items.length}
                </span>
              </button>
              {expanded.has(g.key) && (
                <ul className="divide-y divide-[var(--border-subtle)]">
                  {g.items.map((f, i) => (
                    <FindingItem
                      key={`${f.check_id}-${i}`}
                      projectId={projectId}
                      finding={f}
                      onJumpToRow={onJumpToRow}
                      onRefresh={onRefresh}
                    />
                  ))}
                </ul>
              )}
            </div>
          ))}

          {grouped.every(g => g.items.length === 0) && (
            <div className="rounded-xl border border-dashed border-emerald-200 bg-emerald-50/40 px-4 py-6 text-center">
              <Check size={20} className="mx-auto text-emerald-600 mb-1" />
              <p className="text-sm font-semibold text-emerald-900">
                Clean as a whistle
              </p>
              <p className="text-[11px] text-emerald-800/80 mt-1">
                No findings yet. Validate to lock the FRS and unlock export.
              </p>
            </div>
          )}
        </div>

        {/* Footer — Validate button */}
        <div className="shrink-0 border-t border-[var(--border-default)] px-4 py-3 space-y-1">
          <button
            onClick={handleValidate}
            disabled={blocking > 0 || submitting}
            title={blocking > 0
              ? `${blocking} blocking finding(s) must be resolved first`
              : 'Lock all rows and mark FRS as validated'}
            className={cn(
              'w-full inline-flex items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-sm font-semibold transition-colors',
              blocking === 0 && !submitting
                ? 'bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)]'
                : 'bg-[var(--bg-elevated)] text-[var(--text-tertiary)] cursor-not-allowed',
            )}
          >
            {submitting
              ? <Loader2 size={13} className="animate-spin" />
              : <ArrowRight size={13} />}
            {blocking > 0
              ? `Validate FRS (${blocking} blocking)`
              : 'Validate FRS — lock all rows'}
          </button>
        </div>
      </aside>
    </>
  )
}

// ── Finding item ─────────────────────────────────────────────────────────────

function FindingItem({
  projectId, finding, onJumpToRow, onRefresh,
}: {
  projectId: string
  finding: FrsFinding
  onJumpToRow?: (rowKey: string) => void
  onRefresh: () => void
}) {
  const [accepting, setAccepting] = useState(false)

  // Spec-level finding row_keys look like M001-FRS001 (or follow M-prefix).
  // Sub-row findings like M001-FRS001-AS-3 are scoped to a spec — derive the
  // parent spec_row_key for the "Accept fix → regenerate spec" path.
  const specMatch = /^([A-Z]\d+-FRS\d+)/.exec(finding.row_key ?? '')
  const specRowKey = specMatch?.[1]
  const canAcceptFix = !!specRowKey && (
    finding.check_id === 'too_few_scenarios'
    || finding.check_id === 'too_few_negative_scenarios'
    || finding.check_id === 'spec_no_br_trace'
  )

  async function handleAcceptFix() {
    if (!specRowKey) return
    setAccepting(true)
    try {
      await api.frs.regenerateSpec(projectId, specRowKey, 'full')
      toast.success(`Regenerated ${specRowKey}`)
      onRefresh()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Accept-fix failed')
    } finally {
      setAccepting(false)
    }
  }

  return (
    <li className="px-3 py-2 text-xs space-y-1">
      <p className="text-[var(--text-primary)] leading-snug">{finding.description}</p>
      {finding.suggested_fix && (
        <p className="text-[var(--text-tertiary)] italic leading-snug">
          {finding.suggested_fix}
        </p>
      )}
      <div className="flex items-center gap-2 pt-0.5">
        {finding.row_key && (
          <code className="text-[10px] font-mono text-[var(--text-tertiary)]">
            {finding.row_key}
          </code>
        )}
        {finding.target_ref && (
          <code className="text-[10px] font-mono text-[var(--text-tertiary)]">
            → {finding.target_ref}
          </code>
        )}
        <div className="flex-1" />
        {canAcceptFix && (
          <button
            onClick={handleAcceptFix}
            disabled={accepting}
            className="inline-flex items-center gap-1 text-[10px] font-semibold rounded-md bg-[var(--accent)] text-white px-2 py-0.5 hover:bg-[var(--accent-hover)] disabled:opacity-50 transition-colors"
          >
            {accepting && <Loader2 size={9} className="animate-spin" />}
            Accept fix
          </button>
        )}
        {finding.row_key && onJumpToRow && (
          <button
            onClick={() => onJumpToRow(finding.row_key as string)}
            className="text-[10px] text-[var(--accent)] hover:underline"
          >
            Jump to row →
          </button>
        )}
      </div>
    </li>
  )
}
