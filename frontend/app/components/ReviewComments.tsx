'use client'
import { useState } from 'react'
import { X, ChevronDown, ChevronRight } from 'lucide-react'
import clsx from 'clsx'
import type { ReviewComment, ReviewSeverity } from '@/lib/types'
import { api } from '@/lib/api'

const SEVERITY_ORDER: ReviewSeverity[] = ['critical', 'warning', 'suggestion']

const severityStyle: Record<ReviewSeverity, { label: string; cls: string }> = {
  critical:   { label: 'Critical',   cls: 'text-rose-700   border-rose-400'   },
  warning:    { label: 'Warning',    cls: 'text-amber-700  border-amber-400'  },
  suggestion: { label: 'Suggestion', cls: 'text-indigo-700 border-indigo-400' },
}

function groupBy<T>(items: T[], key: (item: T) => string): Record<string, T[]> {
  return items.reduce<Record<string, T[]>>((acc, item) => {
    const k = key(item)
    ;(acc[k] ??= []).push(item)
    return acc
  }, {})
}

interface ReviewCommentsProps {
  projectId: string
  comments: ReviewComment[]
  onCommentUpdate: () => void
}

export function ReviewComments({ projectId, comments, onCommentUpdate }: ReviewCommentsProps) {
  const visible = comments.filter((c) => !c.dismissed)
  const groups  = groupBy(visible, (c) => c.severity)
  const [open, setOpen] = useState<Record<string, boolean>>({ critical: true, warning: true, suggestion: false })
  const toggle = (key: string) => setOpen((s) => ({ ...s, [key]: !s[key] }))

  async function dismiss(comment: ReviewComment) {
    try {
      await api.reviews.dismiss(projectId, comment.id, true)
      onCommentUpdate()
    } catch { /* silently fail */ }
  }

  if (visible.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center px-4">
        <p className="text-xs text-[var(--text-tertiary)]">No active review comments.</p>
      </div>
    )
  }

  return (
    <div className="divide-y divide-[var(--border-default)]">
      {SEVERITY_ORDER.filter((s) => groups[s]?.length).map((severity) => {
        const items          = groups[severity]
        const { label, cls } = severityStyle[severity]
        return (
          <div key={severity}>
            <button
              onClick={() => toggle(severity)}
              className="flex w-full items-center justify-between px-4 py-2.5 hover:bg-[var(--bg-elevated)] transition-colors"
            >
              <span className={clsx('text-[11px] font-bold uppercase tracking-wider border-l-2 pl-2', cls)}>
                {label} ({items.length})
              </span>
              {open[severity]
                ? <ChevronDown  size={13} className="text-[var(--text-tertiary)]" />
                : <ChevronRight size={13} className="text-[var(--text-tertiary)]" />}
            </button>

            {open[severity] && (
              <ul className="pb-1">
                {items.map((comment) => (
                  <li
                    key={comment.id}
                    className="group flex items-start gap-2.5 px-4 py-3 border-b border-[var(--border-subtle)] last:border-0 hover:bg-[var(--bg-elevated)] transition-colors"
                  >
                    <div className="flex-1 min-w-0">
                      <p className="text-[10px] font-semibold text-[var(--text-tertiary)] uppercase tracking-wide mb-1">
                        {comment.section}
                      </p>
                      <p className="text-xs text-[var(--text-primary)] leading-relaxed">{comment.comment}</p>
                    </div>
                    <button
                      onClick={() => dismiss(comment)}
                      className="shrink-0 mt-0.5 p-1 rounded text-[var(--text-tertiary)] hover:text-rose-600 hover:bg-rose-50 transition-colors opacity-0 group-hover:opacity-100"
                      aria-label="Dismiss comment"
                    >
                      <X size={12} />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )
      })}
    </div>
  )
}
