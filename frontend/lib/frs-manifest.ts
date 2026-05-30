/**
 * FRS frontend manifest — mirrors backend `services/artifacts/manifest/frs.py`.
 *
 * Stage A (modularize) + Stage B (design_module) labels, discover catalog,
 * design tokens for Layer / Priority / Trace-kind, and the capability-icon
 * picker.
 */

// ── Discover catalog ──────────────────────────────────────────────────────────

export const FRS_DISCOVER_CATEGORIES = [
  { key: 'scope',        emoji: '🎯', label: 'Scope',        color: 'emerald' },
  { key: 'personas',     emoji: '👥', label: 'Personas',     color: 'sky' },
  { key: 'integrations', emoji: '🔄', label: 'Integrations', color: 'violet' },
  { key: 'data',         emoji: '📊', label: 'Data',         color: 'amber' },
  { key: 'nfrs',         emoji: '⚡', label: 'NFRs',         color: 'yellow' },
  { key: 'security',     emoji: '🛡', label: 'Security',     color: 'rose' },
  { key: 'errors',       emoji: '⚠',  label: 'Errors',       color: 'orange' },
  { key: 'ui',           emoji: '🎨', label: 'UI',           color: 'pink' },
  { key: 'delivery',     emoji: '🚀', label: 'Delivery',     color: 'blue' },
] as const

export const FRS_DISCOVER_QUESTIONS = [
  { key: 'frs_1a', category: 'scope',        text: 'What user workflows are P0 in this FRS bundle?' },
  { key: 'frs_1b', category: 'scope',        text: 'Any modules you\'d like to be pre-defined?' },
  { key: 'frs_2a', category: 'personas',     text: 'Who are the primary roles?' },
  { key: 'frs_3a', category: 'integrations', text: 'Which external systems will the modules call?' },
  { key: 'frs_3b', category: 'integrations', text: 'Sync API or async events for cross-module communication?' },
  { key: 'frs_4a', category: 'data',         text: 'Source of truth for the main entities? Read vs write patterns?' },
  { key: 'frs_5a', category: 'nfrs',         text: 'Latency / availability / scalability targets you care about?' },
  { key: 'frs_6a', category: 'security',     text: 'Auth/RBAC model? Data sensitivity per entity?' },
  { key: 'frs_6b', category: 'security',     text: 'Audit / compliance requirements that drive design?' },
  { key: 'frs_7a', category: 'errors',       text: 'Failure-handling strategy — retry, queue, fail-fast?' },
  { key: 'frs_8a', category: 'ui',           text: 'Will Figma designs be provided? Where?' },
  { key: 'frs_9a', category: 'delivery',     text: 'Phasing — which modules must ship first?' },
] as const

// Stage A uses these 7 (modularize); Stage B uses the remaining 6 (design_module)
export const FRS_STAGE_A_QUESTION_KEYS = [
  'frs_1a', 'frs_1b', 'frs_2a', 'frs_3a', 'frs_3b', 'frs_4a', 'frs_9a',
] as const

export type FrsCategoryKey = (typeof FRS_DISCOVER_CATEGORIES)[number]['key']
export type FrsQuestionKey = (typeof FRS_DISCOVER_QUESTIONS)[number]['key']

// ── Layer styles ──────────────────────────────────────────────────────────────

export const FRS_MODULE_LAYER_LABELS = {
  foundation:    'Foundation',
  vertical:      'Vertical Feature',
  cross_cutting: 'Cross-cutting',
} as const

export const FRS_LAYER_STYLES = {
  foundation: {
    accent: 'var(--frs-layer-foundation)',
    bg: 'var(--frs-layer-foundation-bg)',
    border: 'var(--frs-layer-foundation-border)',
    iconName: 'Anchor',
    ribbon: 'bg-amber-100 text-amber-800 border-amber-300',
  },
  vertical: {
    accent: 'var(--accent)',
    bg: 'var(--accent-subtle)',
    border: 'var(--accent-subtle)',
    iconName: 'Layers',
    ribbon: 'bg-[var(--accent-subtle)] text-[var(--accent)] border-[var(--accent)]/30',
  },
  cross_cutting: {
    accent: 'var(--frs-layer-cross-cutting)',
    bg: 'var(--frs-layer-cross-cutting-bg)',
    border: 'var(--frs-layer-cross-cutting-border)',
    iconName: 'Network',
    ribbon: 'bg-sky-100 text-sky-800 border-sky-300',
  },
} as const

export type FrsLayer = keyof typeof FRS_LAYER_STYLES

// ── Priority pill colours (P0–P3) ────────────────────────────────────────────

export const FRS_PRIORITY_STYLES = {
  P0: { bg: 'bg-red-50',    text: 'text-red-700',    border: 'border-red-200',    label: 'P0' },
  P1: { bg: 'bg-amber-50',  text: 'text-amber-700',  border: 'border-amber-200',  label: 'P1' },
  P2: { bg: 'bg-blue-50',   text: 'text-blue-700',   border: 'border-blue-200',   label: 'P2' },
  P3: { bg: 'bg-gray-50',   text: 'text-gray-500',   border: 'border-gray-200',   label: 'P3' },
} as const

export type FrsPriority = keyof typeof FRS_PRIORITY_STYLES

// ── Trace chip palette ────────────────────────────────────────────────────────

