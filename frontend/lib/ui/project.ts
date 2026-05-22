import type { ProjectListItem, ProjectPriority, ProjectStatus } from '@/lib/types'

type BadgeVariant = 'neutral' | 'info' | 'warning' | 'success' | 'danger' | 'ai'

export const STATUS_VARIANT: Record<ProjectStatus, BadgeVariant> = {
  draft: 'neutral',
  active: 'info',
  in_review: 'warning',
  finalized: 'success',
  archived: 'neutral',
}

export const PRIORITY_VARIANT: Record<ProjectPriority, BadgeVariant> = {
  low: 'neutral',
  medium: 'info',
  high: 'warning',
  critical: 'danger',
}

export const STATUS_LABEL: Record<ProjectStatus, string> = {
  draft: 'Draft',
  active: 'Active',
  in_review: 'In review',
  finalized: 'Finalized',
  archived: 'Archived',
}

/** The most-advanced stage that is in progress or done, for the table's Stage column. */
export function currentStage(p: ProjectListItem): string {
  const sp = p.stage_progress ?? {}
  let current: string | null = null
  for (const v of Object.values(sp)) {
    if (v.status === 'in_progress') return v.label
    if (v.status === 'done') current = v.label
  }
  return current ?? '—'
}
