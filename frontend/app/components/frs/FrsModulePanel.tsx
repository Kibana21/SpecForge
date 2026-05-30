'use client'
/**
 * FRS Module Panel — the right-column content for the selected module.
 *
 * Layout (top → bottom):
 *   1. FrsModuleIdentityCard (capability icon, ribbon, stats, BR chips, actions)
 *   2. Decision banner (if any module-scoped [SPEC-DECISION] is open)
 *   3. 7 collapsible sections:
 *        - Scope (in / out) — edit pencil on header
 *        - Actors & Dependencies — per-row Edit/Lock/Delete
 *        - Responsibilities — per-row Edit/Lock/Delete
 *        - Interfaces (with FrsContractGraph mini-SVG + textual list) — per-row Edit/Lock/Delete
 *        - Owned Data — per-row Edit/Lock/Delete
 *        - FRS Backlog (stub cards already have actions)
 *
 * Default expanded: Scope + Interfaces + Backlog. Others collapsed for calm density.
 *
 * Edit actions open the generic FrsRowEditDialog driven by a per-table field
 * schema. Delete uses browser confirm + api.frs.deleteRow. Lock toggles via
 * api.frs.editRow (lock=true) / api.frs.unlockRow.
 */
import { useState } from 'react'
import {
  ChevronDown, ChevronRight, AlertCircle, Pencil, Lock, LockOpen, Trash2,
} from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'
import {
  FRS_ACTOR_RELATIONSHIP_LABELS,
  FRS_INTERFACE_KIND_STYLES,
} from '@/lib/frs-manifest'
import type {
  FrsModuleHydrated, FrsSpecDecisionRow,
  FrsModuleActorRow, FrsModuleResponsibilityRow,
  FrsModuleInterfaceRow, FrsModuleDataEntityRow,
  FrsSpecRow,
} from '@/lib/types'
import { FrsModuleIdentityCard } from './FrsModuleIdentityCard'
import { FrsBacklogStubCard } from './FrsBacklogStubCard'
import { FrsContractGraph } from './FrsContractGraph'
import { FrsRowEditDialog, type FrsRowField } from './FrsRowEditDialog'

interface Props {
  projectId: string
  module: FrsModuleHydrated
  allModules: FrsModuleHydrated[]
  decisions: FrsSpecDecisionRow[]
  onMutate: () => void
  onOpenDecision: (decision: FrsSpecDecisionRow) => void
  onDesignStub?: (stubRowKey: string) => void
  onNavigateModule?: (moduleRowKey: string) => void
  onRegenerateModule?: () => void
  onToggleLock?: (table: string, rowId: string, currentLocked: boolean) => void
  onDeleteStub?: (rowId: string) => void
  busy?: boolean
}

interface EditingState {
  table: string
  rowId: string
  title: string
  initialValues: Record<string, unknown>
  fields: FrsRowField[]
  isLocked: boolean
}

const DEFAULT_EXPANDED = new Set(['scope', 'interfaces', 'backlog'])

