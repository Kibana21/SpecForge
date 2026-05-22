import { CheckCircle2, Database, LayoutList, LogIn, Shield, Sparkles } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { AuditSeverity } from './types'

type BadgeVariant = 'info' | 'warning' | 'danger' | 'success' | 'ai' | 'neutral'

export const SEVERITY_VARIANT: Record<AuditSeverity, BadgeVariant> = {
  info: 'info',
  warning: 'warning',
  danger: 'danger',
  success: 'success',
  ai: 'ai',
  neutral: 'neutral',
}

export interface CategoryTab {
  value: string
  label: string
  icon: LucideIcon
}

// Filter tabs (Security includes destructive events, per the backend catalog).
export const CATEGORY_TABS: CategoryTab[] = [
  { value: 'all', label: 'All', icon: LayoutList },
  { value: 'security', label: 'Security', icon: Shield },
  { value: 'auth', label: 'Auth', icon: LogIn },
  { value: 'data', label: 'Data', icon: Database },
  { value: 'ai', label: 'AI', icon: Sparkles },
  { value: 'compliance', label: 'Compliance', icon: CheckCircle2 },
]
