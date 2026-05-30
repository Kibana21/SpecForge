'use client'
/**
 * FrsSpecPanel — the per-spec workspace.
 *
 * Renders the 12-section template structure (Intent · §1 UI · §2 Backend ·
 * §3 Data · §4 Cross-Cutting · Independent Test · Acceptance Scenarios ·
 * Functional Requirements · Data & Validation · Errors & Edge Cases ·
 * Observability · Implementation Tasks · Traceability summary). Default
 * expanded: Intent + Acceptance Scenarios + Functional Requirements. Other
 * sections collapse for calm density.
 *
 * Every editable surface delegates to the atomic Phase B-E cards. The header
 * gives Regenerate / Lock / History actions on the FrsSpec row itself.
 */
import { useMemo, useState } from 'react'
import {
  ArrowLeft, BookOpen, ChevronDown, ChevronRight, Loader2, Pencil,
  RotateCcw, Sparkles,
} from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'
import {
  FRS_LAYER_STYLES, FRS_MODULE_LAYER_LABELS, FRS_PRIORITY_STYLES,
} from '@/lib/frs-manifest'
import type {
  FrsLayer, FrsModuleHydrated, FrsPriority, FrsSpecDecisionRow,
  FrsSpecRowOrHydrated,
} from '@/lib/types'
import { FrsRowEditDialog, type FrsRowField } from './FrsRowEditDialog'
import { FrsScreenCard } from './FrsScreenCard'
import { FrsUiComponentCard } from './FrsUiComponentCard'
import { FrsEndpointCard } from './FrsEndpointCard'
import { FrsDataEntityCard } from './FrsDataEntityCard'
import { FrsBusinessRulesTable } from './FrsBusinessRulesTable'
import { FrsScenariosList } from './FrsScenariosList'
import { FrsFunctionalRequirementsList } from './FrsFunctionalRequirementsList'
import { FigmaLinkPrompt } from './FigmaLinkPrompt'
import { FrsSpecDecisionPrompt } from './FrsSpecDecisionPrompt'

const DEFAULT_EXPANDED = new Set(['intent', 'scenarios', 'frs'])

interface Props {
  projectId: string
  spec: FrsSpecRowOrHydrated
  module: FrsModuleHydrated
  /** Refetch the FRS detail after a mutation. */
  onMutate: () => void
  /** Back to module view. */
  onBack: () => void
}

const SPEC_INTENT_FIELDS: FrsRowField[] = [
  { name: 'title', label: 'Title', type: 'text' },
  { name: 'priority', label: 'Priority', type: 'enum', options: [
    { value: 'P0', label: 'P0 — Must' },
    { value: 'P1', label: 'P1 — Should' },
    { value: 'P2', label: 'P2 — Could' },
    { value: 'P3', label: 'P3 — Won’t (now)' },
  ]},
  { name: 'br_refs', label: 'BR refs', type: 'tags', placeholder: 'BR-001, BR-002' },
  { name: 'nfr_refs', label: 'NFR refs', type: 'tags' },
  { name: 'depends_on', label: 'Depends on (FRS refs)', type: 'tags' },
  { name: 'narrative', label: 'Intent / Narrative', type: 'textarea', rows: 6 },
]

const SPEC_TEXT_FIELDS = {
  independent_test: { label: 'Independent Test', rows: 4 },
  data_and_validation: { label: 'Data and Validation', rows: 4 },
  errors_and_edge_cases: { label: 'Errors and Edge Cases', rows: 4 },
  observability: { label: 'Observability', rows: 4 },
} as const

