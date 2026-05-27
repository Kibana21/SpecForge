'use client'
import { useState } from 'react'
import { X, AlertTriangle, ChevronDown, ChevronUp, CheckCircle2, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { BrdFinding } from '@/lib/types'

interface Props {
  findings: BrdFinding[]
  onClose: () => void
  onAcceptFix: (finding: BrdFinding) => Promise<void>
  onJumpToRow: (rowKey: string) => void
  onValidate: () => void
}

type Group = BrdFinding['group']

const GROUP_META: Record<Group, { label: string; color: string; bgColor: string; borderColor: string }> = {
  critical:  { label: 'Critical',  color: 'text-red-700',    bgColor: 'bg-red-50',    borderColor: 'border-red-200' },
  major:     { label: 'Major',     color: 'text-orange-700', bgColor: 'bg-orange-50', borderColor: 'border-orange-200' },
  minor:     { label: 'Minor',     color: 'text-amber-700',  bgColor: 'bg-amber-50',  borderColor: 'border-amber-200' },
  coverage:  { label: 'Coverage',  color: 'text-blue-700',   bgColor: 'bg-blue-50',   borderColor: 'border-blue-200' },
  warnings:  { label: 'Warnings',  color: 'text-gray-600',   bgColor: 'bg-gray-50',   borderColor: 'border-gray-200' },
}

const GROUP_ORDER: Group[] = ['critical', 'major', 'minor', 'coverage', 'warnings']

function FindingCard({
  finding,
  onAcceptFix,
  onJumpToRow,
}: {
  finding: BrdFinding
  onAcceptFix: (finding: BrdFinding) => Promise<void>
  onJumpToRow: (rowKey: string) => void
}) {
  const [accepting, setAccepting] = useState(false)
  const [accepted, setAccepted] = useState(false)

  async function handleAccept() {
    setAccepting(true)
    try {
      await onAcceptFix(finding)
      setAccepted(true)
    } finally {
      setAccepting(false)
    }
  }

  return (
    <div
      className={cn(
        'rounded-lg border p-3 space-y-2',
        accepted ? 'opacity-50 bg-[var(--bg-elevated)]' : 'bg-[var(--bg-surface)]',
      )}
    >
      <p className="text-xs font-medium text-[var(--text-primary)] leading-snug">
        {finding.description}
      </p>
      {finding.row_key && (
        <p className="font-mono text-[10px] text-[var(--text-tertiary)]">{finding.row_key}</p>
      )}
      {finding.suggested_fix && (
        <p className="text-[11px] text-[var(--text-secondary)] italic bg-[var(--bg-elevated)] rounded px-2 py-1.5">
          {finding.suggested_fix}
        </p>
      )}
      <div className="flex items-center gap-2">
        {finding.suggested_fix && !accepted && (
          <button
            onClick={handleAccept}
            disabled={accepting}
            className="inline-flex items-center gap-1 rounded-md bg-[var(--accent)] px-2.5 py-1 text-[11px] font-medium text-white hover:opacity-90 disabled:opacity-50 transition-opacity"
          >
            {accepting ? (
              <><Loader2 size={10} className="animate-spin" /> Applying…</>
            ) : (
              <><CheckCircle2 size={10} /> Accept fix</>
            )}
          </button>
        )}
        {accepted && (
          <span className="inline-flex items-center gap-1 text-[11px] text-[var(--status-success)]">
            <CheckCircle2 size={10} /> Applied
          </span>
        )}
        {finding.row_key && (
          <button
            onClick={() => onJumpToRow(finding.row_key!)}
            className="text-[11px] text-[var(--text-secondary)] hover:text-[var(--accent)] transition-colors"
          >
            Jump to row →
          </button>
        )}
      </div>
    </div>
  )
}

function FindingGroup({
  group,
  findings,
  onAcceptFix,
  onJumpToRow,
}: {
  group: Group
  findings: BrdFinding[]
  onAcceptFix: (finding: BrdFinding) => Promise<void>
  onJumpToRow: (rowKey: string) => void
}) {
  const [open, setOpen] = useState(group === 'critical' || group === 'major')
  const meta = GROUP_META[group]

  return (
    <div className={cn('rounded-xl border overflow-hidden', meta.borderColor)}>
      <button
        onClick={() => setOpen((o) => !o)}
        className={cn(
          'flex w-full items-center justify-between px-3 py-2.5 transition-colors',
          meta.bgColor,
          'hover:opacity-90',
        )}
      >
        <div className="flex items-center gap-2">
          <span className={cn('text-xs font-bold', meta.color)}>{meta.label}</span>
          <span
            className={cn(
              'rounded-full px-1.5 py-0.5 text-[10px] font-bold',
              meta.bgColor,
              meta.color,
              'border',
              meta.borderColor,
            )}
          >
            {findings.length}
          </span>
        </div>
        {open ? <ChevronUp size={13} className={meta.color} /> : <ChevronDown size={13} className={meta.color} />}
      </button>
      {open && (
        <div className="divide-y divide-[var(--border-subtle)] border-t border-[var(--border-default)]">
          {findings.map((f) => (
            <div key={f.check_id} className="px-3 py-2">
              <FindingCard finding={f} onAcceptFix={onAcceptFix} onJumpToRow={onJumpToRow} />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export function FindingsDrawer({ findings, onClose, onAcceptFix, onJumpToRow, onValidate }: Props) {
  const grouped = GROUP_ORDER.reduce<Partial<Record<Group, BrdFinding[]>>>((acc, g) => {
    const list = findings.filter((f) => f.group === g)
    if (list.length > 0) acc[g] = list
    return acc
  }, {})

  const blockingCount =
    (grouped.critical?.length ?? 0) + (grouped.major?.length ?? 0)
  const canValidate = blockingCount === 0

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-[var(--text-primary)]/20 z-40" onClick={onClose} />

      {/* Drawer */}
      <div className="fixed top-0 right-0 h-full w-[480px] max-w-[92vw] bg-[var(--bg-surface)] border-l border-[var(--border-default)] shadow-[-4px_0_32px_rgba(0,0,0,0.12)] z-50 flex flex-col">
        {/* Header */}
        <div className="shrink-0 flex items-center justify-between px-4 py-3 border-b border-[var(--border-default)] bg-[var(--bg-elevated)]">
          <div className="flex items-center gap-2">
            <AlertTriangle size={15} className="text-[var(--status-warning)]" />
            <div>
              <p className="text-sm font-semibold text-[var(--text-primary)]">Validation Findings</p>
              <p className="text-[11px] text-[var(--text-tertiary)]">
                {findings.length} finding{findings.length !== 1 ? 's' : ''}
                {blockingCount > 0 && (
                  <span className="ml-1 text-[var(--status-danger)] font-medium">
                    · {blockingCount} blocking
                  </span>
                )}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-md text-[var(--text-tertiary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-elevated)] transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
          {findings.length === 0 ? (
            <div className="flex flex-col items-center gap-3 py-12 text-center">
              <CheckCircle2 size={32} className="text-[var(--status-success)]" strokeWidth={1.5} />
              <p className="text-sm font-medium text-[var(--text-primary)]">No findings</p>
              <p className="text-xs text-[var(--text-tertiary)]">The BRD looks good — ready to validate.</p>
            </div>
          ) : (
            GROUP_ORDER.filter((g) => grouped[g]).map((g) => (
              <FindingGroup
                key={g}
                group={g}
                findings={grouped[g]!}
                onAcceptFix={onAcceptFix}
                onJumpToRow={(key) => { onJumpToRow(key); onClose() }}
              />
            ))
          )}
        </div>

        {/* Footer */}
        <div className="shrink-0 border-t border-[var(--border-default)] px-4 py-3">
          {!canValidate && (
            <p className="mb-2 text-[11px] text-[var(--status-danger)]">
              <AlertTriangle size={10} className="inline mr-1" />
              Fix all critical and major findings before validating.
            </p>
          )}
          <button
            onClick={onValidate}
            disabled={!canValidate}
            className={cn(
              'w-full flex items-center justify-center gap-2 rounded-xl py-2.5 text-sm font-semibold transition-all',
              canValidate
                ? 'bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)] shadow-sm'
                : 'bg-[var(--bg-elevated)] text-[var(--text-tertiary)] cursor-not-allowed',
            )}
          >
            <CheckCircle2 size={15} />
            {canValidate ? 'Validate BRD' : `Fix ${blockingCount} blocking issue${blockingCount !== 1 ? 's' : ''} first`}
          </button>
        </div>
      </div>
    </>
  )
}
