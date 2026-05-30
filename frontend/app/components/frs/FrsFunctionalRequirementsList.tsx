'use client'
/**
 * Functional Requirements list — `frs_functional_requirements` rows. Each FR
 * shows the local fr_id, requirement_text, and chip-formatted scenario refs.
 * Same hover Edit/Lock/Delete + [+ Add FR] pattern.
 */
import { useState } from 'react'
import { Plus } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { FrsFunctionalRequirementRow } from '@/lib/types'
import { FrsRowEditDialog, type FrsRowField } from './FrsRowEditDialog'
import { FrsRowActions } from './FrsRowActions'
import { useFrsRowOps } from './useFrsRowOps'

const FR_FIELDS: FrsRowField[] = [
  { name: 'fr_id', label: 'FR ID (local)', type: 'text', placeholder: 'FR-1' },
  { name: 'requirement_text', label: 'Requirement', type: 'textarea', rows: 4 },
  { name: 'scenario_refs', label: 'Scenario refs', type: 'tags',
    placeholder: 'M001-FRS001-AS-1, M001-FRS001-AS-3' },
]

interface Props {
  projectId: string
  frs: FrsFunctionalRequirementRow[]
  specRowKey: string
  onMutate: () => void
}

export function FrsFunctionalRequirementsList({
  projectId, frs, specRowKey, onMutate,
}: Props) {
  const [editing, setEditing] = useState<FrsFunctionalRequirementRow | null>(null)
  const [adding, setAdding] = useState(false)

  const sorted = [...frs].sort((a, b) =>
    (a.fr_id || '').localeCompare(b.fr_id || '', undefined, { numeric: true }),
  )
  const nextId = `FR-${sorted.length + 1}`
  const nextRowKey = `${specRowKey}-FR-${sorted.length + 1}`

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)]">
          Functional Requirements ({sorted.length})
        </p>
        <button
          onClick={() => setAdding(true)}
          className="inline-flex items-center gap-1 text-[10px] text-[var(--text-secondary)] hover:text-[var(--accent)] transition-colors"
        >
          <Plus size={11} /> Add FR
        </button>
      </div>

      {sorted.length === 0 ? (
        <p className="text-xs italic text-[var(--text-tertiary)]">No functional requirements.</p>
      ) : (
        <ul className="space-y-1.5">
          {sorted.map((fr) => (
            <FrCard
              key={fr.row_key}
              projectId={projectId}
              fr={fr}
              onEdit={() => setEditing(fr)}
              onMutate={onMutate}
            />
          ))}
        </ul>
      )}

      {editing && (
        <FrsRowEditDialog
          open
          title={`Edit FR — ${editing.fr_id}`}
          projectId={projectId}
          table="frs_functional_requirements"
          rowId={editing.id}
          initialValues={{
            fr_id: editing.fr_id,
            requirement_text: editing.requirement_text,
            scenario_refs: editing.scenario_refs,
          }}
          fields={FR_FIELDS}
          isLocked={editing.is_locked}
          onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); onMutate() }}
        />
      )}

      {adding && (
        <FrsRowEditDialog
          open
          title="Add functional requirement"
          projectId={projectId}
          table="frs_functional_requirements"
          rowId={crypto.randomUUID()}
          initialValues={{
            fr_id: nextId,
            requirement_text: '',
            scenario_refs: [],
            spec_row_key: specRowKey,
            row_key: nextRowKey,
          }}
          fields={[
            ...FR_FIELDS,
            { name: 'row_key', label: 'Row key (auto)', type: 'text' },
          ]}
          onClose={() => setAdding(false)}
          onSaved={() => { setAdding(false); onMutate() }}
        />
      )}
    </div>
  )
}

function FrCard({
  projectId, fr, onEdit, onMutate,
}: {
  projectId: string
  fr: FrsFunctionalRequirementRow
  onEdit: () => void
  onMutate: () => void
}) {
  const { busy, handleLockToggle, handleDelete } = useFrsRowOps({
    projectId,
    table: 'frs_functional_requirements',
    rowId: fr.id,
    isLocked: fr.is_locked,
    lockPayload: {
      fr_id: fr.fr_id,
      requirement_text: fr.requirement_text,
      scenario_refs: fr.scenario_refs,
    },
    label: `FR "${fr.fr_id}"`,
    onMutate,
  })

  return (
    <li
      className={cn(
        'group rounded-lg border bg-[var(--bg-surface)] px-3 py-2 transition-colors',
        fr.is_locked
          ? 'border-amber-200 ring-1 ring-amber-100/70'
          : 'border-[var(--border-default)] hover:border-[var(--accent)]/40',
      )}
    >
      <div className="flex items-start gap-2">
        <div className="flex-1 min-w-0 text-xs leading-relaxed">
          <p>
            <span className="font-semibold font-mono text-[var(--text-primary)] mr-1">
              {fr.fr_id}.
            </span>
            <span className="text-[var(--text-secondary)]">{fr.requirement_text}</span>
          </p>
          {fr.scenario_refs?.length > 0 && (
            <p className="mt-1 text-[10px] text-[var(--text-tertiary)] italic">
              Validated by: {fr.scenario_refs.map((r) => (
                <span key={r} className="font-mono text-[var(--accent)] not-italic mr-1.5">
                  {r}
                </span>
              ))}
            </p>
          )}
        </div>
        <FrsRowActions
          isLocked={fr.is_locked}
          busy={busy}
          onEdit={onEdit}
          onLock={handleLockToggle}
          onDelete={handleDelete}
        />
      </div>
    </li>
  )
}
