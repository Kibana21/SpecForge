'use client'
import { FileQuestion } from 'lucide-react'

interface EmptyStateProps {
  icon?: React.ReactNode
  title: string
  description?: string
  action?: React.ReactNode
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
      <div className="mb-4 text-[var(--text-tertiary)]">
        {icon ?? <FileQuestion size={36} strokeWidth={1.5} />}
      </div>
      <h3 className="text-sm font-medium text-[var(--text-secondary)]">{title}</h3>
      {description && (
        <p className="mt-1 text-xs text-[var(--text-tertiary)] max-w-[240px]">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}
