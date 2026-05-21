export type SpecType = 'functional' | 'technical' | 'user_stories' | 'review'
export type Confidence = 'high' | 'medium' | 'low'
export type GapSeverity = 'blocker' | 'major' | 'minor'
export type ReviewSeverity = 'critical' | 'warning' | 'suggestion'
export type ParseStatus = 'pending' | 'done' | 'error'

export interface ProjectRead {
  id: string
  name: string
  description: string | null
  created_at: string
  updated_at: string
}

export interface ProjectListItem extends ProjectRead {
  doc_count: number
  latest_spec_type: SpecType | null
}

export interface LatestSpecInfo {
  id: string
  spec_type: SpecType
  version_number: number
  is_edited: boolean
  updated_at: string
}

export interface ProjectDetail extends ProjectRead {
  documents: DocumentRead[]
  gap_count: number
  unresolved_gap_count: number
  latest_specs: Partial<Record<SpecType, LatestSpecInfo>>
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
  kind: FactKind
  text: string
  source_ref: string | null
  confidence: FactConfidence
  status: FactStatus
  chunk_ids: string[]
  created_at: string
  updated_at: string
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
  rebuild_status: string | null
  corpus_doc_count: number
  indexed_doc_count: number
  fact_count: number
  created_at: string
  updated_at: string
}

export interface AppDetail extends AppListItem {
  corpus_docs: AppCorpusDoc[]
  facts: AppFact[]
  pipeline_summary: PipelineSummary
}

export interface AppCreate {
  name: string
  short_name: string
  description?: string
  tier: 1 | 2 | 3
  domain_area?: string
  version?: string
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

export type SSEEvent =
  | { type: 'chunk'; text: string }
  | { type: 'citations'; citations: CitationItem[] }
  | { type: 'error'; message: string }
  | { type: 'done' }