export function FrsModulePanel({
  projectId, module: m, allModules, decisions, onMutate, onOpenDecision,
  onDesignStub, onNavigateModule, onRegenerateModule, onToggleLock, onDeleteStub, busy,
}: Props) {
  const [expanded, setExpanded] = useState<Set<string>>(DEFAULT_EXPANDED)
  const [editing, setEditing] = useState<EditingState | null>(null)

  const toggleSection = (key: string) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const isOpen = (key: string) => expanded.has(key)
  const openDecisions = decisions.filter(
    (d) => d.resolution_status === 'open' && d.module_row_key === m.row_key,
  )
  const uiSurfaces = m.interfaces.filter((i) => i.interface_kind === 'ui_surface')
  const apis = m.interfaces.filter((i) => i.interface_kind === 'api')
  const events = m.interfaces.filter((i) => i.interface_kind === 'event')

  // ── Row-edit launchers ──────────────────────────────────────────────────

  function editScope() {
    setEditing({
      table: 'frs_modules', rowId: m.id, title: `Edit scope — ${m.name}`,
      initialValues: { scope_in: m.scope_in, scope_out: m.scope_out, summary: m.summary },
      isLocked: m.is_locked,
      fields: [
        { name: 'summary', label: 'Summary', type: 'textarea', rows: 3 },
        { name: 'scope_in', label: 'In scope', type: 'textarea', rows: 6,
          placeholder: '- Bullet 1\n- Bullet 2' },
        { name: 'scope_out', label: 'Out of scope', type: 'textarea', rows: 5,
          placeholder: '- Bullet 1\n- Bullet 2' },
      ],
    })
  }

  function editActor(a: FrsModuleActorRow) {
    setEditing({
      table: 'frs_module_actors', rowId: a.id, title: `Edit actor — ${a.actor_name}`,
      initialValues: { actor_name: a.actor_name, relationship: a.relationship, notes: a.notes },
      isLocked: a.is_locked,
      fields: [
        { name: 'actor_name', label: 'Actor name', type: 'text' },
        { name: 'relationship', label: 'Relationship', type: 'enum',
          options: Object.entries(FRS_ACTOR_RELATIONSHIP_LABELS).map(([v, l]) => ({ value: v, label: l })),
        },
        { name: 'notes', label: 'Notes', type: 'textarea', rows: 3 },
      ],
    })
  }

  function editResponsibility(r: FrsModuleResponsibilityRow) {
    setEditing({
      table: 'frs_module_responsibilities', rowId: r.id,
      title: 'Edit responsibility',
      initialValues: { responsibility: r.responsibility, frs_refs: r.frs_refs },
      isLocked: r.is_locked,
      fields: [
        { name: 'responsibility', label: 'Responsibility', type: 'textarea', rows: 3 },
        { name: 'frs_refs', label: 'FRS references', type: 'tags',
          placeholder: 'M001-FRS001, M001-FRS002' },
      ],
    })
  }

  function editInterface(i: FrsModuleInterfaceRow) {
    setEditing({
      table: 'frs_module_interfaces', rowId: i.id, title: `Edit interface — ${i.name}`,
      initialValues: {
        name: i.name,
        interface_kind: i.interface_kind,
        direction: i.direction,
        transport: i.transport ?? '',
        counterpart: i.counterpart ?? '',
        user_role: i.user_role ?? '',
        purpose: i.purpose,
        frs_ref: i.frs_ref ?? '',
      },
      isLocked: i.is_locked,
      fields: [
        { name: 'name', label: 'Name', type: 'text' },
        { name: 'interface_kind', label: 'Kind', type: 'enum', options: [
          { value: 'ui_surface', label: 'UI Surface' },
          { value: 'api', label: 'API' },
          { value: 'event', label: 'Event' },
        ]},
        { name: 'direction', label: 'Direction', type: 'enum', options: [
          { value: 'inbound', label: 'Inbound' },
          { value: 'outbound', label: 'Outbound' },
        ]},
        { name: 'transport', label: 'Transport', type: 'text',
          placeholder: 'rest, event_bus, graphql, …' },
        { name: 'counterpart', label: 'Counterpart module (row_key)', type: 'text',
          placeholder: 'MOD-002' },
        { name: 'user_role', label: 'User role (UI only)', type: 'text' },
        { name: 'purpose', label: 'Purpose', type: 'textarea', rows: 3 },
        { name: 'frs_ref', label: 'FRS reference', type: 'text' },
      ],
    })
  }

  function editStub(s: FrsSpecRow) {
    setEditing({
      table: 'frs_specs', rowId: s.id, title: `Edit backlog stub — ${s.title}`,
      initialValues: {
        title: s.title,
        priority: s.priority,
        br_refs: s.br_refs,
        nfr_refs: s.nfr_refs,
        depends_on: s.depends_on,
        narrative: s.narrative,
      },
      isLocked: s.is_locked,
      fields: [
        { name: 'title', label: 'Title', type: 'text' },
        { name: 'priority', label: 'Priority', type: 'enum', options: [
          { value: 'P0', label: 'P0 — Must' },
          { value: 'P1', label: 'P1 — Should' },
          { value: 'P2', label: 'P2 — Could' },
          { value: 'P3', label: "P3 — Won't (now)" },
        ]},
        { name: 'narrative', label: 'Description', type: 'textarea', rows: 4,
          placeholder: 'What this spec covers; Stage 2 will expand it.' },
        { name: 'br_refs', label: 'BR references', type: 'tags',
          placeholder: 'BR-001, BR-002' },
        { name: 'nfr_refs', label: 'NFR references', type: 'tags',
          placeholder: 'NFR-LAT-01, NFR-SEC-02' },
        { name: 'depends_on', label: 'Depends on (FRS refs)', type: 'tags',
          placeholder: 'M002-FRS001' },
      ],
    })
  }

  function editDataEntity(e: FrsModuleDataEntityRow) {
    setEditing({
      table: 'frs_module_data_entities', rowId: e.id,
      title: `Edit data entity — ${e.entity_name}`,
      initialValues: {
        entity_name: e.entity_name,
        business_purpose: e.business_purpose,
        source_of_truth: e.source_of_truth,
      },
      isLocked: e.is_locked,
      fields: [
        { name: 'entity_name', label: 'Entity name', type: 'text' },
        { name: 'business_purpose', label: 'Business purpose', type: 'textarea', rows: 3 },
        { name: 'source_of_truth', label: 'Source of truth', type: 'text' },
      ],
    })
  }

  // ── Lock & delete ───────────────────────────────────────────────────────

  async function handleToggleLock(table: string, rowId: string, currentLocked: boolean, currentFields: Record<string, unknown>) {
    if (onToggleLock) {
      onToggleLock(table, rowId, currentLocked)
      return
    }
    try {
      if (currentLocked) {
        await api.frs.unlockRow(projectId, table, rowId)
        toast.success('Unlocked')
      } else {
        await api.frs.editRow(projectId, table, rowId, currentFields, { lock: true })
        toast.success('Locked')
      }
      onMutate()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Lock failed')
    }
  }

  async function handleDeleteRow(table: string, rowId: string, label: string) {
    if (!confirm(`Delete this ${label}?\n\nIt will be soft-deleted (status='removed'); regeneration can re-create it.`)) return
    try {
      await api.frs.deleteRow(projectId, table, rowId)
      toast.success('Removed')
      onMutate()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Delete failed')
    }
  }

  return (
    <div className="space-y-4">
      {/* Identity Card */}
      <FrsModuleIdentityCard
        module={m}
        onRegenerate={onRegenerateModule}
        regenerating={busy}
        onLockToggle={() => handleToggleLock('frs_modules', m.id, m.is_locked, {
          name: m.name,
          slug: m.slug,
          summary: m.summary,
          layer: m.layer,
        })}
      />

      {/* Decision banner */}
      {openDecisions.length > 0 && (
        <div className="rounded-lg border border-amber-200 bg-amber-50/60 px-3 py-2.5">
          <div className="flex items-start gap-2">
            <AlertCircle size={14} className="text-amber-600 shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-xs font-semibold text-amber-800">
                {openDecisions.length} [SPEC-DECISION] open
              </p>
              <ul className="mt-1 space-y-1">
                {openDecisions.map((d) => (
                  <li key={d.row_key} className="text-[11px] text-amber-700 leading-snug">
                    <button
                      onClick={() => onOpenDecision(d)}
                      className="text-left hover:underline"
                    >
                      <span className="font-mono">{d.row_key}</span>: {d.question}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* Scope */}
      <Section
        keyName="scope"
        title="Scope"
        open={isOpen('scope')}
        onToggle={() => toggleSection('scope')}
        action={
          <HeaderAction
            label="Edit scope"
            icon={<Pencil size={11} />}
            onClick={editScope}
          />
        }
      >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)] mb-1">
              In scope
            </p>
            <p className="text-[var(--text-secondary)] whitespace-pre-line leading-relaxed">
              {m.scope_in || <em className="text-[var(--text-tertiary)]">No in-scope items yet.</em>}
            </p>
          </div>
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)] mb-1">
              Out of scope
            </p>
            <p className="text-[var(--text-secondary)] whitespace-pre-line leading-relaxed">
              {m.scope_out || <em className="text-[var(--text-tertiary)]">No out-of-scope items yet.</em>}
            </p>
          </div>
        </div>
      </Section>

      {/* Actors & Dependencies */}
      <Section
        keyName="actors"
        title="Actors & Dependencies"
        count={m.actors.length}
        open={isOpen('actors')}
        onToggle={() => toggleSection('actors')}
      >
        {m.actors.length === 0 ? (
          <p className="text-xs text-[var(--text-tertiary)] italic">No actors defined.</p>
        ) : (
          <div className="space-y-1.5">
            {m.actors.map((a) => (
              <RowShell key={a.row_key} isLocked={a.is_locked}>
                <div className="grid grid-cols-[1fr,140px,2fr] gap-3 text-sm flex-1 min-w-0">
                  <span className="font-medium text-[var(--text-primary)] truncate" title={a.actor_name}>
                    {a.actor_name}
                  </span>
                  <span className="text-xs text-[var(--text-tertiary)]">
                    {FRS_ACTOR_RELATIONSHIP_LABELS[a.relationship]}
                  </span>
                  <span className="text-xs text-[var(--text-secondary)] truncate" title={a.notes}>
                    {a.notes || <em className="text-[var(--text-tertiary)]">—</em>}
                  </span>
                </div>
                <RowActions
                  isLocked={a.is_locked}
                  onEdit={() => editActor(a)}
                  onLock={() => handleToggleLock('frs_module_actors', a.id, a.is_locked, {
                    actor_name: a.actor_name, relationship: a.relationship, notes: a.notes,
                  })}
                  onDelete={() => handleDeleteRow('frs_module_actors', a.id, 'actor')}
                />
              </RowShell>
            ))}
          </div>
        )}
      </Section>

      {/* Responsibilities */}
      <Section
        keyName="resp"
        title="Responsibilities"
        count={m.responsibilities.length}
        open={isOpen('resp')}
        onToggle={() => toggleSection('resp')}
      >
        {m.responsibilities.length === 0 ? (
          <p className="text-xs text-[var(--text-tertiary)] italic">No responsibilities defined.</p>
        ) : (
          <ul className="space-y-1.5">
            {m.responsibilities.map((r) => (
              <li key={r.row_key}>
                <RowShell isLocked={r.is_locked}>
                  <div className="flex items-start gap-2 flex-1 min-w-0">
                    <span className="text-[var(--accent)] mt-1 shrink-0">•</span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-[var(--text-secondary)] leading-snug">{r.responsibility}</p>
                      {r.frs_refs.length > 0 && (
                        <p className="text-[10px] text-[var(--text-tertiary)] font-mono mt-0.5">
                          → {r.frs_refs.join(', ')}
                        </p>
                      )}
                    </div>
                  </div>
                  <RowActions
                    isLocked={r.is_locked}
                    onEdit={() => editResponsibility(r)}
                    onLock={() => handleToggleLock('frs_module_responsibilities', r.id, r.is_locked, {
                      responsibility: r.responsibility, frs_refs: r.frs_refs,
                    })}
                    onDelete={() => handleDeleteRow('frs_module_responsibilities', r.id, 'responsibility')}
                  />
                </RowShell>
              </li>
            ))}
          </ul>
        )}
      </Section>

      {/* Interfaces — contract graph + textual list + editable rows */}
      <Section
        keyName="interfaces"
        title="Interfaces"
        count={m.interfaces.length}
        countDetail={`${uiSurfaces.length} UI · ${apis.length} API · ${events.length} event${events.length !== 1 ? 's' : ''}`}
        open={isOpen('interfaces')}
        onToggle={() => toggleSection('interfaces')}
      >
        <FrsContractGraph
          module={m}
          allModules={allModules}
          onNavigateModule={onNavigateModule}
          onEditInterface={(rowKey) => {
            const iface = m.interfaces.find((x) => x.row_key === rowKey)
            if (iface) editInterface(iface)
          }}
        />

        <div className="mt-4 space-y-4">
          {uiSurfaces.length > 0 && (
            <InterfaceList
              title="UI Surfaces"
              kindEmoji={FRS_INTERFACE_KIND_STYLES.ui_surface.emoji}
              items={uiSurfaces}
              renderLeft={(i) => `${FRS_INTERFACE_KIND_STYLES.ui_surface.emoji} ${i.name}`}
              renderMiddle={(i) => i.user_role ?? '—'}
              renderRight={(i) => i.purpose}
              onEdit={editInterface}
              onLock={(i) => handleToggleLock('frs_module_interfaces', i.id, i.is_locked, ifaceFields(i))}
              onDelete={(i) => handleDeleteRow('frs_module_interfaces', i.id, 'interface')}
            />
          )}
          {apis.length > 0 && (
            <InterfaceList
              title="APIs"
              kindEmoji=""
              items={apis}
              renderLeft={(i) => `${i.direction === 'inbound' ? '← in' : '→ out'} · ${i.transport ?? 'rest'}`}
              renderMiddle={(i) => i.name}
              renderRight={(i) => i.counterpart ? `${i.purpose} (${i.counterpart})` : i.purpose}
              onEdit={editInterface}
              onLock={(i) => handleToggleLock('frs_module_interfaces', i.id, i.is_locked, ifaceFields(i))}
              onDelete={(i) => handleDeleteRow('frs_module_interfaces', i.id, 'API')}
            />
          )}
          {events.length > 0 && (
            <InterfaceList
              title="Events"
              kindEmoji=""
              items={events}
              renderLeft={(i) => `${i.direction === 'inbound' ? '← in' : '→ out'} · event_bus`}
              renderMiddle={(i) => i.name}
              renderRight={(i) => i.counterpart ? `${i.purpose} (${i.counterpart})` : i.purpose}
              onEdit={editInterface}
              onLock={(i) => handleToggleLock('frs_module_interfaces', i.id, i.is_locked, ifaceFields(i))}
              onDelete={(i) => handleDeleteRow('frs_module_interfaces', i.id, 'event')}
            />
          )}
        </div>
      </Section>

      {/* Owned data */}
      <Section
        keyName="data"
        title="Owned Data"
        count={m.data_entities.length}
        open={isOpen('data')}
        onToggle={() => toggleSection('data')}
      >
        {m.data_entities.length === 0 ? (
          <p className="text-xs text-[var(--text-tertiary)] italic">No data entities defined.</p>
        ) : (
          <div className="space-y-1.5">
            {m.data_entities.map((e) => (
              <RowShell key={e.row_key} isLocked={e.is_locked}>
                <div className="grid grid-cols-[160px,2fr,1fr] gap-3 text-sm flex-1 min-w-0">
                  <span className="font-mono text-[var(--text-primary)] truncate" title={e.entity_name}>
                    {e.entity_name}
                  </span>
                  <span className="text-xs text-[var(--text-secondary)] truncate" title={e.business_purpose}>
                    {e.business_purpose}
                  </span>
                  <span className="text-xs text-[var(--text-tertiary)] italic truncate" title={e.source_of_truth}>
                    SoT: {e.source_of_truth}
                  </span>
                </div>
                <RowActions
                  isLocked={e.is_locked}
                  onEdit={() => editDataEntity(e)}
                  onLock={() => handleToggleLock('frs_module_data_entities', e.id, e.is_locked, {
                    entity_name: e.entity_name,
                    business_purpose: e.business_purpose,
                    source_of_truth: e.source_of_truth,
                  })}
                  onDelete={() => handleDeleteRow('frs_module_data_entities', e.id, 'data entity')}
                />
              </RowShell>
            ))}
          </div>
        )}
      </Section>

      {/* Backlog */}
      <Section
        keyName="backlog"
        title="FRS Backlog"
        count={m.backlog.length}
        countDetail={`${m.backlog.filter((s) => s.completeness > 0).length} designed · ${m.backlog.filter((s) => s.completeness === 0).length} stub${m.backlog.filter((s) => s.completeness === 0).length !== 1 ? 's' : ''}`}
        open={isOpen('backlog')}
        onToggle={() => toggleSection('backlog')}
      >
        {m.backlog.length === 0 ? (
          <p className="text-xs text-[var(--text-tertiary)] italic">No backlog stubs yet.</p>
        ) : (
          <div className="space-y-2">
            {m.backlog.map((s) => (
              <FrsBacklogStubCard
                key={s.row_key}
                stub={s}
                onDesignNow={onDesignStub ? () => onDesignStub(s.row_key) : undefined}
                onEdit={() => editStub(s)}
                onLockToggle={() => handleToggleLock('frs_specs', s.id, s.is_locked, {
                  title: s.title, priority: s.priority, br_refs: s.br_refs,
                  nfr_refs: s.nfr_refs, depends_on: s.depends_on, narrative: s.narrative,
                })}
                onDelete={() => handleDeleteRow('frs_specs', s.id, 'backlog stub')}
                busy={busy}
              />
            ))}
          </div>
        )}
      </Section>

      {/* Row-edit dialog */}
      {editing && (
        <FrsRowEditDialog
          open
          title={editing.title}
          projectId={projectId}
          table={editing.table}
          rowId={editing.rowId}
          initialValues={editing.initialValues}
          fields={editing.fields}
          isLocked={editing.isLocked}
          onClose={() => setEditing(null)}
          onSaved={onMutate}
        />
      )}
    </div>
  )
}

