import type {
  Confidence,
  FactKind,
  GapSeverity,
  IndexStatus,
  ReviewSeverity,
} from '@/lib/types'

type BadgeTone = 'success' | 'warning' | 'danger' | 'info' | 'neutral' | 'ai'

// Confidence → shadcn Badge variant
export const confidenceVariant: Record<Confidence, BadgeTone> = {
  high: 'success',
  medium: 'warning',
  low: 'danger',
}

// Index status — icon/text color
export const indexStatusColor: Record<IndexStatus, string> = {
  pending: 'text-ink-tertiary',
  running: 'text-warning',
  done: 'text-success',
  error: 'text-danger',
}

// Gap severity — label text + left-border accent
export const gapSeverity: Record<GapSeverity, { label: string; cls: string }> = {
  blocker: { label: 'Blocker', cls: 'text-danger border-danger' },
  major: { label: 'Major', cls: 'text-warning border-warning' },
  minor: { label: 'Minor', cls: 'text-ink-tertiary border-line' },
}

// Review severity — label text + left-border accent
export const reviewSeverity: Record<ReviewSeverity, { label: string; cls: string }> = {
  critical: { label: 'Critical', cls: 'text-danger border-danger' },
  warning: { label: 'Warning', cls: 'text-warning border-warning' },
  suggestion: { label: 'Suggestion', cls: 'text-info border-info' },
}

// Fact kind — icon color
export const factKindColor: Record<FactKind, string> = {
  capability: 'text-success',
  constraint: 'text-warning',
  limitation: 'text-danger',
  integration: 'text-accent',
  gotcha: 'text-ai',
}

// Fact confidence → shadcn Badge variant
export const factConfidenceVariant: Record<string, BadgeTone> = {
  high: 'success',
  medium: 'warning',
  low: 'neutral',
}
