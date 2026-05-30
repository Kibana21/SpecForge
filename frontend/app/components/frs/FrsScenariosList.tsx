'use client'
/**
 * Acceptance Scenarios list — rendered Given/When/Then with a live counter
 * (`6/6 scenarios · 2/2 negatives ✓`). The validator catches <6 / <2 negatives,
 * but the UI signals the state in real-time via the counter color.
 *
 * Each scenario card has the hover Edit/Lock/Delete cluster; `[+ Add scenario]`
 * opens a fresh edit dialog with a sensible default scenario_index.
 */
import { useState } from 'react'
import { Plus } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'
import type { FrsAcceptanceScenarioRow } from '@/lib/types'
import { FrsRowEditDialog, type FrsRowField } from './FrsRowEditDialog'
import { FrsRowActions } from './FrsRowActions'
import { useFrsRowOps } from './useFrsRowOps'

const SCENARIO_FIELDS: FrsRowField[] = [
  { name: 'scenario_index', label: 'Display order', type: 'text', placeholder: '1' },
  { name: 'given', label: 'Given', type: 'textarea', rows: 2 },
  { name: 'when', label: 'When', type: 'textarea', rows: 2 },
  { name: 'then', label: 'Then', type: 'textarea', rows: 2 },
  { name: 'is_negative', label: 'Negative scenario',
    type: 'bool', description: 'Failure / error / rejection path' },
  { name: 'fr_refs', label: 'FR refs', type: 'tags',
    placeholder: 'M001-FRS001-FR-1, M001-FRS001-FR-2' },
]

interface Props {
  projectId: string
  scenarios: FrsAcceptanceScenarioRow[]
  specRowKey: string
  onMutate: () => void
}

export function FrsScenariosList({
  projectId, scenarios, specRowKey, onMutate,
}: Props) {
  const [editing, setEditing] = useState<FrsAcceptanceScenarioRow | null>(null)
  const [adding, setAdding] = useState(false)

  const sorted = [...scenarios].sort((a, b) => a.scenario_index - b.scenario_index)
  const negativeCount = sorted.filter(s => s.is_negative).length
  const sceCount = sorted.length

  const sceCls =
    sceCount >= 6 ? 'text-emerald-700' : 'text-amber-700'
  const negCls =
    negativeCount >= 2 ? 'text-emerald-700' : 'text-amber-700'

  const nextIndex = (sorted[sorted.length - 1]?.scenario_index ?? 0) + 1
  const nextRowKey = `${specRowKey}-AS-${nextIndex}`

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)]">
          Acceptance Scenarios
        </p>
        <div className="flex items-center gap-3">
          <span className={cn('text-[11px] font-semibold', sceCls)}>
            {sceCount}/6 scenarios {sceCount >= 6 && '✓'}
          </span>
          <span className={cn('text-[11px] font-semibold', negCls)}>
            {negativeCount}/2 negative {negativeCount >= 2 && '✓'}
          </span>
          <button
            onClick={() => setAdding(true)}
            className="inline-flex items-center gap-1 text-[10px] text-[var(--text-secondary)] hover:text-[var(--accent)] transition-colors"
          >
            <Plus size={11} /> Add scenario
          </button>
        </div>
      </div>

      {sorted.length === 0 ? (
        <p className="text-xs italic text-[var(--text-tertiary)]">No scenarios.</p>
      ) : (
        <ol className="space-y-2">
          {sorted.map((sc) => (
            <ScenarioCard
              key={sc.row_key}
              projectId={projectId}
              scenario={sc}
              onEdit={() => setEditing(sc)}
              onMutate={onMutate}
            />
          ))}
        </ol>
      )}

      {editing && (
        <FrsRowEditDialog
          open
          title={`Edit scenario #${editing.scenario_index}`}
          projectId={projectId}
          table="frs_acceptance_scenarios"
          rowId={editing.id}
          initialValues={{
            scenario_index: String(editing.scenario_index),
            given: editing.given,
            when: editing.when,
            then: editing.then,
            is_negative: editing.is_negative,
            fr_refs: editing.fr_refs,
          }}
          fields={SCENARIO_FIELDS}
          isLocked={editing.is_locked}
          onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); onMutate() }}
        />
      )}

      {adding && (
        <FrsRowEditDialog
          open
          title="Add scenario"
          projectId={projectId}
          table="frs_acceptance_scenarios"
          rowId={crypto.randomUUID()}
          initialValues={{
            scenario_index: String(nextIndex),
            given: '',
            when: '',
            then: '',
            is_negative: false,
            fr_refs: [],
            spec_row_key: specRowKey,
            row_key: nextRowKey,
          }}
          fields={[
            ...SCENARIO_FIELDS,
            { name: 'row_key', label: 'Row key (auto)', type: 'text' },
          ]}
          onClose={() => setAdding(false)}
          onSaved={() => { setAdding(false); onMutate() }}
        />
      )}
    </div>
  )
}

function ScenarioCard({
  projectId, scenario: sc, onEdit, onMutate,
}: {
  projectId: string
  scenario: FrsAcceptanceScenarioRow
  onEdit: () => void
  onMutate: () => void
}) {
  const { busy, handleLockToggle, handleDelete } = useFrsRowOps({
    projectId,
    table: 'frs_acceptance_scenarios',
    rowId: sc.id,
    isLocked: sc.is_locked,
    lockPayload: {
      scenario_index: sc.scenario_index,
      given: sc.given,
      when: sc.when,
      then: sc.then,
      is_negative: sc.is_negative,
      fr_refs: sc.fr_refs,
    },
    label: `scenario #${sc.scenario_index}`,
    onMutate,
  })

  return (
    <li
      className={cn(
        'group rounded-lg border bg-[var(--bg-surface)] px-3 py-2 transition-colors',
        sc.is_locked
          ? 'border-amber-200 ring-1 ring-amber-100/70'
          : 'border-[var(--border-default)] hover:border-[var(--accent)]/40',
      )}
    >
      <div className="flex items-start gap-2">
        <div className="flex-1 min-w-0 text-xs leading-relaxed">
          <p>
            <span className="font-semibold text-[var(--text-tertiary)] mr-1">
              {sc.scenario_index}.
            </span>
            <span className="font-semibold text-[var(--text-primary)]">Given</span>{' '}
            {sc.given}
            {sc.is_negative && (
              <span className="ml-2 inline-flex items-center text-[10px] rounded px-1.5 py-0.5 bg-rose-50 text-rose-700 border border-rose-200">
                ✘ negative
              </span>
            )}
          </p>
          <p className="mt-0.5">
            <span className="font-semibold text-[var(--text-primary)]">When</span> {sc.when}
          </p>
          <p className="mt-0.5">
            <span className="font-semibold text-[var(--text-primary)]">Then</span> {sc.then}
          </p>
          {sc.fr_refs?.length > 0 && (
            <p className="mt-1 text-[10px] text-[var(--accent)] font-mono">
              → {sc.fr_refs.join(', ')}
            </p>
          )}
        </div>
        <FrsRowActions
          isLocked={sc.is_locked}
          busy={busy}
          onEdit={onEdit}
          onLock={handleLockToggle}
          onDelete={handleDelete}
        />
      </div>
    </li>
  )
}