// ── Section wrapper ─────────────────────────────────────────────────────────

function Section({
  title, count, countDetail, open, onToggle, action, children,
}: {
  keyName: string
  title: string
  count?: number
  countDetail?: string
  open: boolean
  onToggle: () => void
  action?: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <div className="rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface)] overflow-hidden">
      <div className="w-full flex items-center gap-2 px-3 py-2.5 hover:bg-[var(--bg-elevated)] transition-colors">
        <button
          onClick={onToggle}
          aria-expanded={open}
          className="flex-1 flex items-center gap-2 text-left"
        >
          {open ? (
            <ChevronDown size={13} className="shrink-0 text-[var(--text-tertiary)]" />
          ) : (
            <ChevronRight size={13} className="shrink-0 text-[var(--text-tertiary)]" />
          )}
          <span className="text-sm font-semibold text-[var(--text-primary)]">{title}</span>
          {count !== undefined && (
            <span className="text-[11px] text-[var(--text-tertiary)]">
              ({count})
            </span>
          )}
          {countDetail && (
            <span className="text-[10px] text-[var(--text-tertiary)]">
              · {countDetail}
            </span>
          )}
        </button>
        {action}
      </div>
      {open && <div className="px-3 pb-3 pt-1">{children}</div>}
    </div>
  )
}

