export const BRD_SECTIONS = [
  { num: 1, key: 'business_context', title: 'Business Context', unit_key: 'business_context', emoji: '🏢' },
  { num: 2, key: 'problem_statement', title: 'Problem Statement', unit_key: 'problem_statement', emoji: '🎯' },
  { num: 3, key: 'objectives', title: 'Strategic Objectives', unit_key: 'objectives', emoji: '📊' },
  { num: 4, key: 'stakeholders', title: 'Stakeholders & Actors', unit_key: 'stakeholders', emoji: '👥' },
  { num: 5, key: 'scope', title: 'Scope', unit_key: 'scope', emoji: '📦' },
  { num: 6, key: 'processes', title: 'Business Processes', unit_key: 'asis_process', emoji: '🔄' },
  { num: 7, key: 'business_requirements', title: 'Business Requirements', unit_key: 'business_requirements', emoji: '⭐', isKeystone: true },
  { num: 8, key: 'data_reporting', title: 'Data & Reporting', unit_key: 'data_entities', emoji: '📈' },
  { num: 9, key: 'assumptions', title: 'Assumptions, Deps & Constraints', unit_key: 'assumptions', emoji: '📋' },
  { num: 10, key: 'risks', title: 'Risks & Issues', unit_key: 'risks', emoji: '⚠️' },
  { num: 11, key: 'implementation', title: 'Implementation & Phasing', unit_key: 'implementation_phases', emoji: '🚀' },
  { num: 12, key: 'kpis', title: 'KPIs & Success Metrics', unit_key: 'kpis', emoji: '📉' },
  { num: 13, key: 'open_questions', title: 'Open Questions & Decisions', unit_key: 'open_questions', emoji: '❓' },
  { num: 14, key: 'references', title: 'References & Glossary', unit_key: 'references', emoji: '📚' },
] as const

export const BRD_UNITS = [
  { key: 'business_context', label: 'Business Context', depends_on: [] as string[] },
  { key: 'problem_statement', label: 'Problem Statement', depends_on: ['business_context'] },
  { key: 'objectives', label: 'Objectives', depends_on: ['problem_statement'] },
  { key: 'stakeholders', label: 'Stakeholders', depends_on: ['objectives'] },
  { key: 'actors', label: 'Actors', depends_on: ['stakeholders'] },
  { key: 'scope', label: 'Scope', depends_on: ['objectives', 'stakeholders'] },
  { key: 'asis_process', label: 'As-Is Process', depends_on: ['scope', 'stakeholders'] },
  { key: 'tobe_process', label: 'To-Be Process', depends_on: ['asis_process', 'scope'] },
  { key: 'business_requirements', label: 'Business Requirements ★', depends_on: ['objectives', 'scope', 'asis_process', 'tobe_process', 'stakeholders'] },
  { key: 'data_entities', label: 'Data Entities', depends_on: ['business_requirements', 'scope'] },
  { key: 'report_requirements', label: 'Report Requirements', depends_on: ['business_requirements', 'kpis'] },
  { key: 'assumptions', label: 'Assumptions', depends_on: ['scope', 'business_requirements'] },
  { key: 'constraints', label: 'Constraints', depends_on: ['scope', 'business_requirements'] },
  { key: 'dependencies', label: 'Dependencies', depends_on: ['scope', 'business_requirements'] },
  { key: 'risks', label: 'Risks', depends_on: ['scope', 'assumptions', 'constraints', 'dependencies'] },
  { key: 'implementation_phases', label: 'Implementation Phases', depends_on: ['business_requirements', 'risks'] },
  { key: 'milestones', label: 'Milestones', depends_on: ['implementation_phases'] },
  { key: 'kpis', label: 'KPIs', depends_on: ['objectives', 'business_requirements'] },
  { key: 'open_questions', label: 'Open Questions', depends_on: ['business_requirements', 'risks', 'dependencies'] },
  { key: 'decisions', label: 'Decisions', depends_on: ['scope', 'business_requirements'] },
  { key: 'references', label: 'References', depends_on: ['business_context'] },
  { key: 'glossary', label: 'Glossary', depends_on: ['business_context', 'business_requirements'] },
] as const

export const MOSCOW_COLORS = {
  must:   { bg: 'bg-red-50',  text: 'text-red-700',  border: 'border-red-200' },
  should: { bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200' },
  could:  { bg: 'bg-blue-50',  text: 'text-blue-700',  border: 'border-blue-200' },
  wont:   { bg: 'bg-gray-50',  text: 'text-gray-500',  border: 'border-gray-200' },
} as const

export const RISK_SEVERITY_COLORS = {
  critical: 'text-red-700 bg-red-50 border-red-200',
  high:     'text-orange-700 bg-orange-50 border-orange-200',
  medium:   'text-amber-700 bg-amber-50 border-amber-200',
  low:      'text-green-700 bg-green-50 border-green-200',
} as const

export const TRACE_KIND_STYLES = {
  cb_text_block:  { bg: 'bg-green-50', text: 'text-green-700', border: 'border-l-2 border-green-500', label: 'CB' },
  cb_outcome:     { bg: 'bg-green-50', text: 'text-green-700', border: 'border-l-2 border-green-500', label: 'CB' },
  cb_metric:      { bg: 'bg-green-50', text: 'text-green-700', border: 'border-l-2 border-green-500', label: 'CB' },
  cb_capability:  { bg: 'bg-green-50', text: 'text-green-700', border: 'border-l-2 border-green-500', label: 'CB' },
  cb_scope_item:  { bg: 'bg-green-50', text: 'text-green-700', border: 'border-l-2 border-green-500', label: 'CB' },
  cb_milestone:   { bg: 'bg-green-50', text: 'text-green-700', border: 'border-l-2 border-green-500', label: 'CB' },
  app_fact:       { bg: 'bg-blue-50',   text: 'text-blue-700',  border: 'border-l-2 border-blue-500',  label: 'App' },
  doc_section:    { bg: 'bg-sky-50',    text: 'text-sky-700',   border: 'border-l-2 border-sky-500',   label: 'Doc' },
  discover_qa:    { bg: 'bg-violet-50', text: 'text-violet-700', border: 'border-l-2 border-violet-500', label: 'Q&A' },
  within_brd:     { bg: 'bg-gray-50',  text: 'text-gray-700',  border: 'border-l-2 border-gray-400',  label: '→BRD' },
} as const
