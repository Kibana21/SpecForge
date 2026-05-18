'use client'
import { useState } from 'react'
import { CheckCircle, Circle, ChevronDown, ChevronRight } from 'lucide-react'
import clsx from 'clsx'
import type { GapQuestion, GapSeverity } from '@/lib/types'
import { api } from '@/lib/api'

const SEVERITY_ORDER: GapSeverity[] = ['blocker', 'major', 'minor']

const severityStyle: Record<GapSeverity, string> = {
  blocker: 'text-rose-700   border-rose-400',
  major:   'text-amber-700  border-amber-400',
  minor:   'text-slate-500  border-[var(--border-default)]',
}

const severityLabel: Record<GapSeverity, string> = {
  blocker: 'Blocker',
  major:   'Major',
  minor:   'Minor',
}

function groupBy<T>(items: T[], key: (item: T) => string): Record<string, T[]> {
  return items.reduce<Record<string, T[]>>((acc, item) => {
    const k = key(item)
    ;(acc[k] ??= []).push(item)
    return acc
  }, {})
}

interface GapRowProps {
  gap: GapQuestion
  projectId: string
  onUpdate: () => void
}

function GapRow({ gap, projectId, onUpdate }: GapRowProps) {
  const [text, setText] = useState(gap.resolution_text ?? '')
  const [saving, setSaving] = useState(false)

  async function toggleResolved() {
    setSaving(true)
    try {
      await api.gaps.resolve(projectId, gap.id, { resolved: !gap.resolved, resolution_text: text || null })
      onUpdate()
    } finally {
      setSaving(false)
    }
  }

  async function saveText() {
    if (!gap.resolved) return
    setSaving(true)
    try {
      await api.gaps.resolve(projectId, gap.id, { resolved: gap.resolved, resolution_text: text || null })
      onUpdate()
    } finally {
      setSaving(false)
    }
  }

  return (
    <li className="px-4 py-3 border-b border-[var(--border-subtle)] last:border-0">
      <div className="flex items-start gap-2.5">
        <button
          onClick={toggleResolved}
          disabled={saving}
          className="mt-0.5 shrink-0 transition-colors"
          aria-label={gap.resolved ? 'Mark unresolved' : 'Mark resolved'}
        >
          {gap.resolved
            ? <CheckCircle size={15} className="text-emerald-600" />
            : <Circle      size={15} className="text-[var(--text-tertiary)]" />}
        </button>
        <div className="flex-1 min-w-0">
          <p className={clsx('text-xs leading-relaxed', gap.resolved && 'line-through text-[var(--text-tertiary)]')}>
            {gap.question}
          </p>
          <div className="mt-1.5">
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              onBlur={saveText}
              rows={2}
              placeholder="Add resolution answer…"
              className="w-full resize-none rounded-md border border-[var(--border-default)] bg-[var(--bg-elevated)] px-2.5 py-1.5 text-[11px] text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:border-[var(--accent-blue)] transition-colors"
            />
          </div>
        </div>
      </div>
    </li>
  )
}

interface GapQuestionsProps {
  projectId: string
  gaps: GapQuestion[]
  onGapUpdate: () => void
}

export function GapQuestions({ projectId, gaps, onGapUpdate }: GapQuestionsProps) {
  const groups = groupBy(gaps, (g) => g.severity)
  const [open, setOpen] = useState<Record<string, boolean>>({ blocker: true, major: true, minor: false })
  const toggle = (key: string) => setOpen((s) => ({ ...s, [key]: !s[key] }))

  return (
    <div className="divide-y divide-[var(--border-default)]">
      {SEVERITY_ORDER.filter((s) => groups[s]?.length).map((severity) => {
        const items    = groups[severity]
        const resolved = items.filter((g) => g.resolved).length
        return (
          <div key={severity}>
            <button
              onClick={() => toggle(severity)}
              className="flex w-full items-center justify-between px-4 py-2.5 hover:bg-[var(--bg-elevated)] transition-colors"
            >
              <div className="flex items-center gap-2">
                <span className={clsx('text-[11px] font-bold uppercase tracking-wider border-l-2 pl-2', severityStyle[severity])}>
                  {severityLabel[severity]}
                </span>
                <span className="text-[10px] text-[var(--text-tertiary)]">{resolved}/{items.length}</span>
              </div>
              {open[severity]
                ? <ChevronDown  size={13} className="text-[var(--text-tertiary)]" />
                : <ChevronRight size={13} className="text-[var(--text-tertiary)]" />}
            </button>

            {open[severity] && (
              <ul>
                {items.map((gap) => (
                  <GapRow key={gap.id} gap={gap} projectId={projectId} onUpdate={onGapUpdate} />
                ))}
              </ul>
            )}
          </div>
        )
      })}
    </div>
  )
}