function HeaderAction({
  label, icon, onClick,
}: { label: string; icon: React.ReactNode; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      title={label}
      className="inline-flex items-center gap-1 rounded-md border border-[var(--border-default)] bg-[var(--bg-surface)] px-2 py-1 text-[10px] font-semibold text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--accent)] transition-colors"
    >
      {icon}
      {label}
    </button>
  )
}

// ── Row shell + actions ─────────────────────────────────────────────────────

function RowShell({
  isLocked, children,
}: { isLocked: boolean; children: React.ReactNode }) {
  return (
    <div
      className={cn(
        'group flex items-center gap-3 rounded-md px-2 py-1.5 transition-colors',
        'hover:bg-[var(--bg-elevated)]',
        isLocked && 'ring-1 ring-amber-200/70 bg-amber-50/30',
      )}
    >
      {children}
    </div>
  )
}

function RowActions({
  isLocked, onEdit, onLock, onDelete,
}: {
  isLocked: boolean
  onEdit: () => void
  onLock: () => void
  onDelete: () => void
}) {
  return (
    <div className="shrink-0 flex items-center gap-0.5 opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition-opacity">
      <IconBtn label="Edit" onClick={onEdit}>
        <Pencil size={11} />
      </IconBtn>
      <IconBtn label={isLocked ? 'Unlock' : 'Lock'} onClick={onLock}>
        {isLocked
          ? <LockOpen size={11} className="text-amber-600" />
          : <Lock size={11} />}
      </IconBtn>
      <IconBtn label="Delete" onClick={onDelete} danger>
        <Trash2 size={11} />
      </IconBtn>
    </div>
  )
}

