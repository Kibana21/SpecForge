'use client'
import { Fragment } from 'react'

// Lightweight Markdown renderer for chat answers: bold/italic/code inline,
// headings, bullet + numbered lists, and horizontal rules. No external deps.

function inline(text: string): React.ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`|\*[^*\n]+\*)/g)
  return parts.map((p, i) => {
    if (p.startsWith('**') && p.endsWith('**')) {
      return <strong key={i} className="font-semibold text-[var(--text-primary)]">{p.slice(2, -2)}</strong>
    }
    if (p.startsWith('`') && p.endsWith('`')) {
      return <code key={i} className="px-1 py-0.5 rounded bg-[var(--bg-elevated)] text-[12px] font-mono text-[var(--text-primary)]">{p.slice(1, -1)}</code>
    }
    if (p.length > 1 && p.startsWith('*') && p.endsWith('*')) {
      return <em key={i}>{p.slice(1, -1)}</em>
    }
    return <Fragment key={i}>{p}</Fragment>
  })
}

export function Markdown({ md }: { md: string }) {
  const lines = md.split('\n')
  const nodes: React.ReactNode[] = []

  lines.forEach((raw, i) => {
    const line = raw.trimEnd()
    if (/^###\s+/.test(line)) {
      nodes.push(<h4 key={i} className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wide mt-3 mb-1">{inline(line.replace(/^###\s+/, ''))}</h4>)
    } else if (/^##\s+/.test(line)) {
      nodes.push(<h3 key={i} className="text-sm font-semibold text-[var(--text-primary)] mt-3 mb-1">{inline(line.replace(/^##\s+/, ''))}</h3>)
    } else if (/^#\s+/.test(line)) {
      nodes.push(<h2 key={i} className="text-base font-bold text-[var(--text-primary)] mt-3 mb-1.5">{inline(line.replace(/^#\s+/, ''))}</h2>)
    } else if (/^---+$/.test(line.trim())) {
      nodes.push(<hr key={i} className="my-3 border-[var(--border-subtle)]" />)
    } else if (/^\s*[-*]\s+/.test(line)) {
      nodes.push(
        <div key={i} className="flex gap-2 leading-relaxed">
          <span className="text-[var(--text-tertiary)] mt-0.5 flex-shrink-0">•</span>
          <span>{inline(line.replace(/^\s*[-*]\s+/, ''))}</span>
        </div>
      )
    } else if (/^\s*\d+\.\s+/.test(line)) {
      const num = line.match(/^\s*(\d+)\./)?.[1] ?? '•'
      nodes.push(
        <div key={i} className="flex gap-2 leading-relaxed">
          <span className="text-[var(--text-tertiary)] mt-0.5 flex-shrink-0 tabular-nums">{num}.</span>
          <span>{inline(line.replace(/^\s*\d+\.\s+/, ''))}</span>
        </div>
      )
    } else if (line.trim() === '') {
      nodes.push(<div key={i} className="h-2" />)
    } else {
      nodes.push(<p key={i} className="leading-relaxed">{inline(line)}</p>)
    }
  })

  return <div className="text-sm text-[var(--text-primary)] space-y-0.5">{nodes}</div>
}
