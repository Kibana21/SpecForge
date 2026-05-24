export type SpecType = 'functional' | 'technical' | 'user_stories' | 'review'
export type Confidence = 'high' | 'medium' | 'low'
export type GapSeverity = 'blocker' | 'major' | 'minor'
export type ReviewSeverity = 'critical' | 'warning' | 'suggestion'
export type ParseStatus = 'pending' | 'done' | 'error'

export type ProjectStatus = 'draft' | 'active' | 'in_review' | 'finalized' | 'archived'
export type ProjectPriority = 'low' | 'medium' | 'high' | 'critical'

export interface ProjectRead {
  id: string
  name: string
  description: string | null
  owner_id: string | null
  human_id: string | null
  business_unit: string | null
  app_scope: string | null
  status: ProjectStatus
  priority: ProjectPriority
  completion_pct: number
  go_live_date: string | null
  stage_progress: Record<string, StageProgress>
  ru_validated: boolean
  created_at: string
  updated_at: string
}

export interface ProjectListItem extends ProjectRead {
  doc_count: number
  latest_spec_type: SpecType | null
  open_review_count: number
  is_stale: boolean
}

export interface LatestSpecInfo {
  id: string
  spec_type: SpecType
  version_number: number
  is_edited: boolean
  updated_at: string
}

export interface StageProgress {
  label: string
  progress: number
  status: 'not_started' | 'in_progress' | 'done' | 'stale'
}

export interface QualityScore {
  completeness: number
  clarity: number
  traceability: number
  nfr_coverage: number
  risk_coverage: number
  consistency: number
  overall: number
  heuristic: boolean
}

export interface AppInScope {
  app_id: string
  name: string
  short_name: string
  tier: number
  included: boolean
  suggested: boolean
}

export interface AssumptionItem {
  id: string
  ext_id: string
  text: string
  confidence: Confidence
  source_ref: string | null
  status: 'open' | 'confirmed' | 'rejected'
}

export interface OpenQuestionItem {
  id: string
  ext_id: string
  question: string
  section: string | null
}

export interface ActivityItem {
  event: string
  actor_id: string | null
  ts: string
  kind: 'ai' | 'human'
}

export interface ProjectDetail extends ProjectRead {
  documents: DocumentRead[]
  apps_in_scope: AppInScope[]
  gap_count: number
  unresolved_gap_count: number
  latest_specs: Partial<Record<SpecType, LatestSpecInfo>>
  quality: QualityScore | Record<string, never>
  open_questions: OpenQuestionItem[]
  assumptions: AssumptionItem[]
  recent_activity: ActivityItem[]
  ru_status: string | null
}

export interface ProjectsFilter {
  q?: string
  view?: string
  group_by?: string
}

export interface SavedViewCount {
  view: string
  label: string
  count: number
}

export interface PortfolioGroup {
  key: string
  count: number
  stale: number
  review: number
  finalized: number
}

export interface TriageItem {
  id: string
  project_id: string | null
  kind: string
  priority: number
  title: string
  link: string
  computed_at: string
  next_at: string | null
}

export interface SimilarProject {
  source_project_id: string
  name: string
  business_unit: string | null
  match_pct: number
  finalized_at: string | null
  asset_tags: string[]
}

export interface AppSuggestion {
  id: string
  name: string
  short_name: string
  description: string | null
  tier: number
  domain_area: string | null
  version: string | null
  owner_id: string | null
  fact_count: number
  corpus_doc_count: number
  suggested: boolean
  match_pct: number
}

export interface RequirementUnderstanding {
  id: string
  project_id: string
  objective: string | null
  content_json: Record<string, unknown>
  field_confidence: Record<string, { confidence: Confidence; completeness: number }>
  status: string
  version_number: number
  validated_at: string | null
  validated_by: string | null
  created_at: string
  updated_at: string
}

export interface InterviewMessage {
  id: string
  role: 'ai' | 'user' | 'question' | 'understanding'
  content: string
  citations: { doc_name?: string; section_title?: string; ref?: string; excerpt?: string }[]
  seq: number
  created_at: string
}

export interface UnderstandingDetail {
  understanding: RequirementUnderstanding | null
  messages: InterviewMessage[]
}