export function FrsSpecPanel({
  projectId, spec, module: m, onMutate, onBack,
}: Props) {
  const [expanded, setExpanded] = useState(DEFAULT_EXPANDED)
  const [busyRegen, setBusyRegen] = useState(false)
  const [editing, setEditing] = useState<null | 'intent' | keyof typeof SPEC_TEXT_FIELDS>(null)
  const [activeDecision, setActiveDecision] = useState<FrsSpecDecisionRow | null>(null)

  const screens = spec.screens ?? []
  const components = spec.ui_components ?? []
  const endpoints = spec.endpoints ?? []
  const entities = spec.data_entities ?? []
  const rules = spec.business_rules ?? []
  const scenarios = spec.scenarios ?? []
  const frs = spec.functional_requirements ?? []
  const decisions = useMemo(() => spec.decisions ?? [], [spec.decisions])
  const traceability = spec.traceability ?? []

  const openDecisions = useMemo(
    () => decisions.filter(d => d.resolution_status === 'open'),
    [decisions],
  )

  const uiBlocked =
    // module declares ui_surface AND no real figma link on any screen
    m.interfaces.some(i => i.interface_kind === 'ui_surface')
    && !screens.some(s => s.figma_link && s.figma_link !== '__none__')

  const skippedFigma =
    screens.some(s => s.figma_link === '__none__')
    && !screens.some(s => s.figma_link && s.figma_link !== '__none__')

  const layerStyle = FRS_LAYER_STYLES[spec.layer as FrsLayer]
  const priorityStyle = FRS_PRIORITY_STYLES[spec.priority as FrsPriority]

  const sceCount = scenarios.length
  const negCount = scenarios.filter(s => s.is_negative).length
  const counterCls = (sceCount >= 6 && negCount >= 2)
    ? 'text-emerald-700'
    : 'text-amber-700'

  function toggle(key: string) {
    setExpanded(prev => {
      const n = new Set(prev)
      if (n.has(key)) n.delete(key); else n.add(key)
      return n
    })
  }

  async function handleRegenerate(scope: 'full' | 'ui_only') {
    setBusyRegen(true)
    try {
      await api.frs.regenerateSpec(projectId, spec.row_key, scope)
      toast.success(scope === 'ui_only' ? 'UI re-authored' : 'Spec regenerated')
      onMutate()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Regenerate failed')
    } finally {
      setBusyRegen(false)
    }
  }

  return (
    <div className="flex flex-col h-full overflow-hidden bg-[var(--bg-base)]">
      {/* Header */}
      <div className="shrink-0 flex items-start gap-3 px-4 py-3 border-b border-[var(--border-default)] bg-[var(--bg-surface)]">
        <button
          onClick={onBack}
          className="shrink-0 inline-flex items-center gap-1 rounded-md px-2 py-1 text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] transition-colors"
        >
          <ArrowLeft size={14} /> Module
        </button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <code className="text-[11px] font-mono text-[var(--text-tertiary)]">
              {spec.row_key}
            </code>
            <span
              className={cn(
                'text-[10px] font-semibold rounded px-1.5 py-0.5 border',
                priorityStyle?.bg, priorityStyle?.text, priorityStyle?.border,
              )}
            >
              {spec.priority}
            </span>
            <span
              className={cn(
                'text-[10px] font-semibold rounded-full px-2 py-0.5 border',
                layerStyle?.ribbon,
              )}
            >
              {FRS_MODULE_LAYER_LABELS[spec.layer as FrsLayer]}
            </span>
            {(spec.completeness ?? 0) > 0 && (
              <span className="text-[10px] text-[var(--text-tertiary)]">
                completeness {spec.completeness}% · {spec.confidence}
              </span>
            )}
          </div>
          <h1 className="mt-0.5 text-lg font-semibold text-[var(--text-primary)] leading-snug truncate">
            {spec.title}
          </h1>
          <div className="mt-0.5 flex items-center gap-2 text-[11px] text-[var(--text-secondary)] flex-wrap">
            <span>Module:</span>
            <code className="font-mono">{m.row_key}</code>
            <span className="text-[var(--text-tertiary)]">·</span>
            <span>{m.name}</span>
            {spec.depends_on?.length ? (
              <>
                <span className="text-[var(--text-tertiary)]">·</span>
                <span>Depends on:</span>
                <span className="font-mono text-[var(--accent)]">
                  {spec.depends_on.join(', ')}
                </span>
              </>
            ) : null}
          </div>
        </div>
        <div className="shrink-0 flex items-center gap-1">
          <button
            onClick={() => handleRegenerate('full')}
            disabled={busyRegen}
            title="Re-author the entire spec from scratch"
            className="inline-flex items-center gap-1 rounded-md border border-[var(--border-default)] bg-[var(--bg-surface)] px-2 py-1 text-xs hover:bg-[var(--bg-elevated)] disabled:opacity-50 transition-colors"
          >
            {busyRegen ? <Loader2 size={11} className="animate-spin" /> : <RotateCcw size={11} />}
            Regenerate
          </button>
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-auto px-4 py-3 space-y-3">
        {/* Open decision banners */}
        {openDecisions.length > 0 && (
          <div className="rounded-xl border border-amber-200 bg-amber-50/70 px-3 py-2">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-amber-800 mb-1">
              <Sparkles size={11} className="inline mr-1" />
              {openDecisions.length} open [SPEC-DECISION]
            </p>
            <ul className="space-y-0.5">
              {openDecisions.map(d => (
                <li key={d.row_key} className="text-xs text-amber-900">
                  <button
                    onClick={() => setActiveDecision(d)}
                    className="text-left hover:underline"
                  >
                    {d.question}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Intent / Narrative */}
        <Section
          k="intent"
          title="Intent / Narrative"
          open={expanded.has('intent')}
          onToggle={() => toggle('intent')}
          action={
            <HeaderAction onClick={() => setEditing('intent')} label="Edit metadata + narrative">
              <Pencil size={10} />
            </HeaderAction>
          }
        >
          {spec.narrative
            ? <p className="text-sm text-[var(--text-secondary)] leading-relaxed whitespace-pre-line">{spec.narrative}</p>
            : <p className="text-xs italic text-[var(--text-tertiary)]">No narrative yet — click [Edit] to author or [Regenerate].</p>
          }
        </Section>

        {/* §1 UI Specification */}
        <Section
          k="ui"
          title="§ 1 UI Specification"
          open={expanded.has('ui')}
          onToggle={() => toggle('ui')}
        >
          {uiBlocked || skippedFigma ? (
            <FigmaLinkPrompt
              projectId={projectId}
              specRowKey={spec.row_key}
              hasSentinel={skippedFigma}
              onChanged={onMutate}
            />
          ) : screens.length === 0 ? (
            <p className="text-xs italic text-[var(--text-tertiary)]">
              No UI surfaces for this spec. (Backend-only FRS.)
            </p>
          ) : (
            <div className="space-y-3">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)] mb-1">
                  1.1 Screens
                </p>
                <div className="space-y-2">
                  {screens.map(s => (
                    <FrsScreenCard
                      key={s.row_key}
                      projectId={projectId}
                      screen={s}
                      onMutate={onMutate}
                    />
                  ))}
                </div>
              </div>
              {components.length > 0 && (
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)] mb-1">
                    1.2 Components ({components.length})
                  </p>
                  <div className="space-y-1.5">
                    {components.map(c => (
                      <FrsUiComponentCard
                        key={c.row_key}
                        projectId={projectId}
                        component={c}
                        screenLabel={
                          screens.find(s => s.row_key === c.screen_row_key)?.screen_name
                        }
                        onMutate={onMutate}
                      />
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </Section>

        {/* §2 Backend Service Specification */}
        <Section
          k="backend"
          title="§ 2 Backend Service Specification"
          open={expanded.has('backend')}
          onToggle={() => toggle('backend')}
        >
          {endpoints.length === 0 ? (
            <p className="text-xs italic text-[var(--text-tertiary)]">
              No backend endpoints. (UI-only / pure aggregation spec.)
            </p>
          ) : (
            <div className="space-y-2">
              {endpoints.map(e => (
                <FrsEndpointCard
                  key={e.row_key}
                  projectId={projectId}
                  endpoint={e}
                  onMutate={onMutate}
                />
              ))}
            </div>
          )}
        </Section>

        {/* §3 Data / Storage / Cache */}
        <Section
          k="data"
          title="§ 3 Data / Storage / Cache"
          open={expanded.has('data')}
          onToggle={() => toggle('data')}
        >
          {entities.length === 0 ? (
            <p className="text-xs italic text-[var(--text-tertiary)]">
              No persistent data for this spec.
            </p>
          ) : (
            <div className="space-y-2">
              {entities.map(e => (
                <FrsDataEntityCard
                  key={e.row_key}
                  projectId={projectId}
                  entity={e}
                  onMutate={onMutate}
                />
              ))}
            </div>
          )}
        </Section>

        {/* §4 Cross-Cutting */}
        <Section
          k="cc"
          title="§ 4 Cross-Cutting"
          open={expanded.has('cc')}
          onToggle={() => toggle('cc')}
        >
          <FrsBusinessRulesTable
            projectId={projectId}
            rules={rules}
            specRowKey={spec.row_key}
            onMutate={onMutate}
          />
        </Section>

        {/* Independent Test */}
        <TextSection
          k="indtest"
          field="independent_test"
          title="Independent Test"
          value={spec.independent_test}
          open={expanded.has('indtest')}
          onToggle={() => toggle('indtest')}
          onEdit={() => setEditing('independent_test')}
        />

        {/* Acceptance Scenarios */}
        <Section
          k="scenarios"
          title={`Acceptance Scenarios (${sceCount}, ${negCount} negative)`}
          titleCls={counterCls}
          open={expanded.has('scenarios')}
          onToggle={() => toggle('scenarios')}
        >
          <FrsScenariosList
            projectId={projectId}
            scenarios={scenarios}
            specRowKey={spec.row_key}
            onMutate={onMutate}
          />
        </Section>

        {/* Functional Requirements */}
        <Section
          k="frs"
          title={`Functional Requirements (${frs.length})`}
          open={expanded.has('frs')}
          onToggle={() => toggle('frs')}
        >
          <FrsFunctionalRequirementsList
            projectId={projectId}
            frs={frs}
            specRowKey={spec.row_key}
            onMutate={onMutate}
          />
        </Section>

        {/* Data and Validation */}
        <TextSection
          k="dataval"
          field="data_and_validation"
          title="Data and Validation"
          value={spec.data_and_validation}
          open={expanded.has('dataval')}
          onToggle={() => toggle('dataval')}
          onEdit={() => setEditing('data_and_validation')}
        />

        {/* Errors and Edge Cases */}
        <TextSection
          k="errors"
          field="errors_and_edge_cases"
          title="Errors and Edge Cases"
          value={spec.errors_and_edge_cases}
          open={expanded.has('errors')}
          onToggle={() => toggle('errors')}
          onEdit={() => setEditing('errors_and_edge_cases')}
        />

        {/* Observability */}
        <TextSection
          k="obs"
          field="observability"
          title="Observability"
          value={spec.observability}
          open={expanded.has('obs')}
          onToggle={() => toggle('obs')}
          onEdit={() => setEditing('observability')}
        />

        {/* Traceability summary */}
        <Section
          k="trace"
          title={`Traceability (${traceability.length})`}
          open={expanded.has('trace')}
          onToggle={() => toggle('trace')}
        >
          {traceability.length === 0 ? (
            <p className="text-xs italic text-[var(--text-tertiary)]">
              No traceability rows yet.
            </p>
          ) : (
            <ul className="space-y-0.5 text-xs">
              {traceability.map(t => (
                <li key={t.id} className="flex items-center gap-1.5">
                  <BookOpen size={10} className="text-[var(--text-tertiary)] shrink-0" />
                  <code className="text-[var(--text-tertiary)]">
                    {t.source_table}/{t.source_row_key}
                  </code>
                  <span className="text-[var(--text-tertiary)]">→</span>
                  <span className="rounded px-1.5 py-0.5 text-[10px] font-semibold bg-[var(--bg-elevated)] text-[var(--text-secondary)]">
                    {t.target_kind}
                  </span>
                  <code className="font-mono text-[var(--accent)]">
                    {t.target_ref}
                  </code>
                  {t.target_label && (
                    <span className="text-[var(--text-secondary)] truncate">— {t.target_label}</span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Section>
      </div>

      {editing === 'intent' && (
        <FrsRowEditDialog
          open
          title={`Edit spec metadata — ${spec.row_key}`}
          projectId={projectId}
          table="frs_specs"
          rowId={spec.id}
          initialValues={{
            title: spec.title,
            priority: spec.priority,
            br_refs: spec.br_refs,
            nfr_refs: spec.nfr_refs,
            depends_on: spec.depends_on,
            narrative: spec.narrative,
          }}
          fields={SPEC_INTENT_FIELDS}
          isLocked={spec.is_locked}
          onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); onMutate() }}
        />
      )}

      {editing && editing !== 'intent' && (
        <FrsRowEditDialog
          open
          title={`Edit ${SPEC_TEXT_FIELDS[editing].label} — ${spec.row_key}`}
          projectId={projectId}
          table="frs_specs"
          rowId={spec.id}
          initialValues={{ [editing]: (spec as unknown as Record<string, unknown>)[editing] ?? '' }}
          fields={[{
            name: editing,
            label: SPEC_TEXT_FIELDS[editing].label,
            type: 'textarea',
            rows: SPEC_TEXT_FIELDS[editing].rows,
          }]}
          isLocked={spec.is_locked}
          onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); onMutate() }}
        />
      )}

      {activeDecision && (
        <FrsSpecDecisionPrompt
          projectId={projectId}
          decision={activeDecision}
          onClose={() => setActiveDecision(null)}
          onResolved={(triggeredRegen) => {
            setActiveDecision(null)
            onMutate()
            if (triggeredRegen) {
              handleRegenerate('full').catch(() => {})
            }
          }}
        />
      )}
    </div>
  )
}

// ── Section primitives ──────────────────────────────────────────────────────

function Section({
  title, titleCls, open, onToggle, action, children,
}: {
  k: string
  title: string
  titleCls?: string
  open: boolean
  onToggle: () => void
  action?: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <div className="rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface)] overflow-hidden">
      <div className="flex items-center gap-2 px-3 py-2 hover:bg-[var(--bg-elevated)] transition-colors">
        <button
          onClick={onToggle}
          aria-expanded={open}
          className="flex-1 flex items-center gap-2 text-left"
        >
          {open
            ? <ChevronDown size={13} className="shrink-0 text-[var(--text-tertiary)]" />
            : <ChevronRight size={13} className="shrink-0 text-[var(--text-tertiary)]" />}
          <span className={cn(
            'text-sm font-semibold text-[var(--text-primary)]',
            titleCls,
          )}>
            {title}
          </span>
        </button>
        {action}
      </div>
      {open && <div className="px-3 pb-3 pt-1">{children}</div>}
    </div>
  )
}

function TextSection({
  k, field, title, value, open, onToggle, onEdit,
}: {
  k: string
  field: keyof typeof SPEC_TEXT_FIELDS
  title: string
  value: string
  open: boolean
  onToggle: () => void
  onEdit: () => void
}) {
  return (
    <Section
      k={k}
      title={title}
      open={open}
      onToggle={onToggle}
      action={
        <HeaderAction onClick={onEdit} label={`Edit ${field}`}>
          <Pencil size={10} />
        </HeaderAction>
      }
    >
      {value
        ? <p className="text-sm text-[var(--text-secondary)] leading-relaxed whitespace-pre-line">{value}</p>
        : <p className="text-xs italic text-[var(--text-tertiary)]">No content — click [Edit] to author.</p>}
    </Section>
  )
}

function HeaderAction({
  onClick, label, children,
}: {
  onClick: () => void
  label: string
  children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      title={label}
      aria-label={label}
      className="inline-flex items-center gap-1 rounded-md border border-[var(--border-default)] bg-[var(--bg-surface)] px-2 py-1 text-[10px] font-semibold text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--accent)] transition-colors"
    >
      {children}
      Edit
    </button>
  )
}