export const FRS_TRACE_KIND_STYLES = {
  brd_business_requirement: { bg: 'bg-pink-50',    text: 'text-pink-700',    border: 'border-l-2 border-pink-500',    label: 'BR' },
  brd_objective:            { bg: 'bg-pink-50',    text: 'text-pink-700',    border: 'border-l-2 border-pink-500',    label: 'OBJ' },
  brd_kpi:                  { bg: 'bg-pink-50',    text: 'text-pink-700',    border: 'border-l-2 border-pink-500',    label: 'KPI' },
  brd_risk:                 { bg: 'bg-pink-50',    text: 'text-pink-700',    border: 'border-l-2 border-pink-500',    label: 'RSK' },
  brd_text_block:           { bg: 'bg-pink-50',    text: 'text-pink-700',    border: 'border-l-2 border-pink-500',    label: 'BRD' },
  nfr_driver:               { bg: 'bg-yellow-50',  text: 'text-yellow-700',  border: 'border-l-2 border-yellow-500',  label: 'NFR' },
  app_fact:                 { bg: 'bg-blue-50',    text: 'text-blue-700',    border: 'border-l-2 border-blue-500',    label: 'App' },
  doc_section:              { bg: 'bg-sky-50',     text: 'text-sky-700',     border: 'border-l-2 border-sky-500',     label: 'Doc' },
  discover_qa:              { bg: 'bg-violet-50',  text: 'text-violet-700',  border: 'border-l-2 border-violet-500',  label: 'Q&A' },
  within_frs:               { bg: 'bg-gray-50',    text: 'text-gray-700',    border: 'border-l-2 border-gray-500',    label: 'FRS' },
} as const

export type FrsTraceKind = keyof typeof FRS_TRACE_KIND_STYLES

// ── Interface kind styles ─────────────────────────────────────────────────────

export const FRS_INTERFACE_KIND_STYLES = {
  ui_surface: { label: 'UI Surface', emoji: '🖥', text: 'text-emerald-700' },
  api:        { label: 'API',        emoji: '🔌', text: 'text-blue-700' },
  event:      { label: 'Event',      emoji: '📤', text: 'text-violet-700' },
} as const

export const FRS_ACTOR_RELATIONSHIP_LABELS = {
  primary_user:        'Primary user',
  dependency:          'Dependency',
  external_system:     'External system',
  downstream_consumer: 'Downstream consumer',
} as const

// ── Decision status ───────────────────────────────────────────────────────────

export const FRS_DECISION_STATUS_LABELS = {
  open:         'Open',
  accepted_ai:  'Accepted (AI rec)',
  overridden:   'Overridden',
  dismissed:    'Dismissed',
} as const

// ── Finding groups ────────────────────────────────────────────────────────────

// ── HTTP method palette (FrsEndpointCard) ─────────────────────────────────────

export const FRS_HTTP_METHOD_STYLES = {
  GET:    { color: 'text-green-700',  bg: 'bg-green-50',  border: 'border-green-200',  dot: 'bg-green-500'  },
  POST:   { color: 'text-blue-700',   bg: 'bg-blue-50',   border: 'border-blue-200',   dot: 'bg-blue-500'   },
  PUT:    { color: 'text-amber-700',  bg: 'bg-amber-50',  border: 'border-amber-200',  dot: 'bg-amber-500'  },
  PATCH:  { color: 'text-violet-700', bg: 'bg-violet-50', border: 'border-violet-200', dot: 'bg-violet-500' },
  DELETE: { color: 'text-red-700',    bg: 'bg-red-50',    border: 'border-red-200',    dot: 'bg-red-500'    },
} as const

// ── Finding groups ────────────────────────────────────────────────────────────

export const FRS_FINDING_GROUPS = [
  { key: 'critical', label: 'Critical', cls: 'text-red-700 bg-red-50 border-red-200' },
  { key: 'major',    label: 'Major',    cls: 'text-amber-700 bg-amber-50 border-amber-200' },
  { key: 'minor',    label: 'Minor',    cls: 'text-blue-700 bg-blue-50 border-blue-200' },
  { key: 'coverage', label: 'Coverage', cls: 'text-violet-700 bg-violet-50 border-violet-200' },
  { key: 'warnings', label: 'Warnings', cls: 'text-gray-700 bg-gray-50 border-gray-200' },
] as const

// ── Capability icon picker ────────────────────────────────────────────────────

/**
 * Pick a lucide icon name based on the module slug. Falls back to `Box`.
 * Returns the icon NAME — the consumer dynamically imports + renders it
 * (keeps this manifest free of React imports).
 */
export function pickCapabilityIconName(slug: string): string {
  const s = slug.toLowerCase()
  if (/(auth|identity|login|verify|session)/.test(s)) return 'KeyRound'
  if (/(notif|email|alert|message|comm)/.test(s)) return 'Bell'
  if (/(intake|submission|onboard|register|signup)/.test(s)) return 'UserPlus'
  if (/(triage|routing|classification|dispatch)/.test(s)) return 'GitBranch'
  if (/(payment|billing|settlement|invoice|charge)/.test(s)) return 'CreditCard'
  if (/(audit|compliance|log|trail)/.test(s)) return 'ScrollText'
  if (/(cross-cutting|standards|foundation|shared|common)/.test(s)) return 'Anchor'
  if (/(claim|insurance|policy)/.test(s)) return 'FileText'
  if (/(doc|document|file|upload|ocr)/.test(s)) return 'FileSearch'
  if (/(conversation|chat|nlu|assist|dialog)/.test(s)) return 'MessageSquare'
  if (/(report|analytics|dashboard|insight)/.test(s)) return 'BarChart3'
  if (/(customer|user|profile)/.test(s)) return 'User'
  if (/(data|store|persist|cache)/.test(s)) return 'Database'
  if (/(workflow|process|orchestrat)/.test(s)) return 'Workflow'
  return 'Box'
}
