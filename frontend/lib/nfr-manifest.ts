// NFR (E5) frontend manifest — category metadata, MoSCoW + trace styles, finding groups.
import type { NfrCategory, NfrPriority, NfrTraceKind } from './types'

export const NFR_CATEGORIES: ReadonlyArray<{
  key: NfrCategory
  emoji: string
  label: string
  accent: string  // CSS var
}> = [
  { key: 'performance',    emoji: '⚡', label: 'Performance & Efficiency',         accent: 'var(--nfr-performance)' },
  { key: 'security',       emoji: '🛡', label: 'Security & Compliance',            accent: 'var(--nfr-security)' },
  { key: 'availability',   emoji: '🟢', label: 'Availability & Resilience',        accent: 'var(--nfr-availability)' },
  { key: 'usability',      emoji: '🎨', label: 'Usability',                        accent: 'var(--nfr-usability)' },
  { key: 'scalability',    emoji: '📈', label: 'Scalability & Capacity',           accent: 'var(--nfr-scalability)' },
  { key: 'maintainability',emoji: '🔧', label: 'Maintainability & Supportability', accent: 'var(--nfr-maintainability)' },
  { key: 'portability',    emoji: '🔌', label: 'Portability & Compatibility',      accent: 'var(--nfr-portability)' },
] as const

export const NFR_CATEGORY_LABEL: Record<NfrCategory, string> = Object.fromEntries(
  NFR_CATEGORIES.map((c) => [c.key, c.label]),
) as Record<NfrCategory, string>

export const NFR_PRIORITY_STYLES: Record<NfrPriority, {
  label: string; weight: number; bg: string; text: string; border: string; dot: string
}> = {
  must:   { label: 'Must',   weight: 4, bg: 'bg-red-50',   text: 'text-red-700',   border: 'border-red-200',   dot: 'var(--nfr-must)' },
  should: { label: 'Should', weight: 3, bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200', dot: 'var(--nfr-should)' },
  could:  { label: 'Could',  weight: 2, bg: 'bg-blue-50',  text: 'text-blue-700',  border: 'border-blue-200',  dot: 'var(--nfr-could)' },
  wont:   { label: "Won't",  weight: 1, bg: 'bg-gray-50',  text: 'text-gray-500',  border: 'border-gray-200',  dot: 'var(--nfr-wont)' },
}

export const NFR_TRACE_STYLES: Record<string, { bg: string; text: string; border: string; label: string }> = {
  brd_objective:            { bg: 'bg-pink-50',   text: 'text-pink-700',   border: 'border-l-2 border-pink-500',   label: 'OBJ' },
  brd_business_requirement: { bg: 'bg-pink-50',   text: 'text-pink-700',   border: 'border-l-2 border-pink-500',   label: 'BR' },
  brd_kpi:                  { bg: 'bg-pink-50',   text: 'text-pink-700',   border: 'border-l-2 border-pink-500',   label: 'KPI' },
  brd_risk:                 { bg: 'bg-pink-50',   text: 'text-pink-700',   border: 'border-l-2 border-pink-500',   label: 'RSK' },
  brd_text_block:           { bg: 'bg-pink-50',   text: 'text-pink-700',   border: 'border-l-2 border-pink-500',   label: 'BRD' },
  app_fact:                 { bg: 'bg-blue-50',   text: 'text-blue-700',   border: 'border-l-2 border-blue-500',   label: 'App' },
  doc_section:              { bg: 'bg-sky-50',    text: 'text-sky-700',    border: 'border-l-2 border-sky-500',    label: 'Doc' },
  discover_qa:              { bg: 'bg-violet-50', text: 'text-violet-700', border: 'border-l-2 border-violet-500', label: 'Q&A' },
  within_nfr:               { bg: 'bg-gray-50',   text: 'text-gray-700',   border: 'border-l-2 border-gray-400',   label: 'NFR' },
}

export const NFR_FINDING_GROUPS = [
  { key: 'critical', label: 'Critical', cls: 'text-red-700 bg-red-50 border-red-200' },
  { key: 'major',    label: 'Major',    cls: 'text-amber-700 bg-amber-50 border-amber-200' },
  { key: 'minor',    label: 'Minor',    cls: 'text-blue-700 bg-blue-50 border-blue-200' },
  { key: 'warnings', label: 'Warnings', cls: 'text-gray-700 bg-gray-50 border-gray-200' },
] as const

// Editable governance sections (requirements handled separately by category).
export const NFR_GOVERNANCE_SECTIONS: ReadonlyArray<{
  table: string; label: string; emoji: string; columns: { key: string; label: string; wide?: boolean }[]
}> = [
  { table: 'nfr_risks', label: 'Risks', emoji: '⚠️', columns: [
    { key: 'risk_id', label: 'Risk ID' }, { key: 'description', label: 'Description', wide: true },
    { key: 'affected_attribute', label: 'Affected' }, { key: 'impact', label: 'Impact' },
    { key: 'likelihood', label: 'Likelihood' }, { key: 'mitigation', label: 'Mitigation', wide: true },
    { key: 'owner', label: 'Owner' }, { key: 'risk_status', label: 'Status' },
  ] },
  { table: 'nfr_tradeoffs', label: 'Trade-offs', emoji: '⚖️', columns: [
    { key: 'tradeoff', label: 'Trade-off', wide: true }, { key: 'decision', label: 'Decision', wide: true },
    { key: 'rationale', label: 'Rationale', wide: true }, { key: 'decision_maker', label: 'Decision Maker' },
  ] },
  { table: 'nfr_open_questions', label: 'Open Questions', emoji: '❓', columns: [
    { key: 'question', label: 'Question', wide: true }, { key: 'owner', label: 'Owner' },
    { key: 'due_date', label: 'Due' }, { key: 'oq_status', label: 'Status' },
  ] },
  { table: 'nfr_decisions', label: 'Pending Decisions', emoji: '🧭', columns: [
    { key: 'description', label: 'Description', wide: true }, { key: 'owner', label: 'Owner' },
    { key: 'target_date', label: 'Target' }, { key: 'decision_status', label: 'Status' },
  ] },
  { table: 'nfr_references', label: 'References', emoji: '📚', columns: [
    { key: 'ref_type', label: 'Type' }, { key: 'title', label: 'Title', wide: true },
    { key: 'location', label: 'Location', wide: true }, { key: 'notes', label: 'Notes', wide: true },
  ] },
  { table: 'nfr_glossary', label: 'Glossary', emoji: '📖', columns: [
    { key: 'term', label: 'Term' }, { key: 'definition', label: 'Definition', wide: true },
  ] },
] as const