function IconBtn({
  label, onClick, danger, children,
}: {
  label: string
  onClick: () => void
  danger?: boolean
  children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      title={label}
      aria-label={label}
      className={cn(
        'rounded-md p-1 text-[var(--text-tertiary)] transition-colors',
        danger
          ? 'hover:text-[var(--status-danger)] hover:bg-red-50'
          : 'hover:text-[var(--accent)] hover:bg-[var(--accent-subtle)]',
      )}
    >
      {children}
    </button>
  )
}

// ── Interface list ──────────────────────────────────────────────────────────

function InterfaceList({
  title, items, renderLeft, renderMiddle, renderRight,
  onEdit, onLock, onDelete,
}: {
  title: string
  kindEmoji: string
  items: FrsModuleInterfaceRow[]
  renderLeft: (i: FrsModuleInterfaceRow) => string
  renderMiddle: (i: FrsModuleInterfaceRow) => string
  renderRight: (i: FrsModuleInterfaceRow) => string
  onEdit: (i: FrsModuleInterfaceRow) => void
  onLock: (i: FrsModuleInterfaceRow) => void
  onDelete: (i: FrsModuleInterfaceRow) => void
}) {
  return (
    <div>
      <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)] mb-1">
        {title} ({items.length})
      </p>
      <div className="space-y-1">
        {items.map((it) => (
          <RowShell key={it.row_key} isLocked={it.is_locked}>
            <div className="grid grid-cols-[150px,1fr,2fr,auto] gap-2 text-xs items-center flex-1 min-w-0">
              <span className="text-[var(--text-tertiary)] font-mono truncate" title={renderLeft(it)}>
                {renderLeft(it)}
              </span>
              <span className="font-medium text-[var(--text-primary)] truncate" title={renderMiddle(it)}>
                {renderMiddle(it)}
              </span>
              <span className="text-[var(--text-secondary)] truncate" title={renderRight(it)}>
                {renderRight(it)}
              </span>
              {it.frs_ref && (
                <span className="font-mono text-[10px] text-[var(--accent)]">→ {it.frs_ref}</span>
              )}
            </div>
            <RowActions
              isLocked={it.is_locked}
              onEdit={() => onEdit(it)}
              onLock={() => onLock(it)}
              onDelete={() => onDelete(it)}
            />
          </RowShell>
        ))}
      </div>
    </div>
  )
}

function ifaceFields(i: FrsModuleInterfaceRow): Record<string, unknown> {
  return {
    name: i.name,
    interface_kind: i.interface_kind,
    direction: i.direction,
    transport: i.transport,
    counterpart: i.counterpart,
    user_role: i.user_role,
    purpose: i.purpose,
    frs_ref: i.frs_ref,
  }
}