export interface ProjectCreateWizard {
  name: string
  description?: string
  business_unit?: string
  app_scope?: string
  app_ids?: string[]
  reuse?: { source_project_id: string; asset_category: string }[]
  document_ids?: string[]
}

export interface DocumentRead {
  id: string
  project_id: string
  filename: string
  mime_type: string
  size_bytes: number
  parse_status: ParseStatus
  parse_error: string | null
  created_at: string
  updated_at: string
}

export interface ExtractedRequirement {
  id: string
  project_id: string
  category: string
  ext_id: string
  text: string
  source_reference: string | null
  confidence: Confidence
}

export interface SpecVersion {
  id: string
  project_id: string
  spec_type: SpecType
  version_number: number
  content_json: Record<string, unknown>
  content_markdown: string | null
  is_edited: boolean
  created_at: string
  updated_at: string
}

export interface GapQuestion {
  id: string
  project_id: string
  ext_id: string
  question: string
  category: string
  severity: GapSeverity
  resolved: boolean
  resolution_text: string | null
  resolved_at: string | null
  created_at: string
}

export interface ReviewComment {
  id: string
  project_id: string
  spec_version_id: string | null
  section: string
  comment: string
  severity: ReviewSeverity
  category: string
  dismissed: boolean
  dismissed_at: string | null
  created_at: string
}

// ── App Brain types ───────────────────────────────────────────────────────────

export type IndexStatus = 'pending' | 'running' | 'done' | 'error'
export type FactKind = 'capability' | 'constraint' | 'limitation' | 'integration' | 'gotcha'
export type FactConfidence = 'high' | 'medium' | 'low'
export type FactStatus = 'active' | 'proposed' | 'dismissed'

export interface AppCorpusDoc {
  id: string
  app_id: string
  name: string
  page_count: number | null
  is_primary: boolean
  index_status: IndexStatus
  index_error: string | null
  indexed_at: string | null
  created_at: string
}

export interface AppFact {
  id: string
  app_id: string
  doc_id: string | null
  kind: FactKind
  text: string
  source_ref: string | null
  confidence: FactConfidence
  status: FactStatus
  source: 'ai' | 'human' | 'brain'
  chunk_ids: string[]
  source_fact_ids: string[]
  created_at: string
  updated_at: string
}

export interface BrainContextResponse {
  facts: AppFact[]
  synthesized_at: string | null
  status: 'idle' | 'running'
  source_doc_count: number
}

export interface PipelineSummary {
  total_docs: number
  indexed_docs: number
  pending_docs: number
  total_chunks: number
  total_facts: number
  last_indexed_at: string | null
}

export interface AppListItem {
  id: string
  name: string
  short_name: string
  description: string | null
  tier: number
  domain_area: string | null
  is_onboarded: boolean
  version: string | null
  owner_id: string | null
  owner_team: string | null
  environments: string[]
  rebuild_status: string | null
  corpus_doc_count: number
  indexed_doc_count: number
  fact_count: number
  live_project_count: number
  open_qs: number
  created_at: string
  updated_at: string
}

export interface AppDetail extends AppListItem {
  corpus_docs: AppCorpusDoc[]
  pipeline_summary: PipelineSummary
  brain_context_synthesized_at: string | null
  brain_context_status: 'idle' | 'running'
  wiki_compiled_at: string | null
  wiki_status: 'idle' | 'running'
  wiki_health: WikiHealth | null
}

// ── Brain Wiki ──────────────────────────────────────────────────────────────────

export interface WikiTreeNodeRef {
  doc_id: string
  node_id: string
  title: string
  pages: string
}

export interface DocTreeNode {
  node_id: string
  title: string
  summary: string
  pages: string
  depth: number
  children: DocTreeNode[]
}

export interface DocTreeResponse {
  has_tree: boolean
  node_count: number
  model: string | null
  doc_name: string
  page_count: number | null
  nodes: DocTreeNode[]
}

export interface WikiSectionContent {
  doc_id: string
  doc_name: string
  node_id: string
  title: string
  pages: string
  summary: string
  text: string
}

export interface AppWikiConcept {
  id: string
  slug: string
  title: string
  brief: string
  content_md: string
  source_doc_ids: string[]
  related_slugs: string[]
  tree_node_refs: WikiTreeNodeRef[]
  compiled_at: string
}

