'use client'
/**
 * §4.1 Business Rules — compact table of `frs_business_rules` rows.
 *
 * Each row gets a hover Edit/Lock/Delete cluster + the table header shows
 * `[+ Add rule]` which opens a fresh edit dialog. New rows auto-pick a
 * sequential rule_id (BR-N).
 */
import { useState } from 'react'
import { Plus } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'
import type { FrsBusinessRuleRow } from '@/lib/types'
import { FrsRowEditDialog, type FrsRowField } from './FrsRowEditDialog'
import { FrsRowActions } from './FrsRowActions'
import { useFrsRowOps } from './useFrsRowOps'

const RULE_FIELDS: FrsRowField[] = [
  { name: 'rule_id', label: 'Rule ID (local)', type: 'text', placeholder: 'BR-1' },
  { name: 'description', label: 'Description', type: 'textarea', rows: 3 },
  { name: 'applies_to', label: 'Applies to', type: 'text',
    placeholder: 'Endpoint / component / entity' },
  { name: 'logic_decision', label: 'Logic / Decision', type: 'textarea', rows: 3 },
]

interface Props {
  projectId: string
  /** All business rules for the parent spec, in any order — sorted here. */
  rules: FrsBusinessRuleRow[]
  specRowKey: string
  onMutate: () => void
}

export function FrsBusinessRulesTable({
  projectId, rules, specRowKey, onMutate,
}: Props) {
  const [editing, setEditing] = useState<FrsBusinessRuleRow | null>(null)
  const [adding, setAdding] = useState(false)
  const [addBusy, setAddBusy] = useState(false)

  const sorted = [...rules].sort((a, b) =>
    (a.rule_id || '').localeCompare(b.rule_id || '', undefined, { numeric: true }),
  )
  const nextRuleId = `BR-${sorted.length + 1}`
  const nextRowKey = `${specRowKey}-BR-${sorted.length + 1}`

  async function handleAddRow(payload: Record<string, unknown>) {
    setAddBusy(true)
    try {
      // Create via editRow on a brand-new id+row_key. The orchestrator's
      // upsert_frs_rows auto-creates as version=1.
      const rowId = crypto.randomUUID()
      await api.frs.editRow(projectId, 'frs_business_rules', rowId, {
        ...payload,
        spec_row_key: specRowKey,
        row_key: payload['row_key'] || nextRowKey,
      }, { lock: false })
      toast.success('Rule added')
      setAdding(false)
      onMutate()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Add failed')
    } finally {
      setAddBusy(false)
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)]">
          Business Rules ({rules.length})
        </p>
        <button
          onClick={() => setAdding(true)}
          className="inline-flex items-center gap-1 text-[10px] text-[var(--text-secondary)] hover:text-[var(--accent)] transition-colors"
        >
          <Plus size={11} /> Add rule
        </button>
      </div>
      {sorted.length === 0 ? (
        <p className="text-xs italic text-[var(--text-tertiary)]">No business rules.</p>
      ) : (
        <div className="overflow-x-auto rounded border border-[var(--border-subtle)]">
          <table className="w-full text-xs">
            <thead className="bg-[var(--bg-elevated)]/70">
              <tr>
                <th className="text-left px-2 py-1.5 font-semibold text-[var(--text-secondary)] w-16">Rule ID</th>
                <th className="text-left px-2 py-1.5 font-semibold text-[var(--text-secondary)]">Description</th>
                <th className="text-left px-2 py-1.5 font-semibold text-[var(--text-secondary)] w-32">Applies to</th>
                <th className="text-left px-2 py-1.5 font-semibold text-[var(--text-secondary)]">Logic / Decision</th>
                <th className="w-20"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border-subtle)]">
              {sorted.map((r) => (
                <BusinessRuleRow
                  key={r.row_key}
                  projectId={projectId}
                  rule={r}
                  onEdit={() => setEditing(r)}
                  onMutate={onMutate}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {editing && (
        <FrsRowEditDialog
          open
          title={`Edit rule — ${editing.rule_id}`}
          projectId={projectId}
          table="frs_business_rules"
          rowId={editing.id}
          initialValues={{
            rule_id: editing.rule_id,
            description: editing.description,
            applies_to: editing.applies_to,
            logic_decision: editing.logic_decision,
          }}
          fields={RULE_FIELDS}
          isLocked={editing.is_locked}
          onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); onMutate() }}
        />
      )}

      {adding && (
        <FrsRowEditDialog
          open
          title="Add business rule"
          projectId={projectId}
          table="frs_business_rules"
          rowId={crypto.randomUUID()}
          initialValues={{
            rule_id: nextRuleId,
            description: '',
            applies_to: '',
            logic_decision: '',
          }}
          fields={RULE_FIELDS}
          onClose={() => setAdding(false)}
          onSaved={() => { setAdding(false); onMutate() }}
        />
      )}
    </div>
  )
}

function BusinessRuleRow({
  projectId, rule: r, onEdit, onMutate,
}: {
  projectId: string
  rule: FrsBusinessRuleRow
  onEdit: () => void
  onMutate: () => void
}) {
  const { busy, handleLockToggle, handleDelete } = useFrsRowOps({
    projectId,
    table: 'frs_business_rules',
    rowId: r.id,
    isLocked: r.is_locked,
    lockPayload: {
      rule_id: r.rule_id,
      description: r.description,
      applies_to: r.applies_to,
      logic_decision: r.logic_decision,
    },
    label: `rule "${r.rule_id}"`,
    onMutate,
  })
  return (
    <tr className={cn('group', r.is_locked && 'bg-amber-50/40')}>
      <td className="px-2 py-1.5 font-mono text-[var(--text-primary)] align-top">
        {r.rule_id}
      </td>
      <td className="px-2 py-1.5 text-[var(--text-secondary)] align-top">{r.description}</td>
      <td className="px-2 py-1.5 text-[var(--text-secondary)] align-top">{r.applies_to}</td>
      <td className="px-2 py-1.5 text-[var(--text-secondary)] align-top">{r.logic_decision}</td>
      <td className="px-2 py-1.5 align-top">
        <FrsRowActions
          isLocked={r.is_locked}
          busy={busy}
          onEdit={onEdit}
          onLock={handleLockToggle}
          onDelete={handleDelete}
        />
      </td>
    </tr>
  )
}
