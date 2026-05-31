'use client'
/**
 * Shared inline token renderer extracted from BrainWiki.tsx.
 * Handles wikilinks ([[target|alias]]), **bold**, and S:/C:/F: citation tokens.
 * BrainWiki.tsx re-exports renderInline + TOKEN_SPLIT from here (no behavior change).
 */
import { Fragment } from 'react'
import { Link2 } from 'lucide-react'
import { IntakeTraceChip } from '@/app/components/IntakeTraceChip'

// Canonical citation token regex — must stay in sync with backend TOKEN_RE
export const TOKEN_SPLIT =
  /(\[\[[^\]]+\]\]|\*\*[^*]+\*\*|\bF:[0-9a-fA-F-]{8,}\b|\bC:[a-z0-9][a-z0-9_-]+\b|\bS:[0-9a-fA-F-]{8,}:[A-Za-z0-9._-]+\b)/g

export function renderInline(
  text: string,
  onLink: (target: string) => void,
  projectId?: string,
  onHoverToken?: (token: string | null) => void,
): React.ReactNode {
  const parts = text.split(TOKEN_SPLIT)
  return parts.map((p, i) => {
    if (projectId && (p.startsWith('F:') || p.startsWith('C:') || p.startsWith('S:'))) {
      return (
        <span
          key={i}
          onMouseEnter={onHoverToken ? () => onHoverToken(p) : undefined}
          onMouseLeave={onHoverToken ? () => onHoverToken(null) : undefined}
          className="inline-block"
        >
          <IntakeTraceChip projectId={projectId} token={p} inline />
        </span>
      )
    }
    if (p.startsWith('[[') && p.endsWith(']]')) {
      const inner = p.slice(2, -2)
      const [target, alias] = inner.split('|')
      const label = (alias || target).replace(/^(concepts|summaries)\//, '')
      return (
        <button
          key={i}
          onClick={() => onLink(target.trim())}
          className="inline-flex items-center gap-0.5 text-[var(--accent)] hover:underline font-medium"
        >
          <Link2 size={10} className="inline" />
          {label}
        </button>
      )
    }
    if (p.startsWith('**') && p.endsWith('**')) {
      return (
        <strong key={i} className="font-semibold text-[var(--text-primary)]">
          {p.slice(2, -2)}
        </strong>
      )
    }
    return <Fragment key={i}>{p}</Fragment>
  })
}

/**
 * Line-based markdown renderer that integrates S:/C:/F: citation chips inline.
 * Mirrors BrainWiki's MarkdownBody but designed for chat answer prose.
 */
export function ProjectMarkdown({
  md,
  projectId,
  onHoverToken,
}: {
  md: string
  projectId: string
  onHoverToken?: (token: string | null) => void
}) {
  const noop = () => {}
  const lines = md.split('\n')
  return (
    <div className="text-sm space-y-0.5">
      {lines.map((line, i) => {
        if (line.startsWith('### '))
          return (
            <h3 key={i} className="text-xs font-semibold text-[var(--text-secondary)] mt-4 mb-1 uppercase tracking-wide">
              {renderInline(line.slice(4), noop, projectId, onHoverToken)}
            </h3>
          )
        if (line.startsWith('## '))
          return (
            <h2 key={i} className="text-sm font-bold text-[var(--text-primary)] mt-5 mb-1.5">
              {renderInline(line.slice(3), noop, projectId, onHoverToken)}
            </h2>
          )
        if (line.startsWith('# '))
          return (
            <h1 key={i} className="text-base font-bold text-[var(--text-primary)] mt-5 mb-2">
              {renderInline(line.slice(2), noop, projectId, onHoverToken)}
            </h1>
          )
        if (/^---+$/.test(line.trim()))
          return <hr key={i} className="my-4 border-[var(--border-subtle)]" />
        if (line.trim() === '')
          return <div key={i} className="h-1.5" />
        if (line.startsWith('- ') || line.startsWith('* '))
          return (
            <div key={i} className="flex gap-2 leading-relaxed">
              <span className="text-[var(--text-tertiary)] mt-0.5 flex-shrink-0">·</span>
              <span className="text-[var(--text-secondary)]">
                {renderInline(line.slice(2), noop, projectId, onHoverToken)}
              </span>
            </div>
          )
        return (
          <p key={i} className="leading-relaxed text-[var(--text-secondary)]">
            {renderInline(line, noop, projectId, onHoverToken)}
          </p>
        )
      })}
    </div>
  )
}