export interface AppWikiSummary {
  id: string
  doc_id: string
  brief: string
  content_md: string
  related_slugs: string[]
  doc_type: string
  compiled_at: string
}

export interface WikiConceptBrief {
  slug: string
  title: string
  brief: string
}

export interface WikiSummaryBrief {
  doc_id: string
  doc_name: string
  brief: string
  doc_type: string
}

export interface WikiContradiction {
  concept_a: string
  concept_b: string
  issue: string
  severity?: string
}

export interface WikiOrphan {
  slug: string
  title: string
}

export interface WikiHealth {
  contradictions: WikiContradiction[]
  orphans: WikiOrphan[]
  concept_count: number
  checked_at: string
}

export interface WikiIndexResponse {
  concepts: WikiConceptBrief[]
  summaries: WikiSummaryBrief[]
  status: 'idle' | 'running'
  compiled_at: string | null
  health: WikiHealth | null
}

export interface AppCreate {
  name: string
  short_name: string
  description?: string
  tier: 1 | 2 | 3
  domain_area?: string
  version?: string
  owner_team?: string
  environments?: string[]
}

export interface AppsFilter {
  q?: string
  tier?: 1 | 2 | 3
  mine?: boolean
}

export interface FactsFilter {
  kind?: FactKind
  status?: FactStatus
  confidence?: FactConfidence
}

export interface CitationItem {
  id: string
  doc_name: string
  chunk_no: number
  text_excerpt: string
}

export interface TraceConcept { slug: string; title: string; brief: string }
export interface TraceDocument { doc_id: string; name: string; brief: string }
export interface TraceSection { doc_id: string; doc_name: string; node_id: string; title: string; pages: string; excerpt: string }
export interface TraceChunk { doc_name: string; chunk_no: number; similarity: number; excerpt: string }

export interface DeepTrace {
  mode: AskMode
  selected_concepts: TraceConcept[]
  selected_documents: TraceDocument[]
  sections: TraceSection[]
  chunks: TraceChunk[]
  fallback_used: boolean
  context_chars: number
}

export type SSEEvent =
  | { type: 'step'; text: string }
  | { type: 'chunk'; text: string }
  | { type: 'citations'; citations: CitationItem[] }
  | { type: 'trace'; trace: DeepTrace }
  | { type: 'error'; message: string }
  | { type: 'done' }

export type AskMode = 'quick' | 'deep'

export interface AskSessionCitation {
  id: string
  doc_name: string
  chunk_no: number
}

export interface AskSessionMessage {
  role: 'user' | 'assistant'
  content: string
  mode?: AskMode
  citations?: AskSessionCitation[]
  trace?: DeepTrace
}

export interface AskSessionListItem {
  id: string
  title: string
  message_count: number
  created_at: string
  updated_at: string
}

export interface AskSessionRead {
  id: string
  title: string
  messages: AskSessionMessage[]
  created_at: string
  updated_at: string
}

// ── Audit Log types ───────────────────────────────────────────────────────────

export type AuditCategory = 'auth' | 'security' | 'data' | 'destructive' | 'ai' | 'compliance' | 'other'
export type AuditSeverity = 'info' | 'warning' | 'danger' | 'success' | 'ai' | 'neutral'

export interface AuditEventRead {
  id: number
  ts: string
  event: string
  label: string
  category: AuditCategory
  severity: AuditSeverity
  actor_id: string | null
  actor_name: string | null
  actor_email: string | null
  actor_role: string | null
  action: string | null
  project_id: string | null
  document_key: string | null
  app_key: string | null
  ip: string | null
  user_agent: string | null
  correlation_id: string | null
  metadata: Record<string, unknown> | null
  affected_sections: Record<string, unknown> | null
}

export interface AuditFilters {
  q?: string
  event?: string
  category?: string
  actor_id?: string
  project_id?: string
  correlation_id?: string
  start?: string
  end?: string
  limit?: number
  offset?: number
}

export interface AuditSummary {
  events_today: number
  failed_logins_24h: number
  lockouts_24h: number
  token_reuse_7d: number
  deletions_7d: number
  ai_actions_today: number
}
