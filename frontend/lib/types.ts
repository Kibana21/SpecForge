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
